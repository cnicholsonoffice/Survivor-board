"""Spread -> win probability, calibrated on 2007-present closing lines.

Why not a plain logistic: NFL margins are lumpy. They spike hard on 3 and 7,
and -- the part that actually matters here -- there is a special hole at 0.
A game tied after regulation goes to overtime and usually resolves, so exact
ties are ~0.2% of games, far rarer than a smooth bell curve would imply.

In almost every model the mass at 0 is a rounding error you ignore. In Circa
Survivor a tie is an elimination, so it has to be priced on purpose.

Construction:
  1. regress actual home margin on the closing spread            -> mu
  2. keep the EMPIRICAL, smoothed distribution of (margin - mu),
     fit on non-tie games only                                   -> shape
  3. model P(tie | spread) separately from the real tie rate      -> tie mass
  4. P(win) = (1 - P(tie)) * P(margin > 0 | not a tie)

Result: key-number structure preserved, tie risk priced honestly, and the
whole thing is calibrated against a held-out set of seasons.

This path is the FALLBACK. Where a book has posted a moneyline, the model
prices the game off that instead -- see devig_moneyline below.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class MarginModel:
    """Empirical margin distribution conditional on the point spread."""

    def __init__(self, intercept: float, slope: float, offsets: np.ndarray,
                 dens: np.ndarray, sigma: float, tie_a: float, tie_b: float,
                 base_tie_rate: float):
        self.intercept = intercept
        self.slope = slope
        self.offsets = offsets      # integer margin grid used for evaluation
        self.dens = dens            # smoothed density of (margin - mu), non-tie
        self.sigma = sigma
        self.tie_a = tie_a          # log-odds intercept for P(tie)
        self.tie_b = tie_b          # slope on |spread|
        self.base_tie_rate = base_tie_rate

    # -- fitting ---------------------------------------------------------
    @classmethod
    def fit(cls, hist: pd.DataFrame, smooth_bw: float = 1.1,
            shrink_slope_to_one: float = 0.5) -> "MarginModel":
        x = hist["spread"].to_numpy(float)
        y = hist["home_margin"].to_numpy(float)
        raw_slope, intercept = np.polyfit(x, y, 1)
        # The market is very close to unbiased; a fitted slope meaningfully
        # away from 1.0 is mostly sampling noise. Shrink toward 1.0 so we do
        # not quietly bet a $1,000 entry on a spurious 6% market inefficiency.
        slope = float(raw_slope + shrink_slope_to_one * (1.0 - raw_slope))

        nontie = y != 0
        resid = y[nontie] - (intercept + slope * x[nontie])
        sigma = float(resid.std(ddof=1))

        grid = np.arange(-80, 81, dtype=float)  # evaluation grid for margins
        # density of the residual, evaluated later at (margin - mu)
        rgrid = np.arange(-90, 91, dtype=float)
        counts = np.zeros_like(rgrid)
        for r in resid:
            counts += np.exp(-0.5 * ((rgrid - r) / smooth_bw) ** 2)
        counts /= counts.sum()

        # P(tie): there are only ~14 ties in the whole 2007+ lined sample, and
        # the empirical rate shows no reliable relationship with the spread
        # (0.15%-0.40% across every spread bucket, all within noise of each
        # other). Fitting a curve to 14 events would be pure overfit, so we
        # use a flat base rate and shade it down for lopsided games, where a
        # tie requires an implausible sequence of events.
        ties = (y == 0).astype(float)
        base = float(ties.mean())
        return cls(float(intercept), slope, rgrid, counts, sigma, 0.0, 0.0, base)

    # -- prediction ------------------------------------------------------
    def p_tie(self, spread: float) -> float:
        damp = 1.0 / (1.0 + (abs(float(spread)) / 16.0) ** 2)
        return float(self.base_tie_rate * damp)

    def probs_for_spread(self, spread: float, extra_sd: float = 0.0
                         ) -> tuple[float, float, float]:
        """(P home win, P tie, P home loss); spread positive = home favored.

        `extra_sd` widens the margin distribution to account for the spread
        itself being uncertain. A Week 1 line is known; a projected Week 14
        spread is a guess about injuries, form and rest, so its win
        probabilities have to sit closer to a coin flip. This is the single
        most important guard against the optimizer falling in love with a
        speculative Week 15 blowout it has no business believing in.
        """
        spread = float(spread)
        mu = self.intercept + self.slope * spread
        margins = np.arange(-90, 91, dtype=float)
        d = np.interp(margins - mu, self.offsets, self.dens)
        if extra_sd > 0.05:
            k = np.arange(-60, 61, dtype=float)
            kern = np.exp(-0.5 * (k / extra_sd) ** 2)
            kern /= kern.sum()
            d = np.convolve(d, kern, mode="same")
        keep = margins != 0
        margins, d = margins[keep], d[keep]
        d = d / d.sum()
        pt = self.p_tie(spread)
        p_win = (1.0 - pt) * float(d[margins > 0].sum())
        p_loss = (1.0 - pt) * float(d[margins < 0].sum())
        return p_win, pt, p_loss

    def team_win_prob(self, spread_for_team: float, extra_sd: float = 0.0
                      ) -> tuple[float, float]:
        """(P win, P tie) for a team given its own spread (positive = favored)."""
        w, t, _ = self.probs_for_spread(spread_for_team, extra_sd=extra_sd)
        return w, t

    # -- diagnostics -----------------------------------------------------
    def calibration_report(self, hist: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
        preds, actual = [], []
        for sp, marg in zip(hist["spread"], hist["home_margin"]):
            w, t, _ = self.probs_for_spread(sp)
            preds.append(w + 0.5 * t)
            actual.append(1.0 if marg > 0 else (0.5 if marg == 0 else 0.0))
        preds, actual = np.array(preds), np.array(actual)
        qs = np.quantile(preds, np.linspace(0, 1, bins + 1))
        qs[0], qs[-1] = -1e-9, 1 + 1e-9
        idx = np.clip(np.digitize(preds, qs[1:-1]), 0, bins - 1)
        rows = []
        for b in range(bins):
            m = idx == b
            if m.sum() < 5:
                continue
            rows.append({
                "bin": b + 1, "n": int(m.sum()),
                "predicted": round(float(preds[m].mean()), 4),
                "actual": round(float(actual[m].mean()), 4),
                "gap": round(float(actual[m].mean() - preds[m].mean()), 4),
            })
        return pd.DataFrame(rows)

    def log_loss(self, hist: pd.DataFrame) -> float:
        tot = 0.0
        for sp, marg in zip(hist["spread"], hist["home_margin"]):
            w, t, l = self.probs_for_spread(sp)
            p = w if marg > 0 else (t if marg == 0 else l)
            tot -= np.log(max(p, 1e-9))
        return tot / len(hist)


def _fit_logistic(x: np.ndarray, y: np.ndarray, iters: int = 200,
                  lr: float = 0.05) -> tuple[float, float]:
    """Tiny gradient-descent logistic fit (one feature). Rare-event safe."""
    a = float(np.log((y.mean() + 1e-6) / (1 - y.mean() + 1e-6)))
    b = 0.0
    n = len(x)
    xm, xs = x.mean(), x.std() + 1e-9
    xz = (x - xm) / xs
    bz = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(a + bz * xz)))
        ga = float((p - y).sum() / n)
        gb = float(((p - y) * xz).sum() / n)
        a -= lr * ga * 10
        bz -= lr * gb * 10
    b = bz / xs
    a = a - bz * xm / xs
    return float(a), float(b)


def implied(odds: float) -> float:
    """American odds -> raw implied probability (still carrying the vig)."""
    o = float(odds)
    return (-o) / ((-o) + 100.0) if o < 0 else 100.0 / (o + 100.0)


def _shin_z(q: np.ndarray, tot: float, tol: float = 1e-12) -> float:
    """Solve Shin's z (the insider-money share) so the fair probs sum to 1.

    p_i(z) = (sqrt(z^2 + 4(1-z) q_i^2 / Q) - z) / (2(1-z))

    sum p_i is strictly decreasing in z: at z=0 it equals sqrt(Q) > 1, and it
    falls below 1 well before z=0.5 for any book we would accept. So a plain
    bisection on [0, 0.5] is enough -- no solver dependency, no failure mode.
    """
    def total(z: float) -> float:
        if z <= 0.0:
            return float(np.sum(q / np.sqrt(tot)))
        return float(np.sum(
            (np.sqrt(z * z + 4.0 * (1.0 - z) * q * q / tot) - z) / (2.0 * (1.0 - z))))

    lo, hi = 0.0, 0.5
    if total(hi) > 1.0:            # margin too wide for the bracket
        return hi
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if total(mid) > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def devig_moneyline(home_ml: float, away_ml: float) -> tuple[float, float]:
    """Two-way moneyline -> fair win probabilities, vig removed by Shin's method.

    The moneyline is a direct price on the only question this contest asks --
    does this team win outright -- whereas a spread has to be translated into
    a win probability through a margin model. Fewer assumptions between the
    market and the number, so where a moneyline exists it is the better input.

    Why Shin rather than dividing each side by the total: a book's margin is
    not spread evenly across the two prices. Longshots are systematically
    overpriced, because a book shades against the possibility that some of the
    money against a big favourite is better informed than it is. Shin models
    that explicitly as a share z of insider money and backs it out, which pulls
    proportionally more of the juice off the longshot and leaves the favourite
    a little higher than a flat proportional de-vig would. On the heavy
    favourites this contest lives on, that difference is roughly a point.

    NFL moneylines push on a tie, so these are probabilities conditional on a
    decisive result. The caller scales by (1 - P(tie)) to get the survival
    probability Circa actually settles on.
    """
    h, a = implied(home_ml), implied(away_ml)
    tot = h + a
    if not (1.0 < tot < 1.35):     # implausible book -- refuse rather than guess
        raise ValueError(f"moneyline pair does not devig sanely: {home_ml}/{away_ml}")
    q = np.array([h, a], dtype=float)
    z = _shin_z(q, tot)
    p = (np.sqrt(z * z + 4.0 * (1.0 - z) * q * q / tot) - z) / (2.0 * (1.0 - z))
    p = p / p.sum()                # kill any residual bisection drift
    return float(p[0]), float(p[1])


def survival_prob(margin_model: MarginModel, spread_for_team: float) -> float:
    """Probability a Circa pick SURVIVES: win outright. A tie eliminates you."""
    w, _ = margin_model.team_win_prob(spread_for_team)
    return w


if __name__ == "__main__":
    import data

    df = data.load_games(refresh=False)
    hist = data.historical_lined_games(df)
    tr, te = hist[hist.season < 2022], hist[hist.season >= 2022]
    m = MarginModel.fit(tr)
    print(f"fit: margin = {m.intercept:+.2f} + {m.slope:.3f} * spread   sigma={m.sigma:.2f}")
    print(f"base tie rate in train: {m.base_tie_rate*100:.3f}%   "
          f"actual ties in holdout: {(te.home_margin==0).mean()*100:.3f}%")
    print(f"holdout log-loss (3-way): {m.log_loss(te):.4f}   n={len(te)}")
    print(m.calibration_report(te).to_string(index=False))
    print()
    for sp in [0, 1, 2.5, 3, 6, 7, 9.5, 13, 17]:
        w, t, l = m.probs_for_spread(sp)
        print(f"  favored by {sp:>4}:  win {w:.4f}   tie {t:.4f}   lose {l:.4f}")
