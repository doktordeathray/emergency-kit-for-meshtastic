#!/usr/bin/env python3
"""
Meshtastic Emergency Kit - setup.

Started by SETUP-WINDOWS.bat / SETUP-MAC.command / SETUP-LINUX.sh. Asks where to
install (a USB drive, this computer, or a folder) and which parts to include, then
copies what this kit already has and downloads the rest.

Non-interactive use (for scripts/testing):
    python3 setup.py --target /path --profile essentials --yes
    python3 setup.py --target /path --parts webclient,firmware,android --yes
"""
import argparse, json, os, platform, shutil, subprocess, sys, time
from pathlib import Path

if os.name == "nt":
    os.system("")      # colour codes in the Windows console

KIT = Path(__file__).resolve().parents[2]          # folder this setup runs from
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_usb as B                              # PARTS / PROFILES live there
import drives as D                                 # find USB drives, erase as exFAT

G, Y, R, C, BOLD, N = "\033[1;32m", "\033[1;33m", "\033[1;31m", "\033[1;36m", "\033[1m", "\033[0m"
def ok(t): print(f"{G}✔ {t}{N}")
def warn(t): print(f"{Y}! {t}{N}")
def fail(t): print(f"{R}✖ {t}{N}")

# Where each part lives on the drive (copied from this kit when it already has them).
PART_PATHS = {
    "python": ["_system/tools/python"], "miniserve": ["_system/bin"],
    "webclient": ["_system/webclient"],
    "firmware": ["_system/flasher/release", "_system/flasher/api"],
    "flasher_models": ["_system/flasher/models"],
    "android": ["2-Android-Phone"], "chromium": ["4-Chromium-Browser"],
    "drivers": ["5-Windows-USB-Drivers"], "desktop": ["1-Desktop-App"],
    "esptool": ["_system/tools/esptool"], "pi_imager": ["3-Raspberry-Pi/SD-Card-Writer"],
    "pi_mpwrd": ["3-Raspberry-Pi/Option-A-Ready-Made-Meshtastic-Image"],
    "pi_raspios": ["3-Raspberry-Pi/Option-B-Raspberry-Pi-OS-plus-Meshtastic"],
}
BIG_PATHS = {p for ps in PART_PATHS.values() for p in ps}
SKIP_NAMES = {".update-cache", ".DS_Store", "settings.json", "__pycache__", "VERSIONS.json", "versions.js"}


def ask(prompt, default=""):
    try:
        a = input(f"{prompt} ").strip()
    except EOFError:
        a = ""
    return a or default


def gb(mb):
    return f"{mb/1024:.1f} GB" if mb >= 1024 else f"{mb} MB"


def free_mb(path):
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        return shutil.disk_usage(p).free >> 20
    except OSError:
        return None


def is_pi():
    try:
        return "Raspberry Pi" in Path("/proc/device-tree/model").read_text(errors="ignore")
    except OSError:
        return False


# ---- find USB drives -------------------------------------------------------------
def find_drives():
    """[(label, path)] of removable / external drives."""
    out = []
    sysname = platform.system()
    if sysname == "Windows":
        import ctypes
        k = ctypes.windll.kernel32
        mask = k.GetLogicalDrives()
        sysdrive = os.environ.get("SystemDrive", "C:").upper()
        for i in range(26):
            if not mask & (1 << i):
                continue
            letter = f"{chr(65+i)}:"
            root = letter + "\\"
            kind = k.GetDriveTypeW(root)
            if letter == sysdrive or kind not in (2, 3):     # 2 removable, 3 fixed
                continue
            name = ctypes.create_unicode_buffer(261)
            if not k.GetVolumeInformationW(root, name, 261, None, None, None, None, 0):
                continue
            tag = "USB drive" if kind == 2 else "other disk"
            out.append((f"{letter} {name.value or '(no name)'}  [{tag}]", root))
    elif sysname == "Darwin":
        import plistlib
        for v in sorted(Path("/Volumes").iterdir()):
            if os.path.realpath(v) == "/" or v.name.startswith("com.apple"):
                continue
            try:
                info = plistlib.loads(subprocess.run(["diskutil", "info", "-plist", str(v)],
                                                     capture_output=True, timeout=10).stdout)
            except Exception:
                continue
            if info.get("BusProtocol") == "Disk Image" or info.get("Internal", False):
                continue
            if not info.get("WritableVolume", True):
                continue
            out.append((f"{v.name}  [external drive]", str(v)))
    else:
        user = os.environ.get("USER") or os.environ.get("SUDO_USER") or ""
        seen = set()
        try:
            for line in open("/proc/mounts"):
                mp = line.split()[1].replace("\\040", " ")
                if mp.startswith((f"/media/{user}/", f"/run/media/{user}/", "/media/", "/mnt/")) \
                        and mp not in seen and os.access(mp, os.W_OK):
                    seen.add(mp)
                    out.append((f"{os.path.basename(mp)}  [{mp}]", mp))
        except OSError:
            pass
    return out


