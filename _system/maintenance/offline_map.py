"""
Offline map for the Meshtastic web client.

The web client draws its map from an online style. This module puts a map of one
area on the drive and points the web client at it:

  _system/webclient/maps/
      area.pmtiles        map of the chosen area (OpenStreetMap data, via Protomaps)
      style.json          how to draw it (Protomaps "light" style, made by make_map_style.mjs)
      fonts/, sprites/    label fonts and map icons (protomaps/basemaps-assets)
      pmtiles.js          lets the map library read area.pmtiles (protomaps/PMTiles, BSD-3)
      area.json           which area this is, and from which map build

Two changes to the web client:
  fix_maplibre()     The web client release bundles MapLibre 6, which needs worker files
                     the release doesn't include, so its map can't draw at all. We put the
                     official files for that exact MapLibre version next to it and load
                     those instead (always done, map or no map).
  patch_webclient()  Only with an offline map: the map style address points at
                     maps/style.json, and a small "Map © OpenStreetMap contributors" credit
                     is shown on the map page, as the OpenStreetMap licence requires.

Downloads (all at setup / update time, never when offline):
  - the map area: cut from Protomaps' daily world map with the official pmtiles tool,
    which downloads only the part needed (https://build.protomaps.com)
  - place-name search: OpenStreetMap Nominatim, one request per search
"""
import json, os, platform, re, shutil, subprocess, sys, tarfile, time, urllib.parse, urllib.request, zipfile
from math import cos, radians
from pathlib import Path

HERE = Path(__file__).resolve().parent
STYLE_TEMPLATE = HERE / "map-style-light.json"
UA = "Meshtastic-Emergency-Kit (+https://github.com/doktordeathray/emergency-kit-for-meshtastic)"
BUILDS = "https://build-metadata.protomaps.dev/builds.json"
BUILD_URL = "https://build.protomaps.com/{key}"
ASSETS_ZIP = "https://codeload.github.com/protomaps/basemaps-assets/zip/refs/heads/main"
PMTILES_JS = "https://registry.npmjs.org/pmtiles/-/pmtiles-{v}.tgz"
PMTILES_JS_VERSION = "4.5.0"
TOOL_REPO = "protomaps/go-pmtiles"
FONT_STACKS = ["Noto Sans Regular", "Noto Sans Medium", "Noto Sans Italic"]
MARK = "/*meshtastic-kit:offline-map*/"
ONLINE_STYLE = "https://raw.githubusercontent.com/hc-oss/maplibre-gl-styles/master/styles/osm-mapnik/v8/default.json"


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _download(url, dest: Path):
    """curl when available (shows progress, follows redirects); else urllib."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    if shutil.which("curl"):
        subprocess.run(["curl", "-fL", "--retry", "3", "-#", "-A", UA, "-o", str(tmp), url], check=True)
    else:
        tmp.write_bytes(_get(url, timeout=600))
    tmp.replace(dest)
    return dest


# ---- choosing an area -----------------------------------------------------------------
def search_place(q):
    """[(name, lat, lon)] from OpenStreetMap Nominatim (max 5)."""
    url = ("https://nominatim.openstreetmap.org/search?format=json&limit=5&q=" + urllib.parse.quote(q))
    out = []
    for r in json.loads(_get(url, timeout=30)):
        out.append((r.get("display_name", q), float(r["lat"]), float(r["lon"])))
    return out


def parse_latlon(text):
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$", text)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    return None


def bbox_around(lat, lon, km):
    dlat = km / 111.0
    dlon = km / (111.0 * max(cos(radians(lat)), 0.05))
    return [round(max(lon - dlon, -180), 5), round(max(lat - dlat, -85), 5),
            round(min(lon + dlon, 180), 5), round(min(lat + dlat, 85), 5)]


# ---- the pmtiles tool (for this computer only, kept in the download cache) ---------------
def _tool_asset_pattern():
    s, m = platform.system(), platform.machine().lower()
    arm = m in ("arm64", "aarch64")
    if s == "Darwin":
        return rf"_Darwin_{'arm64' if arm else 'x86_64'}\.zip$"
    if s == "Windows":
        return rf"_Windows_{'arm64' if arm else 'x86_64'}\.zip$"
    if s == "Linux" and (arm or m in ("x86_64", "amd64")):
        return rf"_Linux_{'arm64' if arm else 'x86_64'}\.tar\.gz$"
    return None


def get_tool(cache: Path):
    pat = _tool_asset_pattern()
    if not pat:
        raise RuntimeError(f"Map download isn't supported on this computer ({platform.system()} {platform.machine()}).")
    exe = cache / "pmtiles-tool" / ("pmtiles.exe" if os.name == "nt" else "pmtiles")
    if exe.exists():
        return exe
    rel = json.loads(_get(f"https://api.github.com/repos/{TOOL_REPO}/releases/latest"))
    a = next((a for a in rel["assets"] if re.search(pat, a["name"])), None)
    if not a:
        raise RuntimeError("Couldn't find the map tool for this computer.")
    arc = _download(a["browser_download_url"], cache / "pmtiles-tool" / a["name"])
    if arc.suffix == ".zip":
        zipfile.ZipFile(arc).extractall(exe.parent)
    else:
        with tarfile.open(arc) as t:
            t.extractall(exe.parent)
    exe.chmod(0o755)
    if platform.system() == "Darwin":
        subprocess.run(["xattr", "-d", "com.apple.quarantine", str(exe)], capture_output=True)
    return exe


def latest_build():
    builds = json.loads(_get(BUILDS))
    keys = sorted(b["key"] for b in builds if re.match(r"^\d{8}\.pmtiles$", b["key"]))
    return keys[-1]


def estimate_mb(tool, bbox, maxzoom=15):
    """Size of the area in MB, from the tool's dry run (downloads nothing but an index)."""
    r = subprocess.run([str(tool), "extract", BUILD_URL.format(key=latest_build()), "unused.pmtiles",
                        f"--bbox={','.join(map(str, bbox))}", f"--maxzoom={maxzoom}", "--dry-run"],
                       capture_output=True, text=True, timeout=300)
    m = re.search(r"archive size of ([\d.]+) (kB|KB|MB|GB|B)", r.stdout + r.stderr)
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2).upper()
    return n * {"B": 1e-6, "KB": 1e-3, "MB": 1, "GB": 1000}[unit]


