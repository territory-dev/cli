'''Client for territory.dev'''
__version__ = '1.2.0'
VERSION_STRING = f'territory CLI {__version__}'


from argparse import ArgumentParser
from hashlib import blake2b
from dataclasses import dataclass
from multiprocessing import cpu_count
from multiprocessing.pool import Pool
from pathlib import Path
from socket import gethostname
from subprocess import PIPE, STDOUT, check_output, run
from tempfile import TemporaryDirectory
from urllib.parse import urlencode, urlparse
import http.server
import json
import logging
import os
import re
import shlex
from sys import exit
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

    print(VERSION_STRING)
    cwd = (args.C or Path.cwd()).resolve()
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

        cc_path = compile_commands_dir / 'compile_commands.json'
        cc_data = read_compile_commands(cc_path)
        cc_files = collect_details(td, compile_commands_dir, cc_data)
        captured_files.update(cc_files)
        gen_ccs_path = Path(td, 'compile_commands.json')
        with gen_ccs_path.open('w') as f:
            json.dump(cc_data, f, indent=4)

        if args.tarball_only:
            tarball_in = repo_root
        else:
            tarball_in = td
        tarball_path = Path(tarball_in, 'territory_upload.tar.gz')
        added = set()
        with tarfile.open(tarball_path, 'w:gz') as output:
            output.add(tfl, arcname=repo_root / 'TERRITORY_FILE_LISTING')
            output.add(gen_ccs_path, arcname=cc_path)
            for path in tqdm.tqdm(captured_files, 'compressing'):
                if not path.exists():
                    print('missing file:', path)
                    continue
                add_path_to_archive(added, output, path)

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
            'index_system': args.system,
        }

        print('registering build request')
        blob_size = tarball_path.stat().st_size
        intent = _create_build_request(
            upload_token, args.repo_id, branch, meta, blob_size)

        print('uploading')
        with tarball_path.open('rb') as f:
            resp = requests.put(intent['url'], data=f, headers=intent['extensionHeaders'])
        resp.raise_for_status()

    if args.repo_id:
        print(f'Indexing will begin shortly. You can track build status at <https://app.territory.dev/repos/{args.repo_id}/jobs>.')


def add_path_to_archive(added: set[Path], archive: tarfile.TarFile, path: Path):
    '''Adds a file to archive, ensuring symlinks are preserved and paths normalized'''
    stk = list(path.parts)
    i = 1
    while i <= len(stk):
        p = Path(*stk[:i])
        if stk[i-1] == '..':
            stk[i-2 : i] = []
            i -= 2
        elif p.is_symlink():
            if p not in added:
                added.add(p)
                archive.add(p)
            lp = list(p.readlink().parts)
            stk[i-1:i] = lp
            i -= 1
        elif p not in added:
            added.add(p)
            archive.add(p, recursive=False)
        i += 1


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
    if response.status_code == 429:
        exit(response.text)
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


def read_compile_commands(cc_path):
    with cc_path.open('r') as f:
        cc_data = json.load(f)

    for cc in cc_data:
        try:
            cmd_str = cc.pop('command')
        except KeyError:
            continue
        cc['arguments'] = shlex.split(cmd_str)

    return cc_data


def collect_details(tmp_dir, cc_dir, cc_data):
    with \
            Pool(cpu_count() * 2) as pool, \
            tqdm.tqdm(total=len(cc_data), desc='collecting compilation details') as progr:
        dep_paths = set()
        def _cb(details):
            idx, paths, arguments = details
            dep_paths.update(paths)
            cc_data[idx]['arguments'] = arguments
            progr.update(1)
        def _ecb(e):
            print('error:', e)
            progr.update(1)
        for i, cmd in enumerate(cc_data):
            dir_ = cmd.get('directory') or cc_dir
            p = Path(dir_, cmd['file'])
            dep_paths.add(p)
            pool.apply_async(
                _query_details,
                (i, cc_dir, tmp_dir, cmd),
                {},
                callback=_cb,
                error_callback=_ecb)
        pool.close()
        pool.join()

    return dep_paths


