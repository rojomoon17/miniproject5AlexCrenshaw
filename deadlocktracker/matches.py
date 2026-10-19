# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Mini Project 5

import re
import sqlite3

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)

from deadlocktracker.auth import login_required
from deadlocktracker.db import get_db

bp = Blueprint("matches", __name__)

TEAMS = ("Hidden King", "Archmother")
LANES = ("Yellow", "Blue", "Green")
# Bootstrap colour used for each lane's badges and buttons.
LANE_STYLES = {"Yellow": "warning", "Blue": "primary", "Green": "success"}

# Deadlock is 6v6, so every match has 12 heroes: you plus 5 teammates, against
# 6 enemies. Lanes are always 2v2: you and 1 lane partner against 2 lane opponents.
ALLY_SLOTS = 5
ENEMY_SLOTS = 6
LANE_PARTNERS = 1
LANE_OPPONENTS = 2

# Shown if the database refuses a save the form checks didn't catch.
SAVE_ERROR = ("That match couldn't be saved because it conflicts with data that's already "
              "saved. Check the heroes and try again.")

# Match length is entered as minutes:seconds and stored in seconds.
DURATION_RE = re.compile(r"^(\d{1,3}):([0-5]\d)$")
MAX_DURATION_SEC = 240 * 60
MAX_HERO_NOTE_LENGTH = 5000

# Souls per minute for one match. Expects match_log aliased as m.
SPM_EXPR = """
    CASE WHEN m.duration_sec > 0 AND m.souls IS NOT NULL
         THEN CAST(ROUND(m.souls * 60.0 / m.duration_sec) AS INTEGER) END
"""

# Souls per minute across several matches: total souls / total minutes, counting
# only matches where both were recorded. Heroes farm at very different rates,
# so this is only ever used for matches on a single hero.
SPM_AGG = """
    CAST(ROUND(SUM(CASE WHEN m.duration_sec > 0 AND m.souls IS NOT NULL THEN m.souls END) * 60.0
         / SUM(CASE WHEN m.duration_sec > 0 AND m.souls IS NOT NULL THEN m.duration_sec END))
         AS INTEGER)
"""

# Shared SELECT for match rows, with the hero name, a KDA ratio
# ((kills + assists) / deaths, treating 0 deaths as 1), souls per minute,
# and the names of your lane opponents.
MATCH_SELECT = f"""
    SELECT m.*, h.name AS hero_name,
           ROUND((m.kills + m.assists) * 1.0 / MAX(m.deaths, 1), 2) AS kda,
           {SPM_EXPR} AS spm,
           (SELECT GROUP_CONCAT(oh.name, ', ')
              FROM match_player p JOIN hero oh ON oh.id = p.hero_id
             WHERE p.match_id = m.id AND p.side = 'enemy' AND p.in_lane = 1) AS lane_opponents
    FROM match_log m
    JOIN hero h ON h.id = m.hero_id
"""


# Experience-weighted "rating": a win rate that starts from a baseline and only
# moves away from it as you play more games. Each record is treated as if it
# already had `prior` games at the baseline win rate, so winning your only game
# on a hero doesn't make it your best hero.
#   rating = (wins + prior * baseline) / (games + prior)
# The baseline is your overall win rate when comparing heroes, and your win
# rate on a hero when comparing that hero's lanes and matchups.
HERO_PRIOR_GAMES = 5
# Lanes and matchups get a heavier prior: each one only has a few games, and a
# stress test (140 matches plus 300 simulated heroes) showed that with a prior of
# 5, lucky 2-0 or 3-0 records crowded real matchup patterns out of the top 3.
MATCHUP_PRIOR_GAMES = 10
# A hero needs at least this many games together to be listed as a best or
# toughest lane matchup, partner, teammate or enemy on a hero page.
MIN_LIST_GAMES = 3
# Fewer games than this is a small sample; at least the second is a solid one.
CONFIDENCE_LEVELS = ((3, "Low", "secondary"), (10, "Medium", "info"))
# A hero needs this many games (a "High" sample) to be ranked on the Rankings
# page. The rating alone isn't enough: when your main heroes sit near your
# average, a single win on another hero nudges it just above average and it
# outranked mains with 40+ games.
MIN_RANKED_GAMES = 10


def win_rate(wins, games):
    return 100.0 * wins / games if games else 0.0


