# pymove

A minimal Windows mouse automation utility that keeps your cursor moving to prevent idle/screensaver timeouts. Supports configurable move intervals, randomised active/pause cycles to mimic natural behaviour, and a live status display.

## Requirements

- Windows
- Python ≥ 3.14
- [uv](https://github.com/astral-sh/uv) package manager

## Installation

```bash
uv sync
```

## Usage

```bash
uv run main.py [options]
```

### Options

| Flag | Default | Description |
|---|---|---|
| `-t MINUTES` | — | Total runtime in minutes. Omit to run forever. |
| `-i SECONDS` | `5` | Interval between cursor moves in seconds. |
| `-p`, `--permanent` | off | Start without pause phases — cursor moves continuously (toggleable at runtime with Ctrl+P). |
| `--active-min MINUTES` | `6` | Minimum duration of an active (moving) phase. |
| `--active-max MINUTES` | `7` | Maximum duration of an active (moving) phase. |
| `--pause-min MINUTES` | `1` | Minimum duration of a pause (idle) phase. |
| `--pause-max MINUTES` | `2` | Maximum duration of a pause (idle) phase. |
| `-s`, `--shutdown` | off | Shut down the computer when the `-t` runtime expires. Has no effect if the app is stopped manually with Ctrl+C. |
| `-f`, `--force` | off | Force shutdown — kills running processes without waiting. Only meaningful with `-s`. |

### Examples

Run forever with default settings:
```bash
uv run main.py
```

Run for exactly 30 minutes:
```bash
uv run main.py -t 30
```

Run for 2 hours, move every 10 seconds, no pauses:
```bash
uv run main.py -t 120 -i 10 --permanent
```

Run for 1 hour with longer active periods and shorter pauses:
```bash
uv run main.py -t 60 --active-min 10 --active-max 15 --pause-min 0.5 --pause-max 1
```

Shut down the PC after 2 hours (force-kill open apps):
```bash
uv run main.py -t 120 -s -f
```

## Behaviour

By default the app alternates between **active** and **paused** phases:

- **Active** — moves the cursor to a random position and fires a left-click every `-i` seconds.
- **Paused** — cursor is left alone for a random duration in the `[--pause-min, --pause-max]` range.

The length of each active phase is also randomised within `[--active-min, --active-max]`. This pattern is intended to look less mechanical than continuous movement.

Use `-p` / `--permanent` to skip pause phases entirely.

## Runtime hotkeys

| Hotkey | Action |
|---|---|
| `Ctrl+P` | Toggle between **Permanent** (no pauses) and **Active/Pause** cycle modes. |
| `Ctrl+Shift+P` | Toggle **Halted** state — cursor stops moving until pressed again. |

## Status display

While running, a live counter is shown in the terminal:

```
00:03:42 | Active  (remaining: 00:02:18)
00:09:11 | Paused  (remaining: 00:00:47)
00:11:04 | Permanent (remaining: 00:00:03)
00:14:22 | Halted   (Ctrl+Shift+P to resume)
```

On exit (either `Ctrl+C` or the `-t` deadline), the summary is printed:

```
Started:  09:14:02
Stopped:  09:24:02
Elapsed:  00:10:00
```

## Terminal compatibility note

The hotkey watcher runs in a background thread but **never calls `print()` directly**. All notifications are passed through a queue and printed by the main thread. This avoids a known issue in [Cmder](https://cmder.app/) / ConEmu where concurrent `print()` calls from two threads can corrupt the PTY layer, causing the terminal to become unresponsive after the app exits (characters appear with long delays or stop appearing at all).

If you observe terminal freezes after exit in other terminal emulators, this is the relevant code path to investigate: `msg_queue`, `flush_messages()`, and the `stop_event` / `join()` sequence before the exit summary is printed.