def extract(tool, bbox, dest: Path, maxzoom=15):
    key = latest_build()
    tmp = dest.with_name(dest.name + ".part")
    tmp.unlink(missing_ok=True)
    subprocess.run([str(tool), "extract", BUILD_URL.format(key=key), str(tmp),
                    f"--bbox={','.join(map(str, bbox))}", f"--maxzoom={maxzoom}", "--download-threads=4"],
                   check=True)
    tmp.replace(dest)
    return key


# ---- fonts, icons, pmtiles.js, style -------------------------------------------------------
def install_assets(maps: Path, cache: Path):
    have = maps / "fonts" / FONT_STACKS[0] / "0-255.pbf"
    if not have.exists() or not (maps / "sprites" / "light.json").exists():
        z = _download(ASSETS_ZIP, cache / "map-assets.zip")
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                parts = n.split("/", 1)
                if len(parts) < 2 or n.endswith("/"):
                    continue
                rel = parts[1]
                if rel.startswith("fonts/") and (rel.split("/")[1] in FONT_STACKS or rel == "fonts/OFL.txt"):
                    out = maps / rel
                elif rel.startswith("sprites/v4/light"):
                    out = maps / "sprites" / rel.split("/")[-1]
                else:
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(zf.read(n))
        (maps / "sprites" / "LICENSE.txt").write_text(
            "Map icons from protomaps/basemaps-assets, derived from MIT-licensed tangrams/icons:\n"
            "https://github.com/tangrams/icons/blob/master/LICENSE.md\n")
    js = maps / "pmtiles.js"
    if not js.exists():
        tgz = _download(PMTILES_JS.format(v=PMTILES_JS_VERSION), cache / f"pmtiles-{PMTILES_JS_VERSION}.tgz")
        with tarfile.open(tgz) as t:
            js.write_bytes(t.extractfile("package/dist/pmtiles.js").read())
        (maps / "pmtiles.LICENSE.txt").write_text(
            "pmtiles.js from https://github.com/protomaps/PMTiles - BSD-3-Clause licence:\n"
            "https://github.com/protomaps/PMTiles/blob/main/LICENSE\n")
    style = json.loads(STYLE_TEMPLATE.read_text(encoding="utf-8"))
    # kitmap:// = "this server" (MapLibre needs absolute addresses; see patch_webclient)
    style["glyphs"] = "kitmap://maps/fonts/{fontstack}/{range}.pbf"
    style["sprite"] = "kitmap://maps/sprites/light"
    style["sources"]["protomaps"]["url"] = "pmtiles:///maps/area.pmtiles"
    (maps / "style.json").write_text(json.dumps(style), encoding="utf-8")


