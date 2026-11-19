# Basic Timer

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A small desktop timer and stopwatch written in Python with Tkinter. The time is shown in the middle of an atom, and the electrons speed up while it's running.

## Features

- Countdown timer with quick presets (1m, 5m, 10m, 25m, 1h) or a custom time
- Stopwatch with laps
- Sound and popup when the timer finishes
- Option to keep the window on top of other windows
- Keyboard shortcuts

## Getting started

### Requirements

- Python 3.8 or newer
- Tkinter (comes with Python on Windows and macOS; on Linux install `python3-tk`)

### Run it

```
git clone https://github.com/MW4-Salud/Basic-Timer.git
cd Basic-Timer
python electron_timer.py
```

## Keyboard shortcuts

| Key   | Action                    |
|-------|---------------------------|
| Space | Start / pause             |
| R     | Reset                     |
| L     | Lap (stopwatch)           |
| T     | Switch timer / stopwatch  |

## Project structure

```
Basic-Timer/
├── electron_timer.py   # the app
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
└── .gitignore
```

## Branches

- `main` - stable version
- `develop` - work in progress, merged into `main` for releases
- `feature/...` - one branch per new feature, merged into `develop` with a pull request

## License

MIT. See [LICENSE](LICENSE).
