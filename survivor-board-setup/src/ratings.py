"""Market-anchored team power ratings.

The single best predictor of an NFL game is the closing point spread. The
problem for a survivor model is that you need a spread for *every* game
through Week 18, and the market only prices a few weeks out.

So we invert it. Treat each posted line as an observation of

    spread(home) = rating(home) - rating(away) + home_field

solve for the 32 ratings by weighted ridge regression, and then use those
ratings to generate a projected spread for every unlined game on the
schedule. As real lines and real results arrive each week they get folded
into the same fit, so the ratings drift with the season instead of being
frozen at a preseason guess.

Three sources of information, in descending order of trust:
  1. posted 2026 lines            (the market, weighted highest)
  2. actual 2026 results          (margin, capped to blunt garbage-time blowouts)
  3. end-of-2025 ratings          (the prior, regressed toward the mean)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TEAMS_ORDER: list[str] = []

# How much a team's true strength reverts across an offseason. NFL year-to-year
# correlation of team strength is roughly 0.5-0.6 once you account for roster
# and coaching churn, so we pull last year's ratings well back toward average.
OFFSEASON_REGRESSION = 0.45

# Trust weights
W_LINE = 1.0        # a posted line
W_RESULT = 0.28     # a single game result
MARGIN_CAP = 24.0   # cap on result margins fed into the fit


def _fit_ratings(teams: list[str], obs: list[tuple[str, str, float, float]],
                 prior: dict[str, float] | None, prior_weight: float,
                 fixed_hfa: float | None = None
                 ) -> tuple[dict[str, float], float]:
    """Weighted ridge fit of ratings + home-field from (home, away, y, w) rows.

    y is the expected home margin for that observation.
    """
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    fit_hfa = fixed_hfa is None
    p = n + (1 if fit_hfa else 0)

    rows, ys, ws = [], [], []
    for home, away, y, w in obs:
        if home not in idx or away not in idx:
            continue
        r = np.zeros(p)
        r[idx[home]] = 1.0
        r[idx[away]] = -1.0
        if fit_hfa:
            r[n] = 1.0
            rows.append(r); ys.append(y)
        else:
            rows.append(r); ys.append(y - fixed_hfa)
        ws.append(w)

    # ridge pull toward the prior
    pri = prior or {t: 0.0 for t in teams}
    for t in teams:
        r = np.zeros(p)
        r[idx[t]] = 1.0
        rows.append(r); ys.append(pri.get(t, 0.0)); ws.append(prior_weight)
    # sum-to-zero identifiability constraint
    r = np.zeros(p); r[:n] = 1.0
    rows.append(r); ys.append(0.0); ws.append(50.0)
    if fit_hfa:  # keep home field in a sane range
        r = np.zeros(p); r[n] = 1.0
        rows.append(r); ys.append(1.8); ws.append(6.0)

    A = np.array(rows, float)
    b = np.array(ys, float)
    w = np.sqrt(np.array(ws, float))
    sol, *_ = np.linalg.lstsq(A * w[:, None], b * w, rcond=None)
    ratings = {t: float(sol[idx[t]]) for t in teams}
    hfa = float(sol[n]) if fit_hfa else float(fixed_hfa)
    return ratings, hfa


def prior_from_season(df: pd.DataFrame, season: int, teams: list[str]
                      ) -> tuple[dict[str, float], float]:
    """End-of-season ratings from that season's lines and results."""
    s = df[(df.season == season) & (df.game_type == "REG")]
    obs = []
    maxwk = s.week.max() if len(s) else 18
    for _, g in s.iterrows():
        # weight recent games far more: strength late in the year is what
        # carries into next season
        rec = 0.35 + 0.65 * (g.week / max(maxwk, 1))
        if pd.notna(g.spread_line):
            obs.append((g.home_team, g.away_team, float(g.spread_line), W_LINE * rec))
        if pd.notna(g.result):
            m = float(np.clip(g.result, -MARGIN_CAP, MARGIN_CAP))
            obs.append((g.home_team, g.away_team, m, W_RESULT * rec))
    if not obs:
        return {t: 0.0 for t in teams}, 1.8
    r, hfa = _fit_ratings(teams, obs, None, prior_weight=0.6)
    return r, hfa


def current_ratings(df: pd.DataFrame, season: int, teams: list[str],
                    through_week: int | None = None
                    ) -> tuple[dict[str, float], float, dict]:
    """Ratings for `season`, blending the prior season, this year's lines and
    this year's results."""
    prior_raw, _ = prior_from_season(df, season - 1, teams)
    prior = {t: v * (1.0 - OFFSEASON_REGRESSION) for t, v in prior_raw.items()}

    s = df[(df.season == season) & (df.game_type == "REG")]
    if through_week is not None:
        s = s[s.week <= through_week + 4]  # lines a few weeks ahead are fine

    obs, n_lines, n_results = [], 0, 0
    for _, g in s.iterrows():
        if pd.notna(g.spread_line):
            obs.append((g.home_team, g.away_team, float(g.spread_line), W_LINE))
            n_lines += 1
        if pd.notna(g.result):
            m = float(np.clip(g.result, -MARGIN_CAP, MARGIN_CAP))
            obs.append((g.home_team, g.away_team, m, W_RESULT))
            n_results += 1

    # Early in the year we have almost no 2026 information, so the prior has
    # to carry the load. Its weight decays as real evidence accumulates.
    evidence = n_lines * W_LINE + n_results * W_RESULT
    prior_weight = max(0.45, 6.0 / (1.0 + evidence / 40.0))

    ratings, hfa = _fit_ratings(teams, obs, prior, prior_weight)
    meta = {
        "n_lines": n_lines, "n_results": n_results,
        "prior_weight": round(prior_weight, 3),
        "home_field": round(hfa, 2),
        "offseason_regression": OFFSEASON_REGRESSION,
    }
    return ratings, hfa, meta


def projected_spread(ratings: dict[str, float], hfa: float,
                     home: str, away: str, neutral: bool = False) -> float:
    """Projected spread from the HOME team's perspective (positive = favored)."""
    return ratings.get(home, 0.0) - ratings.get(away, 0.0) + (0.0 if neutral else hfa)


if __name__ == "__main__":
    import data

    df = data.load_games(refresh=False)
    teams = sorted(data.TEAM_NAMES)
    r, hfa, meta = current_ratings(df, data.SEASON, teams)
    print(meta)
    tbl = sorted(r.items(), key=lambda kv: -kv[1])
    print(f"\n{'#':>2}  {'team':<5} {'rating':>7}")
    for i, (t, v) in enumerate(tbl, 1):
        print(f"{i:>2}  {t:<5} {v:>+7.2f}")
