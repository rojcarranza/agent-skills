# Python

Loaded when the diff touches `*.py`, `pyproject.toml`, `requirements*.txt`,
`setup.py`, or `tox.ini`. These are automation and scripting projects, so
weight failure paths and subprocess handling over API design.

## Correctness

- Mutable default argument (`def f(x=[])`, `={}`).
- Late binding in a closure or a lambda built inside a loop.
- `is` used for value comparison instead of `==` (outside `None`, `True`,
  `False`).
- Truthiness where the value can legitimately be `0` or `""` — use
  `is not None`.
- Dict access with `[]` on a key that may be absent; `.get()` whose `None`
  result then flows into arithmetic or string formatting.
- Mutating a list or dict while iterating it.
- Shadowing a builtin or a module name in a way that changes behavior later
  in the file.
- Integer/float division confusion (`/` versus `//`).
- Comparing `type(x) == T` instead of `isinstance`, where a subclass is
  passed elsewhere in the diff.

## Subprocess and shell interaction

This is the highest-value area for these repositories.

- `subprocess.run` without `check=True` and without inspecting
  `returncode` — a failed command silently continues. → **Major**.
- `shell=True` with any interpolated variable. → **Blocker** when the value
  comes from an argument, an environment variable, or a file.
- No `timeout=` on a call that can hang the Bamboo agent.
- `capture_output=True` on a command producing large output, with no
  streaming.
- `os.system` or `os.popen` in new code.
- Output decoded without specifying an encoding, or `text=True` omitted then
  compared against a `str`.
- Exit codes swallowed by a wrapping try/except that logs and returns.

## Files, paths, IO

- `open()` outside a context manager.
- A path built by string concatenation rather than `os.path.join`/`pathlib`.
- Writing in place with no temp-file-and-rename, so a crash truncates the
  original.
- Hardcoded `/tmp` rather than `tempfile`.
- Reading an entire large file into memory when a line loop would do.
- Encoding not specified on `open()` for text.

## Errors and control flow

- Bare `except:` or `except Exception` with `pass`, or catching more than the
  operation can raise.
- `raise` losing context — prefer `raise X from e`.
- `sys.exit()` inside a library function rather than raising.
- A retry loop with no backoff, no cap, or retrying a non-idempotent call.
- `assert` used to enforce a runtime precondition (stripped under `-O`).

## Typing and interfaces

- A signature changed without updating every caller in the repository (the
  system pass covers this — Python will not catch it at build time).
- Type hints that contradict what the function returns on the failure path.
- `Any` introduced where the concrete type is known and callers depend on it.

## Dependencies and packaging

- A new import with no corresponding entry in `requirements*.txt` or
  `pyproject.toml`. → **Major**: it works locally and fails on the agent.
- Unpinned or range-pinned versions in a deployment context.
- A dependency added for something the standard library covers.
- A test-only dependency in the runtime requirements.
- Python version assumptions (a 3.10+ syntax such as `match`, or `X | Y`
  annotations) that the Bamboo agent's interpreter may not satisfy.

## Tests

- New branch logic, especially failure paths, with no test.
- `mock.patch` targeting the definition site rather than the use site, so the
  patch does nothing and the test passes vacuously.
- Tests that hit the network or the filesystem outside `tmp_path`.
- A test asserting only that no exception was raised.
- `pytest.mark.skip` added in this diff with no reason.

## Not a finding here

- f-string versus `.format()`; comprehension versus loop; `pathlib` versus
  `os.path` where the file is already consistent.
- Missing type hints in a module that has none.
- Import order, line length, quote style — Ruff, Black or Flake8 own these.
- Docstring presence in internal scripts.
