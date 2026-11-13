"""
Update the Emergency Kit itself (start windows, setup, updater, guides) on a drive.

Used by build_usb.py when you press U. The parts (firmware, apps, maps...) are updated
separately; this only replaces the kit's own small files with those from the newest
release on GitHub:

  1. read the newest release (version + the zip's SHA-256 fingerprint published by GitHub)
  2. download the zip and check its fingerprint; refuse it if it doesn't match
  3. copy the kit's files onto the drive, leaving this drive's settings, version records
     and downloaded parts alone; only files that changed are replaced, each one swapped in
     as a new file (never rewritten in place, so a running start window isn't disturbed)
"""
import hashlib, json, os, re, shutil, sys, tempfile, urllib.request, zipfile
from pathlib import Path

REPO = "doktordeathray/emergency-kit-for-meshtastic"
UA = "Meshtastic-Emergency-Kit-updater"
KEEP = {"_system/settings.json", "_system/VERSIONS.json", "_system/hub/versions.js"}   # this drive's own


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "0")[:3])


def current_version(root: Path):
    try:
        return (root / "VERSION").read_text().strip()
    except OSError:
        return "0.0.0"


def latest():
    """(version, zip url, sha256 or None) of the newest kit release."""
    rel = json.loads(_get(f"https://api.github.com/repos/{REPO}/releases/latest"))
    ver = rel["tag_name"].lstrip("v")
    a = next((a for a in rel.get("assets", []) if re.match(r"Meshtastic-Emergency-Kit-Setup.*\.zip$", a["name"])), None)
    if not a:
        raise RuntimeError("the newest release has no setup kit attached")
    sha = re.sub(r"^sha256:", "", a.get("digest") or "") or None
    if not sha:     # fall back to the fingerprint printed in the release notes
        m = re.search(r"```\s*([0-9a-f]{64})\s*```", rel.get("body") or "")
        sha = m.group(1) if m else None
    return ver, a["browser_download_url"], sha


def new_sections(changelog: str, have: str):
    """Changelog sections newer than the version this drive has."""
    out = []
    for v, d, body in re.findall(r"^## (\d+\.\d+\.\d+) \(([\d-]+)\)\n(.*?)(?=^## |\Z)", changelog, re.M | re.S):
        if vtuple(v) > vtuple(have):
            out.append((v, d, body.strip()))
    return out


def update(root: Path, log=print):
    """Update the kit on this drive if a newer one is released. Returns the new version,
    or None if it was already current. Raises on errors (nothing is changed then)."""
    have = current_version(root)
    ver, url, sha = latest()
    if vtuple(ver) <= vtuple(have):
        return None
    if not sha:
        raise RuntimeError("the release has no published fingerprint, so it can't be checked")
    log(f"    downloading kit v{ver} ...")
    data = _get(url, timeout=300)
    if hashlib.sha256(data).hexdigest() != sha:
        raise RuntimeError("the downloaded kit's fingerprint doesn't match the published one; not installed")
    with tempfile.TemporaryDirectory() as td:
        zp = Path(td) / "kit.zip"
        zp.write_bytes(data)
        with zipfile.ZipFile(zp) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            top = names[0].split("/")[0]
            changed = 0
            for n in names:
                rel = n[len(top) + 1:]
                if not rel or rel in KEEP or "/._" in "/" + rel or rel.endswith(".DS_Store"):
                    continue
                new = z.read(n)
                dst = root / rel
                try:
                    if dst.read_bytes() == new:
                        continue
                except OSError:
                    pass
                dst.parent.mkdir(parents=True, exist_ok=True)
                tmp = dst.with_name(f".{dst.name}.new")
                tmp.write_bytes(new)
                if rel.endswith((".sh", ".command")):
                    tmp.chmod(0o755)
                os.replace(tmp, dst)
                changed += 1
            try:
                notes = z.read(f"{top}/CHANGELOG.md").decode("utf-8")
            except KeyError:
                notes = ""
    log(f"    kit updated to v{ver} ({changed} files)")
    for v, d, body in new_sections(notes, have):
        log(f"\n    What's new in {v}:")
        for line in body.splitlines():
            if line.startswith("- "):
                log("      - " + re.sub(r"[`*]", "", line[2:]))
    if sys.platform == "darwin":
        import subprocess
        subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(root)], capture_output=True)
    return ver
