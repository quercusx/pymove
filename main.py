"""
pymove — Windows mouse automation utility
==========================================
Keeps the cursor moving to prevent idle/screensaver timeouts.
Supports randomised active/pause cycles, live status display,
runtime hotkeys, and optional system shutdown on completion.

Usage:
    uv run main.py [options]

    -t MINUTES          Run for this many minutes then exit (default: run forever)
    -i SECONDS          Interval between cursor moves in seconds (default: 5)
    -p, --permanent     Start without pause phases (toggle at runtime with Ctrl+P)
    --active-min MIN    Min duration of an active phase in minutes (default: 6)
    --active-max MIN    Max duration of an active phase in minutes (default: 7)
    --pause-min  MIN    Min duration of a pause phase in minutes (default: 1)
    --pause-max  MIN    Max duration of a pause phase in minutes (default: 2)
    -s, --shutdown      Shut down the PC when the -t runtime expires
    -f, --force         Force shutdown without waiting for open processes (use with -s)

Runtime hotkeys:
    Ctrl+P              Toggle Permanent / Active+Pause mode
    Ctrl+Shift+P        Toggle Halted state (freeze/unfreeze cursor movement)
    Ctrl+C              Exit the app cleanly

License: MIT
Copyright (c) 2025 quercusx
"""

import argparse
import queue
import subprocess
import threading
import win32api
import win32con
import time
from datetime import datetime
from random import randrange, uniform


def mmc(x, y):
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)