def rating(wins, games, baseline, prior=HERO_PRIOR_GAMES):
    """Experience-weighted win rate (0-100), pulled towards `baseline` (0-100)."""
    return round(100.0 * (wins + prior * baseline / 100.0) / (games + prior), 1)


def confidence(games):
    """How much to trust a record: (label, Bootstrap colour)."""
    for limit, label, style in CONFIDENCE_LEVELS:
        if games < limit:
            return label, style
    return "High", "success"


def rate_rows(rows, baseline, prior=HERO_PRIOR_GAMES):
    """Rows with games and wins -> dicts with `rating` and `confidence` added."""
    rated = []
    for row in rows:
        item = dict(row)
        item["rating"] = rating(item["wins"], item["games"], baseline, prior)
        item["confidence"] = confidence(item["games"])
        rated.append(item)
    return rated


def format_duration(seconds):
    """Seconds -> "m:ss" (e.g. 2052 -> "34:12"), or "" if not recorded."""
    if seconds is None:
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}"


@bp.app_template_filter("mmss")
def mmss_filter(seconds):
    return format_duration(seconds) or "—"


def blank_slots():
    """Empty teammate/enemy slots for the match form."""
    return {
        "ally": [{"hero_id": None, "in_lane": False} for _ in range(ALLY_SLOTS)],
        "enemy": [{"hero_id": None, "in_lane": False} for _ in range(ENEMY_SLOTS)],
    }


@bp.app_context_processor
def inject_heroes():
    """Make the hero list available to every template (navbar quick-log modal)."""
    if g.get("user") is None:
        return {}
    heroes = get_db().execute("SELECT id, name FROM hero ORDER BY name").fetchall()
    return {"all_heroes": heroes, "teams": TEAMS, "lane_styles": LANE_STYLES,
            "blank_slots": blank_slots, "hero_prior_games": HERO_PRIOR_GAMES,
            "matchup_prior_games": MATCHUP_PRIOR_GAMES, "min_list_games": MIN_LIST_GAMES}


def get_match(id, check_owner=True):
    """Fetch a match by id, or 404. Optionally 403 if it isn't the user's."""
    match = get_db().execute(MATCH_SELECT + " WHERE m.id = ?", (id,)).fetchone()

    if match is None:
        abort(404, "That match doesn't exist. It may have been deleted.")

    if check_owner and match["user_id"] != g.user["id"]:
        abort(403, "That match was logged by another player, so you can't view or change it.")

    return match


def get_hero(id):
    hero = get_db().execute("SELECT * FROM hero WHERE id = ?", (id,)).fetchone()
    if hero is None:
        abort(404, "That hero isn't in the roster.")
    return hero


def form_values(match):
    """A saved match as form values (the form shows length as m:ss)."""
    values = dict(match)
    values["duration"] = format_duration(match["duration_sec"])
    return values


def slots_from_form(form):
    """Read the teammate/enemy slots out of a submitted match form."""
    slots = blank_slots()
    for i, slot in enumerate(slots["ally"], start=1):
        slot["hero_id"] = form.get(f"ally_{i}", type=int)
        slot["in_lane"] = form.get("lane_partner") == str(i)
    for i, slot in enumerate(slots["enemy"], start=1):
        slot["hero_id"] = form.get(f"enemy_{i}", type=int)
        slot["in_lane"] = f"enemy_lane_{i}" in form
    return slots


def slots_from_db(match_id):
    """Load a saved match's teammates and enemies into form slots."""
    slots = blank_slots()
    rows = get_db().execute(
        "SELECT hero_id, side, in_lane FROM match_player WHERE match_id = ? ORDER BY id",
        (match_id,),
    ).fetchall()
    filled = {"ally": 0, "enemy": 0}
    for row in rows:
        side = row["side"]
        if filled[side] < len(slots[side]):
            slots[side][filled[side]] = {"hero_id": row["hero_id"], "in_lane": bool(row["in_lane"])}
            filled[side] += 1
    return slots


