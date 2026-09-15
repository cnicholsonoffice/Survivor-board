"""Data layer: nflverse schedules + historical closing lines.

nflverse publishes a single games.csv covering 1999->present, including
closing spread_line / moneylines / totals and final results. That one file
is enough to (a) calibrate spread->win probability and (b) drive the 2026
season plan. It is refreshed continuously during the season, so re-pulling
it each week is what makes this model "living".
"""
from __future__ import annotations

import os
import time
import urllib.request

import pandas as pd

GAMES_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
GAMES_CSV = os.path.join(DATA_DIR, "games.csv")

SEASON = int(os.environ.get("SURVIVOR_SEASON", "2026"))

# nflverse abbreviations that differ from the everyday ones.
TEAM_NAMES = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills",
    "CAR": "Panthers", "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns",
    "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs",
    "LA": "Rams", "LAC": "Chargers", "LV": "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants",
    "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks",
    "SF": "49ers", "TB": "Buccaneers", "TEN": "Titans", "WAS": "Commanders",
}

# Rough "public brand" score, 0-1. Used only by the pick-popularity estimator
# as a nudge on top of win probability -- casual entrants over-pick famous
# teams. Not used anywhere in the survival math.
BRAND = {
    "KC": 1.00, "DAL": 0.95, "PHI": 0.92, "SF": 0.90, "BAL": 0.88, "BUF": 0.88,
    "DET": 0.85, "GB": 0.85, "PIT": 0.80, "NE": 0.72, "LAR": 0.70, "LA": 0.70,
    "CIN": 0.72, "MIN": 0.70, "HOU": 0.68, "NYJ": 0.62, "NYG": 0.62, "MIA": 0.62,
    "SEA": 0.65, "DEN": 0.65, "LAC": 0.60, "WAS": 0.62, "TB": 0.62, "CHI": 0.65,
    "IND": 0.52, "ATL": 0.55, "NO": 0.55, "CLE": 0.52, "LV": 0.58, "ARI": 0.48,
    "TEN": 0.42, "JAX": 0.42, "CAR": 0.40,
}


def download_games(max_age_hours: float = 6.0, force: bool = False) -> str:
    """Refresh the local nflverse games file if it is stale."""
    os.makedirs(DATA_DIR, exist_ok=True)
    fresh = (
        os.path.exists(GAMES_CSV)
        and (time.time() - os.path.getmtime(GAMES_CSV)) < max_age_hours * 3600
    )
    if fresh and not force:
        return GAMES_CSV
    tmp = GAMES_CSV + ".tmp"
    try:
        req = urllib.request.Request(GAMES_URL, headers={"User-Agent": "survivor-model"})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            f.write(r.read())
        os.replace(tmp, GAMES_CSV)
    except Exception as exc:  # keep running on the cached copy
        if not os.path.exists(GAMES_CSV):
            raise
        print(f"[data] refresh failed ({exc}); using cached copy")
    return GAMES_CSV


def load_games(refresh: bool = True) -> pd.DataFrame:
    if refresh:
        download_games()
    df = pd.read_csv(GAMES_CSV, low_memory=False)
    df["season"] = df["season"].astype(int)
    df["week"] = df["week"].astype(int)
    # nflverse spread_line is stated from the HOME team's perspective and is
    # POSITIVE when the home team is favored (i.e. it is the home team's
    # points-given, sign-flipped from the way a book quotes it).
    return df


def historical_lined_games(df: pd.DataFrame, since: int = 2007) -> pd.DataFrame:
    """Completed regular-season games with a closing spread. Calibration set."""
    h = df[
        (df["season"] >= since)
        & (df["game_type"] == "REG")
        & df["spread_line"].notna()
        & df["result"].notna()
    ].copy()
    h["home_margin"] = h["result"].astype(float)
    h["spread"] = h["spread_line"].astype(float)
    return h


def season_games(df: pd.DataFrame, season: int = SEASON) -> pd.DataFrame:
    s = df[(df["season"] == season) & (df["game_type"] == "REG")].copy()
    s = s.sort_values(["week", "gameday", "gametime"], na_position="last")
    return s.reset_index(drop=True)


def bye_weeks(sched: pd.DataFrame) -> dict[str, list[int]]:
    weeks = set(sched["week"].unique())
    played: dict[str, set[int]] = {t: set() for t in TEAM_NAMES}
    for _, g in sched.iterrows():
        played.setdefault(g["home_team"], set()).add(int(g["week"]))
        played.setdefault(g["away_team"], set()).add(int(g["week"]))
    return {t: sorted(weeks - w) for t, w in played.items()}


if __name__ == "__main__":
    d = load_games()
    s = season_games(d)
    print(f"{SEASON}: {len(s)} games, weeks {s.week.min()}-{s.week.max()}")
    print(f"with closing/lookahead lines: {s.spread_line.notna().sum()}")
    h = historical_lined_games(d)
    print(f"calibration set: {len(h)} games ({h.season.min()}-{h.season.max()})")
