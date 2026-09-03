"""The Circa Survivor leg structure.

Circa is not a normal survivor pool, and the difference is the whole reason
this model is built the way it is:

  * 20 legs, not 18. NFL Weeks 1-18, plus a standalone Thanksgiving leg and a
    standalone Christmas leg carved out of their host weeks.
  * Each team may be used ONCE across all 20 legs. 20 picks out of 32 teams
    means you must retire 20 different franchises -- you cannot ride four
    good teams all year.
  * A tie is an elimination, not a push.
  * A missed pick is an elimination. There is no auto-pick.

The carve-out matters more than it looks. The eight teams playing on
Thanksgiving are unavailable for the regular Week 12 leg, because that game
is their Week 12 game. Same for Christmas and Week 16. Those two legs have
tiny candidate pools, which is exactly why they wreck unplanned entries.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# 2026 special dates. Thanksgiving is Thu Nov 26; Circa has historically run
# Thanksgiving Day + Black Friday as one leg. Christmas Day 2026 falls on a
# Friday with a three-game slate.
THANKSGIVING_DATES = ["2026-11-26", "2026-11-27"]
CHRISTMAS_DATES = ["2026-12-25"]


@dataclass
class Leg:
    key: str                 # "W1", "TG", "XM"
    label: str
    order: int               # chronological position, 1..20
    week: int                # host NFL week
    games: list = field(default_factory=list)    # (home, away, neutral)

    @property
    def teams(self) -> set[str]:
        out: set[str] = set()
        for h, a, _ in self.games:
            out.add(h); out.add(a)
        return out


def build_legs(sched: pd.DataFrame,
               thanksgiving_dates: list[str] | None = None,
               christmas_dates: list[str] | None = None) -> list[Leg]:
    tg = set(thanksgiving_dates or THANKSGIVING_DATES)
    xm = set(christmas_dates or CHRISTMAS_DATES)

    tg_rows = sched[sched.gameday.isin(tg)]
    xm_rows = sched[sched.gameday.isin(xm)]
    tg_week = int(tg_rows.week.iloc[0]) if len(tg_rows) else None
    xm_week = int(xm_rows.week.iloc[0]) if len(xm_rows) else None

    def rows_to_games(rows: pd.DataFrame):
        out = []
        for _, g in rows.iterrows():
            neutral = str(g.get("location", "Home")).lower() != "home"
            out.append((g.home_team, g.away_team, neutral))
        return out

    legs: list[Leg] = []
    for wk in sorted(sched.week.unique()):
        rows = sched[sched.week == wk]
        if wk == tg_week:
            rows = rows[~rows.gameday.isin(tg)]
        if wk == xm_week:
            rows = rows[~rows.gameday.isin(xm)]
        legs.append(Leg(f"W{wk}", f"Week {wk}", 0, int(wk), rows_to_games(rows)))
        if wk == tg_week and len(tg_rows):
            legs.append(Leg("TG", "Thanksgiving", 0, int(wk), rows_to_games(tg_rows)))
        if wk == xm_week and len(xm_rows):
            legs.append(Leg("XM", "Christmas", 0, int(wk), rows_to_games(xm_rows)))

    # order chronologically: the special leg sits just before its host week's
    # Sunday slate in real life, but for planning purposes only the count and
    # the team-availability split matter.
    legs.sort(key=lambda L: (L.week, 0 if L.key in ("TG", "XM") else 1))
    for i, L in enumerate(legs, 1):
        L.order = i
    return legs


def summarize(legs: list[Leg]) -> pd.DataFrame:
    return pd.DataFrame([
        {"order": L.order, "key": L.key, "label": L.label, "week": L.week,
         "games": len(L.games), "teams_available": len(L.teams)}
        for L in legs
    ])


if __name__ == "__main__":
    import data

    df = data.load_games(refresh=False)
    sched = data.season_games(df)
    legs = build_legs(sched)
    print(f"{len(legs)} legs\n")
    print(summarize(legs).to_string(index=False))
    for L in legs:
        if L.key in ("TG", "XM"):
            print(f"\n{L.label} ({L.key}) pool: {sorted(L.teams)}")
            for h, a, _ in L.games:
                print(f"   {a} @ {h}")
    tot = sum(len(L.games) for L in legs)
    print(f"\nsanity: {tot} games across all legs (schedule has {len(sched)})")
