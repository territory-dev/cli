from territory import set_compiler_targets, read_compile_commands
from territory_testlib import init_repo


def test_targets_are_set(tmp_path):
    init_repo(tmp_path / 'repo')
    cc_data = read_compile_commands(tmp_path / 'repo/compile_commands.json')
    set_compiler_targets(cc_data)
    assert '-target' in cc_data[0]['arguments']
    assert '-target' in cc_data[1]['arguments']
