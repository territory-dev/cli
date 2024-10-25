from pathlib import Path
import tarfile

from territory.files import add_path_to_archive


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
    added = set()
    with tarfile.open(tp, 'w:gz') as tar:
        add_path_to_archive(added, tar, Path(tmp_path, 'd/e/G'))

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
    added = set()
    with tarfile.open(tp, 'w:gz') as tar:
        add_path_to_archive(added, tar, Path(tmp_path, 'l'))

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


def test_dir_paths_with_dotdot(tmp_path):
    d = tmp_path / 'd/e/g'
    d.mkdir(parents=True)
    h = tmp_path / 'd/e/h'
    h.mkdir(parents=True)
    f = tmp_path / 'd/e/h/f'
    f.write_text('f')

    out = tmp_path / 'out'
    # out.mkdir()
    out.joinpath('d/e').mkdir(parents=True)

    tp = tmp_path / 'territory_upload.tar.gz'
    added = set()
    with tarfile.open(tp, 'w:gz') as tar:
        add_path_to_archive(added, tar, Path(tmp_path, 'd/e/g/../h/f'))
        add_path_to_archive(added, tar, Path(tmp_path, 'd/e/h/f'))

    with tarfile.open(tp, 'r:gz') as tar:
        tar.extractall(out, filter='tar')

    if tmp_path.parts[0] == '/':
        mp = Path(*tmp_path.parts[1:])  # remove leading /
    else:
        mp = tmp_path
    assert (out / mp / 'd/e/h/f').is_file()


def test_many_dotdots(tmp_path):
    d = tmp_path / 'd/e/g/h/i'
    d.mkdir(parents=True)
    f1 = tmp_path / 'd/f1'
    f1.write_text('f1')
    f2 = tmp_path / 'd/e/g/h/i/../../../../f2'
    f2.write_text('f2')

    out = tmp_path / 'out'

    tp = tmp_path / 'territory_upload.tar.gz'
    added = set()
    with tarfile.open(tp, 'w:gz') as tar:
        add_path_to_archive(added, tar, f1)
        add_path_to_archive(added, tar, f2)

    with tarfile.open(tp, 'r:gz') as tar:
        tar.extractall(out, filter='tar')

    if tmp_path.parts[0] == '/':
        mp = Path(*tmp_path.parts[1:])  # remove leading /
    else:
        mp = tmp_path
    assert (out / mp / 'd/f1').is_file()
    assert (out / mp / 'd/f2').is_file()
