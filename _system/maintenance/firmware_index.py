"""
Index pages for the firmware files on the drive, so nobody has to guess which file is theirs.

  _system/flasher/release/index.html          the firmware versions on this drive
  _system/flasher/release/<version>/index.html every drag-and-drop (.uf2) file with the radio
                                              it's for, its chip, how to get the radio ready,
                                              plus what the other kinds of files are

Radio names come from the flasher's own device list (flasher/api/resource/deviceHardware.json,
downloaded from api.meshtastic.org with the firmware). Made by build_usb.py after the firmware
step; safe to run again at any time.
"""
import html, json, re
from pathlib import Path

CHIP = {"nrf52840": "nRF52840", "rp2040": "RP2040", "rp2350": "RP2350"}
HOW = {
    "nrf52840": "Plug it in, then <b>double-press the reset button</b> quickly. A drive appears "
                "(named like <code>RAK4631</code>, <code>TECHOBOOT</code>, <code>T1000-E</code> or <code>HT-n5262</code>).",
    "rp2040": "Hold the <b>BOOTSEL</b> button while plugging it in. A drive called <code>RPI-RP2</code> appears.",
    "rp2350": "Hold the <b>BOOTSEL</b> button while plugging it in. A drive called <code>RP2350</code> appears.",
}
# Firmware builds that aren't in the flasher's device list (or need a word of explanation)
EXTRA = {
    "pico2": ("Raspberry Pi Pico 2", "with a LoRa module wired to it", "rp2350"),
    "pico2w": ("Raspberry Pi Pico 2 W", "with a LoRa module wired to it", "rp2350"),
    "feather_diy": ("Adafruit Feather nRF52840 (DIY)", "home-built Feather with a LoRa radio", "nrf52840"),
    "rak4631_eink": ("RAK WisBlock 4631", "version for an e-ink display module", "nrf52840"),
    "rak4631_eth_gw": ("RAK WisBlock 4631", "Ethernet gateway version (RAK13800 Ethernet module)", "nrf52840"),
    "t-impulse-plus": ("LILYGO T-Impulse Plus", "", "nrf52840"),
    "wio-sdk-wm1110": ("Seeed Wio-WM1110 Dev Kit", "", "nrf52840"),
    "heltec-mesh-pocket-5000": ("Heltec MeshPocket", "5000 mAh battery version", "nrf52840"),
    "heltec-mesh-pocket-10000": ("Heltec MeshPocket", "10000 mAh battery version", "nrf52840"),
    "heltec-mesh-solar": ("Heltec MeshSolar", "version without a display", "nrf52840"),
    "heltec-mesh-solar-eink": ("Heltec MeshSolar", "version with an e-ink display", "nrf52840"),
    "heltec-mesh-solar-oled": ("Heltec MeshSolar", "version with an OLED display", "nrf52840"),
    "heltec-mesh-solar-tft": ("Heltec MeshSolar", "version with a colour TFT display", "nrf52840"),
}
INKHUD = "InkHUD: a simpler screen layout made for e-ink displays"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bg:#f6f7f5; --panel:#fff; --ink:#17201a; --muted:#5d6a61; --line:#dfe5e0; --accent:#2c9a5a; --soft:#e3f6ea;
  --warn-bg:#fff4d6; --warn-ink:#6b4a00; --warn-line:#f0d48a;
  font-family: system-ui,-apple-system,"Segoe UI",Roboto,Ubuntu,sans-serif; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111613; --panel:#1a211c; --ink:#e8efe9; --muted:#9aa89e;
  --line:#2b352e; --accent:#67ea94; --soft:#1d3325; --warn-bg:#3a2f10; --warn-ink:#ffe3a1; --warn-line:#6b5520; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); line-height:1.5; font-size:16px; }}
.wrap {{ max-width:1000px; margin:0 auto; padding:0 16px 48px; }}
header {{ background:var(--panel); border-bottom:1px solid var(--line); padding:16px 0; margin-bottom:20px; }}
h1 {{ font-size:1.4rem; margin:0; }} h2 {{ font-size:1.1rem; margin:28px 0 8px; }}
a {{ color:var(--accent); }} .muted {{ color:var(--muted); font-size:.92rem; }}
code {{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.88em; overflow-wrap:anywhere; }}
.steps {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 16px 12px 36px; }}
.steps li {{ margin:4px 0; }}
.tip {{ background:var(--warn-bg); color:var(--warn-ink); border:1px solid var(--warn-line); border-radius:12px; padding:10px 14px; margin:12px 0; }}
input[type=search] {{ width:100%; padding:10px 12px; font-size:1rem; border-radius:10px; border:1px solid var(--line);
  background:var(--panel); color:var(--ink); margin:8px 0 4px; }}
