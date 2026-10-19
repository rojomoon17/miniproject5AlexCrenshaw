# INF601 - Advanced Programming in Python
# Alex Crenshaw
# Mini Project 5

import sqlite3

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)

from deadlocktracker.auth import login_required
from deadlocktracker.db import get_db

bp = Blueprint("matches", __name__)

TEAMS = ("Amber Hand", "Sapphire Flame")

# Deadlock is 6v6, so every match has 12 heroes: you plus 5 teammates, against
# 6 enemies. Lanes are always 2v2: you and 1 lane partner against 2 lane opponents.
ALLY_SLOTS = 5
ENEMY_SLOTS = 6
LANE_PARTNERS = 1
LANE_OPPONENTS = 2

# Shown if the database refuses a save the form checks didn't catch.
SAVE_ERROR = ("That match couldn't be saved because it conflicts with data that's already "
              "saved. Check the heroes and try again.")

# Shared SELECT for match rows, with the hero name, a KDA ratio
# ((kills + assists) / deaths, treating 0 deaths as 1), souls per minute,
# and the names of your lane opponents.
MATCH_SELECT = """
    SELECT m.*, h.name AS hero_name,
           ROUND((m.kills + m.assists) * 1.0 / MAX(m.deaths, 1), 2) AS kda,
           CASE WHEN m.duration_min > 0 AND m.souls IS NOT NULL
                THEN CAST(ROUND(m.souls * 1.0 / m.duration_min) AS INTEGER) END AS spm,
           (SELECT GROUP_CONCAT(oh.name, ', ')
              FROM match_player p JOIN hero oh ON oh.id = p.hero_id
             WHERE p.match_id = m.id AND p.side = 'enemy' AND p.in_lane = 1) AS lane_opponents
    FROM match_log m
    JOIN hero h ON h.id = m.hero_id
"""

# Souls per minute across many matches: total souls / total minutes, counting
# only matches where both were recorded. Expects match_log aliased as m.
SPM_AGG = """
    CAST(ROUND(SUM(CASE WHEN m.duration_min > 0 AND m.souls IS NOT NULL THEN m.souls END) * 1.0
         / SUM(CASE WHEN m.duration_min > 0 AND m.souls IS NOT NULL THEN m.duration_min END))
         AS INTEGER)
"""


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
    return {"all_heroes": heroes, "teams": TEAMS, "blank_slots": blank_slots}


def get_match(id, check_owner=True):
    """Fetch a match by id, or 404. Optionally 403 if it isn't the user's."""
    match = get_db().execute(MATCH_SELECT + " WHERE m.id = ?", (id,)).fetchone()

    if match is None:
        abort(404, "That match doesn't exist. It may have been deleted.")

    if check_owner and match["user_id"] != g.user["id"]:
        abort(403, "That match was logged by another player, so you can't view or change it.")

    return match


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
    ("duration_min", "Length", None, 240),
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


def parse_match_form():
    """Validate the submitted match form. Returns (data, error)."""
    form = request.form
    hero_id = form.get("hero_id", type=int)
    result = form.get("result")
    team = form.get("team") or None
    notes = form.get("notes", "").strip() or None
    data = {"hero_id": hero_id, "result": result, "team": team, "notes": notes}

    hero_names = {
        row["id"]: row["name"]
        for row in get_db().execute("SELECT id, name FROM hero").fetchall()
    }

    if hero_id not in hero_names:
        return None, "Please choose a hero."
    if result not in ("Win", "Loss"):
        return None, "Please choose Win or Loss."
    if team is not None and team not in TEAMS:
        return None, "Please choose a side from the list."
    for field, label, default, maximum in NUMBER_FIELDS:
        data[field], error = parse_number(form, field, label, default, maximum)
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
                    "INSERT INTO match_log (user_id, hero_id, result, team, kills, deaths,"
                    " assists, souls, duration_min, notes)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (g.user["id"], data["hero_id"], data["result"], data["team"],
                     data["kills"], data["deaths"], data["assists"], data["souls"],
                     data["duration_min"], data["notes"]),
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
                    "UPDATE match_log SET hero_id = ?, result = ?, team = ?, kills = ?,"
                    " deaths = ?, assists = ?, souls = ?, duration_min = ?, notes = ?"
                    " WHERE id = ?",
                    (data["hero_id"], data["result"], data["team"], data["kills"],
                     data["deaths"], data["assists"], data["souls"],
                     data["duration_min"], data["notes"], id),
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

    return render_template("matches/update.html", match=match, m=match,
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
    overall = db.execute(
        "SELECT COUNT(*) AS games,"
        "       COALESCE(SUM(m.result = 'Win'), 0) AS wins,"
        "       ROUND((COALESCE(SUM(m.kills), 0) + COALESCE(SUM(m.assists), 0)) * 1.0"
        "             / MAX(COALESCE(SUM(m.deaths), 0), 1), 2) AS kda,"
        "       ROUND(AVG(m.souls)) AS avg_souls,"
        f"      {SPM_AGG} AS spm"
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

    return render_template("matches/stats.html", overall=overall, per_hero=per_hero)


def matchup_stats(side, lane_only):
    """Your record when each hero was on the given side (optionally only in your lane)."""
    return get_db().execute(
        "SELECT h.id, h.name, COUNT(*) AS games,"
        "       SUM(m.result = 'Win') AS wins,"
        "       ROUND(100.0 * SUM(m.result = 'Win') / COUNT(*), 1) AS win_rate,"
        f"      {SPM_AGG} AS spm"
        " FROM match_player p"
        " JOIN match_log m ON m.id = p.match_id"
        " JOIN hero h ON h.id = p.hero_id"
        " WHERE m.user_id = ? AND p.side = ? AND p.in_lane >= ?"
        " GROUP BY h.id ORDER BY games DESC, win_rate DESC, h.name",
        (g.user["id"], side, 1 if lane_only else 0),
    ).fetchall()


@bp.route("/matchups")
@login_required
def matchups():
    tabs = [
        ("lane-opponents", "Lane opponents", "vs", matchup_stats("enemy", True)),
        ("lane-partners", "Lane partners", "with", matchup_stats("ally", True)),
        ("enemies", "Enemy team", "vs", matchup_stats("enemy", False)),
        ("allies", "Your team", "with", matchup_stats("ally", False)),
    ]
    return render_template("matches/matchups.html", tabs=tabs)


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
    db = get_db()
    hero = db.execute("SELECT * FROM hero WHERE id = ?", (id,)).fetchone()
    if hero is None:
        abort(404, "That hero isn't in the roster.")

    matches = db.execute(
        MATCH_SELECT + " WHERE m.user_id = ? AND m.hero_id = ?"
        " ORDER BY m.played DESC, m.id DESC",
        (g.user["id"], id),
    ).fetchall()
    return render_template("matches/hero.html", hero=hero, matches=matches)
