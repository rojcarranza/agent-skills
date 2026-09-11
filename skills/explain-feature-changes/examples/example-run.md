# Example run

Worked example on a small Python service. The branch
`feature/LISA-123-integration-decision` moves the decision "should this
event go to the partner integration?" out of `process_event()` into its own
module. Use it to calibrate depth and tone. Never copy its facts into a real
report.

## Chat output

    Comparing `feature/LISA-123-integration-decision → develop` (merge base `3f9c2e1`)

    <Feature Change Overview, as in the report>
    <Key Things to Understand, as in the report>

    Full report: feature-LISA-123-integration-decision-changes.md
    Tour: .tours/changes-feature-LISA-123-integration-decision.tour
    Both are untracked. Add them to .git/info/exclude so they are never committed?

## Report

# feature/LISA-123-integration-decision — change explanation

Comparing `feature/LISA-123-integration-decision → develop` (merge base
`3f9c2e1`), 3 commits.
Uncommitted, not covered: `app/metrics.py` (untracked).
Listed only (generated, vendored, formatting): none.

# Changed Files

| Path | Status | Area | What changed |
|---|---|---|---|
| `app/decision.py` | added | decision logic | new `should_trigger_integration()`, `validate_conditions()` |
| `app/processor.py` | modified | event processing | asks the decision instead of an inline condition |
| `config/settings.yaml` | modified | configuration | new `integration.event_types` list |
| `tests/test_decision.py` | added | tests | allowed type, test events, cancelled orders |

# Feature Change Overview

The branch moves the integration decision out of `process_event()` into a
new function, `should_trigger_integration()` (`app/decision.py:1-8`). The
event types that trigger the integration now come from configuration
(`integration.event_types`) instead of a hard-coded tuple, and the list adds
`order.shipped`. Two new conditions stop the trigger: cancelled orders and
events without an `id` (`app/decision.py:11-13`).

# Why This Change Exists

- Confirmed: the decision moved into its own function — commit "LISA-123
  move integration decision into should_trigger_integration".
- Confirmed: cancelled orders and events without an id are skipped — commit
  "LISA-123 skip cancelled orders and events without an id".
- Likely: the event types moved to configuration so they can change without
  a code change. The new key sits next to `integration.endpoint` in
  `config/settings.yaml`.
- Unknown: why `order.shipped` was added. The exact reason is not explicit
  in the code.

# Changes by File

## `app/decision.py` (added)

### What changed
New module with `should_trigger_integration()` (`app/decision.py:1-8`) and
`validate_conditions()` (`app/decision.py:11-13`).

### Why
Holds the whole trigger decision in one place (confirmed by commit message).

### Important functions/classes
- `should_trigger_integration(event, config)` returns `False` for test
  events and for types not in `integration.event_types`, otherwise defers to
  `validate_conditions()`.
- `validate_conditions(event)` requires a truthy `id` and a `status` other
  than `cancelled`.

### Before → After
Before, the decision was one inline condition in `process_event()`. After,
the caller asks this module and acts only on the answer.

## `app/processor.py` (modified)

### What changed
`process_event()` (`app/processor.py:5-9`) calls
`should_trigger_integration(event, config)` at `app/processor.py:7` instead
of evaluating the condition inline.

### Before → After
Before (`app/processor.py:6` at the merge base): trigger when the type is
`order.created` or `order.updated` and the event is not a test. After:
trigger when `should_trigger_integration()` returns `True`. The `config`
parameter, previously unused, now drives the decision.

## `config/settings.yaml` (modified)

### What changed
Adds `integration.event_types` with `order.created`, `order.updated` and
`order.shipped` (`config/settings.yaml:3-6`).

### Before → After
Before, the key did not exist and the types were hard-coded. After,
`app/decision.py:5` reads the list.

## `tests/test_decision.py` (added)

