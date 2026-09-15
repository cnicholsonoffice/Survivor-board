"""Server-side HTML fragments. Every number the dashboard shows is written
here, in Python, into static markup.

The rule this file exists to enforce: if the browser never runs a line of
script, the page still contains all the data. Tooltips are emitted as
`data-tip` attributes so the optional JS layer can pick them up, but the
same information is always present in the visible table too.
"""
from __future__ import annotations

import os

# Hover tooltips are emitted as data-tip attributes for the optional JS layer.
# They cost ~86KB on a full board and do nothing at all in a viewer that does
# not execute scripts -- which is the viewer this dashboard is actually read
# in. Everything a tooltip would say is already visible in the tables, so they
# are off unless explicitly switched on.
TOOLTIPS = os.environ.get("SURVIVOR_TOOLTIPS", "0") == "1"


def tip_attr(text: str) -> str:
    return f' data-tip="{text}"' if TOOLTIPS else ""


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def pct(x, d=1) -> str:
    if x is None:
        return "—"
    return f"{100*float(x):.{d}f}%"


def leg_short(k: str) -> str:
    return "Thx" if k == "TG" else "Xmas" if k == "XM" else k


def leg_axis(k: str) -> str:
    return "T" if k == "TG" else "X" if k == "XM" else k[1:]


def leg_name(payload: dict, k: str | None) -> str:
    if not k:
        return "—"
    if k == "TG":
        return "Thanksgiving"
    if k == "XM":
        return "Christmas"
    L = next((l for l in payload["legs"] if l["key"] == k), None)
    return L["label"] if L else k


def pts(x) -> str:
    """A gap in percentage points, e.g. '1 pt' / '24 pts'."""
    n = round((x or 0) * 100)
    return f"{n} pt" if n == 1 else f"{n} pts"


def spread_str(sp: float) -> str:
    return f"-{sp:.1f}" if sp > 0 else f"+{-sp:.1f}"


def money_str(ml) -> str:
    """A moneyline the way a book writes it: -450 / +320."""
    if ml is None:
        return "—"
    try:
        n = int(round(float(ml)))
    except (TypeError, ValueError):
        return "—"
    return f"+{n}" if n > 0 else str(n)


def src_badge(src: str) -> str:
    """Flag only the rows that did NOT come from a moneyline.

    Tagging every row "money" restates the column header 32 times; the useful
    signal is the exception -- a probability that came from a spread, or from
    the ratings because nothing is posted yet.
    """
    if src == "ml":
        return ""
    label = "spread" if src == "line" else "proj"
    cls = "" if src == "line" else " proj"
    return f'<span class="badge{cls}" style="margin-left:5px">{label}</span>'


# ---------------------------------------------------------------------------

def tile(k: str, v: str, d: str = "", hero: bool = False) -> str:
    sub = f'<div class="d">{d}</div>' if d else ""
    return (f'<div class="tile{" hero" if hero else ""}"><div class="k">{k}</div>'
            f'<div class="v">{v}</div>{sub}</div>')


def _game_key(r) -> tuple:
    opp = str(r["opponent"]).replace("vs", "").replace("@", "").strip()
    return tuple(sorted([r["team"], opp]))