def format_duration(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main():
    parser = argparse.ArgumentParser(description="Mouse automation utility")
    parser.add_argument("-t", type=float, metavar="MINUTES",
                        help="Total runtime in minutes (default: run forever)")
    parser.add_argument("-i", type=float, metavar="SECONDS", default=5,
                        help="Move interval in seconds (default: 5)")
    parser.add_argument("--active-min", type=float, metavar="MINUTES", default=6,
                        help="Min active period in minutes (default: 6)")
    parser.add_argument("--active-max", type=float, metavar="MINUTES", default=7,
                        help="Max active period in minutes (default: 7)")
    parser.add_argument("--pause-min", type=float, metavar="MINUTES", default=1,
                        help="Min pause duration in minutes (default: 1)")
    parser.add_argument("--pause-max", type=float, metavar="MINUTES", default=2,
                        help="Max pause duration in minutes (default: 2)")
    parser.add_argument("-p", "--permanent", action="store_true",
                        help="Start without pause phases (toggleable at runtime with Ctrl+P)")
    parser.add_argument("-s", "--shutdown", action="store_true",
                        help="Shut down the computer after the runtime (-t) expires")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Force shutdown without waiting for running processes (use with -s)")
    args = parser.parse_args()

    start = time.monotonic()
    start_wall = datetime.now()
    deadline = start + args.t * 60 if args.t is not None else None

    permanent = [args.permanent]
    frozen = [False]

    # Threading design note:
    # The hotkey watcher runs in a background thread and must NEVER call print()
    # directly. Concurrent print() calls from two threads can corrupt the terminal
    # in Cmder/ConEmu (PTY layer locks up, characters arrive with long delays).
    # Instead, the watcher posts notification strings into msg_queue and the main
    # thread drains it at each 1-second tick via flush_messages().
    #
    # On exit, stop_event signals the watcher to quit, and we join() it with a
    # short timeout before printing the exit summary. This prevents a race where
    # the daemon thread still holds the stdout lock while Python tears down
    # sys.stdout, which would also freeze the terminal.
    msg_queue = queue.Queue()
    stop_event = threading.Event()

    def hotkey_watcher():
        was_ctrl_p = False
        was_ctrl_shift_p = False
        while not stop_event.is_set():
            ctrl  = bool(win32api.GetAsyncKeyState(win32con.VK_CONTROL) & 0x8000)
            shift = bool(win32api.GetAsyncKeyState(win32con.VK_SHIFT)   & 0x8000)
            p_key = bool(win32api.GetAsyncKeyState(0x50)                & 0x8000)

            ctrl_shift_p = ctrl and shift and p_key
            ctrl_p       = ctrl and not shift and p_key

            if ctrl_shift_p and not was_ctrl_shift_p:
                frozen[0] = not frozen[0]
                label = "Halted" if frozen[0] else "Resumed"
                msg_queue.put(f"[Ctrl+Shift+P] {label}")

            if ctrl_p and not was_ctrl_p:
                permanent[0] = not permanent[0]
                label = "Permanent" if permanent[0] else "Active/Pause"
                msg_queue.put(f"[Ctrl+P] Switched to: {label}")

            was_ctrl_shift_p = ctrl_shift_p
            was_ctrl_p       = ctrl_p
            # stop_event.wait() doubles as a cancellable sleep: wakes immediately
            # when stop_event is set instead of blocking for the full 0.05s.
            stop_event.wait(timeout=0.05)

    hotkey_thread = threading.Thread(target=hotkey_watcher, daemon=True)
    hotkey_thread.start()

    def is_done():
        return deadline is not None and time.monotonic() >= deadline

    def flush_messages():
        while not msg_queue.empty():
            try:
                print(f"\n{msg_queue.get_nowait()}")
            except queue.Empty:
                break

    def print_status(phase, phase_end):
        flush_messages()
        elapsed = time.monotonic() - start
        remaining = max(0, phase_end - time.monotonic())
        print(f"\r{format_duration(elapsed)} | {phase} (remaining: {format_duration(remaining)})  ", end="", flush=True)

    def not_frozen():
        return not frozen[0]

    try:
        while not is_done():
            # Halt loop — spin here while frozen
            while frozen[0] and not is_done():
                flush_messages()
                elapsed = time.monotonic() - start
                print(f"\r{format_duration(elapsed)} | Halted   (Ctrl+Shift+P to resume)          ", end="", flush=True)
                time.sleep(1)

            if is_done():
                break

            if permanent[0]:
                mmc(randrange(1000), randrange(1000))
                move_end = time.monotonic() + args.i
                while time.monotonic() < move_end and not is_done() and permanent[0] and not_frozen():
                    print_status("Permanent", move_end)
                    time.sleep(1)
            else:
                # Active phase
                active_end = time.monotonic() + uniform(args.active_min, args.active_max) * 60
                while time.monotonic() < active_end and not is_done() and not permanent[0] and not_frozen():
                    mmc(randrange(1000), randrange(1000))
                    move_end = min(time.monotonic() + args.i, active_end)
                    while time.monotonic() < move_end and not is_done() and not permanent[0] and not_frozen():
                        print_status("Active  ", active_end)
                        time.sleep(1)

                if is_done():
                    break
                if permanent[0] or frozen[0]:
                    continue

                # Pause phase
                pause_end = time.monotonic() + uniform(args.pause_min, args.pause_max) * 60
                while time.monotonic() < pause_end and not is_done() and not permanent[0] and not_frozen():
                    print_status("Paused  ", pause_end)
                    time.sleep(1)

    except KeyboardInterrupt:
        deadline = None  # mark as cancelled so shutdown won't trigger

    # Signal and join the hotkey thread BEFORE any print() call.
    # If we printed first, the daemon thread might still be holding the stdout
    # lock during Python shutdown, freezing the terminal (observed in Cmder).
    stop_event.set()
    hotkey_thread.join(timeout=0.2)

    deadline_reached = deadline is not None and time.monotonic() >= deadline
    elapsed = time.monotonic() - start
    stop_wall = datetime.now()
    # Leading \n moves off the \r status line (which has no trailing newline).
    # Without it the first summary line overwrites the last status in the PTY.
    print(f"\nStarted:  {start_wall.strftime('%H:%M:%S')}")
    print(f"Stopped:  {stop_wall.strftime('%H:%M:%S')}")
    print(f"Elapsed:  {format_duration(elapsed)}")

    if args.shutdown and deadline_reached:
        cmd = ["shutdown", "/s", "/t", "10"]
        if args.force:
            cmd.append("/f")
        print("Shutting down in 10 seconds... (run 'shutdown /a' to abort)")
        subprocess.run(cmd)


if __name__ == "__main__":
    main()
