import json
import argparse
import re
from collections import defaultdict

from build_analysis.utils import format_timestamp_ms
from build_analysis.compile_time import get_compile_times

def parse_args():
    parser = argparse.ArgumentParser(description='Create VLC playlist')
    parser.add_argument('trace', type=str, help='Trace file')
    return parser.parse_args()


def collect_avx_timings(compile_times):
    # HACK: pytorch cpu kernel files get compiled three ways, so this special
    # case adds those jobs timings together as if it were a single compilation
    timings = {}
    cpu_pattern = re.compile(r'\.(DEFAULT|AVX2|AVX512)\.cpp')
    for output, duration in compile_times.items():
        name = cpu_pattern.sub('', output)
        if name in timings:
            timings[name] += duration
        else:
            timings[name] = duration
    return timings


def main():
    args = parse_args()
    with open(args.trace, 'r') as f:
        timings = get_compile_times(f)

    timings = list(collect_avx_timings(timings).items())
    libs = [
        "c10",
        "torch_cpu",
        "torch_cuda",
        "torch_python",
    ]
    lib_timings = defaultdict(lambda: 0)
    for name, dur in timings:
        for l in libs:
            if l in name:
                break
        else:
            l = "other"
        lib_timings[l] += dur

    for lib, timing in sorted(lib_timings.items(), key=lambda kv : kv[1], reverse=True):
        print(f"{lib}: {format_timestamp_ms(timing)}")

    print(f"total: {format_timestamp_ms(sum(lib_timings.values()))}\n")

    # timings = [(name, duration) for name, duration in timings if "torch_cpu" in name]
    timings.sort(key=lambda kv: kv[1], reverse=True)
    for name, duration in timings[:20]:
        print(name)
        print("    ", format_timestamp_ms(duration))

if __name__ == '__main__':
    main()
