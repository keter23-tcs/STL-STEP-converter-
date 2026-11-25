STL/STEP to DAE Converter
=========================

How to use:
  1. Put your STL or STEP files (.stl, .step, .stp) into the "Input" folder.
  2. Double-click "STL-Converter.exe" (it takes about 3 seconds to start).
  3. Type "1" in the menu and press Enter.
  4. The finished DAE files are in the "Output" folder.

Menu:
  [1] Convert all files (STL and STEP)
      All files from "Input" are converted one after another.
      A DAE with the same name in "Output" is overwritten.
  [2] Show files in the Input folder
  [3] Move finished files to "Input\done": ON/OFF
      When ON, successfully converted files are moved to
      "Input\done" (default: ON). Files that failed always
      stay in "Input".
  [4] STEP quality: coarse / medium / fine  (default: medium)
      How finely curves (e.g. driver cut-outs) are broken into triangles.
      "fine" looks rounder but makes the file larger and
      SketchUp slower. It has no effect on STL files.
  [0] Quit

Notes:
  - The DAE files are saved in millimeters with the Z axis pointing up,
    so SketchUp takes over the dimensions 1:1.
  - STEP: single parts, assemblies and colors from the CAD are preserved
    (as separate groups in SketchUp). The unit of the STEP file (mm, inch,
    meter ...) is converted to mm automatically.
  - STL has no colors and no parts, so the DAE gets a neutral gray.
  - Do NOT save files from Notion through the browser (Ctrl+S); STL files
    get corrupted that way. In Notion click "..." -> "Download" on the file instead.
  - "STL-Converter.exe" and the folders "Input" and "Output" have to be in
    the same folder. The whole folder can be copied to another PC, no
    Python is needed there.
  - Windows may warn about the unknown .exe on the first start:
    "More info" -> "Run anyway".

To change the program:
  Edit stl_converter.py, then double-click build_exe.bat. That rebuilds
  STL-Converter.exe (needs Python).
