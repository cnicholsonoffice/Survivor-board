"""How wrong is a projected spread, as a function of how far ahead it is?

This is the number that keeps the season-path optimizer honest. If we tell it
a Week 16 game is a 12-point mismatch and it believes that as confidently as
a Week 1 posted line, it will happily plan the whole season around a game
nobody has priced yet.

So: replay past seasons. Stand at the end of week W knowing only what was
knowable then, project every remaining game, and compare against the spread
the market eventually posted. The spread of those errors, bucketed by weeks
ahead, becomes the `extra_sd` fed into the win-probability model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import data
import ratings


def run(seasons=(2021, 2022, 2023, 2024, 2025), stand_at=(0, 2, 4, 6, 8, 10, 12)):
    df = data.load_games(refresh=False)
    teams = sorted(data.TEAM_NAMES)
    rows = []
    for season in seasons:
        for w in stand_at:
            # knowledge cutoff: results through week w, plus lines already posted
            known = df[
                (df.season < season)
                | ((df.season == season) & (df.week <= w))
            ]
            sub = df[(df.season == season) & (df.game_type == "REG")]
            hist = sub[sub.week <= w]
            prior_raw, _ = ratings.prior_from_season(df, season - 1, teams)
            prior = {t: v * (1 - ratings.OFFSEASON_REGRESSION)
                     for t, v in prior_raw.items()}
            obs = []
            for _, g in hist.iterrows():
                if pd.notna(g.spread_line):
                    obs.append((g.home_team, g.away_team, float(g.spread_line),
                                ratings.W_LINE))
                if pd.notna(g.result):
                    m = float(np.clip(g.result, -ratings.MARGIN_CAP,
                                      ratings.MARGIN_CAP))
                    obs.append((g.home_team, g.away_team, m, ratings.W_RESULT))
            evidence = sum(o[3] for o in obs)
            pw = max(0.45, 6.0 / (1.0 + evidence / 40.0))
            r, hfa = ratings._fit_ratings(teams, obs, prior, pw)

            fut = sub[(sub.week > w) & sub.spread_line.notna()]
            for _, g in fut.iterrows():
                proj = ratings.projected_spread(r, hfa, g.home_team, g.away_team)
                rows.append({
                    "season": season, "stand_at": w, "week": int(g.week),
                    "ahead": int(g.week) - w,
                    "proj": proj, "actual": float(g.spread_line),
                })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    d = run()
    print(f"n = {len(d)} projected-vs-posted comparisons\n")
    d["bucket"] = pd.cut(d.ahead, [0, 1, 2, 4, 6, 9, 13, 20],
                         labels=["1", "2", "3-4", "5-6", "7-9", "10-13", "14+"])
    g = d.groupby("bucket", observed=True).apply(
        lambda x: pd.Series({
            "n": len(x),
            "err_sd": (x.actual - x.proj).std(),
            "bias": (x.actual - x.proj).mean(),
            "scale": np.polyfit(x.proj, x.actual, 1)[0],
            "corr": np.corrcoef(x.proj, x.actual)[0, 1],
        }), include_groups=False)
    print(g.round(3).to_string())
    print("\nOverall scale factor (posted ~ projected):",
          round(float(np.polyfit(d.proj, d.actual, 1)[0]), 3))
    resid = d.actual - d.proj * np.polyfit(d.proj, d.actual, 1)[0]
    print("Residual sd after rescaling:", round(float(resid.std()), 2))
