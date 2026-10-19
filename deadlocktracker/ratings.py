# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Mini Project 5

"""Win-rate ratings that account for sample size and how recent the games are.

Ratings form a chain, each level starting from the one above it:
    50% (matchmaking aims every player at 50%)
      -> your average                (BASELINE_PRIOR_GAMES games of pull to 50%)
        -> your rating on each hero  (pulled to your average)
          -> each lane / matchup on that hero (pulled to the hero's rating)

At every level:

1. Recency: each game is weighted by its age, measured from your most recent
   game (not today's date, so a break from the game doesn't erase your history).
   A game HALF_LIFE_DAYS older than your latest counts half as much.
2. Empirical Bayes: each record starts from the level above with a prior
   strength of k imaginary games, and k is estimated from the data: if the
   records' win rates are spread further apart than luck alone would explain,
   they really differ and k is small; if the spread looks like luck, k is large.
3. Ranges: the result is a Beta distribution, which gives both the rating (its
   mean) and an 80% range for the true win rate.

The settings below were chosen by testing the method on ten very different kinds
of simulated player (newcomers, one-tricks, flex players, strong and struggling
players, heroes that are all equal or very different, 15 to 1,500 games) and on
stable, slowly changing and patch-affected skill, not by fitting any one data set.
"""

import math
from datetime import datetime

# Recency half-life. No single value is best for every player (short ones suit
# fast-changing skill, long ones stable skill and players with few games a week);
# 60 days had the smallest worst-case error across daily, every-3-days and
# weekly players with stable, drifting or patch-changed skill.
HALF_LIFE_DAYS = 60
RANGE = 0.80  # the shown range covers the middle 80% of likely win rates
LOW_Q, HIGH_Q = (1 - RANGE) / 2, 1 - (1 - RANGE) / 2

# Your average is itself uncertain when you have few games, so it starts at 50%
# (what matchmaking aims for) and moves to your real average as games add up.
# This lifted range accuracy for newcomers from 71% to 86% and lowered the
# rating error for every kind of player tested.
BASELINE_PRIOR_GAMES = 20

# Limits for the fitted prior strength (in imaginary games). With only a few
# heroes or matchups to learn from, the fit often comes out far too large, which
# makes ranges overconfident (true win rates fell inside the "80%" range only
# 47-72% of the time with no ceiling). A ceiling of 15 kept every kind of player
# tested at 79-91% while barely changing which matchups are found.
K_MIN, K_MAX = 3.0, 15.0
MIN_GROUPS_TO_FIT = 4


def baseline_rate(wins, games):
    """Your average win rate (0-100), pulled towards 50% while you have few games."""
    return 100.0 * (wins + BASELINE_PRIOR_GAMES * 0.5) / (games + BASELINE_PRIOR_GAMES)


def age_weight(age_days):
    """Weight of a game played `age_days` before your latest: 1, then 0.5 after HALF_LIFE_DAYS."""
    if age_days is None:
        return 1.0
    return 0.5 ** (max(age_days, 0.0) / HALF_LIFE_DAYS)


def recency_weight(played, latest):
    """Weight of a game played at `played`, given your most recent game at `latest`
    (datetimes or "YYYY-MM-DD HH:MM:SS" text)."""
    if played is None or latest is None:
        return 1.0
    if isinstance(played, str):
        played = datetime.fromisoformat(played)
    if isinstance(latest, str):
        latest = datetime.fromisoformat(latest)
    return age_weight((latest - played).total_seconds() / 86400.0)


def fit_prior_strength(records, baseline, default):
    """Estimate the prior strength k from how spread out the records' win rates are.

    `records` are (weighted wins, weighted games) pairs and `baseline` is the
    average win rate as a fraction. Uses the method of moments: the spread we
    see is the real spread between records plus the spread luck alone would
    cause; whatever is left after removing the luck part tells us k.
    """
    groups = [(w, n) for w, n in records if n > 0]
    if len(groups) < MIN_GROUPS_TO_FIT or not 0 < baseline < 1:
        return default
    total = sum(n for _, n in groups)
    spread = sum(n * (w / n - baseline) ** 2 for w, n in groups)
    luck = (len(groups) - 1) * baseline * (1 - baseline)
    denominator = total - sum(n * n for _, n in groups) / total
    if denominator <= 0:
        return default
    real_variance = (spread - luck) / denominator
    if real_variance <= 0:
        return K_MAX  # all the differences look like luck
    k = baseline * (1 - baseline) / real_variance - 1
    return min(max(k, K_MIN), K_MAX)


def _betacf(a, b, x):
    """Continued fraction for the incomplete beta function (Numerical Recipes)."""
    tiny = 1e-30
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c if abs(c) > tiny else 1 + aa / tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c if abs(c) > tiny else 1 + aa / tiny
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return h


def beta_cdf(x, a, b):
    """P(X <= x) for X ~ Beta(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    log_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                 + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return math.exp(log_front) * _betacf(a, b, x) / a
    return 1 - math.exp(log_front) * _betacf(b, a, 1 - x) / b


def beta_quantile(q, a, b):
    """The x where beta_cdf(x, a, b) == q, found by bisection.

    25 halvings pin x down to within 0.000003, far finer than the 0.1% the app
    shows, and keep pages with hundreds of rated matchups fast.
    """
    lo, hi = 0.0, 1.0
    for _ in range(25):
        mid = (lo + hi) / 2
        if beta_cdf(mid, a, b) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clamp_baseline(baseline):
    """Keep a baseline fraction inside 1-99%: a 0% or 100% baseline (every game
    lost or won) would leave the Beta distribution with a zero parameter."""
    return min(max(baseline, 0.01), 0.99)


def estimate(wins, games, baseline, k):
    """Rating and range (all 0-100) for weighted `wins` out of weighted `games`."""
    baseline = clamp_baseline(baseline)
    a = k * baseline + wins
    b = k * (1 - baseline) + (games - wins)
    return {
        "rating": round(100 * a / (a + b), 1),
        "low": round(100 * beta_quantile(LOW_Q, a, b), 1),
        "high": round(100 * beta_quantile(HIGH_Q, a, b), 1),
    }


def rate_group(rows, baseline, default_k):
    """Rate a group of rows that have weighted `wwins`/`wgames`.

    `baseline` is a 0-100 win rate. Returns (rated dicts, fitted k); each dict
    gains `rating`, `low` and `high`.
    """
    base = clamp_baseline(baseline / 100.0)
    k = fit_prior_strength([(r["wwins"], r["wgames"]) for r in rows], base, default_k)
    rated = []
    for row in rows:
        item = dict(row)
        item.update(estimate(item["wwins"], item["wgames"], base, k))
        rated.append(item)
    return rated, k
