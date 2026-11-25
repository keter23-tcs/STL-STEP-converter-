"""STL/STEP -> DAE (COLLADA) Konverter mit Konsolenmenue.

Reads all STL and STEP files from the "Input" folder, converts them one
after another to DAE files and writes them to the "Output" folder.
Successfully converted files can be moved to "Input\\done".

STL is read without external libraries. STEP is tessellated into triangles
with cascadio (OpenCASCADE); parts, assemblies and colors are preserved.
Starting without arguments opens the menu, "--all" converts everything directly.
"""

import contextlib
import datetime
import json
import math
import os
import shutil
import struct
import sys
import time
import traceback

APP_TITEL = "STL/STEP to DAE Converter"
ENDUNGEN = (".stl", ".step", ".stp")

# STEP tessellation detail: (max. deviation in mm, max. angle in radians)
STEP_QUALITAET = {
    "coarse": (0.5, 0.5),
    "medium": (0.1, 0.3),
    "fine": (0.02, 0.15),
}
STANDARD_MATERIAL = ("Gray", (0.7, 0.7, 0.7))


def basis_ordner():
    # Built as .exe: folder of the .exe, otherwise folder of this script
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASIS = basis_ordner()
INPUT = os.path.join(BASIS, "Input")
OUTPUT = os.path.join(BASIS, "Output")
ERLEDIGT = os.path.join(INPUT, "done")


class KonverterFehler(Exception):
    pass


# ---------------------------------------------------------------------------
# STL einlesen
# ---------------------------------------------------------------------------

def lese_stl(pfad):
    """Liefert einen Iterator ueber Dreiecke als 9er-Tupel (ax, ay, az, bx, ..., cz)."""
    with open(pfad, "rb") as f:
        daten = f.read()

    if len(daten) >= 84:
        anzahl = struct.unpack_from("<I", daten, 80)[0]
        if anzahl > 0 and 84 + 50 * anzahl == len(daten):
            return _lese_binaer(daten, anzahl)

    kopf = daten[:1024].lstrip().lower()
    if kopf.startswith(b"solid") and b"facet" in daten[:4096].lower():
        return _lese_ascii(daten)

    # Manche Programme haengen Bytes an das Ende einer Binaer-STL an
    if len(daten) >= 84:
        anzahl = struct.unpack_from("<I", daten, 80)[0]
        if anzahl > 0 and 84 + 50 * anzahl <= len(daten):
            return _lese_binaer(daten, anzahl)

    raise KonverterFehler("File is neither a valid binary nor ASCII STL.")


def _lese_binaer(daten, anzahl):
    bereich = memoryview(daten)[84:84 + 50 * anzahl]
    # Je Dreieck: Normale (3 float), 3 Eckpunkte (9 float), Attribut (uint16)
    return (t[3:12] for t in struct.iter_unpack("<12fH", bereich))


def _lese_ascii(daten):
    punkte = []
    for zeile in daten.decode("latin-1").splitlines():
        teile = zeile.split()
        if teile and teile[0].lower() == "vertex":
            if len(teile) < 4:
                raise KonverterFehler("Fehlerhafte vertex-Zeile: " + zeile.strip())
            try:
                punkte.extend((float(teile[1]), float(teile[2]), float(teile[3])))
            except ValueError:
                raise KonverterFehler("Invalid number in line: " + zeile.strip())
            if len(punkte) == 9:
                yield tuple(punkte)
                punkte = []
    if punkte:
        raise KonverterFehler("ASCII-STL endet mitten in einem Dreieck.")


# ---------------------------------------------------------------------------
# Read STEP (cascadio tessellates into triangles and returns GLB)
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def stille_ausgabe():
    """Unterdrueckt Meldungen, die OpenCASCADE direkt in die Konsole schreibt."""
    try:
        sys.stdout.flush()
        sys.stderr.flush()
        alt = (os.dup(1), os.dup(2))
    except (OSError, AttributeError, ValueError):
        alt = None
    if alt is None:
        yield
        return
    null = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(null, 1)
        os.dup2(null, 2)
        yield
    finally:
        os.dup2(alt[0], 1)
        os.dup2(alt[1], 2)
        for fd in (null,) + alt:
            os.close(fd)


