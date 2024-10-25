from pathlib import Path
import tarfile


def find_in_ancestors(p: Path, f, highest=False):
    found = None
    for p in [p, *p.parents]:
        if f(p):
            if highest:
                found = p
            else:
                return p.resolve()
    if found:
        return found
    raise FileNotFoundError()


def add_path_to_archive(added: set[Path], archive: tarfile.TarFile, path: Path):
    '''Adds a file to archive, ensuring symlinks are preserved and paths normalized'''
    stk = list(path.parts)
    i = 1
    while i <= len(stk):
        p = Path(*stk[:i])
        if stk[i-1] == '..':
            stk[i-2 : i] = []
            i -= 2
        elif p.is_symlink():
            if p not in added:
                added.add(p)
                archive.add(p)
            lp = list(p.readlink().parts)
            stk[i-1:i] = lp
            i -= 1
        elif p not in added:
            added.add(p)
            archive.add(p, recursive=False)
        i += 1
