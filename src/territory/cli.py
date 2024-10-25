from . import __version__
VERSION_STRING = f'territory CLI {__version__}'


from argparse import ArgumentParser
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import logging
import tarfile

import requests
import tqdm

from .api_client import DEFAULT_UPLOAD_TOKEN_PATH, auth, create_build_request
from .git import find_repo_root, list_repo_files, get_sha, get_commit_message, get_branch
from .c import find_compile_commands_dir, read_compile_commands, collect_details
from .files import add_path_to_archive


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

    repo_root = find_repo_root(cwd)
    print('repository root directory:', repo_root)

    compile_commands_dir = find_compile_commands_dir(cwd)
    print('compilation database:', compile_commands_dir / 'compile_commands.json')

    with TemporaryDirectory() as td:
        td = Path(td)
        captured_files: set[Path] = set()

        tfl = Path(td, 'TERRITORY_FILE_LISTING')
        repo_files = list_repo_files(cwd)
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
        branch = str(get_branch(repo_root))
        meta = {
            'commit': get_sha(repo_root),
            'commit_message': get_commit_message(repo_root),
            'repo_root': str(repo_root),
            'compile_commands_dir': str(compile_commands_dir),
            'index_system': args.system,
        }

        print('registering build request')
        blob_size = tarball_path.stat().st_size
        intent = create_build_request(
            upload_token, args.repo_id, branch, meta, blob_size)

        print('uploading')
        with tarball_path.open('rb') as f:
            resp = requests.put(intent['url'], data=f, headers=intent['extensionHeaders'])
        resp.raise_for_status()

    if args.repo_id:
        print(f'Indexing will begin shortly. You can track build status at <https://app.territory.dev/repos/{args.repo_id}/jobs>.')


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

