import json
from pathlib import Path
from shutil import which
from subprocess import check_call


EXAMPLE_REPO_DIR = Path(__file__).parent


def init_repo(test_repo_dir, lang='c', compile_commands=None):
    check_call(['cp', '-R', EXAMPLE_REPO_DIR / f'repo-{lang}', test_repo_dir])
    check_call(['git', 'init', '-b', 'main', test_repo_dir])
    check_call(['git', '-C', test_repo_dir, 'add', '.'])
    check_call(['git', '-C', test_repo_dir, 'commit', '-m', 'initial commit'])

    if lang == 'c':
        cc = which('clang')
        (test_repo_dir / 'compile_commands.json').write_text(json.dumps(compile_commands or [
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