Covers an allowed type (`tests/test_decision.py:6-7`), test events
(`tests/test_decision.py:10-11`) and cancelled orders
(`tests/test_decision.py:14-15`). No test covers a missing `id` or a config
without `integration.event_types`.

# New Functions / Classes

## `should_trigger_integration()`

    File / lines:         app/decision.py:1-8
    Purpose:              decides whether one event is sent to the partner integration
    Inputs:               event (dict), config (dict loaded from config/settings.yaml)
    Outputs:              bool; no side effects
    Important conditions: test event → False; type not in integration.event_types → False
    Called by:            process_event() at app/processor.py:7
    Calls:                validate_conditions() at app/decision.py:8
    Return value use:     True → trigger_integration(event) at app/processor.py:8
    Before:               inline condition at app/processor.py:6 (merge base)
    Tests:                tests/test_decision.py:6-15

## `validate_conditions()`

    File / lines:         app/decision.py:11-13
    Purpose:              rejects events without an id and cancelled orders
    Called by:            should_trigger_integration() at app/decision.py:8
    Before:               new behavior — no equivalent check existed

# End-to-End Flow

    main()                              app/main.py:17      entry point; defined at app/main.py:9, loads config/settings.yaml
      → process_event()                 app/main.py:13      once per stdin line; defined at app/processor.py:5
        → should_trigger_integration()  app/processor.py:7  defined at app/decision.py:1
          → validate_conditions()       app/decision.py:8   defined at app/decision.py:11
        → trigger_integration()         app/processor.py:8  only when the decision is True; defined at app/integration.py:1

# Structure Before → After

    Before                              After
    process_event()                     process_event()
     ├── decides (hard-coded tuple)      ├── asks should_trigger_integration()
     └── triggers                        │     └── validate_conditions()
                                         └── triggers

The decision now has its own module, so its rules can change without
touching the processing flow.

# Key Things to Understand

1. The decision lives in `app/decision.py`; `process_event()` only acts on
   its answer.
2. Allowed event types come from `integration.event_types`;
   `order.shipped` is new.
3. Cancelled orders and events without an `id` no longer trigger. That is
   new behavior, not part of the refactor.
4. With no `integration.event_types` in the config, nothing triggers
   (`app/decision.py:5` defaults to `[]`). Before, the two hard-coded types
   always triggered.
5. Tests pin the allowed-type, test-event and cancelled paths. The
   missing-id path is untested.

# PR Explanation

Moves the partner-integration decision out of `process_event()` into
`should_trigger_integration()` (`app/decision.py:1-8`) and makes the
triggering event types configurable.

**Behavior changes**
- Event types come from `integration.event_types` in `config/settings.yaml`
  instead of a hard-coded tuple; `order.shipped` is added
  (`config/settings.yaml:3-6`).
- Cancelled orders and events without an `id` no longer trigger the
  integration (`app/decision.py:11-13`).
- A config without `integration.event_types` triggers nothing
  (`app/decision.py:5`).

**Flow:** `process_event()` → `should_trigger_integration()` →
`validate_conditions()` → `trigger_integration()`

**Tests:** `tests/test_decision.py` covers allowed types, test events and
cancelled orders.

# PR Comments

### `app/decision.py:1-8` — integration decision
Added `should_trigger_integration()` to hold the whole decision.
Previously `process_event()` evaluated the condition inline
(`app/processor.py:6` at the merge base). The caller now acts only on the
result, so the conditions can change without touching the processing flow.

### `app/decision.py:11-13` — new skip conditions
`validate_conditions()` is new behavior: events without an `id` and orders
with `status: cancelled` are no longer sent to the partner.

### `config/settings.yaml:3-6` — configurable event types
The allowed types moved from code to `integration.event_types`, adding
`order.shipped`. If the key is missing, the list defaults to empty and no
event triggers.

# Important Observations

- A config without `integration.event_types` disables the integration
  silently (`app/decision.py:5`). Before, `order.created` and
  `order.updated` always triggered. Any environment whose config lacks the
  key changes behavior on deploy.
