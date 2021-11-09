import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Optional

__all__ = [
    'Deps',
    'evaluate_transitive_dependencies',
    'get_dependencies',
    'get_dynamic_dependencies',
    'get_targets',
    'invert_dependencies',
]

Deps = Dict[str, List[str]]


def parse_targets(targets_str: str) -> Set[str]:
    targets = []
    for line in targets_str.split('\n'):
        target_pos = line.find(':')
        if target_pos == -1:
            continue
        target = line[:target_pos]
        targets.append(target)

    return targets


def get_targets(ninja: str, build_dir: Path, extra_args: List[str]) -> List[str]:
    """Get names of all targets and sub-targets"""
    output = subprocess.run(
        [ninja, '-C', build_dir, '-t', 'targets'] + extra_args,
        check=True, capture_output=True, cwd=build_dir)
    return parse_targets(output.stdout.decode('latin1'))


def parse_deps(deps_str: str) -> Deps:
    deps = {}
    cur_target: Optional[str] = None
    cur_deps: Optional[List[str]] = None

    def flush_target():
        if cur_target is not None:
            assert cur_deps is not None
            assert cur_target not in deps
            deps[cur_target] = cur_deps

    for line in deps_str.split('\n'):
        if line.startswith('    '):
            assert cur_deps is not None
            cur_deps.append(line[4:])
        elif len(line) > 0:
            flush_target()
            colon_pos = line.find(':')
            cur_target = line[:colon_pos]
            cur_deps = []

    flush_target()
    return deps


def get_dynamic_dependencies(ninja: str, build_dir: str, targets: List[str]) -> Deps:
    """Return dynamic dependencies (e.g. headers) for each command target in the list

    NOTE: An empty target list means all targets
    """
    deps_output = subprocess.run(
        [ninja, '-C', build_dir, '-t', 'deps'] + targets,
        check=True, capture_output=True, cwd=build_dir)
    return parse_deps(deps_output.stdout.decode('latin1'))


def parse_query_inputs(query_str: str) -> Deps:
    if 'ninja: error' in query_str:
        raise RuntimeError(f"Failed to query target")

    target = None
    ret = {}

    inputs: List[str] = []
    mode = 'intro'
    for line in query_str.split('\n'):
        if len(line) > 0 and line[0] != ' ':
            target_pos = line.find(':')
            target = line[:target_pos]
            if target is not None:
                assert target not in ret
                ret[target] = inputs
            inputs = []
        elif line.startswith('  input:'):
            mode = 'input'
        elif line.startswith('  outputs:'):
            mode = 'output'
        elif mode == 'input' and line.startswith('    '):
            if '||' in line:
                # Ignore order-only dependencies
                continue
            inputs.append(line[4:].replace('|', ''))
    return ret


def query_inputs(ninja: str, build_dir: Path, targets: List[str]) -> Deps:
    """Query static input dependencies for a list of targets

    NOTE: Does not include dynamic dependencies like header files
    """
    output = subprocess.run(
        [ninja, '-C', build_dir, '-t', 'query'] + targets,
        check=True, capture_output=True, cwd=build_dir)
    return parse_query_inputs(output.stdout.decode('latin1'))


def get_dependencies(ninja: str, build_dir: Path, targets: List[str]) -> Deps:
    """Get dependency info for given targets

    Includes dependency info for sub-commands, and will attempt to use dynamic
    dependency info if available but will otherwise fall-back to static
    dependencies.
    """
    all_targets = get_targets(ninja, build_dir, ['all'] + targets)

    deps = get_dynamic_dependencies(ninja, build_dir, all_targets)
    no_dynamic_info = [target for target, inputs in deps.items()
                       if len(inputs) == 0]

    if len(no_dynamic_info) > 0:
        new_deps = query_inputs(ninja, build_dir, no_dynamic_info)
        deps.update(new_deps)

    return deps


def evaluate_transitive_dependencies(deps: Deps) -> Deps:
    """Expand transitive dependencies inside a dependency map"""
    def gather_inputs(all_inputs: Set[str], inputs: List[str]):
        new_inputs = set(inputs) - all_inputs
        all_inputs.update(new_inputs)

        for in_file in new_inputs:
            if in_file in deps:
                gather_inputs(all_inputs, deps[in_file])

    new_deps: Deps = {}
    for output, inputs in deps.items():
        all_inputs: Set[str] = set()
        gather_inputs(all_inputs, inputs)
        new_deps[output] = list(all_inputs)

    return new_deps


def invert_dependencies(deps: Deps) -> Dict[str, List[str]]:
    """Convert map of targets to inputs into map of inputs to dependant targets"""
    dependants: Dict[str, Set[str]] = defaultdict(lambda: set())

    for output, inputs in deps.items():
        for f in inputs:
            dependants[f].add(output)

    return {input_file: list(outputs) for input_file, outputs in dependants.items()}
