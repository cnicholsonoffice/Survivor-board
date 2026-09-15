"""Per-leg what-if ladders.

The dashboard's headline table answers "what does each team cost me THIS
week". This answers the same question for every leg still to come: assuming
you follow the recommended plan up to that leg, what does each candidate at
that leg do to your season?

That is what makes the answer boxes readable with scripts off. The optional
JS layer re-solves live for any combination the reader clicks; this module
precomputes the spine of it -- the path down the recommended plan -- so the
page still contains real numbers when nothing runs.
"""
from __future__ import annotations

import numpy as np

import model as model_mod


def leg_ladder(board, remaining_keys: list[str], available: list[str],
               base_plan: dict, base_ll: float, top_n: int = 8) -> list[dict]:
    """One entry per remaining leg: the candidates and what each costs.

    Leg i is scored with legs before it pinned to the recommended plan, so
    reading down the list is reading down a single coherent season, not 20
    unrelated counterfactuals.
    """
    out = []
    prefix: dict[str, str] = {}
    for i, key in enumerate(remaining_keys):
        # The near legs are the ones a reader actually weighs; the far ones are
        # projections that will move many times before they matter, so they get
        # a shorter list rather than the same eight rows of false precision.
        keep = top_n if i < 4 else 5
        col = board.p[key]
        cands = [t for t in available
                 if t not in prefix.values() and not _isnan(col.get(t))]
        rows = []
        for t in cands:
            forced = dict(prefix)
            forced[key] = t
            ll, _ = model_mod.solve_path(board, remaining_keys, available,
                                         forced=forced)
            rows.append({
                "team": t,
                "opponent": str(board.opponent.loc[t, key]),
                "spread": float(board.spread.loc[t, key]),
                "ml": (None if board.ml is None or _isnan(board.ml.loc[t, key])
                       else float(board.ml.loc[t, key])),
                "source": str(board.source.loc[t, key]),
                "win_prob": float(col.loc[t]),
                "path_prob": float(np.exp(ll)),
            })
        rows.sort(key=lambda r: -r["path_prob"])
        best = rows[0]["path_prob"] if rows else 0.0
        for r in rows:
            r["kept"] = (r["path_prob"] / best) if best else 0.0
        out.append({
            "leg": key,
            "planned": base_plan.get(key),
            "best_here": rows[0]["team"] if rows else None,
            "best_prob": best,
            "n_candidates": len(rows),
            "rows": rows[:keep],
        })
        if base_plan.get(key):
            prefix[key] = base_plan[key]
    return out


def _isnan(v) -> bool:
    try:
        return v is None or bool(np.isnan(float(v)))
    except (TypeError, ValueError):
        return True


def grid(board, keys: list[str]) -> dict:
    """The compact (team x leg) matrix the browser needs to re-solve.

    Only what the solver and the labels require: win probability, opponent,
    and the market/projection flag. Rounded to 4dp because the assignment is
    nowhere near that sensitive and the bytes matter on a phone.
    """
    teams = list(board.p.index)
    return {
        "teams": teams,
        "keys": keys,
        "p": [[None if _isnan(board.p.loc[t, k]) else round(float(board.p.loc[t, k]), 4)
               for k in keys] for t in teams],
        "opp": [[("" if _isnan_str(board.opponent.loc[t, k])
                  else str(board.opponent.loc[t, k])) for k in keys]
                for t in teams],
        "src": [["" if _isnan_str(board.source.loc[t, k])
                 else {"ml": "m", "line": "l"}.get(str(board.source.loc[t, k]), "p")
                 for k in keys] for t in teams],
    }


def _isnan_str(v) -> bool:
    if v is None:
        return True
    try:
        return bool(np.isnan(v))
    except (TypeError, ValueError):
        return False
