'''Client for territory.dev'''
__version__ = '1.0.2'


from argparse import ArgumentParser
from hashlib import blake2b
from multiprocessing import cpu_count
from multiprocessing.pool import Pool
from pathlib import Path
from socket import gethostname
from subprocess import check_output, run
from tempfile import TemporaryDirectory
from urllib.parse import urlencode, urlparse
import http.server
import json
import logging
import os
import shlex
import tarfile
import threading
import webbrowser

from platformdirs import user_config_path
import requests
import tqdm

DEFAULT_UPLOAD_TOKEN_PATH = user_config_path('Territory') / 'upload_token'


def main(argv=None):
    args = parser.parse_args(args=argv)

    if args.l:
        logging.basicConfig(level=logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

    cwd = args.C or Path.cwd()
    args.func(args, cwd)


def upload(args, cwd):
    if not args.tarball_only:
        upload_token = auth(args)

    repo_root = _find_repo_root(cwd)
    print('repository root directory:', repo_root)

    compile_commands_dir = _find_compile_commands_dir(cwd)
    print('compilation database:', compile_commands_dir / 'compile_commands.json')

    with TemporaryDirectory() as td:
        td = Path(td)
        captured_files: set[Path] = set()

        tfl = Path(td, 'TERRITORY_FILE_LISTING')
        repo_files = _list_repo_files(cwd)
        tfl.write_text(repo_files)
        captured_files.update(Path(cwd, p) for p in repo_files.split('\n'))

        cc_files = _collect_from_compilation_database(td, compile_commands_dir)
        captured_files.update(cc_files)

        if not args.system:
            captured_files = {
                path for path in captured_files
                if repo_root in path.parents
            }

        if args.tarball_only:
            tarball_in = repo_root
        else:
            tarball_in = td
        tarball_path = Path(tarball_in, 'territory_upload.tar.gz')
        with tarfile.open(tarball_path, 'w:gz') as output:
            output.add(tfl, arcname=repo_root / 'TERRITORY_FILE_LISTING')
            for path in tqdm.tqdm(captured_files, 'compressing'):
                output.add(path)

        if args.tarball_only:
            print('created', tarball_path)
            return

        print('collecting commit info')
        branch = str(_get_branch(repo_root))
        meta = {
            'commit': _get_sha(repo_root),
            'commit_message': _get_commit_message(repo_root),
            'repo_root': str(repo_root),
            'compile_commands_dir': str(compile_commands_dir),
        }

        print('registering build request')
        blob_size = tarball_path.stat().st_size
        intent = _create_build_request(
            upload_token, args.repo_id, branch, meta, blob_size)

        print('uploading')
        with tarball_path.open('rb') as f:
            resp = requests.put(intent['url'], data=f, headers=intent['extensionHeaders'])
        resp.raise_for_status()


def _create_build_request(upload_token, repo_id, branch, meta, blob_size):
    uploader_api_url = _uploader_api_url()
    response = requests.post(
        uploader_api_url + '/build-request',
        json={
            'repo_id': repo_id,
            'branch': branch,
            'meta': meta,
            'len': blob_size,
        },
        headers={
            'Authorization': f'bearer {upload_token}',
            'User-Agent': f'territory/{__version__}',
        })
    response.raise_for_status()
    return response.json()


def _uploader_api_url():
    return os.environ.get(
        'TERRITORY_UPLOAD_API',
        'https://maps.territory.dev')


def _authorizer_url():
    return os.environ.get(
        'TERRITORY_AUTHORIZER',
        'https://app.territory.dev/upload-tokens/authorize-local')


def _authorizer_origin():
    url = _authorizer_url()
    scheme, netloc, *_ = urlparse(url)
    origin = f'{scheme}://{netloc}'
    return origin


def open_authorizer(params):
    authorizer_url = _authorizer_url()
    url = authorizer_url + '?' + urlencode(params)
    webbrowser.open(url)


def auth(args):
    token_path = args.upload_token_path
    if token_path.is_file():
        print(f'reading token from {token_path}')
        return token_path.read_text().strip()
    else:
        token = _acquire_token()
        print(f'storing token in {token_path}')
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.touch(mode=0o600)
        token_path.write_text(token)
        return token


def _acquire_token():
    upload_token = None
    upload_token_received = threading.Event()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Access-Control-Allow-Origin', _authorizer_origin())
            self.end_headers()

        def do_POST(self):
            nonlocal upload_token, upload_token_received

            content_length = int(self.headers.get('Content-Length'), 10)
            body = self.rfile.read(content_length)

            try:
                upload_token = json.loads(body)['upload_token']
            except Exception:
                self.send_response(400)
                self.wfile.write(b"bad body")
                return

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Access-Control-Allow-Origin', _authorizer_origin())
            self.end_headers()
            self.wfile.write(b"OK")
            upload_token_received.set()


    print('We will start a local HTTP server and open the web browser now.')
    print('If a web browser is not available, create an upload token manually and')
    print(f'store it in {DEFAULT_UPLOAD_TOKEN_PATH}');
    s = http.server.HTTPServer(('localhost', 0), Handler)
    print('serving on', s.server_port)
    open_authorizer({
        'callback': f'http://localhost:{s.server_port}',
        'display_name': gethostname(),
    })

    thread = threading.Thread(target=s.serve_forever)
    thread.start()

    upload_token_received.wait()

    s.shutdown()
    return upload_token


def _find_repo_root(p):
    try:
        return _find_in_ancestors(p, lambda p: (p / '.git').is_dir(), highest=True)
    except FileNotFoundError:
        raise SystemExit('not a git repository')


def _find_compile_commands_dir(p):
    try:
        return _find_in_ancestors(p, lambda p: (p / 'compile_commands.json').exists())
    except FileNotFoundError:
        raise SystemExit('no compile_commands.json found')


def _collect_from_compilation_database(tmp_dir, cc_dir):
    cc_path = cc_dir / 'compile_commands.json'
    with cc_path.open('r') as f:
        cc_data = json.load(f)

    with \
            Pool(cpu_count() * 2) as tpool, \
            tqdm.tqdm(total=len(cc_data), desc='collecting dependencies from sources') as progr:
        result = { cc_path }
        def _cb(paths):
            result.update(paths)
            progr.update(1)
        def _ecb(e):
            print('error:', e)
            progr.update(1)
        for cmd in cc_data:
            dir_ = cmd.get('directory') or cc_dir
            p = Path(dir_, cmd['file'])
            result.add(p)
            tpool.apply_async(
                _query_dependencies,
                (cc_dir, tmp_dir, cmd),
                {},
                callback=_cb,
                error_callback=_ecb)
        tpool.close()
        tpool.join()

    return result


def _query_dependencies(cc_dir: Path, tmp_dir: Path, compilation_command):
    if 'command' in compilation_command:
        arguments = shlex.split(compilation_command['command'])
    else:
        arguments = compilation_command['arguments']

    args_to_remove = ['-c', '-MMD']
    for arg in args_to_remove:
        try:
            arguments.remove(arg)
        except ValueError:
            pass

    args_with_paths_to_remove = ['-o', '-MF']
    for arg in args_with_paths_to_remove:
        try:
            fi = arguments.index(arg)
        except ValueError:
            continue

        arguments = arguments[0:fi] + arguments[fi+2:]

    deps_dir = tmp_dir / 'deps'
    deps_dir.mkdir(parents=True, exist_ok=True)
    out_file = deps_dir / blake2b(compilation_command['file'].encode()).hexdigest()

    arguments = [arguments[0], '-E', '-MD', '-MF' + str(out_file), *arguments[1:], '-o', '/dev/null']
    run(arguments, cwd=compilation_command.get('directory') or cc_dir)

    if out_file.exists():
        deps_text = out_file.read_text()
        out_file.unlink()
        _target, deps = deps_text.split(':', 1)
        lines = [l.rstrip('\\') for l in deps.splitlines()]
        files = shlex.split(' '.join(lines))

        dir_ = compilation_command.get('directory') or cc_dir

        return {Path(dir_, f).resolve() for f in files}
    else:
        print('no dependencies recorded for', compilation_command['file'])
        return set()


def _list_repo_files(dir):
    return check_output(['git', 'ls-files'], cwd=dir, text=True).strip()


def _get_branch(dir):
    return check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=dir, text=True).strip()


