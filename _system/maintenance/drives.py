"""
Find USB drives and erase one as exFAT, on Windows, macOS and Linux / Raspberry Pi.

Used by setup.py. Only lists external / USB disks, and never the disk the computer
starts from or the disk this kit is running from. Erasing always needs the person
to type ERASE first (setup.py asks), and on Windows also a "Yes" in the Windows
admin prompt; on Linux, the person's own sudo password.

    list_disks(exclude_paths) -> [Disk] or None if this computer can't be asked
    format_exfat(disk)        -> (mount_path or None, message)
"""
import json, os, platform, plistlib, re, shutil, subprocess, tempfile, time
from dataclasses import dataclass, field
from pathlib import Path

LABEL = "MESHTASTIC"          # exFAT names can be at most 11 characters
SYS = platform.system()
SBIN = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


@dataclass
class Vol:
    mount: str          # "" when not mounted / no drive letter
    fs: str             # lower case: exfat, fat32, ntfs, apfs, hfs, ext4, ... or ""
    label: str = ""
    writable: bool = True


@dataclass
class Disk:
    id: str             # diskN (Mac), disk number (Windows), /dev/sdX (Linux)
    name: str
    size: int           # bytes
    vols: list = field(default_factory=list)

    def size_text(self):
        gb = self.size / 1e9
        return f"{gb:.0f} GB" if gb >= 10 else f"{gb:.1f} GB"

    def usable_vols(self):
        return [v for v in self.vols if v.mount and v.writable]

    def ready(self):
        """One exFAT volume we can write to: nothing to do."""
        return len(self.vols) == 1 and self.vols[0].fs == "exfat" and bool(self.usable_vols())


def fs_name(fs):
    return {"exfat": "exFAT", "fat32": "FAT32", "fat16": "FAT", "ntfs": "NTFS", "apfs": "Mac (APFS)",
            "hfs": "Mac (Mac OS Extended)", "ext4": "Linux (ext4)", "": "not formatted"}.get(fs, fs.upper())


def fs_problem(fs):
    if fs in ("fat32", "fat16"):
        return "It works, but can't hold files over 4 GB."
    if fs == "ntfs":
        return "Macs can't write to it."
    if fs in ("apfs", "hfs"):
        return "Windows can't read it."
    if fs.startswith("ext") or fs in ("btrfs", "xfs", "f2fs"):
        return "Windows and Macs can't read it."
    if not fs:
        return "It has no format that computers can use yet."
    return "Not every computer can read it."


def _norm_fs(s):
    s = (s or "").lower()
    if s in ("msdos", "vfat", "fat"):
        return "fat32"
    if s in ("hfs+", "hfsplus", "jhfs+"):
        return "hfs"
    return s


def _under(path, mount):
    try:
        path, mount = os.path.realpath(path), os.path.realpath(mount)
    except OSError:
        return False
    return mount not in ("", "/") and (path == mount or path.startswith(mount.rstrip("\\/") + os.sep))


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=kw.pop("timeout", 60), **kw)


# ---- list -------------------------------------------------------------------------------
def list_disks(exclude_paths=()):
    try:
        disks = {"Darwin": _mac_list, "Windows": _win_list}.get(SYS, _linux_list)()
    except Exception:
        return None
    if disks is None:
        return None
    return [d for d in disks
            if not any(_under(p, v.mount) for v in d.vols if v.mount for p in exclude_paths)]


def _mac_plist(verb, *args):
    """diskutil info|list -plist ...  as a dict."""
    return plistlib.loads(subprocess.run(["diskutil", verb, "-plist", *args],
                                         capture_output=True, timeout=20).stdout)


