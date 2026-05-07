"""
Sandboxed Python code executor for Oracle data-analysis tool.

Called as a subprocess by server.py. Reads a JSON payload from stdin:
  {"code": str, "state": dict, "metrics": dict}

Executes the code in a restricted namespace where:
  - `state`   : full city simulation state (residents, hubs, traffic, zones, weather)
  - `metrics` : aggregated city metrics (counts, averages, hotspot, etc.)
  - Safe stdlib modules are pre-imported: json, math, statistics, collections, itertools, datetime

Prints a single JSON line to stdout:
  {"output": str, "error": null | str}

Security measures:
  - __builtins__ replaced with a safe whitelist (no open, os, sys, __import__, eval, exec)
  - Subprocess isolation: even if code hangs or crashes, the server process is unaffected
  - Timeout enforced by the calling subprocess.run(timeout=5)
  - Output truncated at 2000 chars, code rejected above 4000 chars
"""

import io
import json
import math
import statistics
import collections
import itertools
import datetime
import sys

CODE_MAX_LEN = 4000
OUTPUT_MAX_LEN = 2000

SAFE_BUILTINS = {
    # core
    "print": print,
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "reversed": reversed,
    "sum": sum,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "type": type,
    "isinstance": isinstance,
    "hasattr": hasattr,
    "getattr": getattr,
    "repr": repr,
    "format": format,
    "any": any,
    "all": all,
    "next": next,
    "iter": iter,
    # exceptions
    "Exception": Exception,
    "ValueError": ValueError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "TypeError": TypeError,
    # constants
    "True": True,
    "False": False,
    "None": None,
}


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"output": "", "error": f"Invalid JSON input: {exc}"}))
        return

    code: str = payload.get("code", "")
    state: dict = payload.get("state", {})
    metrics: dict = payload.get("metrics", {})

    if len(code) > CODE_MAX_LEN:
        print(json.dumps({"output": "", "error": f"Code exceeds max length of {CODE_MAX_LEN} characters."}))
        return

    # Capture stdout from exec'd code
    buffer = io.StringIO()

    safe_globals: dict = {
        "__builtins__": SAFE_BUILTINS,
        # pre-injected data
        "state": state,
        "metrics": metrics,
        # pre-imported safe modules
        "json": json,
        "math": math,
        "statistics": statistics,
        "collections": collections,
        "itertools": itertools,
        "datetime": datetime,
    }

    original_stdout = sys.stdout
    sys.stdout = buffer
    error_msg = None

    try:
        exec(code, safe_globals)  # noqa: S102
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
    finally:
        sys.stdout = original_stdout

    output = buffer.getvalue()
    if len(output) > OUTPUT_MAX_LEN:
        output = output[:OUTPUT_MAX_LEN] + f"\n... (truncated at {OUTPUT_MAX_LEN} chars)"

    print(json.dumps({"output": output, "error": error_msg}))


if __name__ == "__main__":
    main()