def picks_table(payload: dict) -> str:
    R = payload["ranked"]
    best = R[0]["path_prob"]
    # "Usable" = how many remaining legs this team is still a real option in.
    # Comes from the team profiles, which count the legs where it clears the
    # same win-probability bar the planner uses.
    usable = {p["team"]: p.get("windows")
              for p in (payload.get("profiles") or [])}

    # ONE ROW PER TEAM, every team playing, ranked best first, in a box that
    # scrolls. Earlier versions cut the list or folded half of it into a
    # disclosure, and both made the table's length read as a count of
    # something -- which it never was. Showing all of them with contiguous
    # ranks removes the ambiguity: the last number IS the number of teams.
    head = ('<thead><tr><th class="l">#</th><th class="l">Pick</th>'
            '<th class="l">Matchup</th><th>Moneyline</th><th>Spread</th>'
            '<th>Win%</th>'
            '<th class="l">Season equity if picked</th><th>Kept</th>'
            '<th>Usable</th><th>Est. field</th><th>EV#</th></tr></thead>')

    def row(r):
        w = max(3.0, 100 * r["path_prob"] / best)
        tipt = (f'{esc(r["name"])} {esc(r["opponent"])}'
                f'|wins this week {pct(r["win_prob"])}'
                f'|runs the table from here {pct(r["path_prob"],3)}'
                f'|keeps {pct(r["future_cost"],0)} of best-case season equity'
                f'|est. {pct(r["pick_share"],0)} of the field · EV rank {r["ev_rank"]}')
        ev_col = ("var(--good)" if r["ev_rank"] < r["rank"]
                  else "var(--text-secondary)")
        return (
            f'<tr class="{"best" if r["rank"]==1 else ""}">'
            f'<td>{r["rank"]}</td>'
            f'<td class="l"><span class="tm">{esc(r["team"])}</span></td>'
            f'<td class="l" style="color:var(--text-secondary)">{esc(r["opponent"])}</td>'
            f'<td>{money_str(r.get("moneyline", r.get("ml")))}{src_badge(r["source"])}</td>'
            f'<td>{spread_str(r["spread"])}</td>'
            f'<td>{pct(r["win_prob"])}</td>'
            f'<td class="bar"{tip_attr(tipt)}><i style="width:{w:.0f}%"></i></td>'
            f'<td>{pct(r["future_cost"],0)}</td>'
            f'<td>{usable.get(r["team"]) if usable.get(r["team"]) is not None else "—"}</td>'
            f'<td>{pct(r["pick_share"],0)}</td>'
            f'<td style="color:{ev_col}">{r["ev_rank"]}</td></tr>')

    gloss = (
        '<div class="gloss">'
        '<div><b>Win%</b> — chance this team wins its own game this week, '
        'taken from the moneyline with the bookmaker\'s margin removed. A row '
        'is only tagged when it came from somewhere else: <b>spread</b> means '
        'no moneyline was posted so the points line was converted instead, '
        '<b>proj</b> means nothing is posted yet and it is projected from '
        'power ratings.</div>'
        '<div><b>Spread</b> — the posted points line, shown for reference. It '
        'no longer drives the maths when a moneyline exists.</div>'
        '<div><b>Season equity if picked</b> — the bar. Your chance of going '
        '20-0 across the whole contest if you spend this team now and play '
        'perfectly after. Tiny by nature: the best bar on the board is under '
        '1%.</div>'
        '<div><b>Kept</b> — that bar as a share of the best bar. 100% means '
        'the pick costs you nothing. 85% means choosing it throws away 15% of '
        'what your entry is currently worth.</div>'
        '<div><b>Usable</b> — how many of the remaining legs this team is '
        'still a genuine option in, counting every leg where it is at least '
        '65% to win. A 1 is a warning: spend them now or you will probably '
        'never get to spend them at all. A high number means they keep, so '
        'there is no rush.</div>'
        '<div><b>Est. field</b> — modelled guess at what share of the ~24,900 '
        'live entries take this team. Circa does not publish this before the '
        'deadline, but it does publish the result afterwards, and the estimate '
        'is now fitted to the Week 1 selections rather than guessed. Still a '
        'rough shape, not a number to lean on hard.</div>'
        '<div><b>EV#</b> — rank once prize-splitting is priced in: winning '
        'alongside fewer people is worth more. Green means it ranks better '
        'here than on survival alone. It is a tiebreaker, not a headline.</div>'
        f'<div><b>#</b> — rank out of all {len(R)} teams playing this leg, best '
        'season outcome first. Every team is listed; both sides of a matchup '
        'appear, since either one is a legal pick.</div>'
        '</div>')
    n_games = len({_game_key(r) for r in R})
    body = "".join(row(r) for r in R)
    return (f'<p class="note" style="margin:0 0 8px">All <b>{len(R)}</b> teams '
            f'playing this leg — {n_games} games, both sides of each — ranked '
            f'by what picking them does to your season. Scroll inside the box '
            f'for the rest.</p>'
            f'<div class="scroll tall"><table>{head}<tbody>{body}</tbody>'
            f'</table></div>' + gloss)


