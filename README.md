# LoL Controller

A gamepad-to-keyboard/mouse remapper for **League of Legends**, similar in spirit
to JoyToKey or reWASD, but purpose-built for the LoL "WASD movement" control
scheme:

- The **left stick** is translated into WASD keypresses (`wasd_logic.py`) —
  tilt the stick in a direction and the corresponding movement key(s) are held
  down, just like a keyboard.
- The **right stick** is translated into **proportional mouse-cursor
  movement** (`aim_math.py`): stick deflection maps to a cursor position
  within a fixed-radius circle around the center of the screen, so you can aim
  skillshots/reticles with the stick. When you release the stick, the cursor
  eases smoothly back to screen center (see **Elastic aim-return** below)
  instead of snapping there in a single frame.
- Face buttons, shoulder buttons, triggers and the D-Pad are mapped to
  keyboard keys or mouse clicks (abilities, summoner spells, item slots,
  shop, recall, etc.) via a `customtkinter` GUI.

**This is input-remapping software, not a memory-reading aimbot.** It never
reads game or process memory — `aim_math.py` only converts analog-stick
position into screen coordinates and moves the OS cursor with
`SetCursorPos`, the same technique any joystick-to-mouse utility uses.

## Requirements

- **Windows only.** The app uses `ctypes.windll.user32` (`SetCursorPos`,
  screen metrics) and the `inputs` package's XInput backend to read gamepad
  state — neither works on macOS/Linux.
- **Python 3.10+** (developed/tested with Python 3.13).
- A Windows-recognized XInput-compatible gamepad (Xbox controller or
  equivalent; DirectInput controllers may need the Calibration Wizard — see
  below).

## Install

```powershell
pip install -r requirements.txt
```

## Usage

### GUI (recommended)

```powershell
python gui.py
```

Launches the `customtkinter` configurator with:

- **Mapping tab** — a visual controller diagram plus a League-of-Legends
  ability HUD; click any button/slot to remap it to a different key, mouse
  click, or `Ctrl`.
- **Settings tab** — screen resolution, deadzone, aim radius, elastic
  aim-return time, and per-axis inversion.
- **Calibration Wizard** — walks through each button/axis/trigger on your
  physical controller and records its raw event code, for controllers whose
  layout doesn't match the built-in XInput defaults.
- A **Start/Stop** button that runs the control loop (the same logic as
  `main.py`) in a background thread, so the GUI stays responsive while the
  remapper is active.

### CLI only

```powershell
python main.py
```

Runs the control loop standalone from the terminal, using whatever is
currently saved in `user_config.json`. Press `Ctrl+C` in the terminal to
stop (this releases all held keys/mouse buttons).

### Diagnostics

```powershell
python debug.py
```

A standalone tool that prints the raw `event.ev_type` / `event.code` /
`event.state` for every input from the `inputs` library. Useful for finding
the correct button/axis codes for `CONTROLLER_LAYOUT` when a controller
doesn't match the XInput defaults and you want to inspect events manually
instead of using the in-app Calibration Wizard.

## Build (standalone `.exe`)

If you'd rather hand a non-technical player a single double-clickable file (no
Python install, no terminal), build a one-file executable with
[PyInstaller](https://pyinstaller.org/):

```powershell
pip install -r requirements.txt
pip install pyinstaller
pyinstaller lolcontroller.spec
```

The result is `dist/LoLController.exe` — a windowed (no-console) one-file build.
The committed `lolcontroller.spec` already collects `customtkinter`'s theme
assets and bundles `icon.ico` if one is present next to the sources. Because the
app often needs to run elevated (see **Troubleshooting** below), a plain `.exe`
is easy to launch with **Right-click → Run as administrator**.

> Note: this is Windows-only, so build it on Windows. `build/`, `dist/`, and
> generated `*.spec` files are git-ignored; only the maintained
> `lolcontroller.spec` is committed.

## Default mapping

| Controller input | Action |
|---|---|
| Square | Right-click (Ability 1) |
| Triangle | Shift (Ability 2) |
| Circle | E (Ability 3) |
| Cross | R (Ability 4) |
| L1 | Q (Summoner spell 1) |
| R1 | F (Summoner spell 2) |
| D-Pad Up / Right / Down / Left | 1 / 2 / 3 / 4 (item slots) |
| L3 | P (Shop) |
| R3 | Free (unmapped) |
| Start | Escape |
| Select | B (Recall) |
| L2 | Ctrl (modifier) |
| R2 | Left-click (attack / confirm) |
| Left stick | WASD movement |
| Right stick | Proportional mouse-cursor aim |

All of these are editable from the GUI's Mapping tab; the table above is
just the shipped default (`config.py`, `DEFAULTS["MAPPING"]`).

## Elastic aim-return

When you let go of the right stick, the aim cursor no longer teleports to the
screen center in one frame — it animates smoothly back with a cubic ease-out
curve (no overshoot). The duration is controlled by **`AIM_RETURN_MS`** (a
slider in the Settings tab, default `120` ms). The animation is driven from the
existing 100 Hz control loop, so it adds no threads or timers, and once it
finishes the app stops touching the cursor so you can still use your real mouse.
Set `AIM_RETURN_MS` to `0` to restore the old instant-snap behavior.

## Configuration file

On first run, the app creates `user_config.json` next to the source files
(see `config.py`, `load_config()`/`save_config()`). It stores your screen
resolution, key mapping, deadzone/aim-radius settings, and calibrated
controller layout. This file is **per-user/per-machine** and is intentionally
excluded from git (see `.gitignore`) — deleting it is safe, the app will
regenerate it from the coded defaults on the next run.

## Troubleshooting

- **Nothing happens in-game when I press buttons.** If League of Legends (or
  its anti-cheat) is running elevated, run this app **as Administrator**
  too — Windows blocks synthetic input from a lower-privilege process from
  reaching a higher-privilege one (UIPI), and it fails silently.
- **The cursor lands in the wrong place / aim feels offset**, especially on a
  scaled (125%/150%) display. Make sure `SCREEN_WIDTH`/`SCREEN_HEIGHT` in the
  Settings tab match your actual desktop resolution.
- **My controller's buttons don't do anything, or the wrong button fires.**
  Run the **Calibration Wizard** from the GUI (or `python debug.py` to
  inspect raw event codes manually) — not all controllers report the same
  event codes as a standard Xbox/XInput pad.
- **A key or mouse button gets "stuck" down.** Click **Stop** in the GUI (or
  `Ctrl+C` in the terminal for `main.py`) to release all held inputs. If a
  controller is unplugged mid-session, stop and restart the script.
- **The app won't start / `ModuleNotFoundError`.** Re-run
  `pip install -r requirements.txt` in the same Python environment you're
  launching the script with.

## License

MIT — see [LICENSE](LICENSE).
