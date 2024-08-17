import json
from pathlib import Path
from shutil import which
from subprocess import check_call


EXAMPLE_REPO_DIR = Path(__file__).parent / 'repo'


def init_repo(test_repo_dir):
    check_call(['cp', '-R', EXAMPLE_REPO_DIR, test_repo_dir])
    check_call(['git', 'init', '-b', 'main', test_repo_dir])
    check_call(['git', '-C', test_repo_dir, 'add', 'mod1.c', 'dir/mod2.c', 'Makefile'])
    check_call(['git', '-C', test_repo_dir, 'commit', '-m', 'initial commit'])
    cc = which('clang')
    (test_repo_dir / 'compile_commands.json').write_text(json.dumps([
        {
            'command': f'{cc} -c -o mod1.o {test_repo_dir}/mod1.c',
            'directory': str(test_repo_dir),
            'file': f'{test_repo_dir}/mod1.c'
        },
        {
            'command': f'{cc} -c -o mod2.o {test_repo_dir}/dir/mod2.c',
            'directory': str(test_repo_dir),
            'file': f'{test_repo_dir}/dir/mod2.c'
        },
    ]))
