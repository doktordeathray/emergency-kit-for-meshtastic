#!/usr/bin/env python3
"""
Make the small, shareable setup kit (a .zip) from this drive.

    python3 make_setup_kit.py [output.zip]

The version comes from the VERSION file at the top of the drive. It goes into the zip's
name (Meshtastic-Emergency-Kit-Setup-v0.1.5.zip) and the folder inside it
(Meshtastic-Emergency-Kit-v0.1.5), so a new version never unzips on top of an old one.

The kit holds only the launchers, guides, setup/updater scripts and the prebuilt
web flasher. Everything else (firmware, apps, images, browser...) is downloaded
by SETUP on the user's computer. No third-party installers are included, so the
kit can be shared freely.
"""
import json, os, sys, time, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = "Meshtastic-Emergency-Kit"

# Folders whose contents are downloaded by setup (never shipped in the kit)
EXCLUDE_DIRS = [
    "_system/bin", "_system/tools", "_system/webclient", "_system/.update-cache",
    "_system/flasher/release", "_system/flasher/api", "_system/flasher/models",
    "3-Raspberry-Pi/Option-B-Raspberry-Pi-OS-plus-Meshtastic/meshtastic-offline/packages",
]
EXCLUDE_NAMES = {".DS_Store", "__pycache__", "settings.json", "VERSIONS.json", "versions.js"}
KEEP_EXT_ALWAYS = {".txt", ".md", ".html", ".sh", ".command", ".bat", ".ps1", ".py", ".css"}
MAX_OTHER = 2 << 20     # any other file over 2 MB (installers, images, apps) stays out


def wanted(rel: str, size: int) -> bool:
    parts = rel.split("/")
    if any(p in EXCLUDE_NAMES for p in parts):
        return False
    if any(rel == d or rel.startswith(d + "/") for d in EXCLUDE_DIRS):
        return False
    if rel.startswith("_system/flasher/"):
        return True                          # the prebuilt flasher app itself
    if os.path.splitext(rel)[1].lower() in KEEP_EXT_ALWAYS:
        return True
    return size <= MAX_OTHER and not rel.lower().endswith((".exe", ".zip", ".dmg", ".apk",
                                                          ".msi", ".deb", ".appimage", ".xz", ".gz"))


def kit_version():
    v = (ROOT / "VERSION").read_text().strip()
    if not v.replace(".", "").isdigit():
        raise SystemExit(f"VERSION file should hold a number like 0.1.5, not {v!r}")
    return v


def main():
    ver = kit_version()
    top = f"{NAME}-v{ver}"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / f"{NAME}-Setup-v{ver}.zip"
    vers = {}
    try:
        full = json.loads((ROOT / "_system" / "VERSIONS.json").read_text())
        vers = {k: full[k] for k in ("flasher", "flasher_commit") if k in full}
    except Exception:
        pass
    n = 0
    tmp = out.with_suffix(".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(ROOT.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if not wanted(rel, p.stat().st_size):
                continue
            zi = zipfile.ZipInfo(f"{top}/{rel}", time.localtime(p.stat().st_mtime)[:6])
            mode = 0o755 if rel.endswith((".sh", ".command")) else 0o644
            zi.external_attr = (0o100000 | mode) << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, p.read_bytes())
            n += 1
        # fresh version info: only what the kit really contains
        for rel, data in (("_system/VERSIONS.json", json.dumps(vers, indent=2)),
                          ("_system/hub/versions.js", "window.MESH_VERSIONS = " + json.dumps(vers) + ";\n")):
            zi = zipfile.ZipInfo(f"{top}/{rel}", time.localtime()[:6])
            zi.external_attr = (0o100644) << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, data)
            n += 1
    tmp.replace(out)
    print(f"Wrote {out}  (version {ver}, {n} files, {out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