def lese_step(pfad, qualitaet):
    """Returns the tessellated STEP file as GLB bytes (meters, Z up)."""
    try:
        import cascadio
    except ImportError as e:
        raise KonverterFehler("STEP support is not available (%s)." % e)

    with open(pfad, "rb") as f:
        daten = f.read()
    linear, winkel = STEP_QUALITAET[qualitaet]
    with stille_ausgabe():
        glb = cascadio.load(daten, "step", tol_linear=linear, tol_angular=winkel)
    if not glb:
        raise KonverterFehler(
            "STEP file could not be read (damaged or not a valid STEP file).")
    return glb


GLB_KOMPONENTEN = {5121: "B", 5123: "H", 5125: "I", 5126: "f"}
GLB_BREITE = {"SCALAR": 1, "VEC3": 3}


def szene_aus_glb(glb, stamm):
    """Converts GLB data into a scene in millimeters (parts, assemblies, colors)."""
    if glb[:4] != b"glTF":
        raise KonverterFehler("Unerwartetes Zwischenformat (kein GLB).")
    json_laenge = struct.unpack_from("<I", glb, 12)[0]
    gltf = json.loads(bytes(glb[20:20 + json_laenge]).decode("utf-8"))
    bin_start = 20 + json_laenge
    binaer = b""
    if len(glb) >= bin_start + 8:
        bin_laenge = struct.unpack_from("<I", glb, bin_start)[0]
        binaer = memoryview(glb)[bin_start + 8:bin_start + 8 + bin_laenge]

    def accessor(nr):
        acc = gltf["accessors"][nr]
        view = gltf["bufferViews"][acc["bufferView"]]
        typ = GLB_KOMPONENTEN[acc["componentType"]]
        breite = GLB_BREITE[acc["type"]]
        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        groesse = struct.calcsize("<" + typ) * breite
        schritt = view.get("byteStride") or groesse
        if schritt == groesse:
            return struct.unpack_from("<%d%s" % (acc["count"] * breite, typ), binaer, start)
        werte = []
        for i in range(acc["count"]):
            werte.extend(struct.unpack_from("<%d%s" % (breite, typ), binaer, start + i * schritt))
        return werte

    materialien = []
    for m in gltf.get("materials", []):
        farbe = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", (1, 1, 1, 1))
        rgb = tuple(linear_zu_srgb(c) for c in farbe[:3])
        materialien.append(("Color_%02X%02X%02X" % tuple(round(c * 255) for c in rgb), rgb))
    standard = []

    def standard_material():
        if not standard:
            standard.append(len(materialien))
            materialien.append(STANDARD_MATERIAL)
        return standard[0]

    geometrien = []
    geo_index = {}
    verworfen = 0
    for nr, mesh in enumerate(gltf.get("meshes", [])):
        gruppen = []
        for prim in mesh.get("primitives", []):
            if prim.get("mode", 4) != 4:  # nur Dreiecke
                continue
            attr = prim["attributes"]
            pos = [v * 1000.0 for v in accessor(attr["POSITION"])]  # Meter -> mm
            nor = accessor(attr["NORMAL"]) if "NORMAL" in attr else None
            idx = accessor(prim["indices"]) if "indices" in prim else range(len(pos) // 3)
            material = prim.get("material")
            if material is None:
                material = standard_material()
            gruppen.append((material, _glb_dreiecke(pos, nor, idx)))
        geo = baue_mesh(gruppen)
        verworfen += geo["verworfen"]
        if any(indizes for _, indizes in geo["gruppen"]):
            name = mesh.get("name", "")
            geo["name"] = "Part_%d" % (nr + 1) if _generisch(name) else name
            geo_index[nr] = len(geometrien)
            geometrien.append(geo)

    zaehler = [0]

    def knoten(nr, tiefe):
        n = gltf["nodes"][nr]
        name = n.get("name", "")
        if _generisch(name) and "mesh" in n:
            name = gltf["meshes"][n["mesh"]].get("name", "")
        if _generisch(name):
            zaehler[0] += 1
            name = stamm if tiefe == 0 else "Part_%d" % zaehler[0]
        return {
            "name": name,
            "matrix": _knoten_matrix(n),
            "geometrie": geo_index.get(n.get("mesh")),
            "kinder": [knoten(k, tiefe + 1) for k in n.get("children", [])],
        }

    szenen = gltf.get("scenes")
    if szenen:
        wurzeln = szenen[gltf.get("scene", 0)].get("nodes", [])
    else:
        kinder = {k for n in gltf.get("nodes", []) for k in n.get("children", [])}
        wurzeln = [i for i in range(len(gltf.get("nodes", []))) if i not in kinder]

    return {
        "materialien": materialien,
        "geometrien": geometrien,
        "knoten": [knoten(nr, 0) for nr in wurzeln],
        "verworfen": verworfen,
    }


def _glb_dreiecke(pos, nor, idx):
    for k in range(0, len(idx) - 2, 3):
        a, b, c = idx[k] * 3, idx[k + 1] * 3, idx[k + 2] * 3
        dreieck = (pos[a], pos[a + 1], pos[a + 2],
                   pos[b], pos[b + 1], pos[b + 2],
                   pos[c], pos[c + 1], pos[c + 2])
        if nor is not None:
            dreieck += (nor[a], nor[a + 1], nor[a + 2],
                        nor[b], nor[b + 1], nor[b + 2],
                        nor[c], nor[c + 1], nor[c + 2])
        yield dreieck


def _generisch(name):
    # Von OpenCASCADE vergebene Platzhalternamen ersetzen wir durch eigene
    return not name or name.isdigit() or name.startswith("Open CASCADE")


def _knoten_matrix(n):
    """4x4-Matrix zeilenweise (wie COLLADA), Verschiebung in mm. None = keine Transformation."""
    if "matrix" in n:
        m = n["matrix"]  # glTF speichert spaltenweise
        zeilen = [m[s * 4 + z] for z in range(4) for s in range(4)]
    else:
        tx, ty, tz = n.get("translation", (0, 0, 0))
        x, y, z, w = n.get("rotation", (0, 0, 0, 1))
        sx, sy, sz = n.get("scale", (1, 1, 1))
        rot = (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w),
               2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w),
               2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))
        zeilen = [rot[0] * sx, rot[1] * sy, rot[2] * sz, tx,
                  rot[3] * sx, rot[4] * sy, rot[5] * sz, ty,
                  rot[6] * sx, rot[7] * sy, rot[8] * sz, tz,
                  0, 0, 0, 1]
    for i in (3, 7, 11):
        zeilen[i] *= 1000.0  # Meter -> mm
    if zeilen == [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]:
        return None
    return zeilen


