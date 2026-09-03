"""Assembles the dashboard. Thin: all markup comes from render.py.

The page is static HTML end to end. The JSON blob and the script tag at the
bottom are there only so the optional enhancement layer can add tooltips,
sorting and team-switching. Strip them and the dashboard is unchanged in
content.
"""
from __future__ import annotations

import json

import render as R
from assets import CSS, JS


def write_dashboard(payload: dict, path: str) -> str:
    ranked = payload["ranked"]
    top = ranked[0]
    mc = payload["mc"]
    meta = payload["meta"]
    diag = payload["diagnostics"]
    W = payload["why"]
    n_legs = len(payload["legs"])
    legs_left = n_legs - payload["leg_order"] + 1
    ev_top = min(ranked, key=lambda r: r["ev_rank"])
    second = ranked[1] if len(ranked) > 1 else None

    # ---- tiles ------------------------------------------------------------
    tiles = "".join([
        R.tile("Recommended pick", R.esc(top["team"]),
               f'{R.esc(top["opponent"])} · {R.spread_str(top["spread"])} · '
               f'wins {R.pct(top["win_prob"],0)}', hero=True),
        R.tile("Runs the table from here",
               f'{payload["base_survival"]*100:.3f}<small>%</small>',
               f'{mc["held_p10"]*100:.3f}% – {mc["held_p90"]*100:.3f}% once you '
               f'allow the ratings to be wrong'),
        R.tile("Legs left", f'{legs_left}<small> of {n_legs}</small>',
               f'{len(payload["available"])} teams still unused'),
        R.tile("Contrarian pick", R.esc(ev_top["team"]),
               f'est. {R.pct(ev_top["pick_share"],0)} of the field vs '
               f'{R.pct(top["pick_share"],0)} on {R.esc(top["team"])}')
        if ev_top["team"] != top["team"] else
        R.tile("Next best", R.esc(second["team"]) if second else "—",
               (f'costs {(1-second["path_prob"]/top["path_prob"])*100:.0f}% of '
                f'season equity · both rankings agree on {R.esc(top["team"])}')
               if second else ""),
    ])

    edge = ""
    if second:
        gap = top["path_prob"] / max(second["path_prob"], 1e-12) - 1
        edge = (f' {R.esc(second["team"])} is the next best and costs '
                f'{gap*100:.0f}% of season equity.')
    ev_line = (
        f'Both views land on <b>{R.esc(top["team"])}</b>.'
        if ev_top["team"] == top["team"] else
        f'Survival says <b>{R.esc(top["team"])}</b>; the contrarian view prefers '
        f'<b>{R.esc(ev_top["team"])}</b> ({R.pct(ev_top["pick_share"],0)} of the '
        f'field vs {R.pct(top["pick_share"],0)}), at the cost of '
        f'{(1-ev_top["path_prob"]/top["path_prob"])*100:.0f}% of season equity.')

    # ---- why-now cards ----------------------------------------------------
    peak_line = (
        f'This is <b>{R.esc(W["pick"])}’s best slot of the whole season.</b> '
        f'Spending them anywhere else is worse for your season, so there is '
        f'nothing to save them for.' if W["is_best_use"] else
        f'Careful: {R.esc(W["pick"])}’s best slot is '
        f'<b>{R.esc(R.leg_name(payload, W["best_use_leg"]))}</b>, not this week. '
        f'Using them now captures {R.pct(W["use_now_ratio"],0)} of what they '
        f'are worth.')
    redeploy = (
        f'you would use <b>{R.esc(W["alt_team"])}</b> this week at '
        f'{R.pct(W["alt_winprob"],0)} and push {R.esc(W["pick"])} to '
        f'<b>{R.esc(R.leg_name(payload, W["redeploy_leg"]))}</b> '
        f'({R.pct(W["redeploy_winprob"],0)})' if W["redeploy_leg"] else
        f'you would use <b>{R.esc(W["alt_team"])}</b> this week and never find '
        f'a better spot for {R.esc(W["pick"])} at all')
    raw_note = (
        f'Their raw win probability actually peaks in '
        f'{R.esc(R.leg_name(payload, W["raw_best_leg"]))} at '
        f'{R.pct(W["raw_best_winprob"],0)}, but that week has other cover and '
        f'this one does not.' if W["raw_best_leg"] != payload["leg_key"] else
        f'This is also their highest win probability of the season '
        f'({R.pct(W["raw_best_winprob"],0)}), so the two views agree.')
    spec = ("a specialist, so the window matters" if (W["windows"] or 0) <= 3
            else "flexible, so the timing is less delicate")
    why_cards = "".join([
        f'<div class="wy"><div class="h">Is this their best use?</div>{peak_line}</div>',
        f'<div class="wy"><div class="h">What saving them costs</div>'
        f'Hold {R.esc(W["pick"])} back and {redeploy} — that is '
        f'<b>{W["defer_cost"]*100:.0f}%</b> of your season equity gone to keep '
        f'an option you never get a better chance to use.</div>',
        f'<div class="wy"><div class="h">How replaceable they are</div>'
        f'Losing {R.esc(W["pick"])} entirely would cost '
        f'<b>{R.pct(W["scarcity"],0)}</b> of your season. They clear 65% in '
        f'<b>{W["windows"]}</b> of the {legs_left} remaining legs — {spec}.</div>',
        f'<div class="wy"><div class="h">Win probability vs. season value</div>'
        f'{raw_note}</div>',
    ])

    # ---- pre-rendered charts, one per team (JS just toggles visibility) ----
    # The recommended pick's chart is always visible. The other 31 live in a
    # <details>, which works with scripts off -- the JS layer only swaps which
    # one sits in the always-visible slot.
    charts = R.curve(payload, top["team"])
    others = "".join(
        R.curve(payload, p["team"]) + '<hr style="border:none;border-top:1px '
        'solid var(--grid);margin:14px 0">'
        for p in payload["profiles"] if p["team"] != top["team"])

    sc = payload.get("scarce_legs", [])
    scarce_rows = "".join(
        f'<tr><td class="l">{R.esc(R.leg_name(payload, s["leg"]))}</td>'
        f'<td>{s["candidates"]}</td><td>{s["playable"]}</td>'
        f'<td>{R.esc(s["best_available"])} {R.pct(s["best_available_p"],0)}</td>'
        f'<td class="l">{R.esc(s["assigned"] or "—")}</td></tr>' for s in sc)
    cal_rows = "".join(
        f'<tr><td>{R.pct(c["predicted"],0)}</td><td>{R.pct(c["actual"],0)}</td>'
        f'<td>{c["n"]}</td></tr>' for c in diag["calibration"])

    tg = next((l["games"] for l in payload["legs"] if l["key"] == "TG"), 0)
    xm = next((l["games"] for l in payload["legs"] if l["key"] == "XM"), 0)

    nav = "".join(f'<a href="#{a}">{t}</a>' for a, t in [
        ("week", "This week"), ("why", "Why this pick"), ("teams", "Team detail"),
        ("compare", "Compare all 32"), ("board", "Full board"),
        ("season", "Season so far"), ("method", "Method")])

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Circa Survivor {payload['season']} — {R.esc(payload['leg_label'])}</title>
<style>{CSS}</style></head>
<body class="viz-root"><div class="wrap">
<header>
  <div>
    <h1>Circa Survivor {payload['season']} — {R.esc(payload['leg_label'])}</h1>
    <div class="sub">Leg {payload['leg_order']} of {n_legs} · updated
      {R.esc(payload['generated'])} · {meta['n_lines']} posted lines,
      {meta['n_results']} results in the fit</div>
  </div>
  <button class="tog" id="tog" hidden>Light / dark</button>