# ---- USB drive: check the format, offer to erase as exFAT --------------------------------
def disk_label(d):
    if not d.vols or not any(v.fs or v.mount for v in d.vols):
        fmt = "not formatted"
    elif d.ready():
        fmt = "exFAT, ready to use"
    elif len(d.vols) > 1:
        fmt = f"{len(d.vols)} parts: " + ", ".join(D.fs_name(v.fs) for v in d.vols)
    else:
        fmt = D.fs_name(d.vols[0].fs)
    name = next((v.label for v in d.vols if v.label), "") or d.name
    return f"USB drive: {name}  ({d.size_text()}, {fmt})"


def prepare_disk(d):
    """Return the folder to install into on this drive, or None to choose again."""
    if d.ready():
        return Path(d.usable_vols()[0].mount)
    print()
    if len(d.vols) > 1:
        warn(f"This drive is split into {len(d.vols)} parts, so not every computer will show the kit.")
    else:
        warn(f"This drive's format is {D.fs_name(d.vols[0].fs)}. {D.fs_problem(d.vols[0].fs)}")
    print("  exFAT works on Windows, Mac, Linux and Raspberry Pi, so it's the best format for this kit.")
    names, count, used = D.contents_summary(d)
    if count or used > 50 << 20:
        print(f"\n  {BOLD}Currently on the drive{N} ({used/1e9:.1f} GB used):")
        for n in names:
            print(f"     {n}")
        if count > len(names):
            print(f"     ...and {count - len(names)} more")
    usable = d.usable_vols()
    print(f"\n  {C}1{N}  Erase the drive and format it as exFAT  (recommended; {R}deletes everything on it{N})")
    if usable:
        print(f"  {C}2{N}  Keep it as it is and install anyway")
    print(f"  {C}{3 if usable else 2}{N}  Go back and choose somewhere else")
    a = ask("\nType a number and press Enter:")
    if usable and a == "2":
        return Path(usable[0].mount)
    if a != "1":
        return None
    label = next((v.label for v in d.vols if v.label), "")
    print(f"\n{R}{BOLD}Everything on {(label + ' - ') if label else ''}{d.name} ({d.size_text()}) will be deleted.{N}")
    if ask("Type ERASE (in capitals) and press Enter to continue, or just press Enter to go back:") != "ERASE":
        print("Not erased. Nothing was changed.")
        return None
    if D.SYS == "Windows":
        print("  Windows will ask for permission to format the drive. Click Yes.")
    print(f"  Formatting as exFAT, named {D.LABEL} ...")
    path, msg = D.format_exfat(d)
    if msg == "needs-exfatprogs":
        print("\n  This computer needs a small tool (exfatprogs) to make exFAT drives.")
        if ask("  Install it now? It needs internet and your password. [Y/n]", "y").lower() in ("y", "yes") \
                and D.install_exfat_tools():
            path, msg = D.format_exfat(d)
        else:
            msg = "Install it with:  sudo apt install exfatprogs   then run setup again."
    if not path:
        fail(f"The drive wasn't formatted. {msg}")
        return None
    ok(f"Formatted as exFAT: {path}")
    return Path(path)


