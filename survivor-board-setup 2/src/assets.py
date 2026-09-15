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
/* A long ranked list in its own scroll box: about 16 rows visible, header
   pinned. Pure CSS, so it behaves the same with scripts off. */
.scroll.tall{overflow-y:auto;max-height:544px;
 border:1px solid var(--grid);border-radius:9px}
.scroll.tall table{border-collapse:separate;border-spacing:0}
.scroll.tall th{position:sticky;top:0;z-index:2;background:var(--surface-1);
 padding:8px 6px;border-bottom:1px solid var(--axis)}
.scroll.tall td{border-bottom:1px solid var(--grid)}
.scroll.tall tbody tr:last-child td{border-bottom:none}
@media (max-width:560px){.scroll.tall{max-height:60vh}}
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

/* --- collapsible sections. Native disclosure elements: no JS involved. --- */
details.sec{background:var(--surface-1);border:1px solid var(--border);
 border-radius:12px;padding:0;margin-top:14px;scroll-margin-top:10px}
details.sec>summary{list-style:none;cursor:pointer;padding:13px 14px;
 display:flex;align-items:center;gap:8px;border-radius:12px}
details.sec>summary::-webkit-details-marker{display:none}
details.sec>summary:hover h2{color:var(--series-1)}
details.sec>summary h2{margin:0;flex:1}
details.sec .chev{width:8px;height:8px;flex:none;
 border-right:1.5px solid var(--axis);border-bottom:1.5px solid var(--axis);
 transform:rotate(45deg) translate(-2px,-2px)}
details.sec[open]>summary .chev{transform:rotate(-135deg) translate(-2px,-2px)}
details.sec[open]>summary{border-bottom:1px solid var(--grid);
 border-radius:12px 12px 0 0}
.secbody{padding:13px 14px 14px}

/* --- schedule grid --- */
.sched{border-collapse:separate;border-spacing:2px;font-size:9.5px}
.sched th{padding:0 0 4px;font-size:9px;text-align:center;border:none;
 color:var(--muted)}
.sched th.now{color:var(--series-1);font-weight:700}
.sched td{padding:2px 4px;border:none;text-align:center;border-radius:3px;
 background:var(--plane);color:var(--text-secondary);white-space:nowrap}
.sched td.hm{color:var(--text-primary);font-weight:600}
.sched td.aw{color:var(--text-secondary)}
.sched td.bye{background:transparent;color:var(--muted);opacity:.5}
.sched td.inplan{box-shadow:inset 0 0 0 1.5px var(--series-1)}
.sched .rl{font-size:10.5px;font-weight:600;color:var(--text-primary);
 text-align:left;position:sticky;left:0;background:var(--surface-1);z-index:1}
.sched .rl.used{opacity:.45}
.heat .rl.used{opacity:.45}

/* --- what-if answer boxes --- */
.lg-box{border:1px solid var(--border);border-radius:9px;margin-top:8px;
 background:var(--plane)}
.lg-box>summary{cursor:pointer;list-style:none;padding:9px 11px;display:flex;
 align-items:center;gap:9px;font-size:12px}
.lg-box>summary::-webkit-details-marker{display:none}
.lg-box .lgk{font-weight:700;min-width:34px}
.lg-box .lgn{color:var(--text-secondary);flex:1}
.lg-box .lgp{color:var(--muted);font-size:11px}
.lg-box>div.scroll,.lg-box>p{margin:0 11px 10px}
.wi-head{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;
 background:var(--plane);border:1px solid var(--border);border-radius:10px;
 padding:11px 12px;margin-bottom:12px}
.wi-head .big{font-size:23px;font-weight:600;letter-spacing:-.02em;
 font-variant-numeric:tabular-nums}
.wi-head .dl{font-size:12px;font-weight:600}
.wi-head .up{color:var(--good)} .wi-head .dn{color:var(--critical)}
.wi-head .lbl{font-size:10.5px;color:var(--muted);text-transform:uppercase;
 letter-spacing:.05em;width:100%}