</header>
<nav>{nav}</nav>
<section id="week">
  <div class="tiles">{tiles}</div>
  <h3>This week, ranked by what it does to your season</h3>
  <p class="note">Not "who wins on Sunday". For each team the model burns it now,
  re-solves the remaining {legs_left} legs optimally, and reports the probability
  of running the table from there. The bar is that number. <b>Kept</b> is how much
  of your best-case season equity survives the choice — 100% means the pick is
  free. <b>Est. field</b> and <b>EV#</b> are the contrarian view.</p>
  {R.picks_table(payload)}
  <p class="note" style="margin:12px 0 0">{ev_line}{edge}</p>
</section>
<section id="why">
  <h2>Why {R.esc(top['team'])}, and why now</h2>
  <p class="note">The no-reuse rule makes every team a single-use asset, so the
  question is never just "will they win" — it is "is this the week to spend
  them". Each number below is a counterfactual: the model re-solves the whole
  season under a different assumption and reports what changed.</p>
  <div class="why">{why_cards}</div>
</section>
<section id="teams">
  <h2>Every team this week, in full</h2>
  <p class="note">One card per team playing in {R.esc(payload['leg_label'])}, in
  pick order. Tap any team to open every number the model has on them —
  this week's line and win probability, what picking them does to the season,
  where their value actually peaks, and how replaceable they are. Teams whose
  best slot is not this week carry a warning at the top of the card.</p>
  {R.team_cards(payload)}