def _get_sha(dir) -> str:
    return check_output(['git', 'rev-parse', 'HEAD'], cwd=dir, text=True).strip()


def _get_commit_message(dir) -> str:
    return check_output(['git', 'log', '-1', r'--format=%B'], cwd=dir, text=True)


def _find_in_ancestors(p, f, highest=False):
    found = None
    for p in [p, *p.parents]:
        if f(p):
            if highest:
                found = p
            else:
                return p.resolve()
    if found:
        return found
    raise FileNotFoundError()


parser = ArgumentParser()
subparsers = parser.add_subparsers(required=True)
parser.add_argument('-C', type=Path, help='execute in a directory')
parser.add_argument('-l', action='store_true', help='enable debug logging')

sp = subparsers.add_parser('upload')
sp.set_defaults(func=upload)
sp.add_argument(
    '--upload-token-path',
    type=Path,
    default=DEFAULT_UPLOAD_TOKEN_PATH)
sp.add_argument(
    '--system',
    action='store_true',
    help='collect system-wide dependencies')
repo_or_tarball = sp.add_mutually_exclusive_group(required=True)
repo_or_tarball.add_argument('--repo-id')
repo_or_tarball.add_argument(
    '--tarball-only',
    action='store_true',
    help='do not upload, create territory_upload.tar.gz output only')


if __name__ == '__main__':
    main()
