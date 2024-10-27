from os import environ
from pathlib import Path
from platform import machine, system
from subprocess import check_call

BINARY_KEY = f'goscan-{system().lower()}-{machine().lower()}'


class Lang:
    def prepare_package(self, package):
        self.uim_dir = package.temp_dir / 'uim'
        self.run_go_scanner(package.work_dir, self.uim_dir, package.index_system)

    def add_to_tar_file(self, package, output):
        for uim in self.uim_dir.glob('*'):
            output.add(uim, arcname=package.repo_root / '.territory/uim' / uim)

    def add_to_meta(self, meta):
        meta['lang'] = 'go'

    def _get_go_scanner(self):
        print('getting parser binary for platform:', BINARY_KEY)
        raise NotImplementedError()

    def _run_go_scanner(self, scan_dir: Path, uim_output_dir: Path, system: bool):
        scanner_path = environ.get('GOSCAN_PATH')
        if not scanner_path:
            scanner_path = self.get_go_scanner()
        cmd = [scanner_path]
        if system:
            cmd.append('--system')
        cmd.extend([
            scan_dir,
            uim_output_dir
        ])
        check_call(cmd)
