"""End-to-end check: play whole past seasons through the model, week by week.

The optimizer can be internally consistent and still be useless, so this
walks real seasons with a strict knowledge cutoff -- at each leg it may only
see results through the previous leg and lines posted by then -- takes the
model's top pick, and looks up what actually happened.

Two comparisons matter:
  * a greedy strategy that always takes the biggest favorite available
  * the model, which reserves teams for Thanksgiving, Christmas and byes

Survivor is high variance, so no single season proves anything. What we are
checking is that the model is not WORSE than greedy, and that when it dies,
it dies later.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import data
import legs as legs_mod
import model as model_mod
from winprob import MarginModel

SPECIALS = {
    2021: (["2021-11-25"], ["2021-12-25"]),
    2022: (["2022-11-24", "2022-11-25"], ["2022-12-24", "2022-12-25"]),
    2023: (["2023-11-23", "2023-11-24"], ["2023-12-25"]),
    2024: (["2024-11-28", "2024-11-29"], ["2024-12-25"]),
    2025: (["2025-11-27", "2025-11-28"], ["2025-12-25"]),
}


def actual_won(sched: pd.DataFrame, team: str, leg) -> bool | None:
    for h, a, _ in leg.games:
        if team in (h, a):
            row = sched[(sched.home_team == h) & (sched.away_team == a) &
                        (sched.week == leg.week)]
            if not len(row) or pd.isna(row.iloc[0].result):
                return None
            m = float(row.iloc[0].result)
            return (m > 0) if team == h else (m < 0)
    return None


def play(season: int, mm: MarginModel, df: pd.DataFrame, greedy: bool = False):
    tg, xm = SPECIALS[season]
    sched = data.season_games(df, season)
    all_legs = legs_mod.build_legs(sched, tg, xm)
    keys = [L.key for L in all_legs]
    used: list[str] = []
    trail = []
    for i, L in enumerate(all_legs, 1):
        # knowledge cutoff: nothing from this leg onward
        cut = df[(df.season < season) |
                 ((df.season == season) & (df.week < L.week))].copy()
        future = df[(df.season == season) & (df.week >= L.week)].copy()
        future["result"] = np.nan          # results not yet known
        vis = pd.concat([cut, future], ignore_index=True)

        avail = [t for t in sorted(data.TEAM_NAMES) if t not in used]
        board = model_mod.build_board(vis, season, mm, current_leg_order=i,
                                      specials=(tg, xm))
        if greedy:
            cand = board.p.loc[avail, L.key].dropna()
            if cand.empty:
                return {"survived": i - 1, "trail": trail, "reason": "no team"}
            pick = str(cand.idxmax())
        else:
            ranked, _, _ = model_mod.rank_picks(board, L.key, keys[i - 1:], avail)
            if ranked.empty:
                return {"survived": i - 1, "trail": trail, "reason": "no team"}
            pick = str(ranked.iloc[0].team)

        won = actual_won(sched, pick, L)
        trail.append((L.key, pick, won))
        used.append(pick)
        if won is not True:
            return {"survived": i - 1, "trail": trail,
                    "reason": f"{pick} {'tied' if won is None else 'lost'} in {L.key}"}
    return {"survived": len(all_legs), "trail": trail, "reason": "ran the table"}


def replay_main():
    df = data.load_games(refresh=False)
    seasons = [2021, 2022, 2023, 2024, 2025]
    print(f"{'season':>7} {'legs':>5} {'model':>7} {'greedy':>7}   model exit")
    tot_m, tot_g = [], []
    for s in seasons:
        # fit the win-prob model WITHOUT the season being tested
        hist = data.historical_lined_games(df)
        mm = MarginModel.fit(hist[hist.season != s])
        m = play(s, mm, df, greedy=False)
        g = play(s, mm, df, greedy=True)
        n = len(legs_mod.build_legs(data.season_games(df, s), *SPECIALS[s]))
        tot_m.append(m["survived"]); tot_g.append(g["survived"])
        print(f"{s:>7} {n:>5} {m['survived']:>7} {g['survived']:>7}   {m['reason']}")
    print(f"\nmean legs survived  model {np.mean(tot_m):.1f}   "
          f"greedy {np.mean(tot_g):.1f}   (n={len(seasons)} seasons)")
    print("Survivor is brutally high variance -- five seasons is a smoke test, "
          "not evidence of edge.")


def path_quality(season: int, mm: MarginModel, df: pd.DataFrame):
    """Ex-ante comparison, which is what the optimizer actually claims.

    Whether an entry survives is one enormous coin flip; five seasons of that
    tells you almost nothing. But both strategies commit to a deterministic
    20-team sequence (you are eliminated the moment you lose, so nothing
    branches), which means we can just score the sequences directly. Same
    probabilities for both, all of them derived from market lines, so the
    only thing being compared is the allocation.
    """
    tg, xm = SPECIALS[season]
    sched = data.season_games(df, season)
    all_legs = legs_mod.build_legs(sched, tg, xm)
    keys = [L.key for L in all_legs]
    # stand at the start of the season: prior seasons only, plus posted lines
    vis = df.copy()
    m = (vis.season == season)
    vis.loc[m, "result"] = np.nan
    board = model_mod.build_board(vis, season, mm, current_leg_order=1,
                                  specials=(tg, xm))
    teams = sorted(data.TEAM_NAMES)

    g_used, g_ll, stuck = [], 0.0, False
    for L in all_legs:
        cand = board.p.loc[[t for t in teams if t not in g_used], L.key].dropna()
        if cand.empty:
            stuck = True
            break
        pick = str(cand.idxmax())
        g_used.append(pick)
        g_ll += float(np.log(cand.max()))

    m_ll, _ = model_mod.solve_path(board, keys, teams)
    # A stuck greedy entry has survival probability ZERO -- it reaches a leg
    # with no legal pick and a missed pick is an elimination in Circa. Scoring
    # it over the legs it did manage would flatter it enormously.
    return {"season": season, "greedy": 0.0 if stuck else float(np.exp(g_ll)),
            "model": float(np.exp(m_ll)), "greedy_stuck": stuck,
            "legs_greedy": len(g_used)}


def quality_main():
    df = data.load_games(refresh=False)
    hist = data.historical_lined_games(df)
    print(f"{'season':>7} {'greedy':>10} {'model':>10} {'lift':>7}  note")
    lifts = []
    for s in [2021, 2022, 2023, 2024, 2025, 2026]:
        if s not in SPECIALS:
            SPECIALS[s] = (legs_mod.THANKSGIVING_DATES, legs_mod.CHRISTMAS_DATES)
        mm = MarginModel.fit(hist[hist.season != s])
        q = path_quality(s, mm, df)
        lift = q["model"] / max(q["greedy"], 1e-12)
        if not q["greedy_stuck"]:
            lifts.append(lift)
        note = (f"greedy ran out of legal teams at leg {q['legs_greedy']+1} "
                f"-> eliminated") if q["greedy_stuck"] else ""
        g = "  dead  " if q["greedy_stuck"] else f"{q['greedy']*100:>9.4f}%"
        lf = "   inf" if q["greedy_stuck"] else f"{lift:>6.2f}x"
        print(f"{s:>7} {g:>10} {q['model']*100:>9.4f}% {lf}  {note}")
    print(f"\nmedian lift where greedy survived at all: {np.median(lifts):.2f}x"
          f"  (it failed outright in {6-len(lifts)} of 6 seasons)")


if __name__ == "__main__":
    replay_main()
    print()
    quality_main()