# ---- offline map: which area ------------------------------------------------------------
def ask_map_area():
    """Ask for a place and a distance around it. Returns the area, or None to skip the map."""
    import offline_map as M
    import tempfile
    print(f"\n{BOLD}Offline map{N}")
    print("  The web app can show your nodes on a map with no internet. Choose the area to save:")
    print("  a town or city and how far around it. (Map data: OpenStreetMap contributors.)")
    while True:
        q = ask(f"\n  Type a town or city (e.g. Toronto), or coordinates like 43.65, -79.38\n"
                f"  (or just press Enter to skip the map):")
        if not q:
            return None
        ll = M.parse_latlon(q)
        if ll:
            name, (lat, lon) = f"{ll[0]:.3f}, {ll[1]:.3f}", ll
        else:
            try:
                hits = M.search_place(q)
            except Exception:
                warn("Couldn't search for places (no internet?). Try coordinates instead.")
                continue
            if not hits:
                warn(f"Nothing found for '{q}'. Try another spelling, a bigger town nearby, or coordinates.")
                continue
            for i, (n, _, _) in enumerate(hits, 1):
                print(f"    {C}{i}{N}  {n}")
            a = ask("  Which one? [1]", "1")
            if not (a.isdigit() and 1 <= int(a) <= len(hits)):
                continue
            name, lat, lon = hits[int(a) - 1]
            name = name.split(",")[0]
        km = ask("  How far around it, in km? (e.g. 10 for a town, 50 for a region) [25]", "25")
        try:
            km = max(1.0, min(float(km), 500.0))
        except ValueError:
            km = 25.0
        bbox = M.bbox_around(lat, lon, km)
        print("  Checking the size of that map ...")
        mb = None
        try:
            tool = M.get_tool(Path(tempfile.gettempdir()) / "meshtastic-kit-map-tool")
            mb = M.estimate_mb(tool, bbox)
        except Exception as e:
            warn(f"Couldn't check the size ({e}).")
        size = f"about {gb(int(mb) + 1)}" if mb is not None else "unknown size"
        if ask(f"  {name}, {km:g} km around: {size}. Use this area? [Y/n]", "y").lower() in ("y", "yes"):
            return {"name": name, "bbox": bbox, "maxzoom": 15, "km": km,
                    "mb": int(mb) + 1 if mb is not None else None}


# ---- Windows drivers by hand (their makers' sites block automatic downloads) ------------
DRIVERS = [   # (name on the drive, what it is, page to open, what to click there)
    ("CH341SER.EXE", "CH340 / CH9102 driver, from WCH",
     "https://www.wch-ic.com/downloads/CH341SER_EXE.html", "click Download (the file is CH341SER.EXE)"),
    ("CP210x_Universal_Windows_Driver.zip", "CP210x driver, from Silicon Labs",
     "https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers?tab=downloads",
     'download "CP210x Universal Windows Driver" (a .zip file)'),
]
MAC_ZIP_NOTE = ("On a Mac, Safari unzips downloads into a folder by itself. To keep the .zip, Control-click\n"
                "          (or right-click) the download link and choose Download Linked File. If it was\n"
                "          already unzipped, that's fine: drag the CP210x_Universal_Windows_Driver folder in instead.")


def dropped_paths(line):
    """Turn what a drag-and-drop typed into this window into file paths."""
    from urllib.parse import unquote
    line = line.strip()
    if not line:
        return []
    if Path(line.strip('"\'')).expanduser().exists():           # one file or folder, any quoting
        return [Path(line.strip('"\'')).expanduser()]
    import shlex
    try:
        parts = shlex.split(line, posix=(os.name != "nt"))
    except ValueError:
        parts = line.split()
    out = []
    for t in parts:
        t = t.strip('"\'')
        if t.startswith("file://"):
            t = unquote(t[7:])
        out.append(Path(t).expanduser())
    return out


def which_driver(path: Path):
    """(name on the drive, None) if this is one of the two drivers, else (None, reason)."""
    if path.is_dir():       # the CP210x zip, already unzipped (Safari does this by itself)
        files = {f.relative_to(path).as_posix().lower() for f in path.rglob("*")
                 if f.is_file() and not f.name.startswith("._")}
        if {"silabser.inf", "silabser.cat"} <= files and any(f.endswith("silabser.sys") for f in files):
            return "CP210x_Universal_Windows_Driver.zip", None
        if any(f.endswith("silabser.inf") for f in files):
            return None, "this CP210x folder is incomplete; download the .zip again"
        return None, "that folder isn't the unzipped CP210x driver"
    if not path.is_file():
        return None, "file not found"
    head = path.read_bytes()[:4]
    low = path.name.lower()
    if head[:2] == b"MZ":
        if "ch34" in low:
            return "CH341SER.EXE", None
        return None, "that's a program, but not CH341SER.EXE"
    if head[:2] == b"PK":
        import zipfile
        try:
            names = " ".join(zipfile.ZipFile(path).namelist()).lower()
        except zipfile.BadZipFile:
            return None, "the zip file is damaged; download it again"
        if "cp210x" in low or "silabser" in names:
            return "CP210x_Universal_Windows_Driver.zip", None
        return None, "that zip file isn't the CP210x driver"
    if head[:1] == b"<" or b"html" in path.read_bytes()[:512].lower():
        return None, "that's a web page, not the driver; download it again"
    return None, "that isn't one of the two driver files"


