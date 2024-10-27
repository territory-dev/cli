from shutil import copyfileobj
from socket import gethostname
from sys import exit
from urllib.parse import urlencode, urlparse
import http.server
import json
import os
import threading
import webbrowser

import requests
from platformdirs import user_config_path

from . import __version__


DEFAULT_UPLOAD_TOKEN_PATH = user_config_path('Territory') / 'upload_token'


def create_build_request(upload_token, repo_id, branch, meta, blob_size):
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
            'Authorization': f'Bearer {upload_token}',
            'User-Agent': f'territory/{__version__}',
        })
    if not response.ok:
        print('HTTP status', response.status_code)
        exit(response.text)
    return response.json()


def download_resource(upload_token, resource, destination):
    uploader_api_url = _uploader_api_url()
    response = requests.get(
        uploader_api_url + '/build-resource/' + resource,
        headers={
            'Authorization': f'Bearer {upload_token}',
            'User-Agent': f'territory/{__version__}',
        })
    response.raise_for_status()
    destination.write_bytes(response.content)


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