def _mac_list():
    want = ["external", "physical"]
    if os.environ.get("MESH_TEST_ALLOW_DISK_IMAGES"):      # for testing with a disk image only
        want = ["external"]
    whole = _mac_plist("list", *want).get("WholeDisks", [])
    disks = {}
    for w in whole:
        info = _mac_plist("info", w)
        if info.get("Internal"):
            continue
        if info.get("BusProtocol") == "Disk Image" and not os.environ.get("MESH_TEST_ALLOW_DISK_IMAGES"):
            continue
        if info.get("VirtualOrPhysical") == "Virtual" and info.get("BusProtocol") != "Disk Image":
            continue        # an APFS container: its physical disk is listed instead
        disks[w] = Disk(w, info.get("MediaName") or info.get("IORegistryEntryName") or w,
                        int(info.get("TotalSize") or info.get("Size") or 0))
    for v in Path("/Volumes").iterdir():
        try:
            info = _mac_plist("info", str(v))
        except Exception:
            continue
        stores = [s.get("APFSPhysicalStore", "") for s in info.get("APFSPhysicalStores") or []]
        owners = {re.match(r"(disk\d+)", s).group(1) for s in stores if re.match(r"disk\d+", s)}
        owners.add(info.get("ParentWholeDisk", ""))
        for o in owners:
            if o in disks:
                disks[o].vols.append(Vol(info.get("MountPoint") or str(v), _norm_fs(info.get("FilesystemType")),
                                         info.get("VolumeName", ""), bool(info.get("WritableVolume", True))))
    # partitions with no mounted volume (unformatted, or a format macOS can't read)
    for w, d in disks.items():
        if not d.vols:
            d.vols.append(Vol("", "", ""))
    return list(disks.values())


_WIN_LIST = r"""
$ErrorActionPreference = 'Stop'
$out = @()
foreach ($d in (Get-Disk | Where-Object { @('USB','SD','MMC') -contains [string]$_.BusType -and -not $_.IsBoot -and -not $_.IsSystem })) {
  $vols = @()
  foreach ($p in @(Get-Partition -DiskNumber $d.Number -ErrorAction SilentlyContinue)) {
    $v = $p | Get-Volume -ErrorAction SilentlyContinue
    $l = [string]$p.DriveLetter
    if ($l -notmatch '^[A-Za-z]$') { $l = '' }
    if ($v) { $vols += [pscustomobject]@{ letter = $l; fs = [string]$v.FileSystem; label = [string]$v.FileSystemLabel } }
  }
  $out += [pscustomobject]@{ id = [string]$d.Number; name = [string]$d.FriendlyName; size = [int64]$d.Size; vols = @($vols) }
}
ConvertTo-Json -InputObject @($out) -Depth 4 -Compress
"""


def _ps(script, timeout=60):
    return _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], timeout=timeout)


def _win_list():
    r = _ps(_WIN_LIST)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    data = json.loads(r.stdout)
    if isinstance(data, dict):
        data = [data]
    disks = []
    for d in data:
        vols = d.get("vols") or []
        if isinstance(vols, dict):
            vols = [vols]
        disk = Disk(d["id"], d.get("name") or f"Disk {d['id']}", int(d.get("size") or 0))
        for v in vols:
            root = f"{v['letter']}:\\" if v.get("letter") else ""
            disk.vols.append(Vol(root, _norm_fs(v.get("fs")), v.get("label") or "",
                                 bool(root) and os.access(root, os.W_OK)))
        if not disk.vols:
            disk.vols.append(Vol("", ""))
        disks.append(disk)
    return disks


def _linux_list():
    if not shutil.which("lsblk", path=SBIN):
        return None
    r = _run([shutil.which("lsblk", path=SBIN), "-J", "-b", "-o",
              "NAME,TRAN,HOTPLUG,SIZE,FSTYPE,MOUNTPOINT,LABEL,MODEL,TYPE"])
    if r.returncode != 0:
        return None
    system_mounts = {"/", "/boot", "/boot/firmware", "/home", "/usr", "/var", "[SWAP]"}
    disks = []

    def walk(node, acc):
        acc.append(node)
        for c in node.get("children") or []:
            walk(c, acc)
        return acc

    for dev in json.loads(r.stdout).get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        hot = dev.get("hotplug") in (True, 1, "1")
        if dev.get("tran") != "usb" and not hot:
            continue
        nodes = walk(dev, [])
        if any((n.get("mountpoint") or "") in system_mounts for n in nodes):
            continue
        disk = Disk("/dev/" + dev["name"], (dev.get("model") or dev["name"]).strip(), int(dev.get("size") or 0))
        for n in nodes[1:] or nodes:
            if n.get("type") not in ("part", "disk"):
                continue
            mp = n.get("mountpoint") or ""
            if n.get("fstype") or mp:
                disk.vols.append(Vol(mp, _norm_fs(n.get("fstype")), n.get("label") or "",
                                     bool(mp) and os.access(mp, os.W_OK)))
        if not disk.vols:
            disk.vols.append(Vol("", ""))
        disks.append(disk)
    return disks


