# Implementation Overview - 2026-05-08

## Scope Agreed Today

The main implementation decision for today was to give the City Oracle a controlled coding capability for on-demand analysis of the live city twin.

Agreed constraints:

- Interactive only: the Oracle uses the capability only when asked in chat
- Live simulation state only: analysis runs against current city state and aggregate metrics, not SQLite history
- Sandboxed execution: Python runs in a subprocess with restricted builtins and a short timeout
- Tool-first integration: the capability is exposed as a real Oracle tool, not a separate admin-only path

## Implementation Plan Used

The working plan for this scope was:

1. Add a sandbox executor that can receive code plus live state and metrics
2. Expose a new `run_python` tool in the City Oracle tool list
3. Wire tool dispatch in `/city/chat`
4. Update the City Oracle capability documentation endpoint
5. Verify the executor directly and then test it through the running app

## Work Executed

### 1. City Oracle coding tool implemented

Implemented a new sandboxed executor in [backend/agents/code_runner.py](backend/agents/code_runner.py).

What it does:

- Reads JSON from stdin in the form `{ "code": ..., "state": ..., "metrics": ... }`
- Injects `state` and `metrics` into the execution namespace
- Preloads safe modules: `json`, `math`, `statistics`, `collections`, `itertools`, `datetime`
- Replaces `__builtins__` with a safe whitelist
- Captures `print()` output and returns structured JSON
- Enforces a code length limit and output truncation

Security model implemented:

- No `open`
- No `os`
- No `sys`
- No `__import__`
- No `eval`
- No `exec` from user-provided scope
- Subprocess isolation from the API process
- 5 second timeout enforced by caller

### 2. Oracle tool wiring completed

Updated [backend/server.py](backend/server.py) to add the new `run_python` tool to the City Oracle tool list and to dispatch it inside `/city/chat`.

The tool now:

- Validates that `code` is present
- Rejects code longer than 4000 characters
- Pulls live state from `city_engine.get_state()`
- Pulls live KPIs from `city_engine.get_city_metrics()`
- Executes the sandbox runner in a subprocess
- Returns either structured tool success output or a tool error

### 3. City Oracle flow docs updated

Updated [backend/server.py](backend/server.py) `/city/agents/flow` so the capability inventory now includes:

- `reroute_traffic`
- `set_signal_timing`
- `run_python`

The endpoint notes now also explain that `run_python` executes Oracle-authored Python in a sandboxed subprocess with live state and metrics injected.

### 4. README refreshed to match the current project state

Updated [README.md](README.md) so the repository documentation reflects the current implementation rather than the older serverless-only description.

README updates include:

- The city twin and Oracle actuation capabilities
- The sandboxed `run_python` analysis tool
- Current backend structure, including `agents/code_runner.py`, `city_simulation.py`, `city_context.py`, and `redis_bus.py`
- The `/city` frontend route
- City-specific backend endpoints
- Correct local backend startup guidance from the `backend/` directory

### 5. Supporting city twin work present in the repo state

The repo state for today also includes the broader city twin implementation surface already built or extended earlier in the day, including:

- City-scale EV + traffic simulation in [backend/city_simulation.py](backend/city_simulation.py)
- Redis pub/sub with local fallback in [backend/redis_bus.py](backend/redis_bus.py)
- A dedicated city UI in [frontend/app/city/page.tsx](frontend/app/city/page.tsx)
- Oracle traffic rerouting and signal timing tools exposed through `/city/chat`

## Validation Performed

### Direct sandbox verification

The new Python runner was exercised directly with multiple test cases.

Passing checks:

- Sum hub queues from `state`
- Compute average EV battery level from `state`
- Read congestion hotspot from `metrics`
- Use `math.sqrt(...)`
- Use `statistics.stdev(...)`

Security check:

- `import os` failed as intended with `ImportError: __import__ not found`

### API/runtime verification

Verified that:

- `/city/agents/flow` responds and includes the updated tool inventory
- The frontend city UI is running on the Next dev server
- The backend city endpoints are being hit successfully in local testing
- `/city/chat` requests return `200 OK` in the active backend logs

## Notable Runtime/Environment Findings

These were observed during execution today and are not core implementation defects in the new feature itself:

- Backend startup must happen from `backend/`, otherwise relative `./data/...` reads can fail
- Port `8000` was intermittently occupied by stale local backend processes
- Next dev had a stale `.next/dev/lock` at one point
- Redis was unavailable locally, but the in-process event bus fallback handled that case correctly
- Codacy CLI initialization is currently broken by a pre-existing CRLF shebang issue in `.codacy/cli.sh`

## Remaining Items / Follow-up

### Functional follow-up

- Do an explicit in-app Oracle test using a prompt that forces `run_python`
- Consider adding a small audit trail for `run_python` usage if tool governance becomes important

### Repo hygiene

- Review local runtime-generated Chroma artifacts under `backend/data/chroma/`
- Decide whether those files should be committed or added to `.gitignore`

### Technical debt already known

- `server.py` still has pre-existing static typing issues around OpenAI message/tool typing
- `city_simulation.py` still has the known type-check warning on the congestion hotspot calculation
- Codacy CLI cannot currently initialize in this environment because of the CRLF shell script issue

## Outcome Summary

The planned feature for today was completed: the City Oracle now has a real coding tool that can execute bounded Python against the live city twin state and metrics through a sandboxed subprocess.

This materially expands the Oracle from fixed-function control into live analytical reasoning while keeping execution isolated and limited.