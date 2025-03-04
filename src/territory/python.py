from pathlib import Path
from subprocess import check_call


class Lang:
    def prepare_package(self, package):
        self.package = package
        self.uim_dir = package.temp_dir / 'uim'
        self._run_python_scanner(package.repo_root, self.uim_dir, package.index_system)

    def add_to_tar_file(self, package, output):
        output.add(self.uim_dir, arcname=package.repo_root / '.territory/uim')

    def add_to_meta(self, meta):
        meta['lang'] = 'python'

    def _run_python_scanner(self, scan_dir: Path, uim_output_dir: Path, system: bool):
        cmd = ['python', '-m', 'territory_python_scanner']
        if system:
            cmd.append('--system')
        cmd.extend([
            str(scan_dir),
            str(uim_output_dir)
        ])
        check_call(cmd)
