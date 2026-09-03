"""The engine: probabilities for every leg, then a season-long assignment.

The mistake almost every survivor entry makes is picking greedily -- take
the biggest favorite available this week, repeat, and discover in Week 15
that every team you have left is bad or on a bye. Circa punishes that
harder than any other pool because you must burn 20 of 32 teams and two of
your legs (Thanksgiving, Christmas) have single-digit candidate pools.

So this does not rank teams by "who wins this week". It solves the whole
remaining season as an assignment problem -- one team per leg, no reuse,
maximizing the probability of surviving ALL of it -- and then asks a
different question:

    for each team available this week, if I burn it now and play optimally
    from there, what is my probability of running the table?

That number, not this week's win probability, is the strength of a pick.
The gap between the best pick and the rest is the real cost of a choice.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

import data
import legs as legs_mod
import ratings as ratings_mod
from winprob import MarginModel

BIG = 60.0  # log-cost stand-in for "impossible" (p ~ 1e-26)

# From backtest_ratings.py: sd of (posted spread - projected spread) grows
# roughly linearly with how many weeks ahead the projection is.
PROJ_SD_BASE, PROJ_SD_SLOPE = 2.50, 0.23
# A posted lookahead line is better information than a pure projection, but
# it still moves before kickoff, so it is not treated as certain either.
LINE_SD_BASE, LINE_SD_SLOPE = 0.45, 0.22


@dataclass
class Board:
    """Survival probability for every (team, leg) pair, plus the trail."""
    legs: list
    teams: list[str]
    p: pd.DataFrame          # index=team, columns=leg key
    spread: pd.DataFrame
    opponent: pd.DataFrame
    source: pd.DataFrame     # "line" or "proj"
    meta: dict


def build_board(df: pd.DataFrame, season: int, mm: MarginModel,
                current_leg_order: int = 1,
                specials: tuple[list[str], list[str]] | None = None) -> Board:
    sched = data.season_games(df, season)
    legs = legs_mod.build_legs(sched, *(specials or (None, None)))
    teams = sorted(data.TEAM_NAMES)

    through = max(0, min(18, current_leg_order - 1))
    rt, hfa, meta = ratings_mod.current_ratings(df, season, teams, through_week=through)

    # Rescale projections onto the market's scale. Ridge shrinkage compresses
    # ratings; the lined games tell us by how much, and that correction is
    # re-estimated every run instead of being hardcoded.
    lined = sched[sched.spread_line.notna()]
    scale = 1.073
    if len(lined) >= 24:
        proj = np.array([ratings_mod.projected_spread(rt, hfa, g.home_team, g.away_team)
                         for _, g in lined.iterrows()])
        act = lined.spread_line.astype(float).to_numpy()
        if proj.std() > 0.5:
            scale = float(np.clip(np.polyfit(proj, act, 1)[0], 0.85, 1.45))
    meta["proj_scale"] = round(scale, 3)
    meta["season"] = season

    line_by_game = {}
    for _, g in sched.iterrows():
        if pd.notna(g.spread_line):
            line_by_game[(g.home_team, g.away_team)] = float(g.spread_line)

    keys = [L.key for L in legs]
    P = pd.DataFrame(np.nan, index=teams, columns=keys, dtype=float)
    S = pd.DataFrame(np.nan, index=teams, columns=keys, dtype=float)
    O = pd.DataFrame("", index=teams, columns=keys, dtype=object)
    SRC = pd.DataFrame("", index=teams, columns=keys, dtype=object)

    for L in legs:
        ahead = max(0, L.order - current_leg_order)
        for home, away, neutral in L.games:
            posted = line_by_game.get((home, away))
            if posted is not None:
                sp_home = posted
                sd = LINE_SD_BASE + LINE_SD_SLOPE * ahead
                src = "line"
            else:
                sp_home = scale * ratings_mod.projected_spread(
                    rt, hfa, home, away, neutral=neutral)
                sd = PROJ_SD_BASE + PROJ_SD_SLOPE * ahead
                src = "proj"
            wh, _ = mm.team_win_prob(sp_home, extra_sd=sd)
            wa, _ = mm.team_win_prob(-sp_home, extra_sd=sd)
            P.loc[home, L.key], P.loc[away, L.key] = wh, wa
            S.loc[home, L.key], S.loc[away, L.key] = sp_home, -sp_home
            O.loc[home, L.key], O.loc[away, L.key] = f"vs {away}", f"@ {home}"
            SRC.loc[home, L.key] = SRC.loc[away, L.key] = src

    meta["ratings"] = rt
    meta["hfa"] = hfa
    return Board(legs, teams, P, S, O, SRC, meta)


# ---------------------------------------------------------------------------
# the optimizer
# ---------------------------------------------------------------------------

def _cost_matrix(board: Board, leg_keys: list[str], teams: list[str]) -> np.ndarray:
    sub = board.p.loc[teams, leg_keys].to_numpy(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        c = -np.log(np.clip(sub, 1e-12, 1.0))
    c[~np.isfinite(c)] = BIG
    c[np.isnan(sub)] = BIG      # team on bye / not in this leg
    return np.minimum(c, BIG)


def solve_path(board: Board, leg_keys: list[str], available: list[str],
               forced: dict[str, str] | None = None):
    """Best assignment of available teams to the given legs.

    Returns (log_survival, {leg_key: team}). Legs it cannot fill are marked
    with a None team and carry the BIG penalty, which is how an infeasible
    plan makes itself obvious instead of silently looking fine.
    """
    forced = forced or {}
    fixed_cost = 0.0
    plan: dict[str, str | None] = {}
    teams = [t for t in available]
    open_legs = []
    for k in leg_keys:
        if k in forced:
            t = forced[k]
            plan[k] = t
            pv = board.p.loc[t, k]
            fixed_cost += BIG if pd.isna(pv) else -np.log(max(float(pv), 1e-12))
            if t in teams:
                teams.remove(t)
        else:
            open_legs.append(k)

    if open_legs:
        if len(teams) < len(open_legs):
            return -BIG * (len(open_legs) - len(teams)) - fixed_cost, plan
        C = _cost_matrix(board, open_legs, teams)
        ri, ci = linear_sum_assignment(C.T)   # legs (rows) -> teams (cols)
        for li, ti in zip(ri, ci):
            plan[open_legs[li]] = teams[ti]
            fixed_cost += C[ti, li]
    return -fixed_cost, plan


def rank_picks(board: Board, current_key: str, remaining_keys: list[str],
               available: list[str]):
    """Rank every team playing in `current_key` by season-long survival value."""
    base_ll, base_plan = solve_path(board, remaining_keys, available)
    rows = []
    for t in available:
        pv = board.p.loc[t, current_key]
        if pd.isna(pv):
            continue
        ll, plan = solve_path(board, remaining_keys, available,
                            forced={current_key: t})
        rows.append({
            "team": t,
            "name": data.TEAM_NAMES.get(t, t),
            "opponent": board.opponent.loc[t, current_key],
            "spread": float(board.spread.loc[t, current_key]),
            "source": board.source.loc[t, current_key],
            "win_prob": float(pv),
            "path_logp": ll,
            "path_prob": float(np.exp(ll)),
            "future_cost": float(np.exp(ll - base_ll)),  # 1.0 = free
            "plan": plan,
        })
    out = pd.DataFrame(rows).sort_values("path_logp", ascending=False)
    out = out.reset_index(drop=True)
    out.insert(0, "rank", out.index + 1)
    return out, base_ll, base_plan


def monte_carlo(board: Board, remaining_keys: list[str], available: list[str],
                first_pick: str | None = None, n: int = 3000,
                rating_sd: float = 1.6, seed: int = 7) -> dict:
    """Re-solve the season under jittered ratings.

    The single-path number assumes today's ratings are right. They are not.
    This asks how often a plan still looks good when the ratings move, and
    -- more usefully -- how often each team survives being in the plan at all.
    """
    rng = np.random.default_rng(seed)
    base_p = board.p.loc[available, remaining_keys].to_numpy(float)
    nan_mask = np.isnan(base_p)
    clipped = np.clip(np.nan_to_num(base_p, nan=0.5), 1e-6, 1 - 1e-6)
    logit = np.log(clipped / (1 - clipped))

    forced_row = available.index(first_pick) if first_pick else None
    open_cols = list(range(1, len(remaining_keys))) if first_pick else list(
        range(len(remaining_keys)))

    probs = np.empty(n)
    keep = {t: 0 for t in available}
    for i in range(n):
        # one shock per team, applied to every leg: a team being better or
        # worse than we think is a season-long error, not a weekly one
        shock = rng.normal(0, rating_sd, size=len(available))[:, None] * 0.13
        pz = 1.0 / (1.0 + np.exp(-(logit + shock)))
        with np.errstate(divide="ignore"):
            C = -np.log(np.clip(pz, 1e-12, 1.0))
        C[nan_mask] = BIG
        C = np.minimum(C, BIG)

        cost = 0.0
        rows = [r for r in range(len(available)) if r != forced_row]
        if forced_row is not None:
            cost += C[forced_row, 0]
            keep[available[forced_row]] += 1
        sub = C[np.ix_(rows, open_cols)]
        ri, ci = linear_sum_assignment(sub.T)
        for li, ti in zip(ri, ci):
            cost += sub[ti, li]
            keep[available[rows[ti]]] += 1
        probs[i] = np.exp(-cost)

    # The re-optimised numbers above are an OPTIMISTIC bound: each simulation
    # gets to rebuild its plan after seeing that draw's shock, which is
    # hindsight we will not have. So we also score the plan we would actually
    # commit to today, held fixed across every draw. That second number is the
    # honest one, and it is the one the dashboard reports.
    _, base_plan = solve_path(board, remaining_keys,
                              available,
                              forced={remaining_keys[0]: first_pick} if first_pick
                              else None)
    rowi = {t: i for i, t in enumerate(available)}
    fixed = []
    for j, k in enumerate(remaining_keys):
        t = base_plan.get(k)
        if t in rowi:
            fixed.append((rowi[t], j))
    rng2 = np.random.default_rng(seed + 1)
    held = np.empty(n)
    for i in range(n):
        shock = rng2.normal(0, rating_sd, size=len(available))[:, None] * 0.13
        pz = 1.0 / (1.0 + np.exp(-(logit + shock)))
        pz = np.where(nan_mask, 0.0, pz)
        held[i] = float(np.prod([pz[r, c] for r, c in fixed]))

    return {
        "mean": float(probs.mean()),
        "median": float(np.median(probs)),
        "p10": float(np.quantile(probs, 0.10)),
        "p90": float(np.quantile(probs, 0.90)),
        "held_mean": float(held.mean()),
        "held_p10": float(np.quantile(held, 0.10)),
        "held_p90": float(np.quantile(held, 0.90)),
        "team_usage": {t: c / n for t, c in sorted(keep.items(), key=lambda kv: -kv[1])},
    }