def parse_players(slots, own_hero_id, hero_names):
    """Validate team slots. Returns (players, error); players are (hero_id, side, in_lane).

    Every match has all 12 heroes (you, 5 teammates, 6 enemies), with exactly
    1 lane partner and 2 lane opponents. Each hero can only be in a match once,
    so a hero may not appear twice on either team, on both teams, or alongside
    the hero you played.
    """
    for side, label, size in (("ally", "teammates", ALLY_SLOTS), ("enemy", "enemies", ENEMY_SLOTS)):
        missing = sum(1 for slot in slots[side] if slot["hero_id"] is None)
        if missing:
            return None, (f"Pick all {size} {label} ({missing} missing). Every match has 12 heroes: "
                          f"you, {ALLY_SLOTS} teammates and {ENEMY_SLOTS} enemies.")

    players = []
    # hero_id -> where it was first seen, for the duplicate error message.
    seen = {own_hero_id: "you"}
    for side, label in (("ally", "your team"), ("enemy", "the enemy team")):
        for slot in slots[side]:
            hero_id = slot["hero_id"]
            if hero_id not in hero_names:
                return None, "Unknown hero on " + label + "."
            if hero_id in seen:
                name = hero_names[hero_id]
                first = seen[hero_id]
                if first == "you":
                    return None, (f"You played {name}, and a hero can only be in a match once. "
                                  f"Remove {name} from {label}.")
                if first == label:
                    return None, f"{name} is listed twice on {label}."
                return None, (f"{name} is on both teams. A hero can only be in a match once, "
                              "so remove one of them.")
            seen[hero_id] = label
            players.append((hero_id, side, int(slot["in_lane"])))

    partners = sum(1 for _, side, in_lane in players if side == "ally" and in_lane)
    if partners != LANE_PARTNERS:
        return None, "Choose your lane partner. Every lane is 2v2, so one teammate laned with you."
    opponents = sum(1 for _, side, in_lane in players if side == "enemy" and in_lane)
    if opponents != LANE_OPPONENTS:
        return None, (f"Choose exactly {LANE_OPPONENTS} lane opponents (you picked {opponents}). "
                      "Every lane is 2v2.")

    return players, None


# Number fields on the match form: (field, label, value when left blank, max).
# The maximums are just sanity limits to catch typos.
NUMBER_FIELDS = (
    ("kills", "Kills", 0, 200),
    ("deaths", "Deaths", 0, 200),
    ("assists", "Assists", 0, 200),
    ("souls", "Souls", None, 1_000_000),
)
MAX_NOTES_LENGTH = 2000


def parse_number(form, field, label, default, maximum):
    """Read a whole number from the form. Returns (value, error)."""
    raw = form.get(field, "").strip().replace(",", "")
    if raw == "":
        return default, None
    try:
        value = int(raw)
    except ValueError:
        return None, f"{label} must be a whole number."
    if value < 0:
        return None, f"{label} can't be negative."
    if value > maximum:
        return None, f"{label} looks too high (the most allowed is {maximum:,})."
    return value, None


def parse_duration(raw):
    """Read a match length typed as m:ss (or whole minutes). Returns (seconds, error)."""
    raw = (raw or "").strip()
    if raw == "":
        return None, None
    found = DURATION_RE.match(raw)
    if found:
        seconds = int(found[1]) * 60 + int(found[2])
    elif raw.isdigit():
        seconds = int(raw) * 60
    else:
        return None, "Length must be minutes:seconds, like 34:12."
    if seconds > MAX_DURATION_SEC:
        return None, f"Length looks too long (the most allowed is {format_duration(MAX_DURATION_SEC)})."
    return seconds, None


def parse_match_form():
    """Validate the submitted match form. Returns (data, error)."""
    form = request.form
    hero_id = form.get("hero_id", type=int)
    result = form.get("result")
    lane = form.get("lane")
    team = form.get("team") or None
    notes = form.get("notes", "").strip() or None
    data = {"hero_id": hero_id, "result": result, "lane": lane, "team": team, "notes": notes}

    hero_names = {
        row["id"]: row["name"]
        for row in get_db().execute("SELECT id, name FROM hero").fetchall()
    }

    if hero_id not in hero_names:
        return None, "Please choose a hero."
    if result not in ("Win", "Loss"):
        return None, "Please choose Win or Loss."
    if lane not in LANES:
        return None, "Please choose the lane you played: Yellow, Blue or Green."
    if team is not None and team not in TEAMS:
        return None, "Please choose a side from the list."
    for field, label, default, maximum in NUMBER_FIELDS:
        data[field], error = parse_number(form, field, label, default, maximum)
        if error is not None:
            return None, error
    data["duration_sec"], error = parse_duration(form.get("duration"))
    if error is not None:
        return None, error
    if notes is not None and len(notes) > MAX_NOTES_LENGTH:
        return None, f"Notes can be at most {MAX_NOTES_LENGTH:,} characters (yours are {len(notes):,})."

    players, error = parse_players(slots_from_form(form), hero_id, hero_names)
    if error is not None:
        return None, error
    data["players"] = players

    return data, None


