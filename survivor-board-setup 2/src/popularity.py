"""Estimated public pick share, and what crowding is actually worth here.

Circa does not publish pick distribution before the deadline, so the share
numbers are a model of crowd behaviour, not observed data. The dashboard
says so.

The part worth getting right is not the share estimate -- it is what to do
with it. The intuition imported from office pools ("fade the chalk") is
close to worthless in Circa, and the math says why.

Your prize is split among entries that survive all 20 legs. Picking a
popular team does not make more entries survive. What it does is change
what you learn about them: conditional on YOUR pick winning, every entry
that shared it is now known to have cleared that leg too. So

    E[co-survivors | I win]  =  N * q * prod over legs of  c_L
    c_L = (1 - s) * 1 + s * (1/p)  =  1 + s * (1/p - 1)

where s is the share of the field on your team and p its win probability.
That factor is the entire crowding penalty, and look at how it behaves: a
heavily-owned 81% favorite gives 1 + 0.19*0.23 = 1.04, while a lightly-owned
60% dog gives 1 + 0.03*0.67 = 1.02. Two percent. The correlation you create
by joining the crowd is small precisely BECAUSE the crowd picked a team that
was going to win anyway.

An earlier version of this file used a hand-tuned exponent on the share
ratio instead, and it ranked a 60% team above an 81% team on "EV". That was
the model being clever rather than correct. The derivation above replaced it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import data

# Circa's field is sharper than a typical office pool, so shares are less
# concentrated than the classic "40% on the biggest favorite" pattern.
CONCENTRATION = 1.55      # softmax temperature on the win-prob logit
BRAND_WEIGHT = 0.45       # public pull toward famous teams
FIELD_ENTRIES = 14000     # approximate Circa Survivor field
FIELD_SURVIVAL = 0.00022  # rough P(a typical entry runs the table)


def pick_shares(win_probs: dict[str, float]) -> dict[str, float]:
    """Estimated share of the field on each team for one leg."""
    teams = list(win_probs)
    p = np.array([np.clip(win_probs[t], 1e-4, 1 - 1e-4) for t in teams])
    logit = np.log(p / (1 - p))
    brand = np.array([data.BRAND.get(t, 0.55) for t in teams])
    score = CONCENTRATION * logit + BRAND_WEIGHT * brand
    e = np.exp(score - score.max())
    return dict(zip(teams, e / e.sum()))


def crowding_factor(share: float, win_prob: float) -> float:
    """c_L: how much this pick inflates the expected number of co-winners."""
    p = float(np.clip(win_prob, 1e-4, 1 - 1e-4))
    return 1.0 + float(share) * (1.0 / p - 1.0)


def annotate(ranked: pd.DataFrame) -> pd.DataFrame:
    """Add estimated pick share and a contrarian-adjusted EV ranking."""
    out = ranked.copy()
    shares = pick_shares(dict(zip(out.team, out.win_prob)))
    out["pick_share"] = [shares[t] for t in out.team]
    out["crowding"] = [crowding_factor(s, p)
                       for s, p in zip(out.pick_share, out.win_prob)]
    base = FIELD_ENTRIES * FIELD_SURVIVAL
    out["exp_cowinners"] = base * out.crowding
    # EV in units of "expected share of the pot"
    out["ev_score"] = out.path_prob / (1.0 + out.exp_cowinners)
    out = out.sort_values("ev_score", ascending=False).reset_index(drop=True)
    out["ev_rank"] = out.index + 1
    return out.sort_values("rank").reset_index(drop=True)


if __name__ == "__main__":
    demo = {"LAC": 0.812, "JAX": 0.736, "DET": 0.722, "PHI": 0.645, "CIN": 0.613,
            "LV": 0.613, "SEA": 0.613, "KC": 0.597, "TEN": 0.597, "PIT": 0.597,
            "DAL": 0.580}
    s = pick_shares(demo)
    print(f"{'tm':<5}{'win':>7}{'share':>8}{'crowd':>8}{'ev/1000':>10}")
    base = FIELD_ENTRIES * FIELD_SURVIVAL
    for t in sorted(demo, key=lambda k: -demo[k]):
        c = crowding_factor(s[t], demo[t])
        print(f"{t:<5}{demo[t]:>7.3f}{s[t]*100:>7.1f}%{c:>8.3f}"
              f"{1000*demo[t]/(1+base*c):>10.3f}")
    print("\nspread in crowding factor across every candidate: "
          f"{max(crowding_factor(s[t], demo[t]) for t in demo) / min(crowding_factor(s[t], demo[t]) for t in demo):.3f}x")
