# Desktop Alt+Tab for Windows 10

A custom Alt+Tab switcher for Windows 10 that brings back the **Desktop** entry from Windows 7. Select it to minimize your windows and land on the desktop, even from a fullscreen game where **Win+D** gets overridden.

## Features

- **Desktop card** in the switcher, showing your wallpaper
- **Live window previews** using Windows' own thumbnail system (DWM)
- **Most-recently-used ordering**, so tapping Alt+Tab swaps between your last two windows (Desktop included)
- **Per-monitor Desktop:** minimizes the windows on the monitor you're working on
- **Grid layout** with arrow-key and mouse selection
- **Stuck-Alt protection:** a watchdog releases Alt/Shift if they get stuck
- **Lightweight:** it only scans your windows when the switcher opens

## Requirements

- **Windows** (made and tested on Windows 10; untested on Windows 11)
- **Python 3** from [python.org](https://www.python.org/downloads/). Tkinter comes with it, so make sure "tcl/tk" stays ticked in the installer (it is by default)
- One package: `pywin32`

## Install

1. Download `desktop_alttab.py` (and `requirements.txt`) from this repo into a folder you won't move later.
2. Open Command Prompt in that folder and run:

   ```
   pip install -r requirements.txt
   ```

   or, without the file:

   ```
   pip install pywin32
   ```

## Run

```
python desktop_alttab.py
```

Or, to hide the console window:

```
pythonw desktop_alttab.py
```

Windows will show a **UAC prompt**, because the script relaunches itself as administrator. This is needed to switch to and from elevated apps and some fullscreen games.

## Controls

| Key | Action |
|---|---|
| **Alt + Tab** | Open the switcher / move to the next window |
| **Alt + Shift + Tab** | Move to the previous window |
| **Arrow keys** | Move around the grid while the switcher is open |
| **Release Alt** | Switch to the selected window |
| **Click a card** | Switch to that window |
| **Esc** | Cancel without switching |
| **Ctrl + Alt + Q** | Quit the script |

Choosing the **Desktop** card minimizes the windows on your current monitor and focuses the desktop. Pressing Alt+Tab again from there returns you to your previous window.

## Settings

Open `desktop_alttab.py` in a text editor. The settings are near the top:

| Setting | What it does |
|---|---|
| `ONLY_ACTIVE_WINDOW = False` | Set to `True` to minimize only the active window instead of every window on the monitor |
| `MAX_COLS = 4` | Number of cards per row |
| `CARD_W`, `CARD_H` | Size of each preview card |

## Run at login

First move the script to a permanent folder. If you move it later, the startup entry will break.

### Option 1: Startup folder (simple, UAC prompt at each login)

1. Find where `pythonw.exe` is. Open Command Prompt, type `where pythonw`, and copy the path it prints (for example `C:\Users\YourName\AppData\Local\Programs\Python\Python312\pythonw.exe`).
2. Press **Win + R**, type `shell:startup`, and press Enter. Anything in this folder runs when you sign in.
3. In that folder, right-click an empty area and choose **New → Shortcut**.
4. In the "Type the location of the item" box, enter the path to `pythonw.exe` in quotes, a space, then the path to the script in quotes. For example:

   ```
   "C:\Users\YourName\AppData\Local\Programs\Python\Python312\pythonw.exe" "C:\Users\YourName\Downloads\desktop_alttab.py"
   ```

5. Click **Next**, name it "Alt Tab Desktop", and click **Finish**. It starts at your next login.

Don't just copy `desktop_alttab.py` itself into the Startup folder, because a plain `.py` file may open in an editor instead of running.

### Option 2: Task Scheduler (no UAC prompt)

1. Press the Windows key, type **Task Scheduler**, and open it.
2. In the right panel, click **Create Task...** (not "Create Basic Task").
3. **General:** name it "Alt Tab Desktop" and tick **Run with highest privileges**.
4. **Triggers:** click New, set **Begin the task** to **At log on**, and click OK.
5. **Actions:** click New and fill in:
   - **Program/script:** the full path to `pythonw.exe` (find it by running `where pythonw` in Command Prompt)
   - **Add arguments:** `"C:\Users\YourName\Downloads\desktop_alttab.py"`
   - **Start in:** the folder containing the script, without quotes
6. **Conditions (laptops):** untick **Start the task only if the computer is on AC power**.
7. **Settings:** untick **Stop the task if it runs longer than 3 days**.
8. Click OK. To test, right-click the task and choose **Run**.

## Stopping and uninstalling

- Press **Ctrl + Alt + Q** to quit. The normal Windows Alt+Tab returns immediately.
- To stop it starting at login, delete the shortcut from the Startup folder or delete the task in Task Scheduler.
- To remove it completely, delete `desktop_alttab.py`. The script installs nothing else.

## Important: games and anti-cheat

This script uses a **low-level keyboard hook** and runs as **administrator**. Some games with strict anti-cheat (for example, kernel-level systems like Riot Vanguard or Easy Anti-Cheat) may not allow this, and it could put your account at risk. **Check the game's rules, or close the script before launching a game, if you're unsure.** Use at your own risk.

Antivirus software may also flag it, since keyboard hooks are a technique used by some malware. The full source is a single file, so you can read it before running it.

## Do I need admin?

The script relaunches itself as administrator by default. Elevation only matters when the window you're switching to is itself running elevated. If you don't need that, you can skip the UAC prompt by commenting out the `ensure_admin()` call near the top of the file (put a `#` in front of it). Fullscreen games may behave differently without it, so test with your own games.

## Troubleshooting

| Problem | Try this |
|---|---|
| Alt+Tab shows the normal Windows switcher | The script isn't running. Check Task Manager for `python` or `pythonw`, and make sure you accepted the UAC prompt |
| `ModuleNotFoundError: No module named 'win32api'` | Run `pip install pywin32` |
| `ModuleNotFoundError: No module named 'tkinter'` | Reinstall Python and keep "tcl/tk and IDLE" ticked |
| Alt seems stuck after a crash | Tap and release **Alt** and **Shift** once |
| Nothing happens in some apps | The app may be elevated. Run the script as administrator |
| A window is missing from the list | Hidden, tool-style, and background windows are skipped, like in the normal Alt+Tab |

## Limitations

- Windows only
- Overlay is always centered on the primary monitor
- Live previews depend on Windows' DWM, so some protected or hardware-accelerated windows may show blank previews
