# STL/STEP → DAE Converter

**English** · [Deutsch](README.de.md)

Converts **STL** and **STEP** files (`.stl`, `.step`, `.stp`) to **DAE** (COLLADA), in millimeters with Z up, so that
SketchUp and the [Raum Simulation / Stack Lab²³](https://github.com/keter23-tcs) take over the dimensions 1:1.
With STEP, single parts, assemblies and colors are preserved (as separate groups in SketchUp), and the unit (mm, inch, m …) is converted automatically.

## Installation (Windows, no Python needed) – recommended

1. On the **[Releases](../../releases/latest)** page download **`STL-Converter-Windows.zip`**.
2. Unzip it (anywhere).
3. Put your STL/STEP files into the **`Input`** folder.
4. Double-click **`STL-Converter.exe`**, press **`1`** + Enter in the menu. Done: the DAE files are in the **`Output`** folder.

> Windows may warn about an unknown app on the first start ("Windows protected your PC"):
> **More info → Run anyway**. The .exe is not signed; the source code (`stl_converter.py`) is open in this repository.

## Alternative: from source (Windows, Mac, Linux)

You need [Python 3.9+](https://www.python.org/downloads/) (on Windows tick "Add python.exe to PATH" during installation).

* **Windows:** double-click `Start.bat`. On the first run the script sets everything up by itself (private Python environment `.venv`, downloads the packages), after that it starts immediately.
* **Mac / Linux:** run `./start.sh` in the terminal.

Plain STL files even work without extra packages (`python stl_converter.py`); STEP needs [cascadio](https://pypi.org/project/cascadio/) (OpenCASCADE), which `Start.bat` / `start.sh` install.

## Menu

| Key | Function |
|---|---|
| `1` | Convert all files from `Input` (a DAE with the same name in `Output` is overwritten) |
| `2` | Show the files in the Input folder |
| `3` | Move finished files to `Input\done`: ON/OFF (default ON; failed files stay in `Input`) |
| `4` | STEP quality coarse / medium / fine (fine = rounder but larger files; no effect on STL) |
| `0` | Quit |

Without the menu: `STL-Converter.exe --all` (or `python stl_converter.py --all`) converts everything directly.

## Notes

* STL has no colors and no parts, so the DAE gets a neutral gray.
* Do **not** save files from Notion with Ctrl+S in the browser (STL files get corrupted that way); click "…" → "Download" on the file instead.
* The `Input` and `Output` folders sit next to the .exe or the script and are created at startup.

## Build it yourself / create a release

* Locally: `build_exe.bat` (builds `STL-Converter.exe`, needs Python).
* On GitHub: push a tag like `v1.0` (`git tag v1.0 && git push --tags`). The **Build Windows EXE** action (`.github/workflows/release.yml`) builds the .exe
  and attaches `STL-Converter-Windows.zip` to a release. It can also be started by hand (*Actions* tab).