def save_players(db, match_id, players):
    """Replace a match's teammates and enemies."""
    db.execute("DELETE FROM match_player WHERE match_id = ?", (match_id,))
    db.executemany(
        "INSERT INTO match_player (match_id, hero_id, side, in_lane) VALUES (?, ?, ?, ?)",
        [(match_id, hero_id, side, in_lane) for hero_id, side, in_lane in players],
    )


def match_params(data):
    return (data["hero_id"], data["result"], data["lane"], data["team"], data["kills"],
            data["deaths"], data["assists"], data["souls"], data["duration_sec"], data["notes"])


@bp.route("/")
def index():
    if g.user is None:
        return render_template("matches/landing.html")

    matches = get_db().execute(
        MATCH_SELECT + " WHERE m.user_id = ? ORDER BY m.played DESC, m.id DESC",
        (g.user["id"],),
    ).fetchall()
    return render_template("matches/index.html", matches=matches)


@bp.route("/match/new", methods=("GET", "POST"))
@login_required
def create():
    if request.method == "POST":
        data, error = parse_match_form()
        if error is None:
            db = get_db()
            try:
                cur = db.execute(
                    "INSERT INTO match_log (hero_id, result, lane, team, kills, deaths, assists,"
                    " souls, duration_sec, notes, user_id)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    match_params(data) + (g.user["id"],),
                )
                save_players(db, cur.lastrowid, data["players"])
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                error = SAVE_ERROR
            else:
                flash("Match logged.", "success")
                return redirect(url_for("matches.detail", id=cur.lastrowid))

        flash(error, "danger")
        # Re-show the form with what the user typed.
        return render_template("matches/create.html", m=request.form,
                               slots=slots_from_form(request.form))

    return render_template("matches/create.html", m=None, slots=blank_slots())


@bp.route("/match/<int:id>")
@login_required
def detail(id):
    match = get_match(id)
    players = get_db().execute(
        "SELECT p.side, p.in_lane, h.id AS hero_id, h.name"
        " FROM match_player p JOIN hero h ON h.id = p.hero_id"
        " WHERE p.match_id = ? ORDER BY p.in_lane DESC, h.name",
        (id,),
    ).fetchall()
    allies = [p for p in players if p["side"] == "ally"]
    enemies = [p for p in players if p["side"] == "enemy"]
    return render_template("matches/detail.html", match=match, allies=allies, enemies=enemies)


@bp.route("/match/<int:id>/edit", methods=("GET", "POST"))
@login_required
def update(id):
    match = get_match(id)

    if request.method == "POST":
        data, error = parse_match_form()
        if error is None:
            db = get_db()
            try:
                db.execute(
                    "UPDATE match_log SET hero_id = ?, result = ?, lane = ?, team = ?, kills = ?,"
                    " deaths = ?, assists = ?, souls = ?, duration_sec = ?, notes = ?"
                    " WHERE id = ?",
                    match_params(data) + (id,),
                )
                save_players(db, id, data["players"])
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                error = SAVE_ERROR
            else:
                flash("Match updated.", "success")
                return redirect(url_for("matches.detail", id=id))

        flash(error, "danger")
        return render_template("matches/update.html", match=match, m=request.form,
                               slots=slots_from_form(request.form))

    return render_template("matches/update.html", match=match, m=form_values(match),
                           slots=slots_from_db(id))


@bp.route("/match/<int:id>/delete", methods=("POST",))
@login_required
def delete(id):
    get_match(id)
    db = get_db()
    # match_player rows are removed by ON DELETE CASCADE.
    db.execute("DELETE FROM match_log WHERE id = ?", (id,))
    db.commit()
    flash("Match deleted.", "info")
    return redirect(url_for("index"))


