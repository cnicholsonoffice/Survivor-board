"""CSS and the (optional) JS layer for the dashboard.

Hard rule for this file: **the page must be fully readable with JavaScript
switched off.** Every table, the heatmap and the value chart are rendered
server-side into static HTML by render.py. The script below only adds
conveniences -- hover tooltips, column sorting, swapping the charted team,
a light/dark toggle. If it never runs, nothing is lost but polish.

This was not the original design, and the original design was wrong: the
first version drew every table in the browser, so in any viewer that does
not execute page scripts the dashboard showed its headings, its legends and
its explanatory copy with nothing in between. All the numbers were missing
and the page still looked deliberate, which is the worst possible failure.
"""

CSS = """
:root{color-scheme:light dark}
.viz-root{
  --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
  --series-1:#2a78d6; --series-2:#eb6834;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
  /* sequential ramp, low -> high. Every step is paired with an ink colour
     that clears 4.5:1 against it, computed not eyeballed. */
  --s1:#cde2fb; --s2:#9ec5f4; --s3:#6da7ec; --s4:#3987e5;
  --s5:#256abf; --s6:#184f95; --s7:#0d366b;
  --i1:#0b0b0b; --i2:#0b0b0b; --i3:#0b0b0b; --i4:#0b0b0b;
  --i5:#ffffff; --i6:#ffffff; --i7:#ffffff;
}
/* Dark mode re-steps the ramp rather than flipping it: low values must still
   recede toward the surface, which on a dark surface means dark. */
@media (prefers-color-scheme:dark){
 :root:where(:not([data-theme="light"])) .viz-root{
  --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
  --series-1:#3987e5; --series-2:#d95926;
  --s1:#0d366b; --s2:#184f95; --s3:#256abf; --s4:#3987e5;
  --s5:#6da7ec; --s6:#9ec5f4; --s7:#cde2fb;
  --i1:#ffffff; --i2:#ffffff; --i3:#ffffff; --i4:#0b0b0b;
  --i5:#0b0b0b; --i6:#0b0b0b; --i7:#0b0b0b;
 }
}
:root[data-theme="dark"] .viz-root{
  --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
  --series-1:#3987e5; --series-2:#d95926;
  --s1:#0d366b; --s2:#184f95; --s3:#256abf; --s4:#3987e5;
  --s5:#6da7ec; --s6:#9ec5f4; --s7:#cde2fb;
  --i1:#ffffff; --i2:#ffffff; --i3:#ffffff; --i4:#0b0b0b;
  --i5:#0b0b0b; --i6:#0b0b0b; --i7:#0b0b0b;
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--text-primary);
 font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
 -webkit-text-size-adjust:100%}
.wrap{max-width:1080px;margin:0 auto;padding:14px 12px 56px}
header{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;
 margin-bottom:4px;flex-wrap:wrap}
h1{font-size:19px;margin:0;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:12px;margin-top:3px}
button.tog{background:var(--surface-1);color:var(--text-secondary);
 border:1px solid var(--border);border-radius:999px;padding:6px 12px;
 font-size:12px;cursor:pointer;font-family:inherit}
nav{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0 0}
nav a{font-size:11.5px;text-decoration:none;color:var(--text-secondary);
 background:var(--surface-1);border:1px solid var(--border);
 border-radius:999px;padding:5px 11px}
nav a:hover{color:var(--text-primary);border-color:var(--axis)}
section{background:var(--surface-1);border:1px solid var(--border);
 border-radius:12px;padding:14px;margin-top:14px;scroll-margin-top:10px}
h2{font-size:14px;margin:0 0 2px;letter-spacing:-.01em}
h3{font-size:12px;margin:16px 0 6px;letter-spacing:-.01em;
 color:var(--text-secondary)}
.note{color:var(--muted);font-size:11.5px;line-height:1.5;margin:0 0 12px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:10px}
.tile{background:var(--plane);border:1px solid var(--border);border-radius:10px;
 padding:11px 12px}
.tile .k{font-size:10.5px;color:var(--muted);text-transform:uppercase;
 letter-spacing:.05em}
.tile .v{font-size:24px;font-weight:600;margin-top:3px;letter-spacing:-.02em}
.tile .v small{font-size:12px;font-weight:500;color:var(--text-secondary)}
.tile .d{font-size:11px;color:var(--text-secondary);margin-top:3px;line-height:1.4}
.hero{border-color:var(--series-1);border-width:1.5px}
table{width:100%;border-collapse:collapse;font-size:12.5px;
 font-variant-numeric:tabular-nums}
th{text-align:right;color:var(--muted);font-weight:500;font-size:10.5px;
 text-transform:uppercase;letter-spacing:.04em;padding:0 6px 7px;
 border-bottom:1px solid var(--grid);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th.l,td.l{text-align:left}
td{padding:7px 6px;border-bottom:1px solid var(--grid);white-space:nowrap;
 text-align:right}
tr:last-child td{border-bottom:none}
tbody tr.best td{background:color-mix(in srgb,var(--series-1) 8%,transparent)}
tbody tr.win td:first-child{box-shadow:inset 3px 0 0 var(--good)}
tbody tr.loss td:first-child{box-shadow:inset 3px 0 0 var(--critical)}
.bar{position:relative;min-width:96px}
.bar i{display:block;height:9px;border-radius:0 4px 4px 0;background:var(--series-1)}
.tm{font-weight:600}
.badge{display:inline-block;font-size:9.5px;padding:1.5px 5px;border-radius:4px;
 border:1px solid var(--border);color:var(--text-secondary);vertical-align:1px}
.badge.proj{border-color:var(--series-2);color:var(--series-2)}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.heat{border-collapse:separate;border-spacing:2px;font-size:9.5px}
.heat th{padding:0 0 4px;font-size:9px;text-align:center;border:none;
 color:var(--muted)}
.heat th.now{color:var(--series-1);font-weight:700}
.heat td{padding:0;border:none}
.heat .rl{font-size:10.5px;font-weight:600;color:var(--text-primary);
 padding:0 6px 0 0;text-align:left;position:sticky;left:0;
 background:var(--surface-1);z-index:1}
.cell{width:30px;height:21px;border-radius:3px;display:flex;align-items:center;
 justify-content:center;font-variant-numeric:tabular-nums;cursor:default}
.c1{background:var(--s1);color:var(--i1)} .c2{background:var(--s2);color:var(--i2)}
.c3{background:var(--s3);color:var(--i3)} .c4{background:var(--s4);color:var(--i4)}
.c5{background:var(--s5);color:var(--i5)} .c6{background:var(--s6);color:var(--i6)}
.c7{background:var(--s7);color:var(--i7)}
.cell.na{background:repeating-linear-gradient(45deg,transparent,transparent 3px,
 var(--grid) 3px,var(--grid) 4px)}
.cell.inplan{outline:1.5px solid var(--text-primary);outline-offset:1px;
 font-weight:700}
.cell.used{opacity:.28}
.legend{display:flex;align-items:center;gap:8px;font-size:11px;
 color:var(--text-secondary);margin-top:10px;flex-wrap:wrap}
.ramp{display:flex;gap:2px}
.ramp i{width:16px;height:9px;border-radius:2px}
.plan{display:grid;grid-template-columns:repeat(auto-fill,minmax(78px,1fr));gap:6px}
.pl{background:var(--plane);border:1px solid var(--border);border-radius:8px;
 padding:7px 8px}
.pl .lg{font-size:9.5px;color:var(--muted);text-transform:uppercase;
 letter-spacing:.04em}
.pl .tm{font-size:14px;margin-top:1px}
.pl .p{font-size:10.5px;color:var(--text-secondary);font-variant-numeric:tabular-nums}
.pl.done{opacity:.55}
.pl.now{border-color:var(--series-1);border-width:1.5px}
.pl.won{border-left:3px solid var(--good)}
.pl.lost{border-left:3px solid var(--critical)}
#tip{position:fixed;pointer-events:none;opacity:0;transition:opacity .1s;
 background:var(--text-primary);color:var(--surface-1);font-size:11.5px;
 padding:6px 9px;border-radius:7px;z-index:99;max-width:230px;line-height:1.45}
details{margin-top:10px}
summary{cursor:pointer;font-size:12px;color:var(--text-secondary);
 padding:5px 0;list-style:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸ ";color:var(--muted)}
details[open]>summary::before{content:"▾ "}
/* --- team value curve --- */
.curve{display:flex;align-items:flex-end;gap:2px;height:132px;
 padding-top:20px;position:relative}
.cb{flex:1;min-width:9px;display:flex;flex-direction:column;
 justify-content:flex-end;align-items:stretch;height:100%;position:relative}
.cb i{display:block;background:var(--series-1);border-radius:4px 4px 0 0;
 min-height:2px}
.cb.bye i{background:transparent;
 background-image:repeating-linear-gradient(45deg,transparent,transparent 3px,
 var(--grid) 3px,var(--grid) 4px);height:6px !important;border-radius:0}
.cb.here i{box-shadow:inset 0 0 0 2px var(--surface-1),0 0 0 1.5px var(--text-primary)}
.cb.peak i{box-shadow:inset 0 0 0 2px var(--surface-1),0 0 0 1.5px var(--good)}
.cb b{position:absolute;top:-17px;left:50%;transform:translateX(-50%);
 font-size:9px;font-weight:600;white-space:nowrap;color:var(--text-secondary)}
.cb.edgeL b{left:0;transform:none}
.cb.edgeR b{left:auto;right:0;transform:none}
.cx{display:flex;gap:2px;margin-top:5px}
.cx span{flex:1;min-width:9px;text-align:center;font-size:8.5px;color:var(--muted)}
.cx span.on{color:var(--series-1);font-weight:700}
/* --- comparison table --- */
.cmp th{cursor:pointer;user-select:none}
.cmp th.sorted{color:var(--text-primary)}
.cmp tbody tr.sel td{background:color-mix(in srgb,var(--series-1) 10%,transparent)}
.cmp tbody tr.gone{opacity:.45}
.spark{display:inline-flex;align-items:flex-end;gap:1px;height:16px;width:74px}
.spark i{flex:1;background:var(--series-1);border-radius:1px;min-height:1px;
 opacity:.55}
.spark i.pk{opacity:1;background:var(--good)}
.pill{display:inline-block;font-size:9.5px;padding:1px 5px;border-radius:4px;
 background:var(--plane);border:1px solid var(--border);
 color:var(--text-secondary)}
.why{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
.wy{background:var(--plane);border:1px solid var(--border);border-radius:10px;
 padding:11px 12px;font-size:11.5px;line-height:1.55;color:var(--text-secondary)}
.wy b{color:var(--text-primary)}
.wy .h{font-size:10.5px;color:var(--muted);text-transform:uppercase;
 letter-spacing:.05em;margin-bottom:5px}
/* --- per-team detail cards --- */
.tcard{background:var(--plane);border:1px solid var(--border);border-radius:10px;
 padding:0 12px;margin-top:8px}
.tcard>summary{padding:10px 0;font-size:13px;color:var(--text-primary);
 display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.tcard>summary .rk{font-size:11px;color:var(--muted);min-width:18px}
.tcard>summary .mu{font-size:11.5px;color:var(--text-secondary)}
.tcard>summary .wp{margin-left:auto;font-size:11.5px;color:var(--text-secondary);
 font-variant-numeric:tabular-nums}
.tcard[open]{border-color:var(--axis)}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));
 gap:8px;padding:2px 0 12px}
.kv div{background:var(--surface-1);border:1px solid var(--border);
 border-radius:8px;padding:7px 9px}
.kv .k{font-size:9.5px;color:var(--muted);text-transform:uppercase;
 letter-spacing:.04em}
.kv .v{font-size:14px;font-weight:600;margin-top:2px;
 font-variant-numeric:tabular-nums}
.kv .n{font-size:10.5px;color:var(--text-secondary);margin-top:2px;
 line-height:1.4;white-space:normal}
.gloss{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));
 gap:7px 16px;margin-top:12px;font-size:11px;line-height:1.5;
 color:var(--muted)}
.gloss b{color:var(--text-secondary);font-weight:600}
.warn{display:flex;gap:8px;align-items:flex-start;background:var(--plane);
 border:1px solid var(--border);border-left:3px solid var(--warning);
 border-radius:8px;padding:10px 12px;font-size:11.5px;line-height:1.55;
 color:var(--text-secondary);margin-top:12px}
.ok{border-left-color:var(--good)}
@media (max-width:560px){
  .tile .v{font-size:20px}
  .wrap{padding:12px 10px 48px}
}
"""

