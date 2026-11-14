var DETAILS = "/SOURCE-AND-CHANGES.txt";
(function () {
  var KEY = 'meshtastic-kit-notice-closed';
  try { if (sessionStorage.getItem(KEY)) return; } catch (e) {}
  function show() {
    if (document.getElementById('mk-notice')) return;
    // Make room at the top: push the page down by the banner's height, and shorten
    // full-height layouts and sticky headers so nothing hides behind it. (Kept in our own
    // <style>, not a class on <html>: some sites, like the docs, rewrite <html>'s classes.)
    var st = document.createElement('style');
    st.id = 'mk-notice-style';
    document.head.appendChild(st);
    function rules(h) {
      st.textContent =
        'body{padding-top:' + h + 'px!important}' +
        '.h-screen,.h-dvh,.h-svh{height:calc(100vh - ' + h + 'px)!important}' +
        '.min-h-screen,.min-h-dvh{min-height:calc(100vh - ' + h + 'px)!important}' +
        '.navbar--fixed-top{top:' + h + 'px!important}' +
        '.theme-doc-sidebar-container>div{top:' + h + 'px!important;height:calc(100vh - ' + h + 'px)!important}' +
        '.theme-doc-toc-desktop{top:calc(var(--ifm-navbar-height) + 1rem + ' + h + 'px)!important}' +
        '#mk-notice a{color:#111;font-weight:700;text-decoration:underline}' +
        '#mk-notice button:hover,#mk-notice button:focus-visible{background:rgba(0,0,0,.12);outline:none}';
    }
    var d = document.createElement('div');
    d.id = 'mk-notice';
    d.setAttribute('role', 'note');
    d.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483000;box-sizing:border-box;' +
      'padding:10px 56px 10px 16px;text-align:center;font:600 14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;' +
      'background:#ffd400;color:#111;border-bottom:2px solid #111;box-shadow:0 2px 8px rgba(0,0,0,.2)';
    var t = document.createElement('span');
    var b = document.createElement('b');
    b.textContent = 'OFFLINE COPY: ';
    t.appendChild(b);
    t.appendChild(document.createTextNode('from Emergency Kit for Meshtastic (an independent project), modified to ' +
      'work from this drive. Not an official Meshtastic service. '));
    var a = document.createElement('a');
    a.href = DETAILS; a.target = '_blank'; a.rel = 'noopener';
    a.textContent = 'Details';
    t.appendChild(a);
    var x = document.createElement('button');
    x.type = 'button'; x.setAttribute('aria-label', 'Close this notice'); x.title = 'Close';
    x.textContent = '×';
    x.style.cssText = 'position:absolute;right:10px;top:50%;transform:translateY(-50%);border:2px solid #111;' +
      'background:transparent;color:#111;font:700 20px/1 system-ui,sans-serif;width:32px;height:32px;' +
      'border-radius:6px;cursor:pointer;padding:0';
    x.onclick = function () {
      d.remove(); st.remove(); window.removeEventListener('resize', fit);
      try { sessionStorage.setItem(KEY, '1'); } catch (e) {}
    };
    d.appendChild(t); d.appendChild(x);
    document.body.appendChild(d);
    function fit() { rules(d.offsetHeight); }
    fit();
    window.addEventListener('resize', fit);
  }
  if (document.body) show(); else document.addEventListener('DOMContentLoaded', show);
})();