table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
th, td {{ text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ font-size:.85rem; color:var(--muted); font-weight:600; background:var(--soft); }}
td.dl a {{ white-space:nowrap; font-weight:600; }}
.tag {{ display:inline-block; font-size:.75rem; border:1px solid var(--line); border-radius:99px; padding:0 8px; margin-left:6px; color:var(--muted); }}
.cards {{ display:grid; gap:12px; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px 16px; text-decoration:none; color:var(--ink); }}
.card:hover {{ border-color:var(--accent); }}
details {{ margin-top:10px; }} summary {{ cursor:pointer; font-weight:600; }}
@media (max-width:640px) {{ th.chip, td.chip {{ display:none; }} }}
</style></head>
<body><header><div class="wrap"><h1>{title}</h1><div class="muted">{subtitle}</div></div></header>
<main class="wrap">{body}</main>
{script}
</body></html>
"""

FILTER_JS = """<script>
var q = document.getElementById('q');
q && q.addEventListener('input', function () {
  var t = q.value.toLowerCase().trim();
  document.querySelectorAll('tbody tr').forEach(function (r) {
    r.hidden = t && r.textContent.toLowerCase().indexOf(t) < 0;
  });
});
</script>"""


def _devices(flasher: Path):
    try:
        return {d["platformioTarget"]: d for d in json.loads(
            (flasher / "api" / "resource" / "deviceHardware.json").read_text(encoding="utf-8"))}
    except Exception:
        return {}


def _channel_of(flasher: Path):
    """version -> 'stable' / 'alpha' from the offline firmware list."""
    out = {}
    try:
        rel = json.loads((flasher / "api" / "github" / "firmware" / "list.json").read_text())["releases"]
        for ch, items in rel.items():
            for r in items:
                out[r["id"].lstrip("v")] = ch
    except Exception:
        pass
    return out


def _describe(target, devices, folder: Path, ver):
    """(radio name, note, chip, maker) for a firmware target name."""
    inkhud = target.endswith("-inkhud")
    base = target[:-len("-inkhud")] if inkhud else target
    d = devices.get(target) or devices.get(base)
    name, note, chip = None, "", None
    if base in EXTRA:
        name, note, chip = EXTRA[base]
    if d:
        name = name or d.get("displayName")
        chip = d.get("architecture", chip)
    try:
        mt = json.loads((folder / f"firmware-{target}-{ver}.mt.json").read_text())
        chip = mt.get("mcu") or chip
    except Exception:
        pass
    if inkhud:
        note = (note + "; " if note else "") + INKHUD
    if d and not d.get("activelySupported", True):
        note = (note + "; " if note else "") + "not actively supported"
    maker = (d.get("tags") or [""])[0] if d else ""
    return name or target.replace("_", " ").replace("-", " "), note, (chip or "").lower(), maker


def write_version_page(folder: Path, devices, channel):
    ver = folder.name
    rows = []
    for f in sorted(folder.glob(f"firmware-*-{ver}.uf2"), key=lambda p: p.name.lower()):
        if f.name.startswith("._"):
            continue
        target = f.name[len("firmware-"):-len(f"-{ver}.uf2")]
        name, note, chip, maker = _describe(target, devices, folder, ver)
        rows.append((name.lower(), f, name, note, chip, maker))
    rows.sort()
    from collections import Counter
    many = Counter(r[2] for r in rows)
    rows = [(k, f, name, note or ("standard version" if many[name] > 1 else ""), chip, maker)
            for k, f, name, note, chip, maker in rows]
    trs = []
    for _, f, name, note, chip, maker in rows:
        mk = f'<span class="tag">{html.escape(maker)}</span>' if maker else ""
        nt = f'<div class="muted">{html.escape(note)}</div>' if note else ""
        trs.append(f'<tr><td><b>{html.escape(name)}</b>{mk}{nt}</td>'
                   f'<td class="chip">{CHIP.get(chip, html.escape(chip) or "?")}</td>'
                   f'<td class="dl"><a href="{html.escape(f.name)}" download>Download</a>'
                   f'<div class="muted"><code>{html.escape(f.name)}</code> · {f.stat().st_size / 1e6:.1f} MB</div></td></tr>')
    erase = sorted(p.name for p in folder.glob("Meshtastic_nRF52_factory_erase*.uf2") if not p.name.startswith("._"))
    erase_html = "".join(f'<li><a href="{html.escape(n)}" download><code>{html.escape(n)}</code></a></li>' for n in erase)
    label = {"stable": "stable", "alpha": "alpha (experimental)"}.get(channel, "")
    body = f"""
