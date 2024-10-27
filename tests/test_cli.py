from io import BytesIO
from pathlib import Path
from threading import Thread
from unittest.mock import ANY
from wsgiref.simple_server import make_server
import tarfile

from flask import Flask, request
import pytest

from territory.cli import main
from territory_testlib import init_repo


AUTHORIZER_DIR = Path(__file__).parent / 'authorizer'

TEST_REPO_EXPECTED_FILES = {
    'c': [
        'TERRITORY_FILE_LISTING',
        'shared.h',
        'mod1.c',
        'compile_commands.json',
        'Makefile',
        'dir',
        'dir/mod2.c',
    ],
    'go': [
        'TERRITORY_FILE_LISTING',
        'go.mod',
        'main.go',
        '.territory/uim',
        '.territory/uim/nodes.uim',
        '.territory/uim/search.uim',
    ]
}

BUILD_REQUESTS = {
    'c': {
        'repo_id': 'test_repo_id',
        'branch': 'main',
        'len': ANY,
        'meta': {
            'commit': ANY,
            'commit_message': 'initial commit\n\n',
            'repo_root': ANY,
            'compile_commands_dir': ANY,
            'index_system': False,
            'lang': 'c',
        },
    },
    'go': {
        'repo_id': 'test_repo_id',
        'branch': 'main',
        'len': ANY,
        'meta': {
            'commit': ANY,
            'commit_message': 'initial commit\n\n',
            'repo_root': ANY,
            'index_system': False,
            'lang': 'go',
        },
    }
}


@pytest.mark.parametrize('lang', ['c', 'go'])
def test_upload(mock_authserver, monkeypatch, tmp_path, lang):
    monkeypatch.setenv(
        'TERRITORY_AUTHORIZER',
        f'{mock_authserver.location}/static/authorize.html')
    monkeypatch.setenv('TERRITORY_UPLOAD_API', mock_authserver.location)
    repo_path = tmp_path / 'repo'
    init_repo(repo_path, lang=lang)

    mock_authserver.expected_build_request = BUILD_REQUESTS[lang]

    main([
        '-C', str(repo_path),
        'upload',
        '--upload-token-path', str(tmp_path / 'upload_token'),
        '--repo-id', 'test_repo_id',
        '-l', lang
    ])

    assert mock_authserver.upload_intent_created is True

    upload, = mock_authserver.uploaded
    assert len(upload) > 0

    with tarfile.open(fileobj=BytesIO(upload), mode='r:gz') as tf:
        assert sorted(tf.getnames()) == sorted([
            str(repo_path / f).lstrip('/')
            for f in TEST_REPO_EXPECTED_FILES[lang]
        ] + [
            str(p).lstrip('/')
            for p in list(repo_path.parents) + [repo_path]
        ])


@pytest.mark.parametrize('lang', ['c', 'go'])
def test_tarball_only(tmp_path, lang):
    repo_path = tmp_path / 'repo'
    init_repo(repo_path, lang=lang)

    main([
        '-C', str(repo_path),
        'upload',
        '--upload-token-path', str(tmp_path / 'upload_token'),
        '--tarball-only',
        '-l', lang
    ])

    tarball_path = tmp_path/'repo/territory_upload.tar.gz'
    assert tarball_path.exists()
    with tarball_path.open('rb') as fo:
        with tarfile.open(fileobj=fo, mode='r:gz') as tf:
            assert sorted(tf.getnames()) == sorted([
                str(repo_path / f).lstrip('/')
                for f in TEST_REPO_EXPECTED_FILES[lang]
            ] + [
                str(p).lstrip('/')
                for p in list(repo_path.parents) + [repo_path]
            ])


class ApiMock:
    def __init__(self):
        self.upload_intent_created = False
        self.uploaded = []
        self.len = None
        self.expected_build_request = {
            'repo_id': 'test_repo_id',
            'branch': 'main',
            'len': ANY,
            'meta': {
                'commit': ANY,
                'commit_message': 'initial commit\n\n',
                'repo_root': ANY,
                'compile_commands_dir': ANY,
                'index_system': False,
                'lang': 'c',
            },
        }


@pytest.fixture
def mock_authserver():
    app = Flask(__name__)
    api = ApiMock()

    @app.route('/build-request', methods=['POST'])
    def create_upload_intent():
        assert request.authorization.type == 'bearer'
        assert request.authorization.token == 'testtoken'

        assert request.json == api.expected_build_request

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