def contents_summary(disk, limit=5):
    """A few names and the used space, so the person knows what they'd lose."""
    names, used = [], 0
    for v in disk.usable_vols() or [v for v in disk.vols if v.mount]:
        try:
            u = shutil.disk_usage(v.mount)
            used += u.total - u.free
            for e in sorted(os.listdir(v.mount)):
                if not e.startswith(".") and e not in ("System Volume Information", "$RECYCLE.BIN"):
                    names.append(e)
        except OSError:
            pass
    return names[:limit], len(names), used


# ---- erase as exFAT ------------------------------------------------------------------
def format_exfat(disk):
    try:
        return {"Darwin": _mac_format, "Windows": _win_format}.get(SYS, _linux_format)(disk)
    except subprocess.TimeoutExpired:
        return None, "Formatting took too long and was stopped."


def _mac_format(disk):
    r = _run(["diskutil", "eraseDisk", "ExFAT", LABEL, "MBR", disk.id], timeout=600)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout).strip() or "diskutil couldn't erase the drive."
    for _ in range(20):
        info = _mac_plist("list", disk.id)
        for whole in info.get("AllDisksAndPartitions", []):
            for p in whole.get("Partitions", []):
                if p.get("MountPoint"):
                    return p["MountPoint"], "ok"
        time.sleep(0.5)
    return None, "The drive was erased, but macOS didn't open it. Unplug it, plug it back in and run setup again."


_WIN_FORMAT = r"""
param([int]$n, [string]$label, [string]$result)
$ErrorActionPreference = 'Stop'
try {
  $d = Get-Disk -Number $n
  if ($d.IsBoot -or $d.IsSystem) { 'refused: system disk' | Out-File -Encoding utf8 $result; exit 3 }
  $parts = @(Get-Partition -DiskNumber $n -ErrorAction SilentlyContinue)
  $lettered = @($parts | Where-Object { [string]$_.DriveLetter -match '^[A-Za-z]$' })
  if ($parts.Count -eq 1 -and $lettered.Count -eq 1) {
    $letter = [string]$lettered[0].DriveLetter
    Format-Volume -DriveLetter $letter -FileSystem exFAT -NewFileSystemLabel $label -Confirm:$false -Force | Out-Null
  } else {
    Clear-Disk -Number $n -RemoveData -RemoveOEM -Confirm:$false
    if ((Get-Disk -Number $n).PartitionStyle -eq 'RAW') { Initialize-Disk -Number $n -PartitionStyle MBR }
    $p = New-Partition -DiskNumber $n -UseMaximumSize -AssignDriveLetter
    Format-Volume -Partition $p -FileSystem exFAT -NewFileSystemLabel $label -Confirm:$false -Force | Out-Null
    $letter = [string](Get-Partition -DiskNumber $n | Where-Object { [string]$_.DriveLetter -match '^[A-Za-z]$' } | Select-Object -First 1).DriveLetter
  }
  "ok:$letter" | Out-File -Encoding utf8 $result
  exit 0
} catch {
  ("error: " + $_.Exception.Message) | Out-File -Encoding utf8 $result
  exit 1
}
"""