@bp.route("/stats")
@login_required
def stats():
    db = get_db()
    # Souls and souls/min aren't averaged across heroes here: heroes farm at
    # very different rates, so those only appear per hero.
    overall = db.execute(
        "SELECT COUNT(*) AS games,"
        "       COALESCE(SUM(m.result = 'Win'), 0) AS wins,"
        "       ROUND((COALESCE(SUM(m.kills), 0) + COALESCE(SUM(m.assists), 0)) * 1.0"
        "             / MAX(COALESCE(SUM(m.deaths), 0), 1), 2) AS kda,"
        "       COUNT(DISTINCT m.hero_id) AS heroes_played"
        " FROM match_log m WHERE m.user_id = ?",
        (g.user["id"],),
    ).fetchone()

    per_hero = db.execute(
        "SELECT h.id, h.name, COUNT(*) AS games,"
        "       SUM(m.result = 'Win') AS wins,"
        "       ROUND(100.0 * SUM(m.result = 'Win') / COUNT(*), 1) AS win_rate,"
        "       ROUND((SUM(m.kills) + SUM(m.assists)) * 1.0 / MAX(SUM(m.deaths), 1), 2) AS kda,"
        "       ROUND(AVG(m.souls)) AS avg_souls,"
        f"      {SPM_AGG} AS spm"
        " FROM match_log m JOIN hero h ON h.id = m.hero_id"
        " WHERE m.user_id = ?"
        " GROUP BY h.id ORDER BY games DESC, win_rate DESC",
        (g.user["id"],),
    ).fetchall()
    per_hero = rate_rows(per_hero, win_rate(overall["wins"], overall["games"]))

    return render_template("matches/stats.html", overall=overall, per_hero=per_hero)


# Ways to order the Rankings page: key -> (label, sort key). Souls/min isn't an
# option because heroes farm at very different rates.
RANKING_SORTS = {
    "rating": ("Rating", lambda r: (-r["rating"], -r["games"], r["name"])),
    "win_rate": ("Win rate", lambda r: (-r["win_rate"], -r["games"], r["name"])),
    "games": ("Games played", lambda r: (-r["games"], -r["rating"], r["name"])),
    "kda": ("KDA", lambda r: (-r["kda"], -r["games"], r["name"])),
}


@bp.route("/rankings")
@login_required
def rankings():
    """Your heroes ranked, by default on the experience-weighted rating."""
    db = get_db()
    rows = db.execute(
        "SELECT h.id, h.name, COUNT(*) AS games,"
        "       SUM(m.result = 'Win') AS wins,"
        "       ROUND(100.0 * SUM(m.result = 'Win') / COUNT(*), 1) AS win_rate,"
        "       ROUND((SUM(m.kills) + SUM(m.assists)) * 1.0 / MAX(SUM(m.deaths), 1), 2) AS kda,"
        f"      {SPM_AGG} AS spm"
        " FROM match_log m JOIN hero h ON h.id = m.hero_id"
        " WHERE m.user_id = ? GROUP BY h.id",
        (g.user["id"],),
    ).fetchall()
    if not rows:
        return render_template("matches/rankings.html", heroes=[], provisional=[],
                               sorts=RANKING_SORTS, sort="rating")

    total_games = sum(r["games"] for r in rows)
    baseline = win_rate(sum(r["wins"] for r in rows), total_games)
    heroes = rate_rows(rows, baseline)

    # Each hero's best lane, rated against your win rate on that hero.
    lanes = db.execute(
        "SELECT m.hero_id, m.lane, COUNT(*) AS games, SUM(m.result = 'Win') AS wins"
        " FROM match_log m WHERE m.user_id = ? GROUP BY m.hero_id, m.lane",
        (g.user["id"],),
    ).fetchall()
    for hero_row in heroes:
        hero_lanes = [dict(l, name=l["lane"]) for l in lanes if l["hero_id"] == hero_row["id"]]
        rated_lanes = by_rating(rate_rows(hero_lanes, hero_row["win_rate"], MATCHUP_PRIOR_GAMES))
        hero_row["best_lane"] = rated_lanes[0]["lane"] if len(rated_lanes) > 1 else None

    sort = request.args.get("sort", "rating")
    if sort not in RANKING_SORTS:
        sort = "rating"
    # Only heroes with enough games are ranked; the rest are listed separately,
    # most played first, with how many more games they need.
    ranked = sorted((h for h in heroes if h["games"] >= MIN_RANKED_GAMES), key=RANKING_SORTS[sort][1])
    provisional = sorted((h for h in heroes if h["games"] < MIN_RANKED_GAMES),
                         key=lambda h: (-h["games"], -h["rating"], h["name"]))
    for h in provisional:
        h["games_needed"] = MIN_RANKED_GAMES - h["games"]

    examples = {"one_win": rating(1, 1, baseline), "six_one": rating(6, 7, baseline)}
    return render_template("matches/rankings.html", heroes=ranked, provisional=provisional,
                           sorts=RANKING_SORTS, sort=sort, baseline=round(baseline, 1),
                           total_games=total_games, examples=examples,
                           min_ranked_games=MIN_RANKED_GAMES)


