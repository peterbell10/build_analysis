import json
from typing import Dict

# TODO: Cut out ninjatracing an read .ninja_log directly?
def get_compile_times(f) -> Dict[str, int]:
    trace = json.load(f)

    db = {}
    for item in trace:
        # duration in milliseconds
        duration = item['dur'] // 1000
        outputs = item['name'].split(', ')
        for output in outputs:
            db[output] = duration
    return db
