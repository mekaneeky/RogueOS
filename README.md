# RogueOS (Prototype v3.3 — Roguelike skin + true tile movement)

- '@' now moves across floor tiles (not item-to-item). 
- You descend on a directory tile '>'; ascend on the '<' tile near top-left.
- 'M'/'m' or '/' opens a teleport prompt on the status line; fuzzy LIKE over full paths.
- Selection auto-snaps to the nearest item as you move.

Run:
  python3 run.py /path/to/root

<img width="1453" height="688" alt="image" src="https://github.com/user-attachments/assets/f5bba017-73d3-47d9-97e9-c50f3425bd87" />

## Web renderer (Three.js astral view)

<img width="1919" height="877" alt="image" src="https://github.com/user-attachments/assets/416f45f0-9fff-438e-81f6-ba3a271cd7cf" />


An experimental renderer that reuses the same roguefs core but surfaces the directory
graph inside a Three.js scene:

```
python3 scripts/fetch_web_assets.py
python3 run_web.py /path/to/root
```

Then open http://127.0.0.1:8765/ in your browser. Click glowing nodes to descend into
directories, hover for quick stats, or press ⏎ in the search box to look up paths. Use the
“Reset View” button if you drift too far into space.

## Desktop GUI (embedded Three.js)

If you prefer a native window instead of the browser, install the GUI requirements and run:

```
pip install -r requirements-gui.txt
python3 run_gui.py /path/to/root
```

This spins up the same astral scene in a desktop window, keeping all assets local to the
machine. The CLI accepts `--width`/`--height` to tweak the window size and `--port 0` (the
default) picks a free port for its embedded server. On Linux you need either a Qt (PySide6)
or GTK stack available; the `requirements-gui.txt` bundle pulls in PySide6, the Qt6 add-ons
(including WebEngine), and qtpy for the simplest cross-platform setup.

### Switching from PyQt5

If you previously installed the PyQt-based requirements, remove them before installing the
PySide6 stack:

```
pip uninstall PyQt5 PyQtWebEngine PyQt5-Qt5 PyQtWebEngine-Qt5 -y
```

If you previously attempted to install the Qt5-based packages (or the deprecated
`PySide6-Qt6-WebEngine` wheels), remove them before reinstalling:

```
pip uninstall PyQt5 PyQtWebEngine PyQt5-Qt5 PyQtWebEngine-Qt5 PySide6-Qt6-WebEngine -y
```

Then install the fresh GUI requirements:

```
pip install -r requirements-gui.txt
```

Finally, download the web renderer assets (Three.js, OrbitControls, post-processing passes) so the
desktop view can start without network access:

```
python3 scripts/fetch_web_assets.py
```

### Linux / WSL prerequisites

QtWebEngine also depends on a handful of system libraries that pip cannot install.
On Ubuntu/WSL the following usually covers the missing pieces:

```
sudo apt update
sudo apt install -y libnss3 libsmime3 libxkbcommon-x11-0 libxcomposite1 libxcursor1 \
    libxdamage1 libxfixes3 libxi6 libxrandr2 libxtst6 libdbus-glib-1-2 qt6-base-dev qt6-webengine-dev
```

You also need an X11 server (or Wayland bridge) running on the Windows host so the GUI can display.
