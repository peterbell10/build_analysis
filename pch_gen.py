import shutil
import os
import subprocess
import json
import sys
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import time
from pathlib import Path, PurePath
import numpy as np
import subprocess
import io
import tempfile
import shlex

from typing import Dict, List, Set

from build_analysis.dependencies import get_dependencies, invert_dependencies
from build_analysis.compile_time import get_compile_times

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ninja', type=str, help='Ninja executable')
    parser.add_argument('--build_dir', '-C', type=str, help='Build directory')
    parser.add_argument('--trace', type=str, help='Build trace file')
    parser.add_argument('--target', type=str, nargs='*', help='Target to analyse', default=[])
    parser.add_argument('--threshold', type=float, default=0.95)
    args = parser.parse_args()
    if args.ninja is None:
        args.ninja = shutil.which('ninja')
    return args

args = parse_args()

deps = get_dependencies(args.ninja, args.build_dir, args.target)

def filter_deps(deps: Dict[str, List[str]]) -> Dict[str, List[str]]:
    def condition(inp):
        # Attempt to filter out vendor-specific headers
        return (
            '/asm/' not in inp and
            '/asm-generic/' not in inp and
            '/backward/' not in inp and
            '/bits/' not in inp and
            '/debug/' not in inp and
            '/ext/' not in inp and
            '/gnu/' not in inp and
            '/linux/' not in inp and
            '/sys/' not in inp and
            True
        )
    return {output: [inp for inp in inputs if condition(inp)]
            for output, inputs in deps.items()}
deps = filter_deps(deps)

all_inputs = set()
for output, inputs in deps.items():
    all_inputs.update(inputs)

with open(args.trace, 'r') as f:
    time_map = get_compile_times(f)
min_time = float('inf')
min_output = None
for output in deps.keys():
    if not output.endswith('.cpp.o'):
        # Searching for a cpp compile command
        continue
    time = time_map.get(output, None)
    if time is None:
        continue
    if time < min_time:
        min_time = time
        min_output = output



command_outputs = subprocess.run([args.ninja, '-C', args.build_dir, '-t', 'commands', '-s', min_output],
                                 check=True, capture_output=True)
command = command_outputs.stdout.decode('latin1').strip()
command = shlex.split(command)

# Remove compile file and output file arguments (assumes gcc-like)
i = command.index('-o')
command.pop(i + 1)
command.pop(i)
i = command.index('-c')
command.pop(i + 1)
command.pop(i)

with tempfile.NamedTemporaryFile('r', suffix='.cpp') as f:
    output = subprocess.run(command + ['-E', f.name, '-v'], check=True,
                            capture_output=True, cwd=args.build_dir)
output = output.stderr.decode('latin1').strip()

include_paths = []
active = False
for line in output.split('\n'):
    if line.startswith('#include <...> search'):
        active = True
        print('active')
    elif line.startswith('End of search list.'):
        break
    elif active:
        path = Path(line.strip()).resolve()
        include_paths.append(path)

include_paths.sort(key=lambda x: len(x.parts), reverse=True)



header_cost = defaultdict(lambda: 0)

dependants_map = invert_dependencies(deps)
for in_file, out_files in dependants_map.items():
    out_cost = sum(time_map.get(output, 0) for output in out_files)
    header_cost[in_file] += out_cost

max_cost = max(header_cost.values())
cost_cutoff = args.threshold * max_cost

pch_headers = set(PurePath(header) for header, cost in header_cost.items() if cost > cost_cutoff)
groups = [[] for _ in range(len(include_paths) + 1)]
for header in pch_headers:
    for i, path in enumerate(include_paths):
        if str(header).startswith(str(path)):
            groups[i].append(header.relative_to(path))
            break
    else:
        groups[-1].append(header)

for i, group in enumerate(groups):
    if len(group) == 0:
        continue

    print(f'\n// included from {include_paths[i]}')
    for header in sorted(group):
        print(f'#include <{header}>')
