"""Fit popularity.py's share model against Circa's published selections.

Circa posts a "WEEK N SELECTIONS" graphic after each deadline: every team,
how many entries took it, and the live-entry count. That is the only ground
truth this model ever gets about crowd behaviour, so it is worth folding in
each week.

Add a week by pasting its counts into OBSERVED below, then run:

    python3 src/calibrate_popularity.py

It reports the current fit, the best fit, and a per-team comparison. It does
NOT write anything -- copy the fitted numbers into popularity.py yourself so
the change is deliberate and reviewable.

Only the two scalars are fitted. The 32 hand-set values in data.BRAND are
left alone on purpose: fitting 32 free parameters to a handful of weeks
would be memorising noise, not learning anything.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import data
import popularity
import winprob

# week key -> {team: entries taking it}. Teams absent from a week's dict are
# treated as zero. Counts, not percentages -- Circa's rounded percentages lose
# the whole tail.
OBSERVED: dict[int, dict[str, int]] = {
    1: {"JAX": 8127, "LAC": 7585, "PIT": 4013, "DET": 1771, "LV": 1308,
        "PHI": 784, "CIN": 351, "TEN": 213, "SEA": 174, "CHI": 128,
        "BAL": 111, "NYJ": 89, "DAL": 81, "MIN": 75, "LA": 49, "MIA": 27,
        "NE": 25, "KC": 23, "SF": 10, "HOU": 10, "NYG": 10, "DEN": 7,
        "IND": 7, "TB": 5, "CAR": 4, "CLE": 4, "ARI": 2, "GB": 2, "BUF": 2,
        "NO": 1, "ATL": 1, "WAS": 0},
}

SEASON = 2026


def week_win_probs(df: pd.DataFrame, mm: winprob.MarginModel,
                   week: int) -> dict[str, float]:
    """Survival probability per team for one week, from that week's lines."""
    wk = df[(df.season == SEASON) & (df.game_type == "REG") & (df.week == week)]
    out: dict[str, float] = {}
    for _, g in wk.iterrows():
        sp = float(g.spread_line)
        ptie = mm.p_tie(sp)
        if pd.notna(g.home_moneyline) and pd.notna(g.away_moneyline):
            try:
                fh, fa = winprob.devig_moneyline(
                    float(g.home_moneyline), float(g.away_moneyline))
                out[g.home_team], out[g.away_team] = fh * (1 - ptie), fa * (1 - ptie)
                continue
            except ValueError:
                pass
        h, _ = mm.team_win_prob(sp)
        a, _ = mm.team_win_prob(-sp)
        out[g.home_team], out[g.away_team] = h, a
    return out


def shares(win_probs: dict[str, float], teams: list[str],
           conc: float, bw: float) -> np.ndarray:
    p = np.array([np.clip(win_probs[t], 1e-4, 1 - 1e-4) for t in teams])
    brand = np.array([data.BRAND.get(t, 0.55) for t in teams])
    s = conc * np.log(p / (1 - p)) + bw * brand
    e = np.exp(s - s.max())
    return e / e.sum()


def main() -> None:
    df = data.load_games(refresh=False)
    hist = data.historical_lined_games(df)
    mm = winprob.MarginModel.fit(hist[hist.season < SEASON])

    weeks = []
    for wk, counts in sorted(OBSERVED.items()):
        wp = week_win_probs(df, mm, wk)
        teams = [t for t in counts if t in wp]
        if not teams:
            print(f"week {wk}: no schedule/line data, skipped")
            continue
        act = np.array([counts[t] for t in teams], float)
        if act.sum() <= 0:
            continue
        weeks.append((wk, teams, act / act.sum(), wp))

    if not weeks:
        sys.exit("no usable weeks in OBSERVED")

    def total_kl(conc: float, bw: float) -> float:
        tot = 0.0
        for _, teams, act, wp in weeks:
            q = np.clip(shares(wp, teams, conc, bw), 1e-12, 1)
            tot += float(np.sum(act * np.log(np.clip(act, 1e-12, 1) / q)))
        return tot / len(weeks)

    cur = total_kl(popularity.CONCENTRATION, popularity.BRAND_WEIGHT)
    best = min(
        ((total_kl(c, b), c, b)
         for c in np.arange(1.0, 7.01, 0.05)
         for b in np.arange(0.0, 2.01, 0.05)),
        key=lambda r: r[0])

    n = sum(len(w[1]) for w in weeks)
    print(f"weeks fitted: {[w[0] for w in weeks]}   team-observations: {n}")
    print(f"current  CONCENTRATION={popularity.CONCENTRATION:.2f} "
          f"BRAND_WEIGHT={popularity.BRAND_WEIGHT:.2f}   mean KL={cur:.4f}")
    print(f"best fit CONCENTRATION={best[1]:.2f} "
          f"BRAND_WEIGHT={best[2]:.2f}   mean KL={best[0]:.4f}")
    if best[0] < cur - 1e-9:
        print("  -> better fit available; copy these into popularity.py")
    else:
        print("  -> current values are still the best fit; change nothing")

    for wk, teams, act, wp in weeks:
        curq = shares(wp, teams, popularity.CONCENTRATION, popularity.BRAND_WEIGHT)
        newq = shares(wp, teams, best[1], best[2])
        print(f"\nweek {wk}")
        print(f"{'tm':<5}{'win%':>7}{'actual':>9}{'current':>10}{'refit':>9}")
        for i in np.argsort(-act):
            t = teams[i]
            if act[i] < 0.002 and curq[i] < 0.01:
                continue          # skip the long tail of near-zeros
            print(f"{t:<5}{wp[t]*100:>6.1f}%{act[i]*100:>8.1f}%"
                  f"{curq[i]*100:>9.1f}%{newq[i]*100:>8.1f}%")


if __name__ == "__main__":
    main()
