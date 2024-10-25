from subprocess import check_output

from .files import find_in_ancestors



def find_repo_root(p):
    try:
        return find_in_ancestors(p, lambda p: (p / '.git').is_dir(), highest=True)
    except FileNotFoundError:
        raise SystemExit('not a git repository')


def list_repo_files(dir):
    return check_output(['git', 'ls-files'], cwd=dir, text=True).strip()


def get_branch(dir):
    return check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=dir, text=True).strip()


def get_sha(dir) -> str:
    return check_output(['git', 'rev-parse', 'HEAD'], cwd=dir, text=True).strip()


def get_commit_message(dir) -> str:
    return check_output(['git', 'log', '-1', r'--format=%B'], cwd=dir, text=True)