.wi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(184px,1fr));
 gap:8px}
.wi-box{border:1px solid var(--border);border-radius:9px;background:var(--plane);
 padding:9px 10px}
.wi-box.picked{border-color:var(--series-1)}
.wi-box.next{border-style:dashed}
.wi-box .r1{display:flex;align-items:center;gap:6px;margin-bottom:6px}
.wi-box .lg{font-weight:700;font-size:11.5px;min-width:32px}
.wi-box .sm{font-size:10.5px;color:var(--muted);flex:1}
.wi-box .x{cursor:pointer;border:none;background:none;color:var(--muted);
 font-size:14px;line-height:1;padding:0 2px;font-family:inherit}
.wi-box .x:hover{color:var(--critical)}
.wi-box select{width:100%;font-family:inherit;font-size:12px;padding:5px 6px;
 border-radius:6px;border:1px solid var(--border);background:var(--surface-1);
 color:var(--text-primary)}
.wi-box .eq{font-size:10.5px;color:var(--text-secondary);margin-top:5px;
 font-variant-numeric:tabular-nums;min-height:14px}
.wi-note{font-size:11px;color:var(--muted);margin-top:10px;line-height:1.5}

/* --- one block per entry in the season archive --- */
.entry{border:1px solid var(--border);border-radius:10px;padding:11px 12px;
 margin-bottom:12px;background:var(--plane)}
.entry:last-child{margin-bottom:0}
.ehead{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:9px}
.ehead .elbl{font-size:13px;font-weight:700;letter-spacing:-.01em}
.ehead .esub{font-size:11px;color:var(--muted);margin-left:auto}
.pill.on{border-color:var(--series-1);color:var(--series-1)}
.pill.out{border-color:var(--critical);color:var(--critical)}
.entry .note{margin-bottom:0}
.wi-bar{height:6px;border-radius:3px;background:var(--grid);margin-top:8px;
 overflow:hidden}
