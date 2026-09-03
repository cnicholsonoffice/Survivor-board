"""Per-team analysis: where is each team worth the most, and why now?

The no-reuse rule turns every team into a single-use asset, so the real
question is never "is this team likely to win this week" -- it is "is THIS
the week I should spend them". Those come apart constantly. A team can be
a 78% favorite today and still be the wrong pick, because they are also the
only defensible Christmas option and nobody else can cover that leg.

So for every team, and every leg they still play, we force them into that
leg and re-solve the whole remaining season. That gives a value curve:

    season survival probability, if I spend this team in that week

The peak of that curve is the team's BEST USE CASE. It already accounts for
competition -- a team's raw win probability might peak in Week 6, but if
three better teams also peak in Week 6 and nothing else can cover Week 13,
their season value peaks in Week 13 instead. Raw win probability cannot see
that. This can.

Three numbers come out of it that are worth reading together:

  best use case   the leg where spending them is worth the most
  scarcity        how much of your season disappears if you lose them
                  entirely -- the shadow price of the asset
  windows         how many legs they could plausibly cover. A team with one
                  window is a specialist you must reserve; a team with ten
                  is fungible and should be spent early.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import data
from model import solve_path

# A pick most entrants would consider playable. Used only to count how many
# distinct chances a team gives you, never in the survival math.
WINDOW_THRESHOLD = 0.65


def team_value_curves(board, remaining_keys: list[str], available: list[str],
                      base_ll: float) -> dict[str, dict[str, float]]:
    """{team: {leg_key: season survival prob if spent there}}.

    This is the expensive call -- roughly (teams x legs) assignment solves --
    but each solve is about a millisecond, so the whole thing lands under a
    couple of seconds for a full 32-team board.
    """
    curves: dict[str, dict[str, float]] = {}
    for t in available:
        row: dict[str, float] = {}
        for k in remaining_keys:
            if pd.isna(board.p.loc[t, k]):
                continue
            ll, _ = solve_path(board, remaining_keys, available, forced={k: t})
            row[k] = float(np.exp(ll))
        curves[t] = row
    return curves


def team_profiles(board, remaining_keys: list[str], available: list[str],
                  base_ll: float, base_plan: dict, current_key: str,
                  curves: dict | None = None) -> pd.DataFrame:
    """One row per still-available team: the full asset picture."""
    curves = curves if curves is not None else team_value_curves(
        board, remaining_keys, available, base_ll)
    base = float(np.exp(base_ll))
    plan_of = {t: k for k, t in base_plan.items() if t}
    rows = []

    for t in available:
        curve = curves.get(t, {})
        if not curve:
            continue
        probs = {k: float(board.p.loc[t, k]) for k in curve}

        best_use_leg = max(curve, key=lambda k: curve[k])
        best_use_val = curve[best_use_leg]
        raw_best_leg = max(probs, key=lambda k: probs[k])

        # scarcity: what the season is worth without this team at all
        ll_without, _ = solve_path(board, remaining_keys,
                                   [x for x in available if x != t])
        scarcity = 1.0 - float(np.exp(ll_without - base_ll))

        windows = int(sum(1 for v in probs.values() if v >= WINDOW_THRESHOLD))
        now_val = curve.get(current_key)
        now_p = probs.get(current_key)

        rows.append({
            "team": t,
            "name": data.TEAM_NAMES.get(t, t),
            "best_use_leg": best_use_leg,
            "best_use_value": best_use_val,
            "best_use_winprob": probs[best_use_leg],
            "best_use_opp": board.opponent.loc[t, best_use_leg],
            "raw_best_leg": raw_best_leg,
            "raw_best_winprob": probs[raw_best_leg],
            "plan_leg": plan_of.get(t),
            "plan_winprob": (float(board.p.loc[t, plan_of[t]])
                             if t in plan_of else None),
            "in_plan": t in plan_of,
            "scarcity": scarcity,
            "windows": windows,
            "now_value": now_val,
            "now_winprob": now_p,
            # 1.00 => this week IS their best use; 0.90 => spending them now
            # throws away a tenth of what they are worth
            "use_now_ratio": (now_val / best_use_val) if now_val else None,
            # How much raw win probability this team gives up by being used
            # where they are actually WORTH the most. A big gap is the
            # signature of a reserved specialist: they look like a great pick
            # in some Week 4 blowout, but the only reason to own them is a
            # leg nobody else can cover.
            "reserve_gap": probs[raw_best_leg] - probs[best_use_leg],
            "peak_premium": probs[raw_best_leg] - float(np.mean(list(probs.values()))),
            "curve": curve,
            "probs": probs,
        })

    df = pd.DataFrame(rows)
    df["value_rank"] = df.best_use_value.rank(ascending=False, method="min").astype(int)
    return df.sort_values("best_use_value", ascending=False).reset_index(drop=True)


def why_now(board, remaining_keys: list[str], available: list[str],
            base_ll: float, base_plan: dict, current_key: str,
            pick: str, profiles: pd.DataFrame, ranked: pd.DataFrame) -> dict:
    """The quantified case for spending `pick` in `current_key` specifically."""
    base = float(np.exp(base_ll))
    prof = profiles[profiles.team == pick]
    prof = prof.iloc[0] if len(prof) else None

    # counterfactual 1: what does the best alternative pick this week cost?
    others = ranked[ranked.team != pick]
    alt = others.iloc[0] if len(others) else None
    defer_cost = (1.0 - alt["path_prob"] / base) if alt is not None else 0.0

    # counterfactual 2: where does the plan send this team if you bench it now?
    ll_b, plan_b = _solve_banned(board, remaining_keys, available,
                                 current_key, pick)
    redeploy_leg = next((k for k, t in plan_b.items() if t == pick), None)

    # counterfactual 3: their second-best window, and what it is worth
    curve = dict(prof["curve"]) if prof is not None else {}
    ranked_legs = sorted(curve, key=lambda k: -curve[k])
    second_leg = next((k for k in ranked_legs if k != current_key), None)

    # how replaceable are they in this leg?
    second_best_now = float(others.iloc[0]["win_prob"]) if alt is not None else None

    return {
        "pick": pick,
        "is_best_use": bool(prof is not None and prof["best_use_leg"] == current_key),
        "best_use_leg": prof["best_use_leg"] if prof is not None else None,
        "use_now_ratio": float(prof["use_now_ratio"]) if prof is not None
        and prof["use_now_ratio"] else None,
        "now_winprob": float(prof["now_winprob"]) if prof is not None else None,
        "raw_best_leg": prof["raw_best_leg"] if prof is not None else None,
        "raw_best_winprob": float(prof["raw_best_winprob"]) if prof is not None else None,
        "scarcity": float(prof["scarcity"]) if prof is not None else None,
        "windows": int(prof["windows"]) if prof is not None else None,
        "defer_cost": float(defer_cost),
        "alt_team": str(alt["team"]) if alt is not None else None,
        "alt_winprob": second_best_now,
        "redeploy_leg": redeploy_leg,
        "redeploy_winprob": (float(board.p.loc[pick, redeploy_leg])
                             if redeploy_leg else None),
        "second_leg": second_leg,
        "second_value": curve.get(second_leg) if second_leg else None,
        "base": base,
    }


def _solve_banned(board, remaining_keys, available, leg_key, team):
    """Best plan when `team` may NOT be used in `leg_key` (but may be used later)."""
    saved = board.p.loc[team, leg_key]
    board.p.loc[team, leg_key] = np.nan
    try:
        return solve_path(board, remaining_keys, available)
    finally:
        board.p.loc[team, leg_key] = saved


def scarcest_legs(board, remaining_keys: list[str], available: list[str],
                  base_plan: dict, top: int = 4) -> list[dict]:
    """Legs with the least room -- the ones forcing every reservation upstream.

    Ranked by how good the BEST available team is, not by how good the
    assigned one is. Those differ on purpose: the optimizer will happily put
    a 53% team on a leg where a 54% team is free, because that 54% team is
    the only thing covering a worse leg later. Reading the assigned team's
    probability as "how hard this leg is" would hide exactly that trade, so
    the difficulty measure here is the ceiling of the leg itself.
    """
    out = []
    for k in remaining_keys:
        col = board.p.loc[available, k].dropna().sort_values(ascending=False)
        if col.empty:
            continue
        assigned = base_plan.get(k)
        out.append({
            "leg": k,
            "candidates": int(len(col)),
            "playable": int((col >= WINDOW_THRESHOLD).sum()),
            "best_available": str(col.index[0]),
            "best_available_p": float(col.iloc[0]),
            "assigned": assigned,
            "assigned_p": float(col.get(assigned, np.nan)) if assigned else None,
            # negative = the plan deliberately took a worse team here to keep
            # a better one free for a leg that needs it more
            "assigned_vs_ceiling": (float(col.get(assigned, np.nan)) - float(col.iloc[0])
                                    if assigned else None),
        })
    out.sort(key=lambda r: (r["playable"], r["best_available_p"]))
    return out[:top]