def team_cards(payload: dict) -> str:
    """One expandable card per team playing this week, with every number."""
    prof_by = {p["team"]: p for p in payload["profiles"]}
    out = []
    for r in payload["ranked"]:
        p = prof_by.get(r["team"], {})
        bu = p.get("best_use_leg")
        is_peak = bu == payload["leg_key"]
        unr = p.get("use_now_ratio")
        second = p.get("raw_best_leg")

        # notes only on the first card: the same ten sentences repeated on all
        # 32 cards cost 30KB and read as noise after the first time
        show_notes = r["rank"] == 1

        def cell(k, v, n=""):
            note = f'<div class="n">{n}</div>' if (n and show_notes) else ""
            return f'<div><div class="k">{k}</div><div class="v">{v}</div>{note}</div>'

        body = "".join([
            cell("Wins this week", pct(r["win_prob"]),
                 f'{money_str(r.get("moneyline", r.get("ml")))} · {spread_str(r["spread"])} — '
                 + {"ml": "de-vigged from the posted moneyline",
                    "line": "converted from the posted spread",
                    }.get(r["source"], "projected from power ratings")),
            cell("Runs the table", pct(r["path_prob"], 3),
                 "probability of going 20-0 if you pick them now"),
            cell("Season equity kept", pct(r["future_cost"], 0),
                 "100% means the pick costs you nothing"),
            cell("Best use", leg_short(bu) if bu else "—",
                 (f'this week is their peak slot'
                  if is_peak else
                  f'their peak is {leg_name(payload, bu)} at '
                  f'{pct(p.get("best_use_winprob"),0)}')),
            cell("Value captured now", "peak" if (unr and unr > 0.999) else pct(unr, 0),
                 "share of what this team is worth that you collect by "
                 "spending them this week"),
            cell("Raw peak", leg_short(second) if second else "—",
                 f'{pct(p.get("raw_best_winprob"),0)} — their highest win '
                 f'probability of the season, ignoring competition'),
            cell("Held back", ("—" if (p.get("reserve_gap") or 0) <= 0.005
                               else pts(p.get("reserve_gap"))),
                 "percentage points of win probability this team gives up by "
                 "being saved for the leg that actually needs them. Never "
                 "negative — it is a gap, not a change"),
            cell("Windows", p.get("windows", "—"),
                 "legs where they clear 65%. Few windows = reserve them"),
            cell("Scarcity", pct(p.get("scarcity"), 0),
                 "share of your season lost if this team vanished"),
            cell("Est. field on them", pct(r["pick_share"], 0),
                 f'modelled, not observed · EV rank {r["ev_rank"]}'),
        ])
        flag = ""
        if not is_peak and unr is not None and unr < 0.9:
            flag = (f'<div class="warn" style="margin:0 0 12px">'
                    f'<span>⚠</span><div>This is not {esc(r["team"])}\'s best slot. '
                    f'Spending them now captures {pct(unr,0)} of what they are '
                    f'worth — their value peaks in '
                    f'<b>{leg_name(payload, bu)}</b>.</div></div>')
        out.append(
            f'<details class="tcard"><summary>'
            f'<span class="rk">{r["rank"]}</span>'
            f'<span class="tm">{esc(r["team"])}</span>'
            f'<span class="mu">{esc(r["opponent"])} · {spread_str(r["spread"])}</span>'
            f'<span class="wp">{pct(r["win_prob"])} · keeps '
            f'{pct(r["future_cost"],0)}</span>'
            f'</summary>{flag}<div class="kv">{body}</div></details>')
    return "".join(out)