def _win_format(disk):
    tmp = Path(tempfile.mkdtemp(prefix="meshkit-"))
    script, result = tmp / "format.ps1", tmp / "result.txt"
    script.write_text(_WIN_FORMAT, encoding="utf-8")
    q = lambda s: str(s).replace("'", "''")
    args = f'-NoProfile -ExecutionPolicy Bypass -File "{q(script)}" {int(disk.id)} {LABEL} "{q(result)}"'
    r = _ps(f"try {{ $p = Start-Process powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden "
            f"-ArgumentList '{args}'; exit $p.ExitCode }} catch {{ exit 9 }}", timeout=900)
    if r.returncode == 9:
        return None, "Windows didn't give permission (the admin prompt was closed or answered No)."
    text = result.read_text(encoding="utf-8-sig").strip() if result.exists() else ""
    shutil.rmtree(tmp, ignore_errors=True)
    if text.startswith("ok:") and re.match(r"^[A-Za-z]$", text[3:].strip()):
        root = text[3:].strip().upper() + ":\\"
        for _ in range(20):
            if os.path.exists(root):
                return root, "ok"
            time.sleep(0.5)
    return None, text.replace("error: ", "") or "Windows couldn't format the drive."


def _part_name(dev):
    return dev + ("p1" if dev[-1].isdigit() else "1")      # /dev/sdb -> sdb1, /dev/mmcblk0 -> p1


def _linux_format(disk):
    mkfs = shutil.which("mkfs.exfat", path=SBIN)
    if not mkfs:
        return None, "needs-exfatprogs"
    for tool in ("wipefs", "sfdisk"):
        if not shutil.which(tool, path=SBIN):
            return None, f"This computer is missing the '{tool}' tool, so setup can't format the drive."
    part = _part_name(disk.id)
    script = (f'set -e; for p in $(lsblk -nrpo NAME "{disk.id}"); do umount "$p" 2>/dev/null || true; done; '
              f'wipefs -a "{disk.id}" >/dev/null; printf "type=7\\n" | sfdisk --quiet "{disk.id}"; '
              f'partprobe "{disk.id}" 2>/dev/null || true; udevadm settle 2>/dev/null || sleep 2; '
              f'mkfs.exfat -L {LABEL} "{part}" >/dev/null')
    print("  Your password may be needed (for 'sudo'), so Linux allows formatting the drive.")
    r = subprocess.run(["sudo", "sh", "-c", script])
    if r.returncode != 0:
        return None, "Formatting didn't finish (see the message above)."
    time.sleep(2)                       # a desktop may open the new drive by itself
    already = _mounted_at(part)
    if already:
        return already, "ok"
    if shutil.which("udisksctl"):
        m = subprocess.run(["udisksctl", "mount", "-b", part], capture_output=True, text=True)
        hit = re.search(r" at (.+?)\.?$", m.stdout.strip())
        if m.returncode == 0 and hit:
            return hit.group(1), "ok"
    user = os.environ.get("USER") or "pi"
    mp = f"/media/{user}/{LABEL}"
    r = subprocess.run(["sudo", "sh", "-c", f'mkdir -p "{mp}" && mount -o uid={os.getuid()},gid={os.getgid()} "{part}" "{mp}"'])
    return (mp, "ok") if r.returncode == 0 else (None, "The drive was formatted, but couldn't be opened. Unplug it, plug it back in and run setup again.")


def _mounted_at(dev):
    try:
        for line in open("/proc/mounts"):
            d, mp = line.split()[:2]
            if os.path.realpath(d) == os.path.realpath(dev):
                return mp.replace("\\040", " ")
    except OSError:
        pass
    return None


def install_exfat_tools():
    """Linux only: install exfatprogs with the system package manager (needs internet + sudo)."""
    if shutil.which("apt-get"):
        cmd = "apt-get install -y exfatprogs"
    elif shutil.which("dnf"):
        cmd = "dnf install -y exfatprogs"
    elif shutil.which("pacman"):
        cmd = "pacman -S --noconfirm exfatprogs"
    elif shutil.which("zypper"):
        cmd = "zypper --non-interactive install exfatprogs"
    else:
        return False
    return subprocess.run(["sudo", "sh", "-c", cmd]).returncode == 0