def played_heroes():
    """Heroes the current user has logged matches on, most played first."""
    return get_db().execute(
        "SELECT h.id, h.name, COUNT(*) AS games, SUM(m.result = 'Win') AS wins"
        " FROM match_log m JOIN hero h ON h.id = m.hero_id"
        " WHERE m.user_id = ? GROUP BY h.id ORDER BY games DESC, h.name",
        (g.user["id"],),
    ).fetchall()


def matchup_stats(hero_id, side, lane_only):
    """Your record on one hero, against or alongside each other hero.

    Matchups are kept separate per hero you played: beating a hero in lane on
    Apollo says nothing about how you do against them on Shiv.
    """
    return get_db().execute(
        "SELECT h.id, h.name, COUNT(*) AS games,"
        "       SUM(m.result = 'Win') AS wins,"
        "       ROUND(100.0 * SUM(m.result = 'Win') / COUNT(*), 1) AS win_rate,"
        f"      {SPM_AGG} AS spm"
        " FROM match_player p"
        " JOIN match_log m ON m.id = p.match_id"
        " JOIN hero h ON h.id = p.hero_id"
        " WHERE m.user_id = ? AND m.hero_id = ? AND p.side = ? AND p.in_lane >= ?"
        " GROUP BY h.id ORDER BY games DESC, win_rate DESC, h.name",
        (g.user["id"], hero_id, side, 1 if lane_only else 0),
    ).fetchall()


def best_and_toughest(rows, limit=3):
    """Split rated matchup rows into your best (won at least half) and toughest
    (lost more than half), each ranked by rating so more games count for more.
    Heroes you've played with or against fewer than MIN_LIST_GAMES times are left out."""
    rows = [r for r in rows if r["games"] >= MIN_LIST_GAMES]
    best = sorted((r for r in rows if r["win_rate"] >= 50),
                  key=lambda r: (-r["rating"], -r["games"], r["name"]))
    toughest = sorted((r for r in rows if r["win_rate"] < 50),
                      key=lambda r: (r["rating"], -r["games"], r["name"]))
    return best[:limit], toughest[:limit]


def by_rating(rows):
    return sorted(rows, key=lambda r: (-r["rating"], -r["games"], r["name"]))


@bp.route("/matchups")
@login_required
def matchups():
    played = played_heroes()
    if not played:
        return render_template("matches/matchups.html", played=played, selected=None, tabs=[])

    hero_id = request.args.get("hero", type=int)
    selected = next((h for h in played if h["id"] == hero_id), played[0])
    if hero_id is not None and selected["id"] != hero_id:
        flash(f"You haven't logged any matches on that hero, so here's {selected['name']}.", "info")

    # Matchups are rated against your usual win rate on this hero.
    baseline = win_rate(selected["wins"], selected["games"])
    tabs = [
        (key, label, verb, by_rating(rate_rows(matchup_stats(selected["id"], side, lane_only),
                                               baseline, MATCHUP_PRIOR_GAMES)))
        for key, label, verb, side, lane_only in (
            ("lane-opponents", "Lane opponents", "vs", "enemy", True),
            ("lane-partners", "Lane partners", "with", "ally", True),
            ("enemies", "Enemy team", "vs", "enemy", False),
            ("allies", "Your team", "with", "ally", False),
        )
    ]
    return render_template("matches/matchups.html", played=played, selected=selected, tabs=tabs,
                           baseline=round(baseline, 1))


@bp.route("/heroes")
def heroes():
    user_id = g.user["id"] if g.user else None
    rows = get_db().execute(
        "SELECT h.id, h.name, COUNT(m.id) AS games,"
        "       COALESCE(SUM(m.result = 'Win'), 0) AS wins"
        " FROM hero h"
        " LEFT JOIN match_log m ON m.hero_id = h.id AND m.user_id = ?"
        " GROUP BY h.id ORDER BY h.name",
        (user_id,),
    ).fetchall()
    return render_template("matches/heroes.html", heroes=rows)