# ---- the web client ------------------------------------------------------------------------
ATTRIB_JS = r"""
(function(){function add(){if(document.getElementById('mk-osm'))return;var d=document.createElement('div');
d.id='mk-osm';d.textContent='Map © OpenStreetMap contributors, Protomaps';
d.style.cssText='position:fixed;right:6px;bottom:4px;z-index:5;font:11px sans-serif;color:#333;background:rgba(255,255,255,.75);padding:1px 6px;border-radius:3px;pointer-events:none';
document.body.appendChild(d);}
function upd(){var m=document.querySelector('.maplibregl-map');var d=document.getElementById('mk-osm');
var a=[].some.call(document.querySelectorAll('.maplibregl-ctrl-attrib'),function(e){return /OpenStreetMap/.test(e.textContent)});
var need=m&&!a;if(need&&!d)add();if(!need&&d)d.remove();}
setInterval(upd,1000);})();
"""


def patch_webclient(web: Path):
    """Point the web client at the offline map. Returns a list of what was changed.
    Safe to run again: files already patched are left alone."""
    done = []
    idx = next((p for p in web.glob("index-*.js") if not p.name.startswith("._")), None)
    html = web / "index.html"
    if not idx or not html.exists():
        raise RuntimeError("This web client version isn't laid out as expected; the offline map can't be added.")

    s = idx.read_text(encoding="utf-8")
    if "/maps/style.json" not in s:
        if ONLINE_STYLE in s:
            s = s.replace(ONLINE_STYLE, "/maps/style.json")
        else:
            s, n = re.subn(r"mapStyle:`https?://[^`]+`", "mapStyle:`/maps/style.json`", s)
            if n == 0:
                raise RuntimeError("Couldn't find the web client's map style address.")
        idx.write_text(s, encoding="utf-8")
        done.append("map style address")

    s = html.read_text(encoding="utf-8")
    if "/maps/pmtiles.js" not in s:
        tag = '<script src="/maps/pmtiles.js"></script><script src="/maps/credit.js"></script>'
        s = s.replace("<script type=\"module\"", tag + "<script type=\"module\"", 1)
        html.write_text(s, encoding="utf-8")
        done.append("index.html")
    (web / "maps").mkdir(exist_ok=True)
    (web / "maps" / "credit.js").write_text(ATTRIB_JS, encoding="utf-8")
    return done


def disable_service_worker(web: Path):
    """The web client's offline cache (service worker) would keep serving files cached on an
    earlier visit, including the unfixed map. The drive already serves everything offline,
    so we switch the cache off and remove any old one."""
    sw = web / "registerSW.js"
    if sw.exists() and MARK not in sw.read_text(encoding="utf-8"):
        sw.write_text(f"{MARK}if('serviceWorker' in navigator){{navigator.serviceWorker.getRegistrations()"
                      f".then(function(r){{r.forEach(function(x){{x.unregister()}})}})}}\n", encoding="utf-8")


