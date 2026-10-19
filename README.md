# Deadlock Match Tracker

**INF601 - Advanced Programming in Python · Mini Project 5 · Alex Crenshaw**

A Flask web app for tracking your matches in Valve's *Deadlock*. Create an account, log each
game (hero, win/loss, lane, side, kills/deaths/assists, souls, match length and notes, plus
every hero on both teams and who you laned with and against), and see how you do on each hero:
win rate, KDA, souls per minute, your best lane, and your best and toughest matchups.

This is a manual tracker: you enter your own stats after each game. It does not pull data
from Valve or any third-party stats service.

## Features

- Register, log in and log out (passwords are stored hashed with Werkzeug)
- Log a match from the **Log match** page or from the **Quick log** modal in the navbar on any page
- Record all 12 heroes in the match: you, your 5 teammates and the 6 enemies. Lanes are always
  2v2, so every match has exactly 1 **lane partner** and 2 **lane opponents**. A hero can only be
  in a match once, so the form greys out heroes already picked and the server rejects duplicates
  on either team, across both teams, or matching the hero you played
- Record the **lane** you played (Yellow, Blue or Green) and your side (**Hidden King** or **Archmother**)
- Match length is entered and shown as **minutes:seconds** (for example `34:12`) and stored in
  seconds, so souls per minute is precise
- **Souls per minute** for every match. Averages (total souls ÷ total minutes) are only ever
  calculated for one hero at a time, because heroes farm at very different rates
- Edit matches, and delete them through a Bootstrap confirmation modal
- **Stats** page: games, win rate, overall KDA and heroes played, plus a per-hero table with
  average souls and souls/min
- **Matchups** page: pick one of your heroes and see your win rate and souls/min against each lane
  opponent, with each lane partner, and with each hero on the enemy team or your team. Matchups are
  kept separate per hero: beating a hero in lane on Apollo says nothing about facing them on Shiv
- **Hero pages** for every hero you've played: record, win rate, KDA, souls and souls/min; win rate
  by lane with your best lane highlighted; your best and toughest lane matchups, lane partners,
  teammates and enemies; your own notes on the hero (saved per player); the notes from all your
  matches on that hero; and your match history on them
- **Heroes** page: the full roster with your record on each hero; heroes you've played link to
  their hero page
- **Rankings** page: your heroes with at least 10 games, ranked from best to worst by an
  experience-weighted **rating** (see below), with a podium for your top three and each hero's best
  lane. Heroes with fewer games are listed separately under "Not enough games yet" with how many more
  games they need. A GET form lets you rank by rating, raw win rate, games played or KDA

## How the rating works

A plain win rate is misleading on small samples: win your only game on a hero and it reads 100%.
The app's **rating** fixes that by treating every record as if it already had 5 games at a
baseline win rate, then adding your real games:

```
rating = (wins + 5 × baseline) / (games + 5)
```

With a 55% baseline, a 1-0 hero rates (1 + 2.75) / 6 = **62.5%**, while a 6-1 hero rates
(6 + 2.75) / 12 = **72.9%**, so the hero with more proven wins ranks higher. This is the same idea
as a Bayesian average, the method review sites use so a product with one 5-star review doesn't
outrank one with hundreds. Records are also tagged **Low** (under 3 games), **Medium** (3–9) or
**High** (10+) so you can see how much data is behind them.

| Ranking | Baseline | Prior weight | Minimum games to be listed |
|---|---|---|---|
| Heroes (Rankings page) | your overall win rate | 5 games | 10 |
| Heroes (Stats page table) | your overall win rate | 5 games | — |
| A hero's lanes and matchups | your win rate on that hero | 10 games | 3 (best/toughest lists) |

**Why the Rankings page needs 10 games:** the rating alone wasn't enough. With 140 matches, the
three main heroes sat close to the overall 49% win rate, so a single win on another hero (rating
57.7%) nudged it just above average and four 1-0 heroes took the top four places over mains with
36–50 games. Requiring a High sample (10+ games, the same threshold as the green badge) means only
heroes with a record worth judging are ranked.

**Why lanes and matchups use a heavier weight:** a stress test with 140 logged matches, plus 300
simulated heroes with planted matchup effects, showed that with a weight of 5 a lucky 2-0 or 3-0
record against a random hero often pushed real patterns out of a hero page's top 3. A weight of 10
plus a 3-game minimum raised how often a real ±25% matchup effect reached the top 3 from about 55%
to about 75% at realistic sample sizes.
- Dark Bootstrap 5 theme, responsive down to phone width

## Error handling

- **Form input:** every form is checked on the server, and problems are shown as a message above
  the form with your input kept. This covers missing fields, non-numeric or negative numbers,
  unrealistically large numbers (for example more than 200 kills), notes over 2,000 characters,
  a missing lane, a length that isn't minutes:seconds, hero notes over 5,000 characters,
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
| Rankings | `/rankings?sort=<rating\|win_rate\|games\|kda>` | Your heroes ranked by rating, with a GET form to change the order |
| Matchups | `/matchups?hero=<id>` | GET form to pick your hero, then tabs for lane opponents, lane partners, enemy team and your team |
| Heroes | `/heroes` | Hero grid |
| Hero page | `/heroes/<id>` | Lanes, matchups, pairings, notes and matches for one hero, plus a POST form (`/heroes/<id>/notes`) to save your notes |

## Database

SQLite, with five tables defined in `deadlocktracker/schema.sql`:

- **user**: `id`, `username`, `password` (hashed)
- **hero**: `id`, `name` (seeded with the roster when the database is initialized)
- **match_log**: one row per game, with `user_id` → `user.id` and `hero_id` → `hero.id` foreign keys.
  Includes `lane` (Yellow/Blue/Green), `team` (Hidden King/Archmother) and `duration_sec`
- **match_player**: the other heroes in a game, one row each, with `match_id` → `match_log.id`
  and `hero_id` → `hero.id` foreign keys. `side` is `ally` or `enemy`, and `in_lane` marks your
  lane partner or lane opponents. `UNIQUE (match_id, hero_id)` stops a hero appearing twice in one
  match. Rows are deleted automatically with their match (`ON DELETE CASCADE`).
- **hero_note**: your own notes on a hero, with `user_id` → `user.id` and `hero_id` → `hero.id`
  foreign keys and `UNIQUE (user_id, hero_id)` so each player has one note per hero

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