@bp.route("/heroes/<int:id>")
@login_required
def hero(id):
    hero = get_hero(id)
    db = get_db()
    params = (g.user["id"], id)

    summary = db.execute(
        "SELECT COUNT(*) AS games,"
        "       COALESCE(SUM(m.result = 'Win'), 0) AS wins,"
        "       ROUND((COALESCE(SUM(m.kills), 0) + COALESCE(SUM(m.assists), 0)) * 1.0"
        "             / MAX(COALESCE(SUM(m.deaths), 0), 1), 2) AS kda,"
        "       ROUND(AVG(m.souls)) AS avg_souls,"
        f"      {SPM_AGG} AS spm"
        " FROM match_log m WHERE m.user_id = ? AND m.hero_id = ?",
        params,
    ).fetchone()

    if summary["games"] == 0:
        return render_template("matches/hero.html", hero=hero, summary=summary)

    # Lanes and matchups are rated against your usual win rate on this hero.
    baseline = win_rate(summary["wins"], summary["games"])
    by_lane = db.execute(
        "SELECT m.lane, COUNT(*) AS games,"
        "       SUM(m.result = 'Win') AS wins,"
        "       ROUND(100.0 * SUM(m.result = 'Win') / COUNT(*), 1) AS win_rate,"
        "       ROUND((SUM(m.kills) + SUM(m.assists)) * 1.0 / MAX(SUM(m.deaths), 1), 2) AS kda,"
        f"      {SPM_AGG} AS spm"
        " FROM match_log m WHERE m.user_id = ? AND m.hero_id = ?"
        " GROUP BY m.lane",
        params,
    ).fetchall()
    by_lane = sorted(rate_rows(by_lane, baseline, MATCHUP_PRIOR_GAMES),
                     key=lambda r: (-r["rating"], -r["games"]))

    def rated(side, lane_only):
        return rate_rows(matchup_stats(id, side, lane_only), baseline, MATCHUP_PRIOR_GAMES)

    best_opponents, toughest_opponents = best_and_toughest(rated("enemy", True))
    best_partners, toughest_partners = best_and_toughest(rated("ally", True))
    best_teammates, _ = best_and_toughest(rated("ally", False))
    _, toughest_enemies = best_and_toughest(rated("enemy", False))

    note = db.execute(
        "SELECT body, updated FROM hero_note WHERE user_id = ? AND hero_id = ?", params
    ).fetchone()
    match_notes = db.execute(
        "SELECT id, played, result, lane, notes FROM match_log"
        " WHERE user_id = ? AND hero_id = ? AND notes IS NOT NULL"
        " ORDER BY played DESC, id DESC",
        params,
    ).fetchall()
    matches = db.execute(
        MATCH_SELECT + " WHERE m.user_id = ? AND m.hero_id = ? ORDER BY m.played DESC, m.id DESC",
        params,
    ).fetchall()

    return render_template(
        "matches/hero.html", hero=hero, summary=summary, by_lane=by_lane,
        best_opponents=best_opponents, toughest_opponents=toughest_opponents,
        best_partners=best_partners, toughest_partners=toughest_partners,
        best_teammates=best_teammates, toughest_enemies=toughest_enemies,
        note=note, match_notes=match_notes, matches=matches, baseline=round(baseline, 1),
    )


@bp.route("/heroes/<int:id>/notes", methods=("POST",))
@login_required
def hero_notes(id):
    """Save (or clear) your own notes about a hero."""
    get_hero(id)
    body = request.form.get("body", "").strip()
    if len(body) > MAX_HERO_NOTE_LENGTH:
        flash(f"Hero notes can be at most {MAX_HERO_NOTE_LENGTH:,} characters "
              f"(yours are {len(body):,}).", "danger")
        return redirect(url_for("matches.hero", id=id) + "#notes")

    db = get_db()
    if body:
        db.execute(
            "INSERT INTO hero_note (user_id, hero_id, body) VALUES (?, ?, ?)"
            " ON CONFLICT (user_id, hero_id)"
            " DO UPDATE SET body = excluded.body, updated = CURRENT_TIMESTAMP",
            (g.user["id"], id, body),
        )
        flash("Notes saved.", "success")
    else:
        db.execute("DELETE FROM hero_note WHERE user_id = ? AND hero_id = ?", (g.user["id"], id))
        flash("Notes cleared.", "info")
    db.commit()
    return redirect(url_for("matches.hero", id=id) + "#notes")