.wi-bar i{display:block;height:100%;background:var(--series-1)}
@media (max-width:560px){
  .tile .v{font-size:20px}
  .wrap{padding:12px 10px 48px}
  .secbody{padding:11px 10px 12px}
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

  // ---- nav / deep links have to open the section they point at ------------
  function openTo(el){
    while (el && el !== document.body){
      if (el.tagName === 'DETAILS') el.open = true;
      el = el.parentElement;
    }
  }
  function openHash(){
    if (!location.hash) return;
    var el = document.querySelector(location.hash);
    if (!el) return;
    if (el.tagName === 'DETAILS') el.open = true;
    openTo(el.parentElement);
    el.scrollIntoView({block:'start'});
  }
  addEventListener('hashchange', openHash);
  openHash();

  // ---- the season sandbox --------------------------------------------------
  // Rectangular Hungarian (Jonker-Volgenant shortest augmenting path), rows =
  // legs, cols = teams, rows <= cols. Same assignment the Python solves, so
  // the numbers on screen match the ones in the static tables underneath.
  function hungarian(cost, nr, nc){
    var INF = 1e18, i, j;
    var u = new Float64Array(nr+1), v = new Float64Array(nc+1);
    var p = new Int32Array(nc+1), way = new Int32Array(nc+1);
    for (i = 1; i <= nr; i++){
      p[0] = i;
      var j0 = 0;
      var minv = new Float64Array(nc+1);
      var used = new Uint8Array(nc+1);
      for (j = 0; j <= nc; j++) minv[j] = INF;
      do {
        used[j0] = 1;
        var i0 = p[j0], delta = INF, j1 = -1;
        for (j = 1; j <= nc; j++){
          if (used[j]) continue;
          var cur = cost[(i0-1)*nc + (j-1)] - u[i0] - v[j];
          if (cur < minv[j]){ minv[j] = cur; way[j] = j0; }
          if (minv[j] < delta){ delta = minv[j]; j1 = j; }
        }
        if (j1 < 0) return null;
        for (j = 0; j <= nc; j++){
          if (used[j]){ u[p[j]] += delta; v[j] -= delta; }
          else minv[j] -= delta;
        }
        j0 = j1;
      } while (p[j0] !== 0);
      do { var jw = way[j0]; p[j0] = p[jw]; j0 = jw; } while (j0);
    }
    var res = new Int32Array(nr);
    for (i = 0; i < nr; i++) res[i] = -1;
    for (j = 1; j <= nc; j++) if (p[j]) res[p[j]-1] = j - 1;
    return res;
  }

  var G = D.grid;
  var host = document.getElementById('wi-live');
  var stat = document.getElementById('wi-static');
  if (G && host && G.keys && G.keys.length){
    var BIG = 60;
    var rowOf = {}; G.teams.forEach(function(t, i){ rowOf[t] = i; });
    var usedSet = {}; (D.used || []).forEach(function(t){ usedSet[t] = 1; });
    var pool0 = G.teams.filter(function(t){ return !usedSet[t]; });
    var legLabel = {}; (D.legs || []).forEach(function(L){ legLabel[L.key] = L.label; });
    var answers = {};

    function costAt(t, j){
      var pv = G.p[rowOf[t]][j];
      if (pv === null || pv === undefined || pv <= 0) return BIG;
      return Math.min(BIG, -Math.log(pv));
    }

    function solve(forced){
      var fixed = 0, plan = {}, openLegs = [], taken = {};
      var dup = false;
      G.keys.forEach(function(k, j){
        var t = forced[k];
        if (t){
          // one team, one leg -- forcing the same team twice is not a worse
          // line, it is an illegal one, and must not score at all
          if (taken[t] || usedSet[t]) dup = true;
          plan[k] = t; taken[t] = 1; fixed += costAt(t, j);
        }
        else openLegs.push(j);
      });
      if (dup) return {ok:false};
      var pool = pool0.filter(function(t){ return !taken[t]; });
      if (pool.length < openLegs.length) return {ok:false};
      if (openLegs.length){
        var nr = openLegs.length, nc = pool.length;
        var cost = new Float64Array(nr*nc);
        for (var r = 0; r < nr; r++)
          for (var c = 0; c < nc; c++)
            cost[r*nc + c] = costAt(pool[c], openLegs[r]);
        var asg = hungarian(cost, nr, nc);
        if (!asg) return {ok:false};
        for (var r2 = 0; r2 < nr; r2++){
          var c2 = asg[r2];
          if (c2 < 0) return {ok:false};
          plan[G.keys[openLegs[r2]]] = pool[c2];
          fixed += cost[r2*nc + c2];
        }
      }
      return {ok:true, p:Math.exp(-fixed), plan:plan};
    }

    function candidates(j){
      var out = [];
      pool0.forEach(function(t){
        var pv = G.p[rowOf[t]][j];
        if (pv === null || pv === undefined) return;
        var k = G.keys[j];
        for (var kk in answers) if (kk !== k && answers[kk] === t) return;
        out.push({t:t, p:pv, opp:G.opp[rowOf[t]][j]});
      });
      out.sort(function(a,b){ return b.p - a.p; });
      return out;
    }

    // Compare against the solver's OWN optimum, not the Python figure. They
    // agree to well under a tenth of a percent, but mixing the two makes the
    // recommended line read "-0.0% vs the plan", which looks like a bug.
    var base = solve({});
    var baseP = base.ok ? base.p : (D.base_survival || 0);

    function render(){
      var cur = solve(answers);
      var firstOpen = 0;
      while (firstOpen < G.keys.length && answers[G.keys[firstOpen]]) firstOpen++;
      var show = Math.min(G.keys.length, firstOpen + 1);

      var d = cur.ok ? (cur.p / baseP - 1) : -1;
      var dcls = d >= -0.0005 ? 'up' : 'dn';
      var dtxt = (Math.abs(d) < 0.0005) ? 'this is the plan'
               : ((d > 0 ? '+' : '') + (100*d).toFixed(1) + '% vs the plan');
      var head =
        '<div class="lbl">Season equity on this line</div>' +
        (cur.ok
          ? '<div class="big">' + (100*cur.p).toFixed(3) + '%</div>' +
            '<div class="dl ' + dcls + '">' + dtxt + '</div>' +
            '<div class="sm" style="font-size:11px;color:var(--muted)">' +
              'best possible from here is ' + (100*baseP).toFixed(3) + '%</div>'
          : '<div class="big">dead</div><div class="dl dn">this combination ' +
            'runs out of legal teams before the season ends</div>');
      if (cur.ok){
        var w = Math.max(2, Math.min(100, 100 * cur.p / baseP));
        head += '<div class="wi-bar" style="width:100%"><i style="width:' +
                w.toFixed(0) + '%"></i></div>';
      }

      var boxes = '';
      for (var i = 0; i < show; i++){
        var k = G.keys[i], chosen = answers[k] || '';
        var cands = candidates(i);
        var active = (i === firstOpen);
        var opts = '<option value="">— let the model choose —</option>';
        cands.forEach(function(c){
          var lab = c.t + '  ' + c.opp + '  ' + (100*c.p).toFixed(0) + '%';
          if (active){
            var trial = {}; for (var kk in answers) trial[kk] = answers[kk];
            trial[k] = c.t;
            var r = solve(trial);
            lab += r.ok ? '  → ' + (100*r.p).toFixed(3) + '%' : '  → dead';
          }
          opts += '<option value="' + c.t + '"' +
                  (c.t === chosen ? ' selected' : '') + '>' + lab + '</option>';
        });
        var planned = cur.ok ? cur.plan[k] : null;
        boxes +=
          '<div class="wi-box' + (chosen ? ' picked' : active ? ' next' : '') + '">' +
          '<div class="r1"><span class="lg">' +
            (k === 'TG' ? 'Thx' : k === 'XM' ? 'Xmas' : k) + '</span>' +
          '<span class="sm">' + (chosen ? 'your pick' :
            (planned ? 'plan: ' + planned : '')) + '</span>' +
          (chosen ? '<button class="x" data-clear="' + k + '" ' +
                    'title="remove this answer">&times;</button>' : '') +
          '</div>' +
          '<select data-leg="' + k + '">' + opts + '</select>' +
          '<div class="eq">' + (cands.length + ' teams play this leg') + '</div>' +
          '</div>';
      }

      var left = G.keys.length - show;
      var note = '<div class="wi-note">Answer a leg and the next one appears. ' +
        'Every number re-solves the whole remaining season against your ' +
        'answers, so the equity shown is what your line is actually worth — ' +
        'not this week\'s win probability.' +
        (left > 0 ? ' ' + left + ' more legs open up as you go.' : '') +
        ' Remove any answer with the × to re-open everything below it.</div>';

      host.innerHTML = '<div class="wi-head">' + head + '</div>' +
                       '<div class="wi-grid">' + boxes + '</div>' + note;

      host.querySelectorAll('select[data-leg]').forEach(function(s){
        s.addEventListener('change', function(){
          var k = s.dataset.leg;
          if (s.value) answers[k] = s.value; else delete answers[k];
          for (var kk in answers){
            if (G.keys.indexOf(kk) > G.keys.indexOf(k) && !s.value) delete answers[kk];
          }
          render();
        });
      });
      host.querySelectorAll('button[data-clear]').forEach(function(b){
        b.addEventListener('click', function(){
          var k = b.dataset.clear, ki = G.keys.indexOf(k);
          Object.keys(answers).forEach(function(kk){
            if (G.keys.indexOf(kk) >= ki) delete answers[kk];
          });
          render();
        });
      });
    }

    host.hidden = false;
    if (stat){
      stat.open = false;
      var sm = stat.querySelector('summary');
      if (sm) sm.textContent = 'Show the printable version of this (one table per leg)';
    }
    render();
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