CHANGES_NOTE = """CHANGES MADE BY THE EMERGENCY KIT FOR MESHTASTIC
================================================
This folder is the Meshtastic web client (https://github.com/meshtastic/web, GPL-3.0),
release as downloaded, with these changes made on this drive by the kit's updater
(_system/maintenance/offline_map.py):

1. Map fix. The release bundles MapLibre {ver}, which needs worker files the release
   doesn't include, so its map couldn't draw. maplibre-gl.mjs, maplibre-gl-shared.mjs and
   maplibre-gl-worker.mjs are the official MapLibre {ver} files (BSD-3-Clause, see
   maplibre-gl.LICENSE.txt), and the bundled map file now loads them instead.
2. The web client's offline cache (service worker) is switched off; the drive serves
   everything already.
3. Only with an offline map (folder maps/): the map style address points at
   maps/style.json, and index.html loads maps/pmtiles.js and maps/credit.js (the
   OpenStreetMap credit shown on the map).
"""


MAPLIBRE_TGZ = "https://registry.npmjs.org/maplibre-gl/-/maplibre-gl-{v}.tgz"
MAPLIBRE_FILES = ["maplibre-gl.mjs", "maplibre-gl-shared.mjs", "maplibre-gl-worker.mjs"]
CHUNK = r"""{mark}
// Replaced by the Emergency Kit for Meshtastic: loads the official MapLibre {ver} files (main +
// worker, which the web client release leaves out) and lets the map read files on this drive.
import * as ml from "./maplibre-gl.mjs";
export * from "./maplibre-gl.mjs";
export default ml;
try {{
  if (globalThis.pmtiles) ml.addProtocol("pmtiles", new globalThis.pmtiles.Protocol().tile);
  ml.addProtocol("kitmap", async function (p, ac) {{   // kitmap://path = this server
    var u = location.origin + "/" + p.url.replace(/^kitmap:\/\//, "");
    var r = await fetch(u, {{ signal: ac.signal }});
    if (!r.ok) throw new Error(r.status + " " + u);
    return {{ data: p.type === "json" ? await r.json() : await r.arrayBuffer() }};
  }});
}} catch (e) {{ console.warn("offline map", e); }}
"""


def fix_maplibre(web: Path, cache: Path, log=print):
    """Make the web client's map work (see module docstring). Returns the MapLibre version
    when it changed something, else None (already done, or not needed)."""
    chunk = next((p for p in web.glob("maplibre-gl-*.js") if not p.name.startswith("._")), None)
    if not chunk:
        return None
    text = chunk.read_text(encoding="utf-8")
    if MARK in text:
        return None                        # already done
    if "maplibre-gl-worker.mjs" not in text:
        return None                        # bundles its own worker: nothing to fix
    vers = re.findall(r"[`\"'](\d+\.\d+\.\d+)[`\"']", text)
    ver = next((v for v in vers if v.split(".")[0] == "6"), None) or next(iter(vers), None)
    if not ver:
        raise RuntimeError("Couldn't tell which MapLibre version the web client uses.")
    tgz = _download(MAPLIBRE_TGZ.format(v=ver), cache / f"maplibre-gl-{ver}.tgz")
    with tarfile.open(tgz) as t:
        for f in MAPLIBRE_FILES:
            (web / f).write_bytes(t.extractfile(f"package/dist/{f}").read())
        (web / "maplibre-gl.LICENSE.txt").write_bytes(t.extractfile("package/LICENSE.txt").read())
    chunk.write_text(CHUNK.format(mark=MARK, ver=ver), encoding="utf-8")
    disable_service_worker(web)
    (web / "CHANGES-BY-THE-KIT.txt").write_text(CHANGES_NOTE.format(ver=ver), encoding="utf-8")
    return ver


def build_area(maps: Path, cache: Path, area: dict, log=print):
    """Download / refresh the area described by {"name","bbox","maxzoom"}. Returns build key."""
    tool = get_tool(cache)
    maps.mkdir(parents=True, exist_ok=True)
    key = extract(tool, area["bbox"], maps / "area.pmtiles", area.get("maxzoom", 15))
    install_assets(maps, cache)
    (maps / "area.json").write_text(json.dumps({**area, "build": key, "made": time.strftime("%Y-%m-%d")}, indent=2))
    return key
