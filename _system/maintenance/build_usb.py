#!/usr/bin/env python3
"""
Emergency Kit for Meshtastic - builder / updater.

Everyday use: choose "U  Update this drive" in the START-HERE window. That runs
this script with the copy of Python that lives on the drive.

    python3 build_usb.py              # fetch / update everything
    python3 build_usb.py --check      # only show what's out of date
    python3 build_usb.py --only firmware,webclient
    python3 build_usb.py --list       # show the component names

Needs: python3 (3.8+) and curl (built into Windows 10+, macOS and Linux).
git + node are only needed to rebuild the web flasher; without them the
current flasher is kept (it still picks up new firmware).
"""
import argparse, gzip, hashlib, io, json, lzma, os, re, shutil, subprocess, sys
import tarfile, tempfile, time, urllib.request, zipfile
from pathlib import Path

if os.name == "nt":
    os.system("")   # enables colour codes in the Windows console

ROOT = Path(__file__).resolve().parents[2]          # the USB root folder
SYS = ROOT / "_system"
# Temporary downloads live on the drive (not the host computer) and are removed afterwards.
CACHE = Path(os.environ.get("MESH_USB_CACHE", SYS / ".update-cache"))
KEEP_CACHE = "MESH_USB_CACHE" in os.environ

# ---- What to mirror ---------------------------------------------------------
FIRMWARE_CHANNELS = {"stable": 1, "alpha": 1}   # how many releases of each channel
SETTINGS_FILE = SYS / "settings.json"            # which parts this drive keeps (written by setup)

# Every part of the drive: (label, approx MB, in "essentials"?)
PARTS = {
    "python":        ("Updater runtime (lets the drive update itself)", 140, True),
    "miniserve":     ("Local web server", 60, True),
    "webclient":     ("Meshtastic web app", 8, True),
    "firmware":      ("Radio firmware for every board (stable)", 600, True),
    "flasher_models":("Device pictures for the flasher", 100, True),
    "android":       ("Android app (.apk)", 65, True),
    "chromium":      ("Chromium browser for Mac & Linux", 610, True),
    "drivers":       ("Windows USB drivers (if they can be downloaded)", 1, True),
    "desktop":       ("Desktop apps for Windows, Mac, Linux", 840, False),
    "esptool":       ("esptool command-line flasher (backup)", 330, False),
    "pi_imager":     ("Raspberry Pi SD card writer", 70, False),
    "pi_mpwrd":      ("Raspberry Pi image A: mPWRD-OS", 470, False),
    "pi_raspios":    ("Raspberry Pi image B: Raspberry Pi OS + Meshtastic", 630, False),
    "alpha":         ("Also keep the newest alpha (experimental) firmware", 760, False),
    "offline_map":   ("Offline map of an area you choose, for the web app", 150, False),
    "flasher":       ("Rebuild the web flasher (only with developer tools)", 0, False),
}
PROFILES = {
    "essentials": [k for k, v in PARTS.items() if v[2]],     # the standard kit (~1.5 GB)
}
EXTRAS = [k for k, v in PARTS.items() if not v[2] and k != "flasher"]   # opt-in parts

def load_settings():
    try:
        st = json.loads(SETTINGS_FILE.read_text())
    except Exception:
        st = {"parts": PROFILES["essentials"] + EXTRAS}    # drives made before settings existed
    parts = [p for p in st.get("parts", []) if p in PARTS]
    FIRMWARE_CHANNELS.clear()
    FIRMWARE_CHANNELS["stable"] = 1
    if "alpha" in parts:
        FIRMWARE_CHANNELS["alpha"] = 1
    return parts

def save_settings(parts):
    try:
        st = json.loads(SETTINGS_FILE.read_text())
    except Exception:
        st = {}
    st["parts"] = parts
    SETTINGS_FILE.write_text(json.dumps(st, indent=2))

def map_area():
    """The offline-map area chosen in setup: {"name","bbox","maxzoom"} or None."""
    try:
        a = json.loads(SETTINGS_FILE.read_text()).get("map")
        return a if a and len(a.get("bbox", [])) == 4 else None
    except Exception:
        return None
FIRMWARE_PLATFORMS = ["esp32", "esp32s3", "esp32c3", "esp32c6", "nrf52840",
                      "rp2040", "rp2350", "stm32"]
WEB_FLASHER_REPO = "https://github.com/meshtastic/web-flasher.git"

UA = "meshtastic-offline-usb-builder"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
if not TOKEN and shutil.which("gh"):
    try:
        TOKEN = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                               timeout=10).stdout.strip() or None
    except Exception:
        TOKEN = None

manifest = {}   # component -> details, written to _system/VERSIONS.json


# ---- helpers ----------------------------------------------------------------
def log(msg):
    print(f"\033[1;36m==>\033[0m {msg}", flush=True)

def warn(msg):
    print(f"\033[1;33m!!  {msg}\033[0m", flush=True)

CURL = shutil.which("curl")

def _curl(accept=None, gh=False):
    """curl command + config text (headers go via stdin so tokens never show in ps)."""
    cfg = f'user-agent = "{UA}"\n'
    if accept:
        cfg += f'header = "Accept: {accept}"\n'
    if gh and TOKEN:
        cfg += f'header = "Authorization: Bearer {TOKEN}"\n'
    return [CURL, "-fsSL", "--retry", "3", "--connect-timeout", "20", "-K", "-"], cfg

