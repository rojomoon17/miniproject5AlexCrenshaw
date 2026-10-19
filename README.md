# Deadlock Match Tracker

**INF601 - Advanced Programming in Python · Mini Project 5 · Alex Crenshaw**

A Flask web app for tracking your matches in Valve's *Deadlock*. Create an account, log each
game (hero, win/loss, side, kills/deaths/assists, souls, match length and notes, plus every
hero on both teams and who you laned with and against), and see your win rate, KDA and souls
per minute overall, by hero, and by matchup.

This is a manual tracker: you enter your own stats after each game. It does not pull data
from Valve or any third-party stats service.

## Features

- Register, log in and log out (passwords are stored hashed with Werkzeug)
- Log a match from the **Log match** page or from the **Quick log** modal in the navbar on any page
- Record all 12 heroes in the match: you, your 5 teammates and the 6 enemies. Lanes are always
  2v2, so every match has exactly 1 **lane partner** and 2 **lane opponents**. A hero can only be
  in a match once, so the form greys out heroes already picked and the server rejects duplicates
  on either team, across both teams, or matching the hero you played
- **Souls per minute** for every match, and averaged (total souls ÷ total minutes) across matches
- Edit matches, and delete them through a Bootstrap confirmation modal
- **Stats** page: games played, win rate, overall KDA, average souls and souls/min, plus a per-hero table
- **Matchups** page: your win rate and souls/min against each lane opponent, with each lane
  partner, and with each hero on the enemy team or your team
- **Heroes** page: the full roster with your record on each hero; click one to see those games
- Dark Bootstrap 5 theme, responsive down to phone width

## Error handling

- **Form input:** every form is checked on the server, and problems are shown as a message above
  the form with your input kept. This covers missing fields, non-numeric or negative numbers,
  unrealistically large numbers (for example more than 200 kills), notes over 2,000 characters,
  missing teammates or enemies, a missing lane partner, anything other than 2 lane opponents,
  duplicate heroes, and usernames/passwords that are too long or too short.
- **Error pages:** 403, 404, 405 and 500 errors show a styled page with a plain-English explanation
  and links back into the app, instead of Flask's default error text. Trying to open another
  player's match gives a 403, and a deleted match or hero gives a 404.
- **Database problems:** if the database hasn't been initialized, the app shows a page telling you
  to run `init-db` instead of crashing. Any other database error rolls back the unfinished change
  and shows an error page, so a failed save never leaves half a match behind.
- Pages that need an account redirect to the login page with a "Log in to see that page" message.

## Pages

| Page | URL | Notes |
|------|-----|-------|
| Home / match history | `/` | Landing page when logged out; your match table when logged in |
| Register | `/auth/register` | GET + POST form |
| Log in | `/auth/login` | GET + POST form |
| Log match | `/match/new` | GET + POST form with a hero dropdown pulled from the database |
| Match detail | `/match/<id>` | Full stats and notes, with edit and delete |
| Edit match | `/match/<id>/edit` | GET + POST form, owner only |
| Stats | `/stats` | Aggregate stats using `JOIN` and `GROUP BY` |
| Matchups | `/matchups` | Tabs for lane opponents, lane partners, enemy team and your team |
| Heroes | `/heroes` | Hero grid |
| Hero detail | `/heroes/<id>` | Your matches on one hero |

## Database

SQLite, with four tables defined in `deadlocktracker/schema.sql`:

- **user**: `id`, `username`, `password` (hashed)
- **hero**: `id`, `name` (seeded with the roster when the database is initialized)
- **match_log**: one row per game, with `user_id` → `user.id` and `hero_id` → `hero.id` foreign keys
- **match_player**: the other heroes in a game, one row each, with `match_id` → `match_log.id`
  and `hero_id` → `hero.id` foreign keys. `side` is `ally` or `enemy`, and `in_lane` marks your
  lane partner or lane opponents. `UNIQUE (match_id, hero_id)` stops a hero appearing twice in one
  match. Rows are deleted automatically with their match (`ON DELETE CASCADE`).

Foreign keys are enforced with `PRAGMA foreign_keys = ON` on every connection.

## Project structure

```
deadlocktracker/
├── __init__.py        # application factory
├── db.py              # database connection + `init-db` command
├── schema.sql         # tables and hero seed data
├── auth.py            # register / login / logout blueprint
├── matches.py         # matches, stats, matchups and heroes blueprint
├── errors.py          # error pages and database error handling
├── static/
│   ├── style.css
│   └── match-form.js  # greys out heroes already picked in the match form
└── templates/
    ├── base.html      # Bootstrap layout, navbar, flash messages, quick-log modal
    ├── auth/          # register.html, login.html
    ├── errors/        # error.html
    └── matches/       # page templates plus shared _form, _table and _delete_modal partials
```

## Installation

1. Clone the repository and move into it:

   ```bash
   git clone https://github.com/rojomoon17/miniproject5AlexCrenshaw.git
   cd miniproject5AlexCrenshaw
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   ```

   Windows: `.venv\Scripts\activate` · macOS/Linux: `source .venv/bin/activate`

3. Install the requirements:

   ```bash
   pip install -r requirements.txt
   ```

## Initialize the database

This creates `instance/deadlocktracker.sqlite` and seeds the hero table. Running it again
**erases all data**.

```bash
flask --app deadlocktracker init-db
```

## Run the development server

```bash
flask --app deadlocktracker run --debug
```

Then open http://127.0.0.1:5000, register an account, and start logging matches.

## Updating the hero roster

The roster has 44 heroes, including the six from **Old Gods, New Blood** (January 2026) and the
six from **City Never Sleeps** (September 2026). Valve adds heroes regularly. Add new names to the
`INSERT INTO hero` statements at the bottom of `deadlocktracker/schema.sql`, then re-run `init-db`
(this clears existing data).

## AI Usage

<!-- Edit this to match what you actually did and your course's AI Use Policy. -->
I used Claude (Anthropic) to help plan the project against the assignment rubric and to generate
the initial scaffold: the Flask application factory, database setup, auth and match blueprints,
SQL schema and Bootstrap templates, modeled on the official Flask tutorial. I reviewed the
generated code, tested the app myself, and [describe your own changes: customizations, fixes,
styling, features you added].

## Credits

- Structure based on the [Flask tutorial](https://flask.palletsprojects.com/en/stable/tutorial/)
- Styling with [Bootstrap 5](https://getbootstrap.com/)
- *Deadlock* is a trademark of Valve Corporation. This is an unofficial fan project for a class assignment.