</section>
<section id="compare">
  <h2>All 32 teams, compared</h2>
  <p class="note"><b>Best use</b> is the leg where spending them is worth the
  most, after accounting for who else could cover each week. <b>Raw peak</b> is
  where their win probability is highest, ignoring competition. <b>Held back</b>
  is the gap — win probability given up by saving them for the leg that needs
  them. <b>Windows</b> counts legs where they clear 65%: one window is a
  specialist you must reserve, ten is fungible and should be spent early.
  <b>Scarcity</b> is how much of your season disappears if you lose them
  entirely. Faded rows are teams the plan never uses.</p>
  {R.compare_table(payload)}
  <h3>Where each team is worth the most</h3>
  <p class="note">Bars are your <b>season survival probability if you spend that
  team in that leg</b> — not their win probability. A team can be a huge favorite
  in Week 4 and still belong on Christmas, because Week 4 has a dozen other
  options and Christmas has three games. Outlined bar is this week, green
  outline is their best use. (Tapping a row above swaps this chart when
  scripts run; every team's chart is in the page either way.)</p>
  <div id="charts">{charts}</div>
  <details><summary>Show the value chart for all 32 teams</summary>
    <div style="margin-top:10px">{others}</div></details>
  <div class="legend"><span>T = Thanksgiving · X = Christmas ·
    hatched = bye week</span></div>
  <details>
    <summary>The legs driving all of this</summary>
    <table style="max-width:460px;margin-top:8px"><thead><tr>
      <th class="l">Leg</th><th>Teams</th><th>Over 65%</th>
      <th>Best available</th><th class="l">Plan uses</th></tr></thead>
      <tbody>{scarce_rows}</tbody></table>
    <p class="note" style="margin-top:8px">The tightest legs left. Every
    reservation the model makes upstream is made for these weeks.</p>
  </details>
</section>
<section id="board">
  <h2>Win probability, every team, every leg</h2>
  <p class="note">The whole board. Rows sorted by how often a team appears in a
  good plan, so the spine of the season sits at the top. Numbers are win
  probability as a percentage. Hatched cells are byes, outlined cells are the
  current plan, faded rows are teams you have already used. Darker means more
  likely.</p>
  {R.heat(payload)}
  <div class="legend">
    <span>less likely</span>
    <span class="ramp"><i style="background:var(--s1)"></i>
    <i style="background:var(--s2)"></i><i style="background:var(--s3)"></i>
    <i style="background:var(--s4)"></i><i style="background:var(--s5)"></i>
    <i style="background:var(--s6)"></i><i style="background:var(--s7)"></i></span>
    <span>more likely</span>
    <span style="margin-left:auto">outlined = planned pick · hatched = bye</span>
  </div>
  <h3>The route the optimizer would commit to</h3>
  <p class="note">All {n_legs} legs. Greyed are already played, with a green or
  red edge for the result. Re-solved every run as lines and results arrive.</p>
  {R.plan_strip(payload)}
  <div class="warn">
    <span>⚐</span>
    <div><b>Thanksgiving and Christmas are the whole game.</b> Those two legs
    have {tg} and {xm} games, so the candidate pools are tiny and several teams
    appear in both. Entries die there in December because they spent those teams
    in September.
    <br><br>Measured: replaying 2021-2026, an entry that just takes the biggest
    available favorite every week <b>runs out of legal teams before the Christmas
    leg in two of six seasons</b> — an automatic elimination — and in the seasons
    it does survive, planning the full route is worth a median <b>2.25×</b> on
    the probability of running the table. 2026 is one of the two seasons where
    greedy picking dies outright.</div>
  </div>
</section>
<section id="season">
  <h2>Season so far</h2>
  <p class="note">The archive. Each completed leg is frozen here with the pick
  you locked, the win probability the model gave it at the time, what the model
  itself wanted, and what actually happened — so you can see whether losses were
  bad picks or bad luck.</p>
  {R.history_section(payload)}
</section>
<section id="method">
  <h2>How much to trust this</h2>
  <p class="note">Win probabilities come from an empirical margin model fit on
  {diag['holdout_n']:,}+ games of closing lines: margin sd {diag['sigma']}, and a
  tie priced at {diag['tie_rate']*100:.2f}% because in Circa a tie eliminates
  you. Held-out log loss {diag['holdout_logloss']}. Games with no posted line are
  projected from ridge-fit power ratings (home field {meta['home_field']}, scale
  correction ×{meta['proj_scale']}) and pulled toward a coin flip in proportion
  to how far out they are.</p>
  <details><summary>Calibration on held-out seasons (2022+)</summary>
    <table style="max-width:320px;margin-top:8px"><thead><tr>
    <th class="l">Predicted</th><th>Actual</th><th>Games</th></tr></thead>
    <tbody>{cal_rows}</tbody></table>
  </details>
  <details><summary>Where the uncertainty band comes from</summary>
    <p class="note" style="margin-top:8px">The plan is scored
    {payload['mc'].get('held_mean',0)*100:.3f}% on average across simulations
    that jitter every team's rating and hold the plan fixed — the honest number.
    Letting each simulation rebuild its plan after seeing the shock gives
    {mc['mean']*100:.3f}%, which is hindsight and therefore an upper bound. The
    tile reports the honest one.</p>
  </details>
  <details><summary>What this model does not know</summary>
    <p class="note" style="margin-top:8px">Injuries and QB changes only reach it
    through the market — a posted line prices them, a projected one does not.
    Circa pick popularity is not published before the deadline, so the field
    column is a behavioural model, not observed data. Weather, short weeks and
    Week 18 resting-starters motivation are not modelled at all; Week 18 is the
    one leg to override on judgment.</p>
  </details>
</section>
<div id="tip"></div>
</div>
<script>window.__DATA__ = {json.dumps({'leg_key': payload['leg_key']})};</script>
<script>{JS}</script>
</body></html>"""

    with open(path, "w") as f:
        f.write(html)
    return path
