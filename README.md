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
- **Rankings** page: your heroes with at least 10 games, ranked from best to worst by their
  **rating** (see below), with a podium for your top three, a range bar for each hero and each hero's
  best lane. Heroes with fewer games are listed separately under "Not enough games yet" with how many
  more games they need. A GET form lets you rank by rating, the safe (low-end) estimate, raw win
  rate, games played or KDA
- Dark Bootstrap 5 theme, responsive down to phone width

## How the rating works

A plain win rate is misleading in two ways: on small samples (win your only game on a hero and it
reads 100%) and over time (a game from months ago counts the same as last night's). The app's
**rating** (in `deadlocktracker/ratings.py`) handles both in three steps:

1. **Recent games count more.** Each game is weighted by its age: a game 60 days old counts half
   as much as one played today, 120 days a quarter, and so on. Ratings follow how you play now and
   the current patch. W-L records and game counts on every page still include every game.
2. **Every rating starts from your average, by an amount the data decides (empirical Bayes).**
   Each record is treated as if it already had *k* games at a baseline win rate (your overall win
   rate when comparing heroes, your win rate on a hero when comparing its lanes and matchups):

   ```
   rating = (recent-weighted wins + k × baseline) / (recent-weighted games + k)
   ```

   Instead of picking *k* by hand, the app estimates it from your data (method of moments): if your
   records' win rates differ by more than luck alone would explain, the differences are real and
   *k* is small; if the spread looks like luck, *k* is large and ratings stay near average. *k* is
   kept between 3 and 30 games, and falls back to 10 when there are too few records to estimate it.
3. **Every rating comes with a range.** The rating is the middle of a Beta distribution, which also
   gives an **80% range**: where your true win rate probably is. The bars on the Rankings, hero and
   Matchups pages show it, coloured green when the whole range is above your baseline and red when
   it's all below. More games means a narrower range.

How each list uses the rating:

| List | Baseline | Ordered by | Minimum games |
|---|---|---|---|
| Rankings page | your overall win rate | rating (or another option in the form) | 10 |
| A hero's best lane | your win rate on that hero | low end of the range | — |
| Best lane matchups / partners / teammates | your win rate on that hero | low end of the range | 3 |
| Toughest lane matchups / partners / enemies | your win rate on that hero | high end of the range | 3 |

Ordering the best by the low end of the range, and the toughest by the high end, puts the records
we're surest about first: a 5-1 matchup outranks a 1-0 one even though 1-0 is a "perfect" record.
Records are also tagged **Low** (under 3 games), **Medium** (3–9) or **High** (10+).

### How it was tested

The method was chosen by testing, using 140 logged sample matches with **planted** effects (for
example, Haze was set up to lose more often against Infernus in lane) and simulations of 300
heroes and 1,000 players:

- **Matchups:** the fitted weight plus range ordering found a planted ±25% lane matchup in a hero
  page's top 3 about **80%** of the time at realistic sample sizes (45 games on a hero), and about
  **96%** with 150 games. The previous fixed-weight method managed about 75% and 80%. On the 140
  logged matches it surfaced 9 of the 12 planted patterns. The 3 it missed were cases where the
  random results went against the plant (for example, a planted bad matchup that went 4-1), so the
  data never showed them; every pattern the data did support was found.
- **Hero rankings:** without the 10-game minimum, heroes with 1–3 games reached the top 3 in 82–96%
  of simulated players. A one- or two-game hero is estimated as "about average", which beats a main
  that's proven slightly below average. With the minimum, small-sample heroes never reach the
  rankings. Every ordering method then picked the truly best main equally often (about 60%), which
  shows the real limit is data: with about 40 games on a hero, its true win rate is still uncertain by
  roughly ±15 points. That's why the app shows ranges instead of a single number.
- **The weight's ceiling** (30 games) barely affected which matchups were found (results were within
  1 point for ceilings from 15 to 100). A lower ceiling keeps real effects visible in the numbers
  instead of squashing every rating towards the baseline.
- **The Beta-distribution maths** is written by hand (no SciPy dependency) and checked against
  200,000 random samples from Python's `random.betavariate` (largest difference 0.1 percentage points).

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
├── ratings.py         # recency weighting, fitted prior and rating ranges
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