def remove_arg(arguments, key, count, prefix=False):
    for fi, arg in enumerate(arguments):
        if arg == key:
            return arguments[0:fi] + arguments[fi+count:]

        if  (prefix and arg.startswith(key)):
            return arguments[0:fi] + arguments[fi+1:]
    else:
        return arguments


@dataclass
class Vee:
    target: str | None = None
    angle_bracket_include_paths: list[str] | None = None


def parse_vee(text) -> Vee:
    vee = Vee()
    m = re.search('^Target: (.+)$', text, re.MULTILINE)
    if m:
        vee.target = m.group(1)

    m = re.search(r'#include <\.\.\.> search starts here:\n((^ .*\n)*)', text, re.MULTILINE)
    if m:
        vee.angle_bracket_include_paths = re.findall(r'^ (.*?)(?: \(framework directory|headermap\)\n|\n)', m.group(1), re.MULTILINE)
    return vee


def _query_details(index, cc_dir: Path, tmp_dir: Path, compilation_command):
    q_arguments = compilation_command['arguments'][:]

    q_arguments = remove_arg(q_arguments, '-c', 1)
    q_arguments = remove_arg(q_arguments, '-M', 1)
    q_arguments = remove_arg(q_arguments, '-MD', 1)
    q_arguments = remove_arg(q_arguments, '-MM', 1)
    q_arguments = remove_arg(q_arguments, '-MMD', 1)
    q_arguments = remove_arg(q_arguments, '-o', 2, prefix=True)
    q_arguments = remove_arg(q_arguments, '-MF', 2, prefix=True)

    deps_dir = tmp_dir / 'deps'
    deps_dir.mkdir(parents=True, exist_ok=True)
    deps_file = deps_dir / (blake2b(compilation_command['file'].encode()).hexdigest() + '.d')

    q_arguments = [q_arguments[0], '-E', '-MD', '-MF' + str(deps_file), *q_arguments[1:], '-v', '-o', '/dev/null']
    completion = run(q_arguments, cwd=compilation_command.get('directory') or cc_dir, stderr=PIPE, text=True)

    arguments = compilation_command['arguments'][:]
    vd = parse_vee(completion.stderr)
    if vd.target is not None:
        arguments[1:1] = ['-target', vd.target]

    if vd.angle_bracket_include_paths:
        arguments = remove_arg(arguments, '-I', 2, prefix=True)
        arguments = remove_arg(arguments, '--include-directory', 2)
        arguments = remove_arg(arguments, '--include-directory=', 1, prefix=True)
        arguments = remove_arg(arguments, '-cxx-isystem', 2, prefix=True)
        arguments = remove_arg(arguments, '-ibuiltininc', 1)
        arguments = remove_arg(arguments, '-iframework', 2, prefix=True)
        arguments = remove_arg(arguments, '-iframeworkwithsysroot', 2, prefix=True)
        arguments = remove_arg(arguments, '--stdlib++-isystem', 2, prefix=True)
        arguments = remove_arg(arguments, '-isystem', 2, prefix=True)

        incs = [f'-I{dir}' for dir in vd.angle_bracket_include_paths]
        arguments[1:1] = ['-nostdinc', *incs]

    if deps_file.exists():
        deps_text = deps_file.read_text()
        deps_file.unlink()
        try:
            _target, deps = deps_text.split(':', 1)
        except Exception as e:
            print('failed to read dependencies:', deps_text, e)
            return set()
        lines = [l.rstrip('\\') for l in deps.splitlines()]
        files = shlex.split(' '.join(lines))

        dir_ = compilation_command.get('directory') or cc_dir

        return index, {Path(dir_, f) for f in files}, arguments
    else:
        print(completion.stderr)
        print('no dependencies recorded for', compilation_command['file'])
        return index, set(), arguments


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
parser.add_argument('-C', type=Path, help='execute in a directory')
parser.add_argument('-l', action='store_true', help='enable debug logging')
parser.add_argument('--version', action='version', version=VERSION_STRING)

subparsers = parser.add_subparsers(required=True)
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
