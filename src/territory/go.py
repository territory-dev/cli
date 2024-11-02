from os import environ
from pathlib import Path
from platform import machine, system
from subprocess import check_call

from .api_client import download_resource


MACHINE = machine().lower()
if MACHINE == 'x86_64':  MACHINE = 'amd64'
if MACHINE == 'aarch64':  MACHINE = 'arm64'
BINARY_KEY = f'goscan-{system().lower()}-{MACHINE}'


class Lang:
    def prepare_package(self, package):
        self.package = package
        self.uim_dir = package.temp_dir / 'uim'
        self._run_go_scanner(package.repo_root, self.uim_dir, package.index_system)

    def add_to_tar_file(self, package, output):
        # for uim in self.uim_dir.glob('*'):
        output.add(self.uim_dir, arcname=package.repo_root / '.territory/uim')

    def add_to_meta(self, meta):
        meta['lang'] = 'go'

    def _get_go_scanner(self):
        print('getting parser binary for platform:', BINARY_KEY)
        bin_path = self.package.temp_dir / 'goscan'
        download_resource(
            upload_token=self.package.upload_token,
            resource=BINARY_KEY,
            destination=bin_path)
        bin_path.chmod(0o700)
        return bin_path

    def _run_go_scanner(self, scan_dir: Path, uim_output_dir: Path, system: bool):
        scanner_path = environ.get('GOSCAN_PATH')
        if not scanner_path:
            scanner_path = str(self._get_go_scanner())
        cmd = [scanner_path]
        if system:
            cmd.append('--system')
        cmd.extend([
            scan_dir,
            uim_output_dir
        ])
        check_call(cmd)
