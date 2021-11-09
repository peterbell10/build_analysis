import shutil
import os
import json
import sys
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import time
from pathlib import Path
import numpy as np

from typing import Dict, List, Set

from build_analysis.dependencies import *
from build_analysis.commit_db import CommitDb, determine_update_frequencies
from build_analysis.utils import format_timestamp_ms
from build_analysis.compile_time import get_compile_times

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ninja', type=str, help='Ninja executable')
    parser.add_argument('--project_dir', type=str, help='Path to project git directory')
    parser.add_argument('--build_dir', '-C', type=str, help='Build directory')
    parser.add_argument('--commit_db', type=str, help='Commit database path')
    parser.add_argument('--trace', type=str, help='Build trace file')
    parser.add_argument('--target', type=str, nargs='*', help='Target to analyse', default=[])
    args = parser.parse_args()
    if args.ninja is None:
        args.ninja = shutil.which('ninja')

    if args.build_dir is None:
        if arg.project_dir is None:
            args.project_dir = os.getcwd()
        args.build_dir = os.path.join(args.project_dir, 'build')
    elif arg.project_dir is None:
        args.build_dir = str(Path(args.build_dir).parent)

    return args

args = parse_args()

with open(args.commit_db, 'r') as f:
    commit_db = CommitDb.load(f)

deps = get_dependencies(args.ninja, args.build_dir, args.target)

def filter_deps(deps: Dict[str, List[str]]) -> Dict[str, List[str]]:
    def condition(inp):
        return (
            not Path(inp).is_absolute() or inp.startswith('/home/peter/git') and
            not 'third_party' in inp)
    return {output: [inp for inp in inputs if condition(inp)]
            for output, inputs in deps.items()}

deps = filter_deps(deps)
deps = evaluate_transitive_dependencies(deps)

all_inputs = set()
for inputs in deps.values():
    all_inputs.update(set(inputs))
# all_inputs = ['../aten/src/ATen/native/native_functions.yaml']

input_to_git_filename = {
    inp: str((Path(args.build_dir) / Path(inp)).resolve().relative_to(args.project_dir))
    for inp in all_inputs
}
git_filename_to_input = {v: k for k, v in input_to_git_filename.items()}

update_frequencies = determine_update_frequencies(
    PROJECT_DIR,
    [input_to_git_filename[inp] for inp in all_inputs],
    commit_db)
update_frequencies = {git_filename_to_input[k]: v for k, v in update_frequencies.items()}
dependants_map = invert_dependencies(deps)


with open(args.trace, 'r') as f:
    time_map = get_compile_times(f)

phony_targets = get_targets(args.ninja, args.build_dir, ['rule', 'phony'])
time_map.update({target: 0 for target in phony_targets})

in_files = dependants_map['../aten/src/ATen/native/native_functions.yaml']
in_files.sort(key=lambda x: time_map.get(x, 0), reverse=True)
for i, in_file in enumerate(in_files[:20]):
    compile_time = time_map.get(in_file, 0)
    print(f'{i}: {in_file}')
    print(f' {format_timestamp_ms(compile_time)} total time')
sys.exit(0)

input_to_ns = {}
for in_file, out_files in dependants_map.items():
    total_time = 0
    for output in out_files:
        if output in time_map:
            total_time += time_map[output]
        else:
            print(f'Warning: no build time info for {output}', file=sys.stderr)
    assert isinstance(total_time, int)
    input_to_ns[in_file] = total_time

# in_files = list(input_to_ns.keys())


for k, v in update_frequencies.items():
    if v < 1:
        print(k, v)

file_weights = {x: input_to_ns[x] / update_frequencies.get(x, np.inf)
                for x in in_files}

in_files.sort(key=lambda x: file_weights[x], reverse=True)
for i, in_file in enumerate(in_files[:200]):
    compile_time = input_to_ns[in_file]
    print(f'{i}: {in_file}')
    msg = f' {ns_to_time(compile_time)} total time'
    if in_file in update_frequencies:
        msg += f', updated once every {update_frequencies[in_file]:.2g} day(s)'
    print(msg)