def heat(payload: dict) -> str:
    H = payload["heat"]
    plan = payload.get("recommended_plan", {}) or {}
    used = set(payload.get("used", []))
    usage = (payload.get("mc", {}) or {}).get("team_usage", {}) or {}
    cur = payload["leg_key"]
    keys = H["keys"]
    idx_of = {t: i for i, t in enumerate(H["teams"])}
    order = sorted(H["teams"], key=lambda t: (-(usage.get(t, -1)), t))

    lo, hi = 0.35, 0.90

    def step(p):
        t = max(0.0, min(1.0, (p - lo) / (hi - lo)))
        return 1 + round(t * 6)

    th = '<th class="rl"></th>' + "".join(
        f'<th class="{"now" if k==cur else ""}">{leg_axis(k)}</th>' for k in keys)
    rows = []
    for t in order:
        i = idx_of[t]
        tds = [f'<td class="rl{" used" if t in used else ""}">{esc(t)}</td>']
        for j, k in enumerate(keys):
            p = H["p"][i][j]
            if p is None:
                tds.append('<td><div class="cell na"></div></td>')
                continue
            cls = f'cell c{step(p)}'
            if plan.get(k) == t:
                cls += " inplan"
            if t in used:
                cls += " used"
            src = {"ml": "posted moneyline", "line": "posted spread"}.get(
                H["src"][i][j], "projected from ratings")
            tipt = (f'{esc(t)} {esc(H["opp"][i][j])}|{esc(leg_name(payload,k))}'
                    f'|win probability {pct(p)}|{src}'
                    + ("|in the plan" if plan.get(k) == t else ""))
            tds.append(f'<td><div class="{cls}"{tip_attr(tipt)}>'
                       f'{round(p*100)}</div></td>')
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return (f'<div class="scroll"><table class="heat"><thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def curve(payload: dict, team: str, hidden: bool = False) -> str:
    """The season-value bar chart for one team, fully static."""
    curves = payload.get("curves", {}).get(team, {})
    probs = payload.get("team_probs", {}).get(team, {})
    prof = next((p for p in payload["profiles"] if p["team"] == team), {})
    peak = prof.get("best_use_leg")
    cur = payload["leg_key"]
    legs = [L for L in payload["legs"] if L["order"] >= payload["leg_order"]]
    vals = [curves.get(L["key"]) for L in legs]
    mx = max([v for v in vals if v is not None] + [1e-12])

    bars = []
    for i, L in enumerate(legs):
        k, v = L["key"], vals[i]
        if v is None:
            bars.append(f'<div class="cb bye"'
                        f'{tip_attr(esc(team) + "|" + esc(leg_name(payload,k)) + " — bye week")}'
                        f'><i></i></div>')
            continue
        h = max(2.0, 100 * v / mx)
        cls = "cb"
        if k == cur:
            cls += " here"
        if k == peak:
            cls += " peak"
        if i < 3:
            cls += " edgeL"
        elif i > len(legs) - 4:
            cls += " edgeR"
        lab = ("<b>best use = now</b>" if (k == peak and k == cur)
               else "<b>best use</b>" if k == peak
               else "<b>this week</b>" if k == cur else "")
        tipt = (f'{esc(team)}|{esc(leg_name(payload,k))}'
                f'|wins that game {pct(probs.get(k))}'
                f'|season worth {pct(v,3)} if spent here'
                + ("|their best use" if k == peak else ""))
        bars.append(f'<div class="{cls}"{tip_attr(tipt)}>{lab}'
                    f'<i style="height:{h:.0f}%"></i></div>')
    axis = "".join(f'<span class="{"on" if L["key"]==cur else ""}">'
                   f'{leg_axis(L["key"])}</span>' for L in legs)

    gap = prof.get("reserve_gap") or 0
    title = (f'<b>{esc(team)}</b> is worth the most in '
             f'<b>{esc(leg_name(payload, peak))}</b>'
             f' — {pct(prof.get("best_use_winprob"),0)} to win that game')
    if gap > 0.04:
        title += (f', even though they peak at '
                  f'{pct(prof.get("raw_best_winprob"),0)} in '
                  f'{esc(leg_name(payload, prof.get("raw_best_leg")))}. '
                  f'Held back on purpose.')
    else:
        title += "."
    return (f'<div class="chart" data-team="{esc(team)}"'
            f'{" hidden" if hidden else ""}>'
            f'<h3 style="font-size:13px;color:var(--text-primary);margin:0 0 10px">'
            f'{title}</h3>'
            f'<div class="curve">{"".join(bars)}</div>'
            f'<div class="cx">{axis}</div></div>')


def spark(payload: dict, team: str) -> str:
    curves = payload.get("curves", {}).get(team, {})
    prof = next((p for p in payload["profiles"] if p["team"] == team), {})
    peak = prof.get("best_use_leg")
    legs = [L for L in payload["legs"] if L["order"] >= payload["leg_order"]]
    vals = [curves.get(L["key"], 0) or 0 for L in legs]
    mx = max(vals + [1e-12])
    pk = ' class="pk"'
    return '<span class="spark">' + "".join(
        f'<i{pk if L["key"] == peak else ""}'
        f' style="height:{max(4.0, 100*vals[i]/mx):.0f}%"></i>'
        for i, L in enumerate(legs)) + "</span>"


def compare_table(payload: dict) -> str:
    rows = []
    for p in payload["profiles"]:
        unr = p.get("use_now_ratio")
        now = ("<span style='color:var(--muted)'>bye</span>" if unr is None
               else "<span style='color:var(--good)'>peak</span>" if unr > 0.999
               else pct(unr, 0))
        held = ("—" if (p.get("reserve_gap") or 0) <= 0.005
                else f'<span style="color:var(--serious)">'
                     f'{pts(p["reserve_gap"])}</span>')
        sc = (pct(p["scarcity"], 0) if p.get("scarcity", 0) > 0.002
              else "<span style='color:var(--muted)'>—</span>")
        rows.append(
            f'<tr data-t="{esc(p["team"])}" '
            f'class="{"" if p.get("in_plan") else "gone"}" '
            f'data-bestuse="{p["best_use_value"]:.10f}" '
            f'data-rawpeak="{p["raw_best_winprob"]:.6f}" '
            f'data-held="{p.get("reserve_gap",0):.6f}" '
            f'data-windows="{p.get("windows",0)}" '
            f'data-scarcity="{p.get("scarcity",0):.6f}" '
            f'data-now="{-1 if unr is None else unr:.6f}">'
            f'<td class="l"><span class="tm">{esc(p["team"])}</span></td>'
            f'<td class="l">{leg_short(p["best_use_leg"])} '
            f'<span class="pill">{pct(p["best_use_winprob"],0)}</span></td>'
            f'<td class="l">{leg_short(p["raw_best_leg"])} '
            f'<span class="pill">{pct(p["raw_best_winprob"],0)}</span></td>'
            f'<td>{held}</td><td>{p.get("windows","—")}</td><td>{sc}</td>'
            f'<td>{now}</td>'
            f'<td class="l">{spark(payload, p["team"])}</td></tr>')
    head = ('<thead><tr>'
            '<th class="l" data-c="team">Team</th>'
            '<th class="l sorted" data-c="bestuse">Best use</th>'
            '<th class="l" data-c="rawpeak">Raw peak</th>'
            '<th data-c="held">Held back</th>'
            '<th data-c="windows">Windows</th>'
            '<th data-c="scarcity">Scarcity</th>'
            '<th data-c="now">Spend now?</th>'
            '<th class="l" data-c="bestuse">Value by leg</th></tr></thead>')
    return (f'<div class="scroll" id="cmp"><table class="cmp">{head}'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def plan_strip(payload: dict) -> str:
    plan = payload.get("recommended_plan", {}) or {}
    picks = payload.get("picks", {}) or {}
    hist = payload.get("history", {}) or {}
    H = payload["heat"]
    ti = {t: i for i, t in enumerate(H["teams"])}
    ki = {k: j for j, k in enumerate(H["keys"])}
    out = []
    for L in payload["legs"]:
        k = L["key"]
        done = L["order"] < payload["leg_order"]
        t = picks.get(k) if done else plan.get(k)
        rec = hist.get(k, {})
        won = rec.get("won")
        cls = "pl"
        if done:
            cls += " done"
            if won is True:
                cls += " won"
            elif won is False:
                cls += " lost"
        if L["order"] == payload["leg_order"]:
            cls += " now"
        p = None
        if t and t in ti and k in ki:
            p = H["p"][ti[t]][ki[k]]
        shown = rec.get("win_prob") if done and rec.get("win_prob") else p
        out.append(f'<div class="{cls}"><div class="lg">{esc(leg_short(k))}</div>'
                   f'<div class="tm">{esc(t or "—")}</div>'
                   f'<div class="p">{pct(shown,0) if shown else "&nbsp;"}</div></div>')
    return f'<div class="plan">{"".join(out)}</div>'


def sec(sid: str, title: str, body: str, open_: bool = False) -> str:
    """A collapsible section.

    <details>/<summary> is native HTML: it opens and closes on click with no
    script at all, which is the only reason this dashboard can be both
    collapsible and readable in a viewer that runs nothing.
    """
    return (f'<details class="sec" id="{sid}"{" open" if open_ else ""}>'
            f'<summary><h2>{title}</h2><span class="chev" aria-hidden="true">'
            f'</span></summary><div class="secbody">{body}</div></details>')


def schedule_table(payload: dict) -> str:
    """Who plays whom, every team, every leg. Opponent only -- the win
    probabilities live in the heat map and repeating them here just makes a
    denser version of a table that already exists."""
    H = payload["heat"]
    keys = H["keys"]
    cur = payload["leg_key"]
    used = set(payload.get("used", []))
    plan = payload.get("recommended_plan", {}) or {}
    idx_of = {t: i for i, t in enumerate(H["teams"])}

    th = '<th class="rl">Team</th>' + "".join(
        f'<th class="{"now" if k == cur else ""}">{leg_axis(k)}</th>' for k in keys)
    rows = []
    for t in sorted(H["teams"]):
        i = idx_of[t]
        tds = [f'<td class="rl{" used" if t in used else ""}">{esc(t)}</td>']
        for j, k in enumerate(keys):
            opp = H["opp"][i][j]
            if not opp or H["p"][i][j] is None:
                tds.append('<td class="bye">bye</td>')
                continue
            away = str(opp).strip().startswith("@")
            name = str(opp).replace("vs", "").replace("@", "").strip()
            cls = "aw" if away else "hm"
            if plan.get(k) == t:
                cls += " inplan"
            tds.append(f'<td class="{cls}">{"@" if away else ""}{esc(name)}</td>')
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return (f'<div class="scroll"><table class="sched"><thead><tr>{th}</tr>'
            f'</thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'<div class="legend"><span>Plain = home · @ = away · '
            f'T = Thanksgiving · X = Christmas · outlined = the plan uses them '
            f'that leg · faded team = already used</span></div>')


def ladder_static(payload: dict) -> str:
    """The scripts-off version of the answer boxes.

    One disclosure per remaining leg, each listing what that choice does to the
    season *given the recommended plan up to that point*. It cannot branch --
    that is what the live version is for -- but every number in it is real.
    """
    lad = payload.get("ladder", []) or []
    if not lad:
        return '<p class="note">No remaining legs to explore.</p>'
    best_overall = payload["base_survival"]
    out = []
    for i, L in enumerate(lad):
        rows = "".join(
            f'<tr class="{"best" if j == 0 else ""}">'
            f'<td class="l"><span class="tm">{esc(r["team"])}</span></td>'
            f'<td class="l" style="color:var(--text-secondary)">'
            f'{esc(r["opponent"])}</td>'
            f'<td>{money_str(r.get("ml"))}</td>'
            f'<td>{spread_str(r["spread"])}</td>'
            f'<td>{pct(r["win_prob"])}</td>'
            f'<td>{pct(r["path_prob"], 3)}</td>'
            f'<td>{pct(r["kept"], 0)}</td></tr>'
            for j, r in enumerate(L["rows"]))
        head = ('<thead><tr><th class="l">Take</th><th class="l">Matchup</th>'
                '<th>Moneyline</th><th>Spread</th><th>Win%</th>'
                '<th>Season equity</th><th>Kept</th></tr></thead>')
        more = (f' · {L["n_candidates"] - len(L["rows"])} more not shown'
                if L["n_candidates"] > len(L["rows"]) else "")
        out.append(
            f'<details class="lg-box"{" open" if i == 0 else ""}>'
            f'<summary><span class="lgk">{esc(leg_short(L["leg"]))}</span>'
            f'<span class="lgn">{esc(leg_name(payload, L["leg"]))}</span>'
            f'<span class="lgp">plan: <b>{esc(L["planned"] or "—")}</b></span>'
            f'</summary>'
            f'<div class="scroll"><table>{head}<tbody>{rows}</tbody></table></div>'
            f'<p class="note" style="margin:8px 0 0">Assumes the plan is '
            f'followed for every leg before this one{more}.</p></details>')
    return (f'<p class="note">Best case if you follow the plan the whole way: '
            f'<b>{pct(best_overall, 3)}</b>. Each leg below shows what a '
            f'different choice at that leg would do to it.</p>'
            + "".join(out))


def history_section(payload: dict) -> str:
    """The modelled entry's archive.

    Only the primary entry is modelled -- the board, the plan and the sandbox
    are all solved for it alone, and it is now the only one shown. Secondary
    entries stay archived in state.json for the record but are not rendered,
    so nothing on the page can be misread as something the optimizer
    accounted for.
    """
    entries = payload.get("entries")
    if not entries:                                  # single-entry state file
        entries = [{"key": "entry", "label": payload.get("entry", {}).get(
            "label", "Entry"), "history": payload.get("history", {}) or {},
            "picks": payload.get("picks", {}) or {}, "active": True}]
    active_key = (payload.get("entry") or {}).get("key")
    # Season so far shows the modelled (primary) entry only. Secondary entries
    # are still archived in state.json, they are just no longer displayed.
    if active_key:
        entries = [e for e in entries if e.get("key") == active_key]
    out = []
    for e in entries:
        used = sorted(set((e.get("picks") or {}).values()))
        head = (f'<div class="ehead"><span class="elbl">{esc(e["label"])}</span>'
                + ('<span class="pill on">the model plans this one</span>'
                   if e.get("key") == active_key else
                   '<span class="pill">tracked only</span>')
                + ('<span class="pill out">eliminated</span>'
                   if e.get("eliminated") else "")
                + f'<span class="esub">{len(used)} of 20 teams used</span></div>')
        out.append(f'<div class="entry">{head}{_entry_history(payload, e)}</div>')
    return "".join(out)


def _entry_history(payload: dict, e: dict) -> str:
    hist = e.get("history", {}) or {}
    picks = e.get("picks", {}) or {}
    legs = [L for L in payload["legs"] if L["key"] in hist]
    if not legs:
        if picks:
            made = ", ".join(f'{leg_short(k)} {esc(v)}' for k, v in picks.items())
            return (f'<p class="note">Picks recorded ({made}) but no leg has '
                    f'finished yet — results fill in automatically once the '
                    f'games are played.</p>')
        return ('<p class="note">Nothing archived yet — this fills in as legs '
                'complete. Each finished leg is snapshotted with the pick you '
                'made, the win probability the model gave it at the time, the '
                'team it recommended, and the actual result. Tell me the team '
                'you submitted and the record writes itself.</p>')
    rows = []
    wins = 0
    for L in legs:
        k = L["key"]
        r = hist[k]
        won = r.get("won")
        mark = ("✓" if won is True else "✗" if won is False else "—")
        cls = "win" if won is True else "loss" if won is False else ""
        if won is True:
            wins += 1
        agreed = (r.get("recommended") == r.get("pick"))
        rows.append(
            f'<tr class="{cls}"><td class="l">{esc(leg_name(payload,k))}</td>'
            f'<td class="l"><span class="tm">{esc(r.get("pick","—"))}</span></td>'
            f'<td class="l" style="color:var(--text-secondary)">'
            f'{esc(r.get("opponent","—"))}</td>'
            f'<td>{pct(r.get("win_prob"))}</td>'
            f'<td class="l">{esc(r.get("score","—"))}</td>'
            f'<td>{mark}</td>'
            f'<td class="l" style="color:var(--text-secondary)">'
            f'{"same" if agreed else esc(r.get("recommended","—"))}</td>'
            f'<td>{pct(r.get("survival"),3)}</td></tr>')
    head = ('<thead><tr><th class="l">Leg</th><th class="l">Your pick</th>'
            '<th class="l">Matchup</th><th>Model gave it</th>'
            '<th class="l">Result</th><th>W/L</th>'
            '<th class="l">Model wanted</th><th>Season odds then</th>'
            '</tr></thead>')
    # Only legs with an actual result count. A pick that is locked but whose
    # game has not kicked off yet is not a loss, and counting it as one turned
    # "your Week 1 pick is in" into "0 of 1 legs survived".
    decided = [L for L in legs if hist[L["key"]].get("won") is not None]
    pending = len(legs) - len(decided)
    tail = (f' {pending} pick{"" if pending == 1 else "s"} locked but not '
            f'played yet.' if pending else '')
    if not decided:
        summary = (f'<p class="note"><b>{pending}</b> '
                   f'pick{"" if pending == 1 else "s"} locked, nothing played '
                   f'yet. The result and the running record appear here once '
                   f'the games finish.</p>')
    else:
        exp = sum(hist[L["key"]].get("win_prob") or 0 for L in decided)
        summary = (f'<p class="note"><b>{wins} of {len(decided)}</b> legs '
                   f'survived. The model expected {exp:.1f} wins from those '
                   f'picks, so you are running '
                   f'{"ahead of" if wins > exp else "behind" if wins < exp else "exactly at"} '
                   f'expectation — over this few legs that is noise, not '
                   f'signal.{tail}</p>')
    return (summary + f'<div class="scroll"><table>{head}'
            f'<tbody>{"".join(rows)}</tbody></table></div>')
