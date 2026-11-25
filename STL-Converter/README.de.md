# STL/STEP → DAE Konverter

[English](README.md) · **Deutsch**

Wandelt **STL**- und **STEP**-Dateien (`.stl`, `.step`, `.stp`) in **DAE** (COLLADA) um, in Millimetern und mit Z nach oben, sodass
SketchUp und die [Raum Simulation / Stack Lab²³](https://github.com/keter23-tcs) die Maße 1:1 übernehmen.
Bei STEP bleiben Einzelteile, Baugruppen und Farben erhalten (in SketchUp als eigene Gruppen), die Einheit (mm, Zoll, m …) wird automatisch umgerechnet.

> Das Programm selbst (Menü und Meldungen) ist auf Englisch.

## Installation (Windows, ohne Python) – empfohlen

1. Auf der Seite **[Releases](../../releases/latest)** die Datei **`STL-Converter-Windows.zip`** herunterladen.
2. Zip entpacken (egal wohin).
3. STL-/STEP-Dateien in den Ordner **`Input`** legen.
4. **`STL-Converter.exe`** doppelklicken, im Menü **`1`** + Enter. Fertig: die DAE-Dateien liegen im Ordner **`Output`**.

> Windows warnt beim ersten Start evtl. vor einer unbekannten App („Der Computer wurde durch Windows geschützt“):
> **Weitere Informationen → Trotzdem ausführen**. Die .exe ist nicht signiert, der Quelltext (`stl_converter.py`) liegt offen in diesem Repository.

## Alternative: aus dem Quelltext (Windows, Mac, Linux)

Du brauchst [Python 3.9+](https://www.python.org/downloads/) (Windows: beim Installieren „Add python.exe to PATH“ ankreuzen).

* **Windows:** `Start.bat` doppelklicken. Beim ersten Mal richtet das Skript alles selbst ein (eigene Python-Umgebung `.venv`, Pakete laden), danach startet es sofort.
* **Mac / Linux:** `./start.sh` im Terminal.

Reine STL-Dateien gehen sogar ohne zusätzliche Pakete (`python stl_converter.py`); für STEP wird [cascadio](https://pypi.org/project/cascadio/) (OpenCASCADE) gebraucht, das `Start.bat` / `start.sh` installieren.

## Menü

| Taste | Funktion |
|---|---|
| `1` | Alle Dateien aus `Input` umwandeln (eine gleichnamige DAE in `Output` wird überschrieben) |
| `2` | Dateien im Input-Ordner anzeigen |
| `3` | Fertige Dateien nach `Input\done` verschieben: ON/OFF (Standard ON; fehlerhafte bleiben in `Input`) |
| `4` | STEP-Qualität coarse / medium / fine (grob / mittel / fein; fine = runder, aber größere Dateien; bei STL ohne Wirkung) |
| `0` | Beenden |

Ohne Menü: `STL-Converter.exe --all` (bzw. `python stl_converter.py --all`) wandelt direkt alles um.

## Hinweise

* STL hat keine Farben und keine Teile, die DAE bekommt ein neutrales Grau.
* Dateien aus Notion **nicht** mit Strg+S im Browser speichern (STL-Dateien werden dabei beschädigt), sondern bei der Datei auf „…“ → „Herunterladen“.
* Die Ordner `Input` und `Output` liegen neben der .exe bzw. dem Skript und werden beim Start angelegt.

## Selbst bauen / Release erstellen

* Lokal: `build_exe.bat` (baut `STL-Converter.exe`, braucht Python).
* Auf GitHub: Einen Tag wie `v1.0` pushen (`git tag v1.0 && git push --tags`). Die Aktion **Build Windows EXE** (`.github/workflows/release.yml`) baut die .exe
  und hängt `STL-Converter-Windows.zip` an ein Release an. Sie lässt sich auch von Hand starten (Reiter *Actions*).
