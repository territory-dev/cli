from dataclasses import dataclass
from hashlib import blake2b
from multiprocessing import cpu_count
from multiprocessing.pool import Pool
from os import environ
from pathlib import Path
from subprocess import DEVNULL, PIPE, run
import json
import re
import shlex

import tqdm

from .files import find_in_ancestors


class Lang:
    def prepare_package(self, package):
        self.compile_commands_dir = find_compile_commands_dir(package.work_dir)
        print('compilation database:', self.compile_commands_dir / 'compile_commands.json')

        self.cc_path = self.compile_commands_dir / 'compile_commands.json'
        cc_data = read_compile_commands(self.cc_path)
        cc_files = collect_details(package.temp_dir, self.compile_commands_dir, cc_data)
        package.captured_files.update(cc_files)
        self.gen_ccs_path = Path(package.temp_dir, 'compile_commands.json')
        with self.gen_ccs_path.open('w') as f:
            json.dump(cc_data, f, indent=4)

    def add_to_tar_file(self, package, output):
        output.add(self.gen_ccs_path, arcname=self.cc_path)

    def add_to_meta(self, meta):
        meta['compile_commands_dir'] = str(self.compile_commands_dir)
        meta['lang'] = 'c'


def find_compile_commands_dir(p):
    try:
        return find_in_ancestors(p, lambda p: (p / 'compile_commands.json').exists())
    except FileNotFoundError:
        raise SystemExit('no compile_commands.json found')


def read_compile_commands(cc_path):
    with cc_path.open('r') as f:
        cc_data = json.load(f)

    for cc in cc_data:
        try:
            cmd_str = cc.pop('command')
        except KeyError:
            continue
        cc['arguments'] = shlex.split(cmd_str)

    return cc_data


def collect_details(tmp_dir, cc_dir, cc_data):
    if 'CORES' in environ:
        procs = int(environ['CORES'])
    else:
        procs = cpu_count() * 2

    with \
            Pool(procs) as pool, \
            tqdm.tqdm(total=len(cc_data), desc='collecting compilation details') as progr:
        dep_paths = set()
        def _cb(details):
            idx, paths, arguments = details
            dep_paths.update(paths)
            cc_data[idx]['arguments'] = arguments
            progr.update(1)
        def _ecb(e):
            print('error:', e)
            progr.update(1)
        for i, cmd in enumerate(cc_data):
            dir_ = cmd.get('directory') or cc_dir
            p = Path(dir_, cmd['file'])
            dep_paths.add(p)
            pool.apply_async(
                _query_details,
                (i, cc_dir, tmp_dir, cmd),
                {},
                callback=_cb,
                error_callback=_ecb)
        pool.close()
        pool.join()

    return dep_paths


def remove_arg(arguments, key, count, prefix=False):
    res = []
    fi = 0
    while fi < len(arguments):
        arg = arguments[fi]

        if arg == key:
            fi += count

        elif  (prefix and arg.startswith(key)):
            fi += 1

        else:
            res.append(arg)
            fi += 1

    return res


@dataclass
class Vee:
    target: str | None = None
    angle_bracket_include_paths: list[str] | None = None


def parse_vee(text) -> Vee:
    vee = Vee()
    m = re.search('^Target: (.+)$', text, re.MULTILINE)
    if m:
        vee.target = m.group(1)

    m = re.search(r'#include <\.\.\.> search starts here:\n((^ .*\n)*)', text, re.MULTILINE)
    if m:
        vee.angle_bracket_include_paths = re.findall(r'^ (.*?)(?: \(framework directory|headermap\)\n|\n)', m.group(1), re.MULTILINE)
    return vee


def _query_details(index: int, cc_dir: Path, tmp_dir: Path, compilation_command):
    q_arguments = compilation_command['arguments'][:]

    q_arguments = remove_arg(q_arguments, '-c', 1)
    q_arguments = remove_arg(q_arguments, '-M', 1)
    q_arguments = remove_arg(q_arguments, '-MD', 1)
    q_arguments = remove_arg(q_arguments, '-MM', 1)
    q_arguments = remove_arg(q_arguments, '-MMD', 1)
    q_arguments = remove_arg(q_arguments, '-o', 2, prefix=True)
    q_arguments = remove_arg(q_arguments, '-MF', 2, prefix=True)

    deps_dir = tmp_dir / 'deps'
    deps_dir.mkdir(parents=True, exist_ok=True)
    deps_file = deps_dir / (blake2b(compilation_command['file'].encode()).hexdigest() + '.d')

    q_arguments = [q_arguments[0], '-E', '-MD', '-MF' + str(deps_file), *q_arguments[1:], '-v', '-o', '/dev/null', '-Wno-error']
    completion = run(
        q_arguments,
        cwd=compilation_command.get('directory') or cc_dir,
        stderr=PIPE,
        stdin=DEVNULL,
        text=True)

    arguments = compilation_command['arguments'][:]
    vd = parse_vee(completion.stderr)
    if vd.target is not None:
        arguments[1:1] = ['-target', vd.target]

    if vd.angle_bracket_include_paths:
        arguments = remove_arg(arguments, '-I', 2, prefix=True)
        arguments = remove_arg(arguments, '--include-directory', 2)
        arguments = remove_arg(arguments, '--include-directory=', 1, prefix=True)
        arguments = remove_arg(arguments, '-cxx-isystem', 2, prefix=True)
        arguments = remove_arg(arguments, '-ibuiltininc', 1)
        arguments = remove_arg(arguments, '-iframework', 2, prefix=True)
        arguments = remove_arg(arguments, '-iframeworkwithsysroot', 2, prefix=True)
        arguments = remove_arg(arguments, '--stdlib++-isystem', 2, prefix=True)
        arguments = remove_arg(arguments, '-isystem', 2, prefix=True)
        arguments = remove_arg(arguments, '-M', 1)
        arguments = remove_arg(arguments, '-MD', 1)
        arguments = remove_arg(arguments, '-MM', 1)
        arguments = remove_arg(arguments, '-MMD', 1)
        arguments = remove_arg(arguments, '-MF', 2, prefix=True)

        incs = [f'-I{dir}' for dir in vd.angle_bracket_include_paths]
        arguments[1:1] = ['-nostdinc', *incs]

    if deps_file.exists():
        deps_text = deps_file.read_text()
        deps_file.unlink()
        try:
            _target, deps = deps_text.split(':', 1)
        except Exception as e:
            print('failed to read dependencies:', deps_text, e)
            return index, set(), arguments
        lines = [l.rstrip('\\') for l in deps.splitlines()]
        files = shlex.split(' '.join(lines))

        dir_ = compilation_command.get('directory') or cc_dir

        return index, {Path(dir_, f) for f in files}, arguments
    else:
        print('no dependencies recorded for', compilation_command['file'])

    if completion.returncode != 0:
        print(completion.stderr)
    return index, set(), arguments
