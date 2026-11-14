var DETAILS = "/SOURCE-AND-CHANGES.txt";
(function () {
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