def add_drivers_by_hand(target: Path):
    d = target / "5-Windows-USB-Drivers"
    missing = [x for x in DRIVERS if not (d / x[0]).exists()]
    if not missing:
        return
    print(f"\n{BOLD}Windows USB drivers{N}")
    print("  Their makers' websites don't allow automatic downloads, so they need saving by hand")
    print("  (about a minute). They're only needed to connect radios to Windows computers.")
    for name, what, url, how in missing:
        print(f"    {name}  ({what})")
    if not sys.stdin.isatty() or ask("\nOpen the download pages in your browser now? [Y/n]", "y").lower() not in ("y", "yes"):
        print("  Skipped. The links are in 5-Windows-USB-Drivers/READ-ME.txt for later.")
        return
    import webbrowser
    for name, what, url, how in missing:
        print(f"  Opening {url}\n    -> {how}")
        if name.endswith(".zip") and platform.system() == "Darwin":
            print(f"    {Y}Note:{N} {MAC_ZIP_NOTE}")
        webbrowser.open(url)
    d.mkdir(parents=True, exist_ok=True)
    added = []
    while missing:
        print(f"\n  When a file has downloaded, drag it from your Downloads folder into this window")
        print(f"  and press Enter. You can drag both at once. Press Enter on its own to finish.")
        line = ask(f"  {C}Drop driver file(s) here:{N}")
        if not line:
            break
        for path in dropped_paths(line):
            name, why = which_driver(path)
            if not name:
                fail(f"{path.name}: {why}")
                continue
            if path.is_dir():       # put the unzipped CP210x folder back into a .zip
                import zipfile
                with zipfile.ZipFile(d / name, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in sorted(path.rglob("*")):
                        if f.is_file() and not f.name.startswith("._") and f.name != ".DS_Store":
                            z.write(f, f.relative_to(path).as_posix())
            else:
                shutil.copyfile(path, d / name)
            ok(f"Added {name}")
            added.append(name)
            missing = [x for x in missing if x[0] != name]
    if added:
        B.write_driver_report(d)
        vp = target / "_system" / "VERSIONS.json"
        try:
            v = json.loads(vp.read_text())
        except Exception:
            v = {}
        v["drivers"] = sorted(set(v.get("drivers") or []) | set(added) |
                              {x[0] for x in DRIVERS if (d / x[0]).exists()})
        vp.write_text(json.dumps(v, indent=2))
        B.remove_appledouble(d)
    if missing:
        print(f"  Still missing: {', '.join(x[0] for x in missing)}. Run setup again later to add it,")
        print("  or save it into the drive's 5-Windows-USB-Drivers folder yourself.")
    else:
        ok("Both Windows drivers are on the drive. The Windows start window checks their signatures before installing.")


# ---- questions ----------------------------------------------------------------------
def choose_target():
    print(f"\n{BOLD}Where should the Meshtastic kit go?{N}\n")
    opts = []
    disks = D.list_disks(exclude_paths=[str(KIT), str(Path.home())])
    if disks is None:       # couldn't ask this computer about its disks: list mounted drives instead
        for label, path in find_drives():
            opts.append((label + (f"   {gb(free_mb(path))} free" if free_mb(path) is not None else ""), Path(path)))
    else:
        for d in disks:
            opts.append((disk_label(d), d))
    home = Path.home() / "Meshtastic-Emergency"
    here_label = "This Raspberry Pi" if is_pi() else "This computer"
    opts.append((f"{here_label}  ({home})", home))
    if os.access(KIT, os.W_OK):
        opts.append((f"Right here, in the folder this setup is in  ({KIT})", KIT))
    opts.append(("Somewhere else (type a folder)", None))
    for i, (label, _) in enumerate(opts, 1):
        print(f"  {C}{i}{N}  {label}")
    if not (disks if disks is not None else find_drives()):
        print(f"\n  {Y}No USB drive found. To use one, plug it in and run setup again.{N}")
    while True:
        a = ask(f"\nType a number and press Enter:")
        if a.isdigit() and 1 <= int(a) <= len(opts):
            label, path = opts[int(a) - 1]
            if isinstance(path, D.Disk):
                path = prepare_disk(path)
                if path is None:
                    return choose_target()
            elif path is None:
                path = Path(os.path.expanduser(ask("Folder path:"))).resolve()
            return path


def choose_parts():
    kit = list(B.PROFILES["essentials"])
    print(f"\n{BOLD}What should it include?{N}\n")
    print(f"  {C}1{N}  The standard kit  (~{gb(parts_mb(kit))})  web app, flasher + firmware, Android app, browser")
    print(f"  {C}2{N}  The standard kit, plus extras I pick  (desktop apps, Raspberry Pi images...)")
    a = ask("\nType a number and press Enter [1]:", "1")
    if a != "2":
        return kit
    keys = list(B.EXTRAS)
    print(f"\nOptional extras (add as many as you like):\n")
    for i, k in enumerate(keys, 1):
        label, mb, _ = B.PARTS[k]
        size = "size depends on the area" if k == "offline_map" else f"~{gb(mb)}"
        print(f"  {C}{i:2d}{N}  {label}  ({size})")
    a = ask("\nType the numbers you want, separated by spaces (e.g. 1 3), or press Enter for none:")
    for tok in a.replace(",", " ").split():
        if tok.isdigit() and 1 <= int(tok) <= len(keys) and keys[int(tok) - 1] not in kit:
            kit.append(keys[int(tok) - 1])
    if ("pi_mpwrd" in kit or "pi_raspios" in kit) and "pi_imager" not in kit:
        kit.append("pi_imager")      # a Pi image is no use without the SD card writer
        print("  (Added the Raspberry Pi SD card writer, needed for the Pi images.)")
    return kit


def parts_mb(parts):
    return sum(B.PARTS[p][1] for p in parts if p in B.PARTS)


# ---- install ---------------------------------------------------------------------------
def copy_kit(target: Path, parts):
    """Copy the small kit files, plus any chosen parts this kit already has."""
    if target.resolve() == KIT.resolve():
        return
    print(f"\nCopying the kit to {target} ...")
    for src in KIT.rglob("*"):
        rel = src.relative_to(KIT).as_posix()
        if any(part in SKIP_NAMES or part.startswith("._") for part in src.relative_to(KIT).parts):
            continue
        if any(rel == bp or rel.startswith(bp + "/") for bp in BIG_PATHS):
            continue
        dst = target / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for p in parts:
        for rel in PART_PATHS.get(p, []):
            src = KIT / rel
            if src.exists() and any(src.rglob("*")):
                print(f"    copying {B.PARTS[p][0]} from this kit (no download needed)")
                shutil.copytree(src, target / rel, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("._*", ".DS_Store"))
    # Merge version info: keep what the target already records, add what was copied.
    def read(p):
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    tv = target / "_system" / "VERSIONS.json"
    merged = {**read(tv), **read(KIT / "_system" / "VERSIONS.json")}
    tv.parent.mkdir(parents=True, exist_ok=True)
    tv.write_text(json.dumps(merged, indent=2))


def finish(target: Path):
    B.remove_appledouble(target)      # macOS '._' helper files on exFAT drives
    for f in ("START-HERE-MAC.command", "START-HERE-LINUX.sh", "SETUP-MAC.command", "SETUP-LINUX.sh",
              "_system/launcher.sh", "_system/maintenance/bootstrap.sh"):
        try:
            (target / f).chmod(0o755)
        except OSError:
            pass
    if platform.system() == "Darwin":
        subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(target)], capture_output=True)
    if platform.system() == "Windows":   # clear "downloaded from the internet" marks
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Get-ChildItem -Recurse -File -LiteralPath '{target}' | Unblock-File"],
                       capture_output=True)
    if platform.system() == "Linux" and str(target).startswith(str(Path.home())):
        apps = Path.home() / ".local/share/applications"
        apps.mkdir(parents=True, exist_ok=True)
        entry = (f"[Desktop Entry]\nType=Application\nName=Meshtastic Emergency Kit\n"
                 f"Exec=bash \"{target}/START-HERE-LINUX.sh\"\nTerminal=true\nCategories=Network;\n")
        (apps / "meshtastic-emergency-kit.desktop").write_text(entry)
        desk = Path.home() / "Desktop"
        if desk.is_dir():
            d = desk / "meshtastic-emergency-kit.desktop"
            d.write_text(entry)
            d.chmod(0o755)
            subprocess.run(["gio", "set", str(d), "metadata::trusted", "true"], capture_output=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target")
    ap.add_argument("--profile", choices=list(B.PROFILES))
    ap.add_argument("--parts", help="comma-separated part names")
    ap.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    ap.add_argument("--map", help="offline map area: 'lat,lon,km' (with --parts ...,offline_map)")
    args = ap.parse_args()

    try:
        kit_ver = (KIT / "VERSION").read_text().strip()
    except OSError:
        kit_ver = "?"
    print(f"\n{G}  MESHTASTIC EMERGENCY KIT - SETUP   v{kit_ver}{N}")
    print("  Builds an offline Meshtastic toolkit: web app, radio flasher + firmware,")
    print("  Android app and more (about 1.5 GB). Needs internet now; never again after.")

    target = Path(os.path.expanduser(args.target)).resolve() if args.target else choose_target()
    if args.parts:
        parts = [p.strip() for p in args.parts.split(",") if p.strip() in B.PARTS]
        for must in ("python", "miniserve", "webclient", "firmware"):
            if must not in parts:
                parts.insert(0, must)
    elif args.profile:
        parts = list(B.PROFILES[args.profile])
    else:
        parts = choose_parts()

    area = None
    if "offline_map" in parts:
        if args.map:
            import offline_map as M
            lat, lon, km = (float(x) for x in args.map.split(","))
            area = {"name": f"{lat:.3f}, {lon:.3f}", "bbox": M.bbox_around(lat, lon, km), "maxzoom": 15, "km": km}
        elif not args.yes:
            area = ask_map_area()
        if not area:
            parts.remove("offline_map")
    need = parts_mb(parts)
    if area and area.get("mb"):
        need += area["mb"] - B.PARTS["offline_map"][1]
    free = free_mb(target)
    print(f"\n{BOLD}Ready to set up:{N}")
    print(f"  Where:  {target}")
    print(f"  Size:   about {gb(need)}" + (f"   ({gb(free)} free there)" if free is not None else ""))
    if free is not None and free < need * 1.1:
        fail("Not enough free space there. Choose a bigger drive or fewer parts.")
        sys.exit(1)
    if not args.yes:
        if ask("\nStart? It can take 15-60 minutes depending on your internet. [Y/n]", "y").lower() not in ("y", "yes"):
            print("Cancelled - nothing was changed.")
            return
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".meshtastic-write-test"
        probe.write_text("ok"); probe.unlink()
    except OSError as e:
        fail(f"Can't write to {target}: {e}")
        sys.exit(1)

    copy_kit(target, parts)
    (target / "_system").mkdir(parents=True, exist_ok=True)
    settings = {"parts": parts}
    if area:
        settings["map"] = area
    (target / "_system" / "settings.json").write_text(json.dumps(settings, indent=2))
    finish(target)

    print(f"\n{BOLD}Downloading (keep this window open; you can use the computer meanwhile)...{N}\n")
    t0 = time.time()
    rc = subprocess.run([sys.executable, "-u", str(target / "_system" / "maintenance" / "build_usb.py")]).returncode
    finish(target)
    mins = (time.time() - t0) / 60
    print()
    if rc == 0:
        ok(f"Done in {mins:.0f} min. The Meshtastic kit is ready at: {target}")
    elif rc == 2:
        warn("No internet right now, so only what this kit already had was copied to "
             f"{target}. Connect to the internet and run setup again (or press U in the "
             "kit's start window) to get the rest.")
    else:
        warn("Some parts didn't finish (see above). Everything else works. Run setup again - "
             "or later, press U in the kit's start window - to finish the rest.")
    if "drivers" in parts and rc != 2 and not args.yes:
        add_drivers_by_hand(target)
    print(f"\n{BOLD}To use it:{N} open that folder and double-click the START-HERE file for your computer.")
    print("Works with no internet from now on. To refresh it later, start it and type U.")
    sys.exit(0 if rc == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Run setup again any time - it continues where it left off.")
        sys.exit(1)