# Enhancement only. Everything below assumes the page already renders without it.
JS = r"""
(function(){
  var D = window.__DATA__ || {};
  var tip = document.getElementById('tip');
  function pct(x,d){ return (100*x).toFixed(d===undefined?1:d) + '%'; }

  function bindTip(el, html){
    function show(e){
      tip.innerHTML = html; tip.style.opacity = 1;
      var t = e.touches ? e.touches[0] : e;
      var w = tip.offsetWidth, h = tip.offsetHeight;
      var x = t.clientX + 12, y = t.clientY - h - 10;
      if (x + w > innerWidth - 8) x = innerWidth - w - 8;
      if (y < 8) y = t.clientY + 16;
      tip.style.left = x + 'px'; tip.style.top = y + 'px';
    }
    el.addEventListener('mouseenter', show);
    el.addEventListener('mousemove', show);
    el.addEventListener('touchstart', show, {passive:true});
    el.addEventListener('mouseleave', function(){ tip.style.opacity = 0; });
    el.addEventListener('touchend', function(){
      setTimeout(function(){ tip.style.opacity = 0; }, 1600); });
  }

  // tooltips come from data-tip attributes the server already wrote
  document.querySelectorAll('[data-tip]').forEach(function(el){
    bindTip(el, el.getAttribute('data-tip').replace(/\|/g, '<br>'));
  });

  // click a comparison row to jump to that team's value chart. Every chart is
  // already in the page (the extras live in a <details>), so this opens the
  // disclosure and scrolls -- it never has to draw anything.
  document.querySelectorAll('#cmp tbody tr[data-t]').forEach(function(tr){
    tr.style.cursor = 'pointer';
    tr.addEventListener('click', function(){
      var t = tr.dataset.t;
      var target = document.querySelector('[data-team="' + t + '"].chart');
      if (!target) return;
      var d = target.closest('details');
      if (d) d.open = true;
      target.scrollIntoView({behavior:'smooth', block:'center'});
      document.querySelectorAll('#cmp tbody tr').forEach(function(x){
        x.classList.toggle('sel', x === tr);
      });
    });
  });

  // column sorting
  var tbl = document.querySelector('#cmp table');
  if (tbl){
    var dir = {};
    tbl.querySelectorAll('th[data-c]').forEach(function(th){
      th.addEventListener('click', function(){
        var c = th.dataset.c;
        // First click on a number sorts DESCENDING -- "who has the most of
        // this" is the question being asked, so the interesting rows belong
        // at the top. Only the team-name column starts ascending.
        if (!(c in dir)) dir[c] = (c === 'team');
        else dir[c] = !dir[c];
        var body = tbl.tBodies[0];
        var rows = Array.prototype.slice.call(body.rows);
        rows.sort(function(a,b){
          var x = a.dataset[c], y = b.dataset[c];
          var nx = parseFloat(x), ny = parseFloat(y);
          if (!isNaN(nx) && !isNaN(ny)) return dir[c] ? nx - ny : ny - nx;
          x = x || ''; y = y || '';
          return dir[c] ? x.localeCompare(y) : y.localeCompare(x);
        });
        rows.forEach(function(r){ body.appendChild(r); });
        tbl.querySelectorAll('th').forEach(function(h){ h.classList.remove('sorted'); });
        th.classList.add('sorted');
      });
    });
  }

  var tog = document.getElementById('tog');
  if (tog){
    tog.hidden = false;
    tog.addEventListener('click', function(){
      var dark = document.documentElement.dataset.theme === 'dark' ||
        (!document.documentElement.dataset.theme &&
         matchMedia('(prefers-color-scheme: dark)').matches);
      document.documentElement.dataset.theme = dark ? 'light' : 'dark';
    });
  }
})();
"""