def http(url, accept=None, gh=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    if accept:
        req.add_header("Accept", accept)
    if gh and TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    return urllib.request.urlopen(req, timeout=120)

def get_bytes(url, accept=None, gh=False):
    if CURL:
        cmd, cfg = _curl(accept, gh)
        r = subprocess.run(cmd + [url], input=cfg.encode(), capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(f"couldn't download {url} ({r.stderr.decode(errors='replace').strip()[:160]})")
        return r.stdout
    with http(url, accept, gh) as r:
        return r.read()

def get_json(url, gh=False):
    return json.loads(get_bytes(url, "application/json", gh))

def gh_releases(repo, n=30):
    return get_json(f"https://api.github.com/repos/{repo}/releases?per_page={n}", gh=True)

def gh_latest(repo):
    return get_json(f"https://api.github.com/repos/{repo}/releases/latest", gh=True)

def asset(release, pattern):
    rx = re.compile(pattern)
    for a in release["assets"]:
        if rx.search(a["name"]):
            return a
    raise SystemExit(f"No asset matching {pattern!r} in {release['tag_name']}")

def download(url, dest: Path, size=None):
    """Download into dest (skips if already complete). Returns dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (size is None or dest.stat().st_size == size):
        return dest
    tmp = dest.with_name(dest.name + ".part")
    print(f"    downloading {dest.name} ...", flush=True)
    t0 = time.time()
    if CURL:
        cmd, cfg = _curl()
        cmd[1] = "-fSL" + ("#" if sys.stdout.isatty() else "s")   # progress bar when interactive
        r = subprocess.run(cmd + ["-C", "-", "-o", str(tmp), url], input=cfg.encode())
        if r.returncode not in (0, 33):   # 33 = server can't resume; fine if file complete
            raise RuntimeError(f"couldn't download {url}")
    else:
        with http(url) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
    if size is not None and tmp.stat().st_size != size:
        tmp.unlink()
        raise SystemExit(f"Size mismatch downloading {url}")
    tmp.replace(dest)
    print(f"      done ({dest.stat().st_size>>20} MB, {time.time()-t0:.0f}s)")
    return dest

def fetch_asset(a, dest: Path):
    return download(a["browser_download_url"], dest, a["size"])

def junk(p: Path) -> bool:
    """macOS writes hidden '._name' helper files on exFAT/FAT drives. They come and go
    with their partner file, so never process them; remove_appledouble() clears them."""
    return p.name.startswith("._")

def remove_appledouble(top: Path):
    for dirpath, dirnames, filenames in os.walk(top):
        for f in filenames:
            if f.startswith("._"):
                try:
                    os.unlink(os.path.join(dirpath, f))
                except OSError:
                    pass

def clean_dir(d: Path, keep=()):
    d.mkdir(parents=True, exist_ok=True)
    for p in list(d.iterdir()):
        if p.name in keep or not (p.exists() or p.is_symlink()):
            continue
        if junk(p):
            p.unlink(missing_ok=True)
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)

def remove_stale(folder: Path, keep_names):
    """Delete files in folder that are not in keep_names (old versions)."""
    if not folder.exists():
        return
    for p in folder.iterdir():
        if junk(p):
            continue
        if p.is_file() and p.name not in keep_names and not p.name.startswith("_") \
                and not p.name.lower().startswith("read") and p.suffix not in (".txt", ".md", ".html"):
            print(f"    removing old {p.name}")
            p.unlink()


# ---- components ---------------------------------------------------------------
def c_miniserve():
    """Tiny web server that runs the apps from the USB (one file per OS)."""
    log("Local web server (miniserve)")
    rel = gh_latest("svenstaro/miniserve")
    v = rel["tag_name"].lstrip("v")
    targets = {
        "miniserve-windows-x64.exe": rf"miniserve-{v}-x86_64-pc-windows-msvc\.exe$",
        "miniserve-mac-arm64": rf"miniserve-{v}-aarch64-apple-darwin$",
        "miniserve-mac-x64": rf"miniserve-{v}-x86_64-apple-darwin$",
        "miniserve-linux-x64": rf"miniserve-{v}-x86_64-unknown-linux-musl$",
        "miniserve-linux-arm64": rf"miniserve-{v}-aarch64-unknown-linux-musl$",
        "miniserve-linux-armv7": rf"miniserve-{v}-armv7-unknown-linux-musleabihf$",
    }
    out = SYS / "bin"
    out.mkdir(parents=True, exist_ok=True)
    if manifest.get("miniserve") == v and all((out / n).exists() for n in targets):
        print(f"    {v} already on the drive")
        return
    for name, pat in targets.items():
        a = asset(rel, pat)
        c = fetch_asset(a, CACHE / "miniserve" / a["name"])
        shutil.copy2(c, out / name)
        (out / name).chmod(0o755)
    manifest["miniserve"] = v


def c_firmware():
    """Firmware files laid out exactly like release.meshtastic.org, for the flasher."""
    log("Device firmware")
    api = get_json("https://api.meshtastic.org/github/firmware/list")
    chosen = {}
    for ch, n in FIRMWARE_CHANNELS.items():
        chosen[ch] = [r for r in api["releases"].get(ch, [])
                      if "revoked" not in r.get("title", "").lower()][:n]
    rel_root = SYS / "flasher" / "release"
    rel_root.mkdir(parents=True, exist_ok=True)
    keep = set()
    gh_rels = {r["tag_name"]: r for r in gh_releases("meshtastic/firmware", 40)}
    for ch, rels in chosen.items():
        for r in rels:
            tag = r["id"]
            ver = tag.lstrip("v")
            keep.add(ver)
            ghr = gh_rels.get(tag) or get_json(
                f"https://api.github.com/repos/meshtastic/firmware/releases/tags/{tag}", gh=True)
            dest = rel_root / ver
            stamp = dest / ".complete"
            if stamp.exists():
                print(f"    {ver} ({ch}) already mirrored")
                continue
            print(f"    mirroring {ver} ({ch})")
            dest.mkdir(parents=True, exist_ok=True)
            for plat in FIRMWARE_PLATFORMS:
                try:
                    a = asset(ghr, rf"^firmware-{plat}-{re.escape(ver)}\.zip$")
                except SystemExit:
                    warn(f"no {plat} zip for {ver}")
                    continue
                z = fetch_asset(a, CACHE / "firmware" / a["name"])
                with zipfile.ZipFile(z) as zf:
                    for m in zf.infolist():
                        name = os.path.basename(m.filename)
                        if not name or m.is_dir() or name.endswith(".elf"):
                            continue
                        with zf.open(m) as src, open(dest / name, "wb") as dst:
                            shutil.copyfileobj(src, dst)
            mj = asset(ghr, rf"^firmware-{re.escape(ver)}\.json$")
            fetch_asset(mj, dest / mj["name"])
            (dest / "release_notes.md").write_text(r.get("release_notes") or ghr.get("body") or "",
                                                   encoding="utf-8")
            stamp.write_text(time.strftime("%Y-%m-%d"))
    for p in rel_root.iterdir():
        if p.is_dir() and p.name not in keep:
            print(f"    removing old firmware {p.name}")
            shutil.rmtree(p)

    # Offline copies of the API documents the flasher asks for.
    apid = SYS / "flasher" / "api"
    (apid / "github" / "firmware").mkdir(parents=True, exist_ok=True)
    (apid / "resource").mkdir(parents=True, exist_ok=True)
    offline_list = {"releases": {}, "pullRequests": []}
    for ch, rels in chosen.items():
        offline_list["releases"][ch] = [
            {**r, "zip_url": f"/release/{r['id'].lstrip('v')}/firmware-{r['id'].lstrip('v')}.json"}
            for r in rels]
    (apid / "github" / "firmware" / "list.json").write_text(json.dumps(offline_list, indent=1))
    hw = get_bytes("https://api.meshtastic.org/resource/deviceHardware")
    json.loads(hw)
    (apid / "resource" / "deviceHardware.json").write_bytes(hw)
    (apid / "resource" / "eventFirmware.json").write_text(
        json.dumps({"version": 2, "source": "offline", "editions": []}))
    manifest["firmware"] = {ch: [r["id"] for r in rels] for ch, rels in chosen.items()}
    try:                                      # pages that say which file is for which radio
        import firmware_index
        firmware_index.write_all(SYS / "flasher")
    except Exception as e:
        warn(f"couldn't write the firmware index pages ({e}); the files are all there")


def c_webclient():
    """Meshtastic web client (client.meshtastic.org) as plain static files."""
    log("Web client")
    rel = gh_latest("meshtastic/web")
    if manifest.get("webclient") == rel["tag_name"] and (SYS / "webclient" / "index.html").exists():
        print(f"    {rel['tag_name']} already on the drive")
        webclient_map_fixes(SYS / "webclient")     # drives made before these fixes
        return
    a = asset(rel, r"^build\.tar$")
    tarp = fetch_asset(a, CACHE / "web" / f"build-{rel['tag_name']}.tar")
    out = SYS / "webclient"
    clean_dir(out, keep=("maps",))           # the offline map stays
    with tarfile.open(tarp) as t:
        t.extractall(out, filter="data") if sys.version_info >= (3, 12) else t.extractall(out)
    remove_appledouble(out)
    for gz in list(out.rglob("*.gz")):        # shipped gzip-only (for devices); unpack
        if junk(gz) or not gz.exists():
            continue
        with gzip.open(gz) as src, open(gz.with_suffix(""), "wb") as dst:
            shutil.copyfileobj(src, dst)
        gz.unlink()
    manifest["webclient"] = rel["tag_name"]
    webclient_map_fixes(out)


def webclient_map_fixes(web: Path):
    """Make the web app's map work (its release leaves out MapLibre's worker files), and
    point it at the offline map when this drive has one. See offline_map.py."""
    import offline_map as M
    try:
        v = M.fix_maplibre(web, CACHE)
        if v:
            print(f"    map fix: official MapLibre {v} files added")
        if (web / "maps" / "area.pmtiles").exists():
            changed = M.patch_webclient(web)
            if changed:
                print("    offline map connected to the web app")
    except Exception as e:
        warn(f"couldn't fix the web app's map ({e}). Everything else in the web app works.")


def c_offline_map():
    """Offline map of the area chosen in setup (OpenStreetMap data via Protomaps)."""
    import offline_map as M
    log("Offline map")
    area = map_area()
    if not area:
        print("    no area chosen (run setup again to pick one)")
        return
    maps = SYS / "webclient" / "maps"
    have = {}
    try:
        have = json.loads((maps / "area.json").read_text())
    except Exception:
        pass
    same = have.get("bbox") == area["bbox"] and have.get("maxzoom", 15) == area.get("maxzoom", 15)
    fresh = same and (maps / "area.pmtiles").exists() and _days_old(have.get("build")) < MAP_REFRESH_DAYS
    if fresh:
        print(f"    {area.get('name', 'area')} (map of {have.get('build', '?')[:8]}) already on the drive")
    else:
        print(f"    {area.get('name', 'area')}: downloading the map ...")
        key = M.build_area(maps, CACHE, area)
        print(f"    map of {key[:8]} saved ({(maps / 'area.pmtiles').stat().st_size >> 20} MB)")
        have = {"build": key}
    if (SYS / "webclient" / "index.html").exists():
        webclient_map_fixes(SYS / "webclient")
    manifest["offline_map"] = {"name": area.get("name"), "build": have.get("build")}


MAP_REFRESH_DAYS = 90       # map data changes slowly; refresh the area every few months

def _days_old(build_key):
    try:
        t = time.mktime(time.strptime((build_key or "")[:8], "%Y%m%d"))
        return (time.time() - t) / 86400
    except ValueError:
        return 10 ** 6


FLASHER_PATCHES = [
    # (file, regex, replacement)  - make every network call same-origin & local
    ("stores/store.ts",
     r"return `\$\{API_ORIGIN\}/\$\{relativeUrl\.replace\('api/', ''\)\}`",
     "return `/api/${relativeUrl.replace('api/', '')}.json`"),
    ("utils/firmwareUrl.ts",
     r"export const RELEASE_BASE = '[^']+'", "export const RELEASE_BASE = '/release'"),
    ("utils/firmwareUrl.ts",
     r"export const NIGHTLY_BASE = '[^']+'", "export const NIGHTLY_BASE = '/nightly'"),
]
FLASHER_DELETE = ["plugins/analytics.clients.ts", "plugins/datadog-rum.client.ts"]

def scrub_paths(folder: Path, local_path: str, neutral: str = "/web-flasher"):
    n = 0
    for f in folder.rglob("*"):
        if junk(f) or not f.is_file() or f.suffix not in (".html", ".js", ".json", ".css", ".mjs", ".txt"):
            continue
        try:
            t = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if local_path in t:
            f.write_text(t.replace(local_path, neutral), encoding="utf-8")
            n += 1
    if n:
        print(f"    removed this computer's folder path from {n} built file(s)")


def write_flasher_notice(src: Path, full_commit: str):
    """GPL-3.0: ship the licence, and say where the source is and what was changed."""
    out = SYS / "flasher"
    lic = src / "LICENSE"
    if lic.exists():
        shutil.copy2(lic, out / "LICENSE.txt")
    lines = [
        "MESHTASTIC WEB FLASHER - SOURCE AND CHANGES",
        "============================================",
        "",
        "This folder holds a build of the Meshtastic Web Flasher, licensed under the",
        "GNU General Public License v3.0 (full text: LICENSE.txt in this folder).",
        "",
        "Original source:  https://github.com/meshtastic/web-flasher",
        f"Version used:     commit {full_commit}",
        f"                  https://github.com/meshtastic/web-flasher/tree/{full_commit}",
        "",
        "Changes made for offline use (nothing else was altered):",
        "  1. stores/store.ts: API requests read local files under /api/ instead of",
        "     api.meshtastic.org.",
        "  2. utils/firmwareUrl.ts: firmware is read from /release/ on this drive",
        "     instead of release.meshtastic.org (and /nightly instead of nightly.meshtastic.org).",
        "  3. Removed plugins/analytics.clients.ts and plugins/datadog-rum.client.ts",
        "     (usage tracking, which can't work offline).",
        "",
        "The exact changes are applied by _system/maintenance/build_usb.py",
        "(see FLASHER_PATCHES and FLASHER_DELETE), which rebuilds this folder from the",
        "original source when run on a computer with git and Node.js.",
    ]
    (out / "SOURCE-AND-CHANGES.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def c_flasher():
    """Build the official web flasher, patched to use the firmware on this drive."""
    log("Web flasher (build from source)")
    for tool in ("git", "node", "npx"):
        if not shutil.which(tool):
            print("    keeping the current flasher (rebuilding it needs developer tools;"
                  " new firmware still shows up in it)")
            return
    src = CACHE / "web-flasher"
    if (src / ".git").exists():
        subprocess.run(["git", "-C", src, "fetch", "--depth", "1", "origin"], check=True)
        subprocess.run(["git", "-C", src, "reset", "--hard", "FETCH_HEAD"], check=True)
        subprocess.run(["git", "-C", src, "clean", "-fdq", "-e", "node_modules"], check=True)
    else:
        subprocess.run(["git", "clone", "--depth", "1", WEB_FLASHER_REPO, src], check=True)
    full = subprocess.run(["git", "-C", src, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    commit = full[:7]
    for f, rx, rep in FLASHER_PATCHES:
        p = src / f
        txt = p.read_text()
        new, n = re.subn(rx, rep, txt)
        if n == 0:
            raise SystemExit(f"Flasher patch no longer applies: {f} ({rx}). "
                             "The upstream code changed - update FLASHER_PATCHES.")
        p.write_text(new)
    for f in FLASHER_DELETE:
        (src / f).unlink(missing_ok=True)
    env = {**os.environ, "NUXT_TELEMETRY_DISABLED": "1", "CI": "1"}
    pnpm = ["npx", "-y", "pnpm@9"]
    subprocess.run(pnpm + ["install", "--frozen-lockfile"], cwd=src, env=env, check=True)
    subprocess.run(pnpm + ["run", "generate"], cwd=src, env=env, check=True)
    built = src / ".output" / "public"
    if not (built / "index.html").exists():
        raise SystemExit("Flasher build produced no index.html")
    out = SYS / "flasher"
    clean_dir(out, keep=("release", "api"))
    for item in built.iterdir():
        if item.name in ("release", "api"):
            continue
        (shutil.copytree if item.is_dir() else shutil.copy2)(item, out / item.name)
    # The build records the source folder's absolute path (which includes the builder's
    # user name) in a few files. Replace it with a neutral path before shipping.
    scrub_paths(out, str(src))
    manifest["flasher"] = f"web-flasher@{commit}"
    manifest["flasher_commit"] = full
    write_flasher_notice(src, full)


def c_flasher_models():
    """3D device pictures the flasher shows (kept out of the setup kit to keep it small)."""
    log("Flasher device pictures")
    sha = manifest.get("flasher_commit")
    if not sha:
        print("    no flasher build recorded - skipping")
        return
    tree = get_json(f"https://api.github.com/repos/meshtastic/web-flasher/git/trees/{sha}?recursive=1", gh=True)
    out = SYS / "flasher"
    n = 0
    for t in tree["tree"]:
        if t["type"] != "blob" or not t["path"].startswith("public/models/"):
            continue
        dest = out / t["path"][len("public/"):]
        if dest.exists() and dest.stat().st_size == t["size"]:
            continue
        download(f"https://raw.githubusercontent.com/meshtastic/web-flasher/{sha}/{t['path']}", dest, t["size"])
        n += 1
    print(f"    {n} new picture file(s)")


def c_desktop():
    """Official Meshtastic Desktop apps (Windows / Mac / Linux)."""
    log("Desktop apps")
    rel = gh_latest("meshtastic/Meshtastic-Android")
    picks = {
        "1-Desktop-App/Windows": [r"^Meshtastic\.Desktop-[\d.]+\.msi$"],
        "1-Desktop-App/Mac": [r"^Meshtastic\.Desktop-[\d.]+\.dmg$"],
        "1-Desktop-App/Linux": [r"^Meshtastic_Desktop-[\d.]+-x86_64\.AppImage$",
                                r"^Meshtastic_Desktop-[\d.]+-aarch64\.AppImage$",
                                r"^meshtastic-desktop_[\d.]+_amd64\.deb$"],
    }
    for folder, pats in picks.items():
        names = []
        for pat in pats:
            a = asset(rel, pat)
            fetch_asset(a, ROOT / folder / a["name"])
            names.append(a["name"])
        remove_stale(ROOT / folder, names)
    for f in (ROOT / "1-Desktop-App/Linux").glob("*.AppImage"):
        f.chmod(0o755)
    manifest["desktop"] = rel["tag_name"]


def c_android():
    """Android app (APK) + adb so it can be installed over a USB cable."""
    log("Android app + adb")
    rel = gh_latest("meshtastic/Meshtastic-Android")
    a = asset(rel, r"^androidApp-fdroid-universal-release\.apk$")
    ver = rel["tag_name"]
    name = f"Meshtastic-{ver}.apk"
    folder = ROOT / "2-Android-Phone"
    fetch_asset(a, folder / name)
    remove_stale(folder, [name])
    if manifest.get("android") == ver and all((SYS / "bin" / f"adb-{o}").is_dir()
                                              for o in ("windows", "mac", "linux")):
        print(f"    {ver} already on the drive")
        return
    for osname, plat in (("windows", "windows"), ("mac", "darwin"), ("linux", "linux")):
        z = download(f"https://dl.google.com/android/repository/platform-tools-latest-{plat}.zip",
                     CACHE / "adb" / f"platform-tools-{plat}.zip")
        out = SYS / "bin" / f"adb-{osname}"
        clean_dir(out)
        with zipfile.ZipFile(z) as zf:
            for m in zf.infolist():
                base = os.path.basename(m.filename)
                # only what's needed to run adb
                if base in ("adb", "adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "NOTICE.txt"):
                    with zf.open(m) as s, open(out / base, "wb") as d:
                        shutil.copyfileobj(s, d)
                    (out / base).chmod(0o755)
    manifest["android"] = ver


def c_esptool():
    """esptool: command-line backup flasher for ESP32 boards."""
    log("esptool (backup flasher)")
    rel = gh_latest("espressif/esptool")
    v = rel["tag_name"]
    targets = {"windows": r"windows-amd64\.zip$", "mac-arm64": r"macos-arm64\.tar\.gz$",
               "mac-x64": r"macos-amd64\.tar\.gz$", "linux-x64": r"linux-amd64\.tar\.gz$",
               "linux-arm64": r"linux-aarch64\.tar\.gz$"}
    base = SYS / "tools" / "esptool"
    for name, pat in targets.items():
        a = asset(rel, pat)
        arc = fetch_asset(a, CACHE / "esptool" / a["name"])
        out = base / name
        clean_dir(out)
        with tempfile.TemporaryDirectory() as td:
            if arc.suffix == ".zip":
                zipfile.ZipFile(arc).extractall(td)
            else:
                with tarfile.open(arc) as t:
                    t.extractall(td, filter="data") if sys.version_info >= (3, 12) else t.extractall(td)
            # flatten the single top folder
            tops = list(Path(td).iterdir())
            src = tops[0] if len(tops) == 1 and tops[0].is_dir() else Path(td)
            for item in src.iterdir():
                shutil.move(str(item), out / item.name)
        for f in out.rglob("*"):
            if not junk(f) and f.is_file() and not f.suffix:
                f.chmod(0o755)
    manifest["esptool"] = v


def c_pi_imager():
    log("Raspberry Pi Imager installers")
    rel = gh_latest("raspberrypi/rpi-imager")
    v = rel["tag_name"]
    picks = {"Windows": r"^imager-v[\d.]+\.exe$", "Mac": r"^rpi-imager-v[\d.]+\.dmg$",
             "Linux": r"^Raspberry_Pi_Imager-v[\d.]+-desktop-x86_64\.AppImage$"}
    for osn, pat in picks.items():
        a = asset(rel, pat)
        d = ROOT / "3-Raspberry-Pi" / "SD-Card-Writer" / osn
        fetch_asset(a, d / a["name"])
        remove_stale(d, [a["name"]])
        if a["name"].endswith(".AppImage"):
            (d / a["name"]).chmod(0o755)
    manifest["rpi_imager"] = v


def c_pi_mpwrd():
    log("Raspberry Pi option A: mPWRD-OS (Meshtastic ready-made image)")
    rel = gh_latest("mPWRD-OS/mPWRD-OS")
    a = asset(rel, r"Rpi4b.*\.img\.xz$")
    d = ROOT / "3-Raspberry-Pi" / "Option-A-Ready-Made-Meshtastic-Image"
    fetch_asset(a, d / a["name"])
    remove_stale(d, [a["name"]])
    manifest["mpwrd_os"] = {"release": rel["tag_name"], "image": a["name"]}


# ---- Raspberry Pi OS + meshtasticd (offline .deb bundle) ---------------------
PI_SUITE = "trixie"
PI_OBS = "https://download.opensuse.org/repositories/network:/Meshtastic:/beta/Debian_13/"
PI_REPOS = [  # highest priority first
    ("raspi", "https://archive.raspberrypi.com/debian/", f"dists/{PI_SUITE}/main/binary-arm64/Packages.gz"),
    ("debsec", "https://security.debian.org/debian-security/", f"dists/{PI_SUITE}-security/main/binary-arm64/Packages.xz"),
    ("debupd", "https://deb.debian.org/debian/", f"dists/{PI_SUITE}-updates/main/binary-arm64/Packages.xz"),
    ("debian", "https://deb.debian.org/debian/", f"dists/{PI_SUITE}/main/binary-arm64/Packages.xz"),
]

def _parse_packages(text, base):
    pkgs = []
    for block in text.split("\n\n"):
        d = {}
        key = None
        for line in block.splitlines():
            if line.startswith((" ", "\t")) and key:
                d[key] += "\n" + line
            elif ":" in line:
                key, _, val = line.partition(":")
                d[key] = val.strip()
        if "Package" in d:
            d["_base"] = base
            pkgs.append(d)
    return pkgs

def c_pi_raspios():
    log("Raspberry Pi option B: Raspberry Pi OS Lite + meshtasticd (offline packages)")
    # 1) the OS image (current Raspberry Pi OS Lite 64-bit)
    osl = get_json("https://downloads.raspberrypi.com/os_list_imagingutility_v4.json")
    found = []
    def walk(items):
        for i in items:
            if "subitems" in i:
                walk(i["subitems"])
            elif i.get("name") == "Raspberry Pi OS Lite (64-bit)":
                found.append(i)
    walk(osl["os_list"])
    img = found[0]
    if PI_SUITE not in img["url"]:
        warn(f"Raspberry Pi OS Lite is no longer {PI_SUITE}! Update PI_SUITE / PI_OBS in this script.")
    d = ROOT / "3-Raspberry-Pi" / "Option-B-Raspberry-Pi-OS-plus-Meshtastic"
    name = os.path.basename(img["url"])
    download(img["url"], d / name, img.get("image_download_size"))
    remove_stale(d, [name])

    # 2) meshtasticd + every library it needs, resolved like apt would
    index = {}      # name -> pkg (first repo wins = highest priority)
    provides = {}
    obs = _parse_packages(get_bytes(PI_OBS + "Packages").decode(), PI_OBS)
    for p in obs:
        if p.get("Architecture") in ("arm64", "all"):
            index.setdefault(p["Package"], p)
    for label, base, path in PI_REPOS:
        try:
            data = get_bytes(base + path)
            data = lzma.decompress(data) if path.endswith(".xz") else gzip.decompress(data) if path.endswith(".gz") else data
            raw = data.decode("utf-8", "replace")
        except Exception as e:
            warn(f"could not read {label} package list: {e}")
            continue
        for p in _parse_packages(raw, base):
            index.setdefault(p["Package"], p)
    for p in index.values():
        for prov in p.get("Provides", "").split(","):
            prov = prov.strip().split(" ")[0]
            if prov:
                provides.setdefault(prov, p["Package"])

    def base_system(p):  # already on every Raspberry Pi OS Lite image
        return p.get("Essential") == "yes" or p.get("Priority") in ("required", "important")

    wanted, queue = [], ["meshtasticd"]
    seen = set()
    while queue:
        n = queue.pop(0)
        if n in seen:
            continue
        seen.add(n)
        p = index.get(n) or index.get(provides.get(n, ""))
        if not p:
            warn(f"package not found: {n}")
            continue
        if base_system(p) and n != "meshtasticd":
            continue
        wanted.append(p)
        for field in ("Pre-Depends", "Depends"):
            for group in p.get(field, "").split(","):
                group = group.strip()
                if not group:
                    continue
                alts = [a.strip().split(" ")[0].split(":")[0] for a in group.split("|")]
                pick = next((a for a in alts if a in index or a in provides), alts[0])
                queue.append(pick)
    debdir = d / "meshtastic-offline" / "packages"
    clean_dir(debdir)
    total = 0
    for p in wanted:
        fn = os.path.basename(p["Filename"])
        c = download(p["_base"] + p["Filename"], CACHE / "debs" / fn, int(p["Size"]))
        if p.get("SHA256") and hashlib.sha256(c.read_bytes()).hexdigest() != p["SHA256"]:
            c.unlink()
            raise SystemExit(f"checksum mismatch for {fn}")
        shutil.copy2(c, debdir / fn)
        total += int(p["Size"])
    # A Packages index makes the folder a local apt repository, so on the Pi apt
    # itself picks exactly which packages are missing or too old.
    stanzas = []
    for p in wanted:
        lines = []
        for k, v in p.items():
            if k.startswith("_"):
                continue
            if k == "Filename":
                v = "./" + os.path.basename(v)
            lines.append(f"{k}: {v}")
        stanzas.append("\n".join(lines))
    (debdir / "Packages").write_text("\n\n".join(stanzas) + "\n", encoding="utf-8")
    mesh = next(p for p in wanted if p["Package"] == "meshtasticd")
    manifest["raspberry_pi_os"] = {"image": name, "meshtasticd": mesh["Version"],
                                   "packages": len(wanted), "MB": total >> 20}
    print(f"    {len(wanted)} packages, {total>>20} MB")


def write_driver_report(d: Path):
    """SECURITY-REPORT.txt for the Windows drivers: checksum + VirusTotal result per file.
    A file whose checksum no longer matches the recorded one is shown as NOT CHECKED."""
    try:
        rec = json.loads((d / "checksums.json").read_text())
    except Exception:
        rec = {}
    L = ["WINDOWS USB DRIVERS - SECURITY REPORT", "=" * 37, "",
         "HOW THE KIT PROTECTS YOU",
         "Before installing a driver, the START-HERE window checks its digital signature:",
         "  - CH340 driver: must be validly signed by Nanjing Qinheng Microelectronics (WCH).",
         "  - CP210x driver: its catalog must be validly signed by Microsoft (WHQL-certified),",
         "    and Windows refuses any driver file that doesn't match that catalog.",
         "A file that fails is not installed. This works for any version the makers release.",
         "",
         "VIRUSTOTAL (background information)",
         "The versions below were looked up on VirusTotal by SHA-256 checksum (files were not",
         "uploaded). A newer version simply shows as not looked up; it is still signature-checked.",
         ""]
    for f in sorted(d.iterdir()):
        if junk(f) or f.suffix.lower() not in (".exe", ".zip"):
            continue
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        r = rec.get(f.name, {})
        L += [f.name, "-" * len(f.name)]
        if r.get("what"):
            L.append(f"  What:        {r['what']}")
        if r.get("publisher"):
            L.append(f"  From:        {r['publisher']}  ({r.get('source', '')})")
        L.append(f"  SHA-256:     {sha}")
        L.append(f"  Size:        {f.stat().st_size:,} bytes")
        if r.get("sha256") == sha:
            L.append(f"  Signed by:   {r.get('signed_by', '-')}")
            L.append(f"  VirusTotal:  {r.get('virustotal', '-')}  (analysis {r.get('virustotal_analysis', '-')},"
                     f" checked {r.get('checked', '-')})")
        else:
            L.append("  VirusTotal:  not looked up (a different version from the one checked).")
            L.append("               Still verified by its digital signature before installing.")
        L.append(f"  Report:      https://www.virustotal.com/gui/file/{sha}")
        L.append("")
    L += ["To check a file yourself:",
          "  Windows:    certutil -hashfile CH341SER.EXE SHA256",
          "  Mac/Linux:  shasum -a 256 CH341SER.EXE",
          "then compare with the SHA-256 above and open the Report link."]
    (d / "SECURITY-REPORT.txt").write_text("\r\n".join(L) + "\r\n", encoding="utf-8")


def c_drivers():
    """USB-serial drivers for Windows (most ESP32 boards use CP210x or CH340)."""
    log("Windows USB drivers")
    d = ROOT / "5-Windows-USB-Drivers"
    d.mkdir(exist_ok=True)
    items = [
        ("CP210x_Universal_Windows_Driver.zip",
         "https://www.silabs.com/documents/public/software/CP210x_Universal_Windows_Driver.zip"),
        ("CH341SER.EXE", "https://www.wch-ic.com/downloads/file/65.html"),
    ]
    got = []
    for name, url in items:
        if (d / name).exists():
            got.append(name)
            continue
        try:
            download(url, CACHE / "drivers" / name)
            data = (CACHE / "drivers" / name).read_bytes()[:4]
            if data[:2] not in (b"PK", b"MZ"):
                raise ValueError("server returned a web page, not the driver")
            shutil.copy2(CACHE / "drivers" / name, d / name)
            got.append(name)
        except Exception as e:
            (CACHE / "drivers" / name).unlink(missing_ok=True)
            warn(f"could not download {name} ({e}). Download it by hand from {url} into {d}")
    manifest["drivers"] = got
    write_driver_report(d)


# ---- Chromium browser (Mac + Linux; Windows always has Edge) --------------------
# ungoogled-chromium: open-source (BSD) Chromium without Google services, so it may be
# shared freely. Needed because Safari/Firefox can't talk to radios over USB.
CHROMIUM = {   # drive folder -> (repo, asset pattern)
    "Mac": ("ungoogled-software/ungoogled-chromium-macos", [r"_arm64-macos\.dmg$", r"_x86_64-macos\.dmg$"]),
    "Linux": ("ungoogled-software/ungoogled-chromium-portablelinux",
              [r"-x86_64_linux\.tar\.xz$", r"-arm64_linux\.tar\.xz$"]),
}

def c_chromium():
    """Chromium web browser (Mac + Linux), for computers with no compatible browser."""
    log("Chromium browser (Mac + Linux)")
    have = manifest.get("chromium") or {}
    for folder, (repo, pats) in CHROMIUM.items():
        rel = gh_latest(repo)
        d = ROOT / "4-Chromium-Browser" / folder
        names = []
        for pat in pats:
            a = asset(rel, pat)
            fetch_asset(a, d / a["name"])
            names.append(a["name"])
        remove_stale(d, names)
        have[folder.lower()] = rel["tag_name"]
    manifest["chromium"] = have

PY_TARGETS = {   # file on the drive -> python-build-standalone target
    "python-windows-x64.tar.gz": "x86_64-pc-windows-msvc",
    "python-mac-arm64.tar.gz": "aarch64-apple-darwin",
    "python-mac-x64.tar.gz": "x86_64-apple-darwin",
    "python-linux-x64.tar.gz": "x86_64-unknown-linux-gnu",
    "python-linux-arm64.tar.gz": "aarch64-unknown-linux-gnu",
}

def _python_release():
    rel = gh_latest("astral-sh/python-build-standalone")
    out = {}
    for fname, target in PY_TARGETS.items():
        out[fname] = asset(rel, rf"^cpython-3\.12\.\d+\+\d+-{re.escape(target)}-install_only_stripped\.tar\.gz$")
    ver = re.match(r"cpython-(3\.12\.\d+)", next(iter(out.values()))["name"]).group(1)
    return ver, out

def c_python():
    """Portable Python, so the drive can update itself on any computer."""
    log("Portable Python (for the updater)")
    ver, assets = _python_release()
    d = SYS / "tools" / "python"
    for fname, a in assets.items():
        dest = d / fname
        if manifest.get("python") != ver or not dest.exists():
            dest.unlink(missing_ok=True)
        fetch_asset(a, dest)
    manifest["python"] = ver


# ---- "what's out of date?" ----------------------------------------------------
def check_updates(parts):
    """Compare the drive (VERSIONS.json) with what's online. Returns list of rows."""
    m = manifest
    rows = []
    def row(name, have, latest):
        rows.append((name, have or "-", latest or "?", (have or "") != (latest or "")))
    want = set(parts)
    fw = get_json("https://api.meshtastic.org/github/firmware/list")["releases"]
    for ch, n in FIRMWARE_CHANNELS.items():
        latest = [r["id"] for r in fw.get(ch, []) if "revoked" not in r.get("title", "").lower()][:n]
        row(f"Firmware ({'stable' if ch == 'stable' else 'alpha, experimental'})",
            ", ".join(m.get("firmware", {}).get(ch, [])), ", ".join(latest))
    row("Web app", m.get("webclient"), gh_latest("meshtastic/web")["tag_name"])
    app = gh_latest("meshtastic/Meshtastic-Android")["tag_name"]
    if "android" in want:
        row("Android app", m.get("android"), app)
    if "desktop" in want:
        row("Desktop apps", m.get("desktop"), app)
    if "pi_mpwrd" in want:
        row("Pi image A (mPWRD-OS)", (m.get("mpwrd_os") or {}).get("release"),
            gh_latest("mPWRD-OS/mPWRD-OS")["tag_name"])
    if "pi_raspios" not in want:
        return _check_rest(rows, row, m, want)
    osl = get_json("https://downloads.raspberrypi.com/os_list_imagingutility_v4.json")
    latest_img = None
    def walk(items):
        nonlocal latest_img
        for i in items:
            if "subitems" in i:
                walk(i["subitems"])
            elif i.get("name") == "Raspberry Pi OS Lite (64-bit)" and not latest_img:
                latest_img = os.path.basename(i["url"])
    walk(osl["os_list"])
    row("Pi image B (Raspberry Pi OS)", (m.get("raspberry_pi_os") or {}).get("image"), latest_img)
    obs = get_bytes(PI_OBS + "Packages").decode()
    mv = re.search(r"Package: meshtasticd\n(?:.+\n)*?Version: (\S+)", obs)
    row("Pi Meshtastic package", (m.get("raspberry_pi_os") or {}).get("meshtasticd"), mv and mv.group(1))
    return _check_rest(rows, row, m, want)

def _check_rest(rows, row, m, want):
    if "pi_imager" in want:
        row("SD card writer", m.get("rpi_imager"), gh_latest("raspberrypi/rpi-imager")["tag_name"])
    if "esptool" in want:
        row("esptool", m.get("esptool"), gh_latest("espressif/esptool")["tag_name"])
    if "chromium" in want:
        ch = m.get("chromium") or {}
        row("Chromium browser (Mac)", ch.get("mac"), gh_latest(CHROMIUM["Mac"][0])["tag_name"])
        row("Chromium browser (Linux)", ch.get("linux"), gh_latest(CHROMIUM["Linux"][0])["tag_name"])
    row("Local web server", m.get("miniserve"), gh_latest("svenstaro/miniserve")["tag_name"].lstrip("v"))
    if "offline_map" in want and map_area():
        have = ((m.get("offline_map") or {}).get("build") or "")
        latest = have if have and _days_old(have) < MAP_REFRESH_DAYS else "newer map"
        row("Offline map", have[:8] or None, latest[:8] if latest == have else latest)
    return rows


COMPONENTS = {
    "miniserve": c_miniserve, "webclient": c_webclient, "firmware": c_firmware,
    "flasher": c_flasher, "desktop": c_desktop, "android": c_android,
    "esptool": c_esptool, "pi_imager": c_pi_imager, "pi_mpwrd": c_pi_mpwrd,
    "pi_raspios": c_pi_raspios, "drivers": c_drivers, "python": c_python, "chromium": c_chromium,
    "flasher_models": c_flasher_models, "offline_map": c_offline_map,
}


def write_versions():
    manifest["built"] = time.strftime("%Y-%m-%d %H:%M")
    try:
        manifest["kit"] = (ROOT / "VERSION").read_text().strip()
    except OSError:
        pass
    (SYS / "VERSIONS.json").write_text(json.dumps(manifest, indent=2))
    (SYS / "hub" / "versions.js").write_text(
        "window.MESH_VERSIONS = " + json.dumps(manifest, indent=2) + ";\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="comma-separated component names")
    ap.add_argument("--skip", help="comma-separated component names to skip")
    ap.add_argument("--check", action="store_true",
                    help="only report what's out of date (exit 0 = up to date, 3 = updates, 1 = offline)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--update-kit", action="store_true",
                    help="also update the kit itself (start windows, setup, updater) first; used by U")
    args = ap.parse_args()
    if args.list:
        for k, f in COMPONENTS.items():
            print(f"  {k:12s} {(f.__doc__ or '').strip()}")
        return
    mf = SYS / "VERSIONS.json"
    if mf.exists():
        manifest.update(json.loads(mf.read_text()))
    parts = load_settings()

    if args.check:
        try:
            rows = check_updates(parts)
        except Exception as e:
            warn(f"Couldn't check for updates - is this computer online? ({e})")
            sys.exit(1)
        try:
            import kit_update as K
            have, (latest_kit, _, _) = K.current_version(ROOT), K.latest()
            rows.insert(0, ("Emergency kit (start window, setup, updater)", have, latest_kit,
                            K.vtuple(latest_kit) > K.vtuple(have)))
        except Exception:
            pass
        w = max(len(r[0]) for r in rows)
        print()
        for name, have, latest, new in rows:
            mark = "\033[1;32mNEW\033[0m" if new else " ok"
            print(f"  {mark}  {name:{w}s}  {have}" + (f"  ->  {latest}" if new else ""))
        n = sum(r[3] for r in rows)
        print()
        print(f"  {n} update(s) available." if n else "  Everything on this drive is up to date.")
        sys.exit(3 if n else 0)

    # make sure the drive is writable before downloading gigabytes
    try:
        probe = SYS / ".write-test"
        probe.write_text("ok"); probe.unlink()
    except OSError:
        warn("This drive is read-only (or full). Can't update it.")
        sys.exit(1)

    try:
        get_bytes("https://api.github.com/zen")
    except Exception:
        warn("No internet connection - keeping what's already here. "
             "Connect and run the update again to download the rest.")
        write_versions()
        sys.exit(2)

    # The kit itself first, so the newest updater does the rest.
    if args.update_kit and not os.environ.get("MESH_KIT_UPDATED"):
        log("Emergency kit")
        import kit_update as K
        try:
            new = K.update(ROOT)
            if not new:
                print(f"    v{K.current_version(ROOT)} is the newest")
        except Exception as e:
            warn(f"Couldn't update the kit itself ({e}). Updating the parts with this version.")
            new = None
        if new:
            manifest["kit"] = new
            write_versions()
            print("\n    Continuing with the new updater ...")
            env = dict(os.environ, MESH_KIT_UPDATED="1")
            argv = [a for a in sys.argv[1:] if a != "--update-kit"]
            rc = subprocess.run([sys.executable, "-u", str(Path(__file__).resolve()), *argv], env=env).returncode
            print(f"\n\033[1;33m  The kit was updated to v{new}. To use the new start window, restart it: "
                  "press R in its menu (or close the window and start the drive again).\033[0m")
            sys.exit(rc)

    # This drive's parts, in a sensible order (flasher rebuild only if it was chosen).
    names = [n for n in COMPONENTS if n in parts or (n == "firmware")]
    if args.only:
        names = [n.strip() for n in args.only.split(",")]
    if args.skip:
        names = [n for n in names if n not in args.skip.split(",")]
    failed = []
    for n in names:
        try:
            COMPONENTS[n]()
            remove_appledouble(ROOT)
            write_versions()          # save progress after each part
        except KeyboardInterrupt:
            warn("Stopped. Run the update again to finish - nothing is broken.")
            write_versions()
            sys.exit(1)
        except (SystemExit, Exception) as e:
            warn(f"{n} FAILED: {e}")
            failed.append(n)
    write_versions()
    remove_appledouble(ROOT)
    if not KEEP_CACHE and not failed:
        shutil.rmtree(CACHE, ignore_errors=True)
    if failed:
        warn("Some parts failed: " + ", ".join(failed) + "  (run the update again to retry)")
        sys.exit(1)
    log("All done - this drive is up to date.")


if __name__ == "__main__":
    main()
