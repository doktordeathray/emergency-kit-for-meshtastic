"""
A small "offline copy" notice on the Meshtastic web flasher and web app on this drive.

Both are Meshtastic's own open-source apps (GPL-3.0), changed by this kit so they work
without internet. The notice says so, and who made the changes, so nobody mistakes the copy
on the drive for an official Meshtastic service. It's a pill at the bottom of the page with
a "Details" link to the change notes, and can be closed (it stays closed until the browser
tab is closed).

    add_notice(folder, details_url)   adds kit-notice.js and loads it from every .html page.
                                      Safe to run again.
"""
import json
from pathlib import Path

MARK = "<!--meshtastic-kit:notice-->"
JS = r"""(function () {
  var KEY = 'meshtastic-kit-notice-closed';
  try { if (sessionStorage.getItem(KEY)) return; } catch (e) {}
  function show() {
    if (document.getElementById('mk-notice')) return;
    var d = document.createElement('div');
    d.id = 'mk-notice';
    d.setAttribute('role', 'note');
    d.style.cssText = 'position:fixed;left:50%;bottom:40px;transform:translateX(-50%);z-index:2147483000;' +
      'max-width:calc(100% - 24px);box-sizing:border-box;display:flex;gap:10px;align-items:center;' +
      'padding:6px 8px 6px 14px;border-radius:999px;font:12px/1.35 system-ui,-apple-system,"Segoe UI",sans-serif;' +
      'background:rgba(23,32,26,.92);color:#e8efe9;box-shadow:0 2px 10px rgba(0,0,0,.25)';
    var t = document.createElement('span');
    t.textContent = 'Offline copy from Emergency Kit for Meshtastic (independent project), modified to work ' +
      'from this drive. Not an official Meshtastic service. ';
    var a = document.createElement('a');
    a.href = DETAILS; a.target = '_blank'; a.rel = 'noopener';
    a.textContent = 'Details';
    a.style.cssText = 'color:#67ea94;font-weight:600';
    t.appendChild(a);
    var x = document.createElement('button');
    x.type = 'button'; x.setAttribute('aria-label', 'Close this notice'); x.textContent = '×';
    x.style.cssText = 'border:0;background:transparent;color:#e8efe9;font-size:16px;line-height:1;' +
      'cursor:pointer;padding:2px 6px;border-radius:999px';
    x.onclick = function () { d.remove(); try { sessionStorage.setItem(KEY, '1'); } catch (e) {} };
    d.appendChild(t); d.appendChild(x);
    document.body.appendChild(d);
  }
  if (document.body) show(); else document.addEventListener('DOMContentLoaded', show);
})();
"""


def script_for(details_url: str) -> str:
    return "var DETAILS = " + json.dumps(details_url) + ";\n" + JS


def add_notice(folder: Path, details_url: str):
    """Returns the number of pages that now load the notice."""
    folder = Path(folder)
    if not folder.is_dir():
        return 0
    (folder / "kit-notice.js").write_text(script_for(details_url), encoding="utf-8")
    n = 0
    for page in folder.glob("*.html"):
        if page.name.startswith("._"):
            continue
        s = page.read_text(encoding="utf-8")
        if MARK not in s and "</head>" in s:
            s = s.replace("</head>", f'{MARK}<script src="/kit-notice.js" defer></script></head>', 1)
            page.write_text(s, encoding="utf-8")
        n += MARK in s
    return n