<p><a href="../">← All firmware versions</a> · <a href="/">Open the web flasher instead</a></p>
<h2>Drag-and-drop radios (nRF52 and Raspberry Pi Pico)</h2>
<ol class="steps">
  <li><b>Find your radio below</b> and click <b>Download</b>. Not sure which model you have? It's usually printed on the board or the box.</li>
  <li><b>Get the radio ready:</b> nRF52 radios: {HOW['nrf52840']}<br>
      Pico (RP2040 / RP2350): hold <b>BOOTSEL</b> while plugging it in (drive <code>RPI-RP2</code> or <code>RP2350</code>).</li>
  <li><b>Drag the downloaded <code>.uf2</code> file onto that drive.</b> The radio restarts by itself when it's done. A "disk not ejected properly" message is normal.</li>
</ol>
<input type="search" id="q" placeholder="Type to find your radio (e.g. RAK, T-Echo, T1000, Pico)" aria-label="Find your radio">
<table><thead><tr><th>Radio</th><th class="chip">Chip</th><th>Firmware file</th></tr></thead>
<tbody>{''.join(trs) or '<tr><td colspan="3">No drag-and-drop files in this version.</td></tr>'}</tbody></table>
<p class="muted">ESP32 radios (Heltec V3/V4, T-Beam, T-Deck, Station G2 and others) aren't in this list: use the <a href="/">web flasher</a>, which picks the right file for you.</p>

<h2>nRF52 radio acting strangely?</h2>
<div class="tip">A <b>factory erase</b> file wipes the radio's settings so you can start clean. Copy it to the radio's drive the same way, wait for it to finish, then copy the firmware again.
To choose between them, open <code>INFO_UF2.TXT</code> on the radio's drive: if it says <b>SoftDevice S140 6.x</b> use the 6.1.0 file, if it says <b>S140 7.x</b> use the 7.3.0 file.
<ul>{erase_html}</ul></div>

<details><summary>What are all the other files in this folder?</summary>
<ul>
<li><code>.uf2</code>: drag-and-drop firmware (the list above).</li>
<li><code>.bin</code> and <code>.factory.bin</code>: ESP32 firmware, used by the web flasher and by esptool. <code>.factory.bin</code> is a full install that wipes the radio; the plain <code>.bin</code> updates it.</li>
<li><code>-ota.zip</code>: nRF52 firmware for updating over Bluetooth from the phone app.</li>
<li><code>.hex</code>: nRF52 firmware for programming tools (most people won't need these).</li>
<li><code>.mt.json</code> and <code>firmware-{html.escape(ver)}.json</code>: descriptions the web flasher reads.</li>
<li><code>device-install</code> / <code>device-update</code> scripts: command-line flashing with esptool.</li>
</ul>
</details>
"""
    page = PAGE.format(title=f"Firmware {html.escape(ver)}" + (f" ({label})" if label else ""),
                       subtitle="Meshtastic firmware on this drive. Works with no internet.",
                       body=body, script=FILTER_JS)
    (folder / "index.html").write_text(page, encoding="utf-8")
    return len(rows)


def write_all(flasher: Path):
    """Write every page. Returns {version: number of drag-and-drop files}."""
    rel_root = flasher / "release"
    if not rel_root.is_dir():
        return {}
    devices, chans = _devices(flasher), _channel_of(flasher)
    done = {}
    versions = sorted((p for p in rel_root.iterdir() if p.is_dir() and not p.name.startswith(".")),
                      key=lambda p: [int(x) if x.isdigit() else 0 for x in re.split(r"[.]", p.name)], reverse=True)
    for v in versions:
        done[v.name] = write_version_page(v, devices, chans.get(v.name))
    versions.sort(key=lambda v: {"stable": 0, "alpha": 1}.get(chans.get(v.name), 2))   # stable first
    cards = []
    for v in versions:
        ch = chans.get(v.name)
        what = {"stable": "Stable: use this one", "alpha": "Alpha: newest, experimental"}.get(ch, "")
        cards.append(f'<a class="card" href="{html.escape(v.name)}/"><b>Firmware {html.escape(v.name)}</b>'
                     f'<div class="muted">{what}{" · " if what else ""}{done[v.name]} drag-and-drop radios</div></a>')
    body = (f'<p><a href="/">← Back to the web flasher</a></p><h2>Choose a firmware version</h2>'
            f'<div class="cards">{"".join(cards)}</div>'
            f'<p class="muted">Not sure? Pick <b>stable</b>. Alpha is the newest firmware and may have bugs.</p>')
    (rel_root / "index.html").write_text(
        PAGE.format(title="Firmware files", subtitle="For radios you update by drag and drop (nRF52, Raspberry Pi Pico).",
                    body=body, script=""), encoding="utf-8")
    return done


if __name__ == "__main__":
    import sys
    print(write_all(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "flasher"))
