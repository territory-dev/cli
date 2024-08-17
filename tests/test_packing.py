from pathlib import Path
import tarfile

from territory import add_path_to_archive


def test_symlink_directories_in_path(tmp_path):
    d = tmp_path / 'd'
    d.mkdir()
    f = tmp_path / 'f'
    f.mkdir()
    e = d / 'e'
    e.symlink_to('../f', target_is_directory=True)
    g = f / 'G'
    g.write_text('g')

    tp = tmp_path / 'territory_upload.tar.gz'
    with tarfile.open(tp, 'w:gz') as tar:
        add_path_to_archive(tar, Path(tmp_path, 'd/e/G'))

    out = tmp_path / 'out'
    out.mkdir()
    with tarfile.open(tp, 'r:gz') as tar:
        tar.extractall(out, filter='tar')

    if tmp_path.parts[0] == '/':
        mp = Path(*tmp_path.parts[1:])  # remove leading /
    else:
        mp = tmp_path
    assert (out / mp / 'f/G').is_file()
    assert (out / mp / 'f/G').read_text() == 'g'
    assert (out / mp / 'd/e').is_symlink()
    assert (out / mp / 'd/e').readlink() == Path('../f')


def test_symlinked_file(tmp_path):
    f = tmp_path / 'f'
    f.write_text('f')
    l = tmp_path / 'l'
    l.symlink_to('f')

    tp = tmp_path / 'territory_upload.tar.gz'
    with tarfile.open(tp, 'w:gz') as tar:
        add_path_to_archive(tar, Path(tmp_path, 'l'))

    out = tmp_path / 'out'
    out.mkdir()
    with tarfile.open(tp, 'r:gz') as tar:
        tar.extractall(out, filter='tar')

    if tmp_path.parts[0] == '/':
        mp = Path(*tmp_path.parts[1:])  # remove leading /
    else:
        mp = tmp_path
    assert (out / mp / 'f').is_file()
    assert (out / mp / 'f').read_text() == 'f'
    assert (out / mp / 'l').is_symlink()
    assert (out / mp / 'l').readlink() == Path('f')
