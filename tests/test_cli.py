from io import BytesIO
from pathlib import Path
from subprocess import check_call
from threading import Thread
from unittest.mock import ANY
from wsgiref.simple_server import make_server
import json
import tarfile

from flask import Flask, request
import pytest

from territory import main


EXAMPLE_REPO_DIR = Path(__file__).parent / 'repo'
AUTHORIZER_DIR = Path(__file__).parent / 'authorizer'

TEST_REPO_EXPECTED_FILES = [
    'TERRITORY_FILE_LISTING',
    'shared.h',
    'mod1.c',
    'compile_commands.json',
    'Makefile',
    'dir/mod2.c',
]


def test_upload(mock_authserver, monkeypatch, tmp_path):
    monkeypatch.setenv(
        'TERRITORY_AUTHORIZER',
        f'{mock_authserver.location}/static/authorize.html')
    monkeypatch.setenv('TERRITORY_UPLOAD_API', mock_authserver.location)
    init_repo(tmp_path / 'repo')

    main([
        '-C', str(tmp_path / 'repo'),
        'upload',
        '--upload-token-path', str(tmp_path / 'upload_token'),
        '--repo-id', 'test_repo_id',
    ])

    assert mock_authserver.upload_intent_created is True

    upload, = mock_authserver.uploaded
    assert len(upload) > 0
    with tarfile.open(fileobj=BytesIO(upload), mode='r:gz') as tf:
        assert sorted(tf.getnames()) == sorted([
            str(tmp_path / 'repo' / f).lstrip('/')
            for f in TEST_REPO_EXPECTED_FILES
        ])


def test_tarball_only(tmp_path):
    init_repo(tmp_path / 'repo')

    main([
        '-C', str(tmp_path / 'repo'),
        'upload',
        '--upload-token-path', str(tmp_path / 'upload_token'),
        '--tarball-only',
    ])

    tarball_path = tmp_path/'repo/territory_upload.tar.gz'
    assert tarball_path.exists()
    with tarball_path.open('rb') as fo:
        with tarfile.open(fileobj=fo, mode='r:gz') as tf:
            assert sorted(tf.getnames()) == sorted([
                str(tmp_path / 'repo' / f).lstrip('/')
                for f in TEST_REPO_EXPECTED_FILES
            ])


class ApiMock:
    def __init__(self):
        self.upload_intent_created = False
        self.uploaded = []
        self.len = None


@pytest.fixture
def mock_authserver():
    app = Flask(__name__)
    api = ApiMock()

    @app.route('/build-request', methods=['POST'])
    def create_upload_intent():
        assert request.authorization.type == 'bearer'
        assert request.authorization.token == 'testtoken'

        assert request.json == {
            'repo_id': 'test_repo_id',
            'branch': 'main',
            'len': ANY,
            'meta': {
                'commit': ANY,
                'commit_message': 'initial commit\n\n',
                'repo_root': ANY,
                'compile_commands_dir': ANY,
            },
        }

        api.len = request.json['len']

        api.upload_intent_created = True

        response = {
            'url': api.location + '/upload',
            'extensionHeaders': {
                'x-some-header': 'foo',
            }
        }
        return response, 200, {'Content-Type': 'text/plain'}

    @app.route('/upload', methods=['PUT'])
    def upload():
        api.uploaded.append(request.data)
        assert len(request.data) == api.len
        assert request.headers['x-some-header'] == 'foo'
        return 'OK', 201

    server = make_server('localhost', 6969, app)
    thread = Thread(target=server.serve_forever)
    thread.start()

    api.location = f'http://localhost:{server.server_port}'
    yield api

    server.shutdown()


def init_repo(test_repo_dir):
    check_call(['cp', '-R', EXAMPLE_REPO_DIR, test_repo_dir])
    check_call(['git', 'init', '-b', 'main', test_repo_dir])
    check_call(['git', '-C', test_repo_dir, 'add', 'mod1.c', 'dir/mod2.c', 'Makefile'])
    check_call(['git', '-C', test_repo_dir, 'commit', '-m', 'initial commit'])
    (test_repo_dir / 'compile_commands.json').write_text(json.dumps([
        {
            'command': f'clang -c -o mod1.o {test_repo_dir}/mod1.c',
            'directory': str(test_repo_dir),
            'file': f'{test_repo_dir}/mod1.c'
        },
        {
            'command': f'clang -c -o mod2.o {test_repo_dir}/dir/mod2.c',
            'directory': str(test_repo_dir),
            'file': f'{test_repo_dir}/dir/mod2.c'
        },
    ]))