def linear_zu_srgb(c):
    # glTF-Farben sind linear, DAE-Programme wie SketchUp erwarten sRGB
    c = min(max(float(c), 0.0), 1.0)
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


# ---------------------------------------------------------------------------
# Mesh aufbereiten
# ---------------------------------------------------------------------------

def baue_mesh(gruppen):
    """Fuehrt gleiche Eckpunkte zusammen und bereitet die Normalen auf.

    gruppen: Liste aus (material, dreiecke). Ein Dreieck ist ein 9er-Tupel
    (Eckpunkte) oder ein 18er-Tupel (Eckpunkte + Normale je Ecke). Ohne
    mitgelieferte Normalen wird die Flaechennormale berechnet.

    Rueckgabe: dict mit positionen/normalen (flache Float-Listen), gruppen
    [(material, indizes)] mit je Dreieck v0 n0 v1 n1 v2 n2, gelesen, verworfen.
    """
    punkt_index = {}
    normal_index = {}
    positionen = []
    normalen = []
    ergebnis = []
    gelesen = 0
    verworfen = 0

    def normale(nx, ny, nz):
        laenge = math.sqrt(nx * nx + ny * ny + nz * nz)
        n = (round(nx / laenge, 6), round(ny / laenge, 6), round(nz / laenge, 6))
        j = normal_index.get(n)
        if j is None:
            j = len(normal_index)
            normal_index[n] = j
            normalen.extend(n)
        return j

    for material, dreiecke in gruppen:
        indizes = []
        for d in dreiecke:
            gelesen += 1
            ax, ay, az, bx, by, bz, cx, cy, cz = d[:9]

            ux, uy, uz = bx - ax, by - ay, bz - az
            vx, vy, vz = cx - ax, cy - ay, cz - az
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            laenge = math.sqrt(nx * nx + ny * ny + nz * nz)
            if laenge == 0.0 or not math.isfinite(laenge):
                verworfen += 1
                continue

            ecken = []
            for p in ((ax, ay, az), (bx, by, bz), (cx, cy, cz)):
                i = punkt_index.get(p)
                if i is None:
                    i = len(punkt_index)
                    punkt_index[p] = i
                    positionen.extend(p)
                ecken.append(i)
            if ecken[0] == ecken[1] or ecken[1] == ecken[2] or ecken[0] == ecken[2]:
                verworfen += 1
                continue

            flaeche = normale(nx, ny, nz)
            eck_normalen = [flaeche, flaeche, flaeche]
            if len(d) == 18:
                for e in range(3):
                    mx, my, mz = d[9 + 3 * e:12 + 3 * e]
                    if mx * mx + my * my + mz * mz > 1e-12:
                        eck_normalen[e] = normale(mx, my, mz)

            indizes.extend((ecken[0], eck_normalen[0], ecken[1], eck_normalen[1],
                            ecken[2], eck_normalen[2]))
        ergebnis.append((material, indizes))

    return {
        "positionen": positionen,
        "normalen": normalen,
        "gruppen": ergebnis,
        "gelesen": gelesen,
        "verworfen": verworfen,
    }


