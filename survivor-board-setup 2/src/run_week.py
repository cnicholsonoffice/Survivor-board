"""Weekly run: refresh data, re-solve the season, write the dashboard.

    python3 src/run_week.py                 # auto-detect the current leg
    python3 src/run_week.py --leg W3
    python3 src/run_week.py --used LAC,PHI  # override the used-team list
    python3 src/run_week.py --lock LAC      # commit this week's pick to state

State lives in state.json so the model knows which teams you have burned. It
is the only thing you have to keep accurate by hand -- everything else is
re-derived from the schedule and the market every time this runs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os

import numpy as np
import pandas as pd

import analysis
import data
import model as model_mod
import popularity
import report
import whatif
from winprob import MarginModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "state.json")
OUT_DIR = os.path.join(ROOT, "out")


# Two pools, two entries. They share a schedule and a market but NOT a pool of
# used teams, so each one needs its own picks and its own archive -- one entry
# taking the model's pick while the other takes a judgment call is the normal
# case, not the exception, and a single used-list would silently plan the wrong
# season for one of them.
ENTRIES = {
    "survivor": "Survivor",
    "mini-survivor": "Mini Survivor",
}
PRIMARY = "survivor"

BLANK_NOTE = ("Keys are leg keys: W1..W18 plus TG (Thanksgiving) and XM "
              "(Christmas). Values are nflverse team abbreviations, e.g. "
              '{"W1": "LAC"}. Each entry tracks its own picks -- this is the '
              "ONLY thing that must be maintained by hand, and if it is wrong "
              "the plan is wrong.")


def _blank_entry(label: str) -> dict:
    return {"label": label, "picks": {}, "history": {}, "eliminated": False}


def migrate_state(s: dict) -> dict:
    """Lift a single-entry state file into the two-entry shape.

    The old format kept picks and history at the top level. Those belong to
    the main pool, so they move into the primary entry and nothing is lost.
    """
    if s.get("entries"):
        for key, label in ENTRIES.items():          # add any new pool
            s["entries"].setdefault(key, _blank_entry(label))
            s["entries"][key].setdefault("label", label)
            s["entries"][key].setdefault("picks", {})
            s["entries"][key].setdefault("history", {})
        s.setdefault("primary", PRIMARY)
        return s
    entries = {k: _blank_entry(v) for k, v in ENTRIES.items()}
    entries[PRIMARY]["picks"] = s.get("picks", {}) or {}
    entries[PRIMARY]["history"] = s.get("history", {}) or {}
    entries[PRIMARY]["eliminated"] = bool(s.get("eliminated", False))
    return {"version": 2, "primary": PRIMARY, "entries": entries,
            "notes": s.get("notes") or BLANK_NOTE}


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return migrate_state(json.load(f))
    return migrate_state({"notes": BLANK_NOTE})


def save_state(s: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(s, f, indent=2)


def snapshot_leg(ent: dict, leg_key: str, pick: str, ranked, base_ll) -> None:
    """Freeze what the model believed at the moment a pick was locked.

    Results can always be recovered from nflverse later, but "what did the
    model think at the time" cannot be reconstructed after the lines move and
    the ratings update. Without this the archive could only ever show whether
    a pick won, not whether it was a good pick -- which is the part actually
    worth reviewing.
    """
    row = ranked[ranked.team == pick]
    rec = str(ranked.iloc[0].team)
    h = ent.setdefault("history", {})
    rec_entry = h.get(leg_key, {})
    rec_entry.update({
        "pick": pick,
        "recommended": rec,
        "survival": float(np.exp(base_ll)),
        "locked_on": dt.date.today().isoformat(),
    })
    if len(row):
        r = row.iloc[0]
        rec_entry.update({
            "opponent": str(r.opponent),
            "spread": float(r.spread),
            "ml": (None if r.get("ml") is None or pd.isna(r.get("ml"))
                   else float(r.ml)),
            "win_prob": float(r.win_prob),
            "source": str(r.source),
            "path_prob": float(r.path_prob),
            "rank_of_pick": int(r["rank"]),
        })
    h[leg_key] = rec_entry


def fill_results(ent: dict, df: pd.DataFrame, season: int, all_legs) -> dict:
    """Attach actual outcomes to archived legs, recomputed from nflverse."""
    sched = data.season_games(df, season)
    hist = ent.get("history", {}) or {}
    by_key = {L.key: L for L in all_legs}
    for k, rec in hist.items():
        team = rec.get("pick")
        L = by_key.get(k)
        if not team or L is None or rec.get("won") is not None:
            continue
        for home, away, _ in L.games:
            if team not in (home, away):
                continue
            g = sched[(sched.home_team == home) & (sched.away_team == away)
                      & (sched.week == L.week)]
            if not len(g) or pd.isna(g.iloc[0].result):
                continue
            m = float(g.iloc[0].result)
            hs, as_ = g.iloc[0].home_score, g.iloc[0].away_score
            rec["won"] = bool(m > 0) if team == home else bool(m < 0)
            if m == 0:
                rec["won"] = False       # a tie eliminates in Circa
            rec["score"] = f"{away} {int(as_)} @ {home} {int(hs)}"
            break
    return hist


def detect_current_leg(legs, sched: pd.DataFrame, today: dt.date) -> str:
    """First leg whose last game has not yet been played."""
    last_date: dict[str, dt.date] = {}
    for L in legs:
        rows = sched[sched.week == L.week]
        if L.key == "TG":
            rows = rows[rows.gameday.isin(__import__("legs").THANKSGIVING_DATES)]
        elif L.key == "XM":
            rows = rows[rows.gameday.isin(__import__("legs").CHRISTMAS_DATES)]
        else:
            import legs as lm
            rows = rows[~rows.gameday.isin(set(lm.THANKSGIVING_DATES) | set(lm.CHRISTMAS_DATES))]
        if len(rows):
            last_date[L.key] = dt.date.fromisoformat(rows.gameday.max())
    for L in legs:
        if last_date.get(L.key, dt.date(2099, 1, 1)) >= today:
            return L.key
    return legs[-1].key


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leg", default=None, help="leg key, e.g. W3 / TG / XM")
    ap.add_argument("--used", default=None, help="comma-separated teams already used")
    ap.add_argument("--lock", default=None, help="record this week's pick into state")
    ap.add_argument("--entry", default=None,
                    help=("which record --lock writes into: "
                          f"{' | '.join(ENTRIES)}. The model always plans the "
                          "primary entry; the other is tracked only."))
    ap.add_argument("--season", type=int, default=data.SEASON)
    ap.add_argument("--sims", type=int, default=4000)
    ap.add_argument("--no-refresh", action="store_true")
    args = ap.parse_args()

    state = load_state()
    entry_key = args.entry or state.get("primary", PRIMARY)
    if entry_key not in state["entries"]:
        raise SystemExit(f"unknown entry {entry_key!r}; "
                         f"expected one of {', '.join(state['entries'])}")
    ent = state["entries"][entry_key]

    df = data.load_games(refresh=not args.no_refresh)
    hist = data.historical_lined_games(df)
    mm = MarginModel.fit(hist)
    holdout = hist[hist.season >= 2022]

    sched = data.season_games(df, args.season)
    import legs as legs_mod
    all_legs = legs_mod.build_legs(sched)
    keys_all = [L.key for L in all_legs]

    today = dt.date.today()
    leg_key = args.leg or detect_current_leg(all_legs, sched, today)
    if args.leg is None:
        # A leg whose pick is already locked is finished as far as the model is
        # concerned, even if its games have not kicked off yet. Re-solving it
        # would drop the team you just spent AND ask you to fill the same leg a
        # second time -- 20 legs' worth of picks out of 31 teams, which quietly
        # understates the season. Move to the first leg that is still open.
        locked = (state["entries"][state.get("primary", PRIMARY)]
                  .get("picks", {}) or {})
        while leg_key in locked and keys_all.index(leg_key) + 1 < len(keys_all):
            leg_key = keys_all[keys_all.index(leg_key) + 1]
    if leg_key not in keys_all:
        raise SystemExit(f"unknown leg {leg_key!r}; expected one of {keys_all}")
    order = keys_all.index(leg_key) + 1

    board = model_mod.build_board(df, args.season, mm, current_leg_order=order)
    remaining_keys = keys_all[order - 1:]

    # The model plans ONE entry: the main pool. It works exactly as it always
    # has -- one used-team list, one solve, one board. The second entry is
    # bookkeeping only: its picks are archived and shown in "Season so far" so
    # the record is in one place, and they never touch the solve.
    label, path = solve_entry(
        state, args, df, mm, holdout, board, all_legs, keys_all,
        leg_key, order, remaining_keys, lock_into=entry_key)
    print(f"{label} board -> {path}")


def solve_entry(state, args, df, mm, holdout, board, all_legs,
                keys_all, leg_key, order, remaining_keys, lock_into: str):
    entry_key = state.get("primary", PRIMARY)
    ent = state["entries"][entry_key]
    if args.used is not None:
        used = [t.strip().upper() for t in args.used.split(",") if t.strip()]
    else:
        used = [t for k, t in (ent.get("picks", {}) or {}).items()
                if keys_all.index(k) < order]
    used = sorted(set(used))

    available = [t for t in sorted(data.TEAM_NAMES) if t not in used]

    ranked, base_ll, base_plan = model_mod.rank_picks(
        board, leg_key, remaining_keys, available)
    if ranked.empty:
        raise SystemExit(f"no available team plays in leg {leg_key}")
    ranked = popularity.annotate(ranked)

    # Locking happens after the solve so the archive can capture what the model
    # believed at that moment, not just which team was chosen. --entry decides
    # WHICH record the pick goes into; it never changes what was solved.
    if args.lock:
        target = state["entries"][lock_into]
        pick = args.lock.upper()
        if pick not in set(ranked.team):
            raise SystemExit(f"{pick} does not play in {leg_key}; "
                             f"options: {', '.join(sorted(ranked.team))}")
        target.setdefault("picks", {})[leg_key] = pick
        snapshot_leg(target, leg_key, pick, ranked, base_ll)
        save_state(state)
        note = ("" if lock_into == entry_key
                else " (tracked only — the model still plans "
                     f"{ent['label']})")
        print(f"locked {pick} for {leg_key} in {target['label']}"
              f" and archived the model's view{note}")

    # Results are recomputed for EVERY entry, not just the active one, so the
    # archive stays current for the pool you are not looking at right now.
    for e in state["entries"].values():
        fill_results(e, df, args.season, all_legs)
    history = ent.get("history", {}) or {}
    save_state(state)

    top = ranked.iloc[0]
    mc = model_mod.monte_carlo(board, remaining_keys, available,
                               first_pick=str(top.team), n=args.sims)

    # per-team asset analysis: where each team is worth the most, and why the
    # recommended pick should be spent now rather than saved
    curves = analysis.team_value_curves(board, remaining_keys, available, base_ll)
    profiles = analysis.team_profiles(board, remaining_keys, available,
                                      base_ll, base_plan, leg_key, curves)
    why = analysis.why_now(board, remaining_keys, available, base_ll, base_plan,
                           leg_key, str(top.team), profiles, ranked)
    scarce = analysis.scarcest_legs(board, remaining_keys, available, base_plan)

    # the what-if spine: every remaining leg, scored down the recommended plan,
    # plus the raw matrix the browser needs to re-solve any other combination
    rec_plan = ranked.iloc[0]["plan"]
    ladder = whatif.leg_ladder(board, remaining_keys, available, rec_plan, base_ll)
    grid = whatif.grid(board, remaining_keys)

    payload = {
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "season": args.season,
        "leg_key": leg_key,
        "leg_label": next(L.label for L in all_legs if L.key == leg_key),
        "leg_order": order,
        "legs": [{"key": L.key, "label": L.label, "order": L.order,
                  "week": L.week, "games": len(L.games)} for L in all_legs],
        "used": used,
        "picks": ent.get("picks", {}) or {},
        "history": history,
        "entry": {"key": entry_key, "label": ent["label"]},
        "entries": [
            {"key": k, "label": e.get("label", k),
             "picks": e.get("picks", {}) or {},
             "history": e.get("history", {}) or {},
             "eliminated": bool(e.get("eliminated", False)),
             "active": k == entry_key}
            for k, e in state["entries"].items()],
        "available": available,
        "base_survival": float(np.exp(base_ll)),
        "base_plan": base_plan,
        "ranked": ranked.drop(columns=["plan"]).to_dict(orient="records"),
        "recommended_plan": ranked.iloc[0]["plan"],
        "mc": mc,
        "profiles": profiles.drop(columns=["curve", "probs"]).to_dict(orient="records"),
        "curves": {t: {k: round(v, 8) for k, v in c.items()}
                   for t, c in curves.items()},
        "team_probs": {r["team"]: {k: round(v, 4) for k, v in r["probs"].items()}
                       for _, r in profiles.iterrows()},
        "why": why,
        "scarce_legs": scarce,
        "ladder": ladder,
        "grid": grid,
        "meta": {k: v for k, v in board.meta.items() if k != "ratings"},
        "ratings": board.meta["ratings"],
        "heat": {
            "teams": list(board.p.index),
            "keys": keys_all,
            "p": [[None if pd.isna(v) else round(float(v), 4)
                   for v in board.p.loc[t, keys_all]] for t in board.p.index],
            "src": [[board.source.loc[t, k] for k in keys_all] for t in board.p.index],
            "opp": [[board.opponent.loc[t, k] for k in keys_all] for t in board.p.index],
        },
        "diagnostics": {
            "holdout_logloss": round(mm.log_loss(holdout), 4),
            "holdout_n": int(len(holdout)),
            "calibration": mm.calibration_report(holdout).to_dict(orient="records"),
            "sigma": round(mm.sigma, 2),
            "tie_rate": round(mm.base_tie_rate, 5),
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "payload.json"), "w") as f:
        json.dump(payload, f, indent=1, default=str)
    html_path = report.write_dashboard(
        payload, os.path.join(OUT_DIR, "survivor.html"))

    print(f"\n=== {ent['label']} === {payload['leg_label']}  "
          f"({leg_key}, leg {order} of {len(all_legs)})")
    print(f"used so far: {', '.join(used) if used else '(none)'}")
    print(f"season survival if played optimally: {payload['base_survival']*100:.3f}%\n")
    cols = ["rank", "team", "opponent", "moneyline", "source", "win_prob",
            "path_prob", "future_cost", "pick_share", "ev_rank"]
    cols = [c for c in cols if c in ranked.columns]
    print(ranked[cols].head(10).to_string(index=False))
    return ent["label"], html_path


if __name__ == "__main__":
    main()