def szene_aus_stl(pfad, stamm):
    geo = baue_mesh([(0, lese_stl(pfad))])
    geo["name"] = stamm
    return {
        "materialien": [STANDARD_MATERIAL],
        "geometrien": [geo],
        "knoten": [{"name": stamm, "matrix": None, "geometrie": 0, "kinder": []}],
        "verworfen": geo["verworfen"],
    }


# ---------------------------------------------------------------------------
# DAE schreiben
# ---------------------------------------------------------------------------

def ncname(text):
    # COLLADA erlaubt in name-Attributen nur xs:NCName (z. B. keine Leerzeichen)
    name = "".join(c if (c.isalnum() or c in "._-") else "_" for c in text) or "mesh"
    if not (name[0].isalpha() or name[0] == "_"):
        name = "_" + name
    return name


def _source(teile, sid, werte, format_):
    teile += [
        '        <source id="%s">\n' % sid,
        '          <float_array id="%s-array" count="%d">' % (sid, len(werte)),
        " ".join(format_ % v for v in werte),
        '</float_array>\n',
        '          <technique_common>\n',
        '            <accessor source="#%s-array" count="%d" stride="3">\n' % (sid, len(werte) // 3),
        '              <param name="X" type="float"/>\n',
        '              <param name="Y" type="float"/>\n',
        '              <param name="Z" type="float"/>\n',
        '            </accessor>\n',
        '          </technique_common>\n',
        '        </source>\n',
    ]


def schreibe_dae(pfad, szene):
    jetzt = datetime.datetime.now().replace(microsecond=0).isoformat()
    teile = [
        '<?xml version="1.0" encoding="utf-8"?>\n',
        '<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">\n',
        '  <asset>\n',
        '    <contributor>\n',
        '      <authoring_tool>%s</authoring_tool>\n' % APP_TITEL,
        '    </contributor>\n',
        '    <created>%s</created>\n' % jetzt,
        '    <modified>%s</modified>\n' % jetzt,
        '    <unit name="millimeter" meter="0.001"/>\n',
        '    <up_axis>Z_UP</up_axis>\n',
        '  </asset>\n',
        '  <library_effects>\n',
    ]
    for nr, (name, (r, g, b)) in enumerate(szene["materialien"]):
        teile += [
            '    <effect id="mat%d-effect">\n' % nr,
            '      <profile_COMMON>\n',
            '        <technique sid="common">\n',
            '          <lambert>\n',
            '            <diffuse>\n',
            '              <color sid="diffuse">%.4f %.4f %.4f 1</color>\n' % (r, g, b),
            '            </diffuse>\n',
            '          </lambert>\n',
            '        </technique>\n',
            '      </profile_COMMON>\n',
            '    </effect>\n',
        ]
    teile.append('  </library_effects>\n  <library_materials>\n')
    for nr, (name, _) in enumerate(szene["materialien"]):
        teile += [
            '    <material id="mat%d" name="%s">\n' % (nr, ncname(name)),
            '      <instance_effect url="#mat%d-effect"/>\n' % nr,
            '    </material>\n',
        ]
    teile.append('  </library_materials>\n  <library_geometries>\n')

    for nr, geo in enumerate(szene["geometrien"]):
        gid = "geom%d" % nr
        teile += [
            '    <geometry id="%s" name="%s">\n' % (gid, ncname(geo["name"])),
            '      <mesh>\n',
        ]
        _source(teile, gid + "-positions", geo["positionen"], "%.8g")
        _source(teile, gid + "-normals", geo["normalen"], "%.6g")
        teile += [
            '        <vertices id="%s-vertices">\n' % gid,
            '          <input semantic="POSITION" source="#%s-positions"/>\n' % gid,
            '        </vertices>\n',
        ]
        for material, indizes in geo["gruppen"]:
            if not indizes:
                continue
            teile += [
                '        <triangles material="mat%d" count="%d">\n' % (material, len(indizes) // 6),
                '          <input semantic="VERTEX" source="#%s-vertices" offset="0"/>\n' % gid,
                '          <input semantic="NORMAL" source="#%s-normals" offset="1"/>\n' % gid,
                '          <p>',
                " ".join(map(str, indizes)),
                '</p>\n',
                '        </triangles>\n',
            ]
        teile += ['      </mesh>\n', '    </geometry>\n']

    teile += [
        '  </library_geometries>\n',
        '  <library_visual_scenes>\n',
        '    <visual_scene id="Scene" name="Scene">\n',
    ]
    knoten_nr = [0]

    def schreibe_knoten(k, tiefe):
        e = "  " * tiefe
        teile.append('%s<node id="node%d" name="%s" type="NODE">\n'
                     % (e, knoten_nr[0], ncname(k["name"])))
        knoten_nr[0] += 1
        if k["matrix"] is not None:
            teile.append('%s  <matrix sid="transform">%s</matrix>\n'
                         % (e, " ".join("%.10g" % v for v in k["matrix"])))
        if k["geometrie"] is not None:
            geo = szene["geometrien"][k["geometrie"]]
            materialien = sorted({m for m, indizes in geo["gruppen"] if indizes})
            teile.extend([
                '%s  <instance_geometry url="#geom%d" name="%s">\n'
                % (e, k["geometrie"], ncname(geo["name"])),
                '%s    <bind_material>\n' % e,
                '%s      <technique_common>\n' % e,
            ])
            for m in materialien:
                teile.append('%s        <instance_material symbol="mat%d" target="#mat%d"/>\n'
                             % (e, m, m))
            teile.extend([
                '%s      </technique_common>\n' % e,
                '%s    </bind_material>\n' % e,
                '%s  </instance_geometry>\n' % e,
            ])
        for kind in k["kinder"]:
            schreibe_knoten(kind, tiefe + 1)
        teile.append('%s</node>\n' % e)

    for k in szene["knoten"]:
        schreibe_knoten(k, 3)

    teile += [
        '    </visual_scene>\n',
        '  </library_visual_scenes>\n',
        '  <scene>\n',
        '    <instance_visual_scene url="#Scene"/>\n',
        '  </scene>\n',
        '</COLLADA>\n',
    ]

    # Write to a temp file first so an abort never leaves a half-written DAE
    temp = pfad + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(teile)
    os.replace(temp, pfad)


# ---------------------------------------------------------------------------
# Ablauf
# ---------------------------------------------------------------------------

def zahl(n):
    return "{:,}".format(n)


def groesse(bytes_):
    if bytes_ >= 1024 * 1024:
        return "%.1f MB" % (bytes_ / 1024 / 1024)
    return "%.0f KB" % max(1, bytes_ / 1024)


def ordner_anlegen():
    os.makedirs(INPUT, exist_ok=True)
    os.makedirs(OUTPUT, exist_ok=True)


def finde_dateien():
    ordner_anlegen()
    dateien = [
        d for d in os.listdir(INPUT)
        if d.lower().endswith(ENDUNGEN) and os.path.isfile(os.path.join(INPUT, d))
    ]
    return sorted(dateien, key=str.lower)


def verschiebe_nach_erledigt(dateiname):
    os.makedirs(ERLEDIGT, exist_ok=True)
    ziel = os.path.join(ERLEDIGT, dateiname)
    if os.path.exists(ziel):
        stamm, endung = os.path.splitext(dateiname)
        stempel = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        ziel = os.path.join(ERLEDIGT, "%s_%s%s" % (stamm, stempel, endung))
    shutil.move(os.path.join(INPUT, dateiname), ziel)


def _zaehle_teile(knoten):
    return sum((k["geometrie"] is not None) + _zaehle_teile(k["kinder"]) for k in knoten)


def konvertiere_datei(dateiname, ziel_name, qualitaet):
    """Wandelt eine STL/STEP aus Input in eine DAE in Output um. Gibt Infos zurueck."""
    stamm, endung = os.path.splitext(dateiname)
    quelle = os.path.join(INPUT, dateiname)

    if endung.lower() == ".stl":
        szene = szene_aus_stl(quelle, stamm)
    else:
        szene = szene_aus_glb(lese_step(quelle, qualitaet), stamm)

    dreiecke = sum(len(indizes) // 6
                   for geo in szene["geometrien"] for _, indizes in geo["gruppen"])
    if not dreiecke:
        raise KonverterFehler("No valid triangles found.")
    schreibe_dae(os.path.join(OUTPUT, ziel_name), szene)
    return dreiecke, szene["verworfen"], _zaehle_teile(szene["knoten"])


def alle_umwandeln(verschieben, qualitaet):
    dateien = finde_dateien()
    if not dateien:
        print()
        print("  No STL or STEP files found.")
        print("  Put your files into this folder:")
        print("  " + INPUT)
        return 0, 0

    print()
    print("  Converting %d file(s) (STEP quality: %s) ..." % (len(dateien), qualitaet))
    print()
    ok = 0
    fehler = []
    benutzt = set()
    start_gesamt = time.time()

    for nr, dateiname in enumerate(dateien, 1):
        print("  [%d/%d] %s" % (nr, len(dateien), dateiname))
        stamm, endung = os.path.splitext(dateiname)
        # An STL and a STEP file with the same name must not overwrite each other
        ziel_name = stamm + ".dae"
        if ziel_name.lower() in benutzt:
            ziel_name = "%s_%s.dae" % (stamm, endung.lstrip(".").lower())
        benutzt.add(ziel_name.lower())

        start = time.time()
        try:
            dreiecke, verworfen, teile = konvertiere_datei(dateiname, ziel_name, qualitaet)
        except Exception as e:
            fehler.append(dateiname)
            print("        ERROR: %s" % e)
            print("        File stays in the Input folder.")
            continue

        dauer = "%.1f s" % (time.time() - start)
        hinweis = ""
        if teile > 1:
            hinweis += ", %d parts" % teile
        if verworfen:
            hinweis += ", %s invalid triangles removed" % zahl(verworfen)
        print("        OK -> %s  (%s triangles, %s%s)" % (ziel_name, zahl(dreiecke), dauer, hinweis))

        if verschieben:
            try:
                verschiebe_nach_erledigt(dateiname)
                print("        File moved to Input\\done")
            except OSError as e:
                print("        Note: file could not be moved (%s)" % e)
        ok += 1

    gesamt = "%.1f s" % (time.time() - start_gesamt)
    print()
    print("  " + "-" * 60)
    print("  Finished in %s: %d succeeded, %d failed" % (gesamt, ok, len(fehler)))
    for d in fehler:
        print("    - failed: %s" % d)
    print("  DAE files are in: " + OUTPUT)
    return ok, len(fehler)


def zeige_dateien():
    dateien = finde_dateien()
    print()
    if not dateien:
        print("  No STL or STEP files in the Input folder.")
        print("  " + INPUT)
        return
    print("  Files in the Input folder:")
    print()
    for nr, d in enumerate(dateien, 1):
        print("  %3d. %-50s %10s" % (nr, d, groesse(os.path.getsize(os.path.join(INPUT, d)))))


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

# Logo (cat in a ring) and lettering from the start animation of the app, drawn with block characters in the top right corner of the window.
# Cat: converted from the app's css/katze.png into half blocks (once, built in: no image library needed).
KATZE = [
    '                             ▄▄███',
    '         ▄▄ ▀▀▀▀▀▀         ▄█████▀',
    '      ▄▀▀                ▄██████▀',
    '    ▄▀        ▄▄████▄   ███████▀',
    '  ▄▀        ▄█████████ ███████▀',
    ' ▄      ▄▄ █████████████████▀ ▄',
    '  ▄   ▄▄██▄███████████████▀    █',
    '█ ██████████████████████▀      █',
    '█  █████████████████████',
    '█ ▀███▄ ████████████████',
    '▀   ▀ ▄▄█ ▀█████▀██████        █',
    ' ▀         █████ █████',
    '  ▀        ████   ████       ▄',
    '   ▀▄      ████   ██▀██    ▄▀',
    '       ▄  ▄████   ██ █▀  ▄▀',
    '         ██▀██▀ ▄██ ▄█▀▀',
    '                   ███',
]
# Lettering "STACK LAB²³" from a pixel font (3 × 5), in half blocks (3 rows high)
SCHRIFT = {
    'S': ['███', '█  ', '███', '  █', '███'], 'T': ['███', ' █ ', ' █ ', ' █ ', ' █ '], 'A': [' █ ', '█ █', '███', '█ █', '█ █'],
    'C': ['███', '█  ', '█  ', '█  ', '███'], 'K': ['█ █', '█ █', '██ ', '█ █', '█ █'], 'L': ['█  ', '█  ', '█  ', '█  ', '███'],
    'B': ['██ ', '█ █', '██ ', '█ █', '██ '], ' ': ['  ', '  ', '  ', '  ', '  '],
}
LOGO_BREITE = 38   # room for logo and lettering (36 characters) plus right margin


def schriftzug(text='STACK LAB'):
    zeilen = ['', '', '']
    for ch in text:
        g = SCHRIFT[ch] + ['   ' if len(SCHRIFT[ch][0]) == 3 else '  ']   # 6. Pixelzeile leer
        for r in range(3):
            for c in range(len(g[0])):
                o, u = g[2 * r][c] != ' ', g[2 * r + 1][c] != ' '
                zeilen[r] += '█' if o and u else '▀' if o else '▄' if u else ' '
            zeilen[r] += ' '
    zeilen[0] = zeilen[0].rstrip() + '²³'
    return [z.rstrip() for z in zeilen]


def terminal_breite():
    try:
        return shutil.get_terminal_size((100, 30)).columns
    except OSError:
        return 100


def ansi_an():
    """Enable escape sequences in the Windows console (newer Windows versions know them but need them switched on)."""
    if os.name == 'nt':
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            m = ctypes.c_uint32()
            if k.GetConsoleMode(h, ctypes.byref(m)):
                k.SetConsoleMode(h, m.value | 0x0004)
                return True
            return False
        except Exception:
            return False
    return sys.stdout.isatty()


def logo_zeichnen():
    """Write logo and lettering at fixed positions in the top right and restore the cursor. Window too narrow: nothing."""
    breite = terminal_breite()
    if breite < LOGO_BREITE + 78 or not sys.stdout.isatty() or not ansi_an():
        return
    spalte = breite - LOGO_BREITE
    wort = schriftzug()
    zeilen = [z.ljust(LOGO_BREITE - 2) for z in KATZE] + [''] + [(' ' * ((LOGO_BREITE - 2 - len(z)) // 2) + z) for z in wort]
    out = ['\x1b7']   # Cursor merken
    for i, z in enumerate(zeilen):
        if z.strip():
            out.append('\x1b[%d;%dH\x1b[97m%s\x1b[0m' % (2 + i, spalte, z))
    out.append('\x1b8')
    sys.stdout.write(''.join(out))
    sys.stdout.flush()


def breite_links():
    """Maximum width of the text on the left so it does not run under the logo."""
    b = terminal_breite()
    return b - LOGO_BREITE - 3 if b >= LOGO_BREITE + 78 else 200


def kuerzen(text, n):
    return text if len(text) <= n else text[:max(1, n - 1)] + '…'


def bildschirm_leeren():
    os.system("cls" if os.name == "nt" else "clear")


def warte_auf_enter():
    print()
    input("  Press Enter to return to the menu ...")


def menue():
    verschieben = True
    stufen = list(STEP_QUALITAET)
    qualitaet = "medium"
    if os.name == "nt":
        os.system("title " + APP_TITEL.replace("/", "-"))

    while True:
        bildschirm_leeren()
        anzahl = len(finde_dateien())
        logo_zeichnen()   # cat in a ring and lettering in the top right (like the 3D Simulator)
        print()
        print("  " + "=" * 60)
        print("    " + APP_TITEL)
        print("  " + "=" * 60)
        print()
        links = breite_links()
        print(kuerzen("  Input:  %s  (%d file(s))" % (INPUT, anzahl), links))
        print(kuerzen("  Output: %s" % OUTPUT, links))
        print()
        print("  [1] Convert all files (STL and STEP)")
        print("  [2] Show files in the Input folder")
        print('  [3] Move finished files to "Input\\done": %s  (toggle)'
              % ("ON" if verschieben else "OFF"))
        print("  [4] STEP quality: %s  (toggle: coarse / medium / fine)" % qualitaet)
        print("  [0] Quit")
        print()
        wahl = input("  Choice: ").strip()

        if wahl == "1":
            alle_umwandeln(verschieben, qualitaet)
            warte_auf_enter()
        elif wahl == "2":
            zeige_dateien()
            warte_auf_enter()
        elif wahl == "3":
            verschieben = not verschieben
        elif wahl == "4":
            qualitaet = stufen[(stufen.index(qualitaet) + 1) % len(stufen)]
        elif wahl == "0":
            return
        else:
            print()
            print("  Invalid choice. Please enter 0, 1, 2, 3 or 4.")
            time.sleep(1.5)


def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    # Create the folders right at startup: a fresh download has none, the user should only have to drop files in
    os.makedirs(INPUT, exist_ok=True)
    os.makedirs(OUTPUT, exist_ok=True)

    if "--all" in sys.argv[1:] or "--alle" in sys.argv[1:]:
        ok, fehler = alle_umwandeln(verschieben=True, qualitaet="medium")
        sys.exit(1 if fehler else 0)

    try:
        menue()
    except (KeyboardInterrupt, EOFError):
        pass
    except Exception:
        # In the .exe the window should not close immediately on a crash
        print()
        print("  Unexpected error:")
        traceback.print_exc()
        try:
            input("\n  Press Enter to quit ...")
        except (KeyboardInterrupt, EOFError):
            pass


if __name__ == "__main__":
    main()
