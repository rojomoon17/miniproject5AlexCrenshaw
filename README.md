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
  rating, average souls and souls/min. It shows the working behind every rating: how much a game
  counts at each age, how your average is worked out, and for each hero its weighted ("counted as")
  record, how much of the rating comes from its own games versus your average, and the formula
  with the real numbers
- The match history shows how much each game **counts as** towards ratings right now (1 for games in
  the 30 days before your latest, then halving every 60 days)
- **Matchups** page: pick one of your heroes and see your win rate and souls/min against each lane
  opponent, with each lane partner, and with each hero on the enemy team or your team. Matchups are
  kept separate per hero: beating a hero in lane on Apollo says nothing about facing them on Shiv
- **Hero pages** for every hero you've played: record, win rate, KDA, souls and souls/min; win rate
  by lane with your best lane highlighted; your best and toughest lane matchups, lane partners,
  teammates and enemies; your own notes on the hero (saved per player); the notes from all your
  matches on that hero; and your match history on them
- **Heroes** page: the full roster with your record on each hero; heroes you've played link to
  their hero page
- **Rankings** page: your heroes with at least 10 games, enough of them recent, ranked from best to
  worst by their **rating** (see below), with a podium for your top three, a range bar for each hero
  and each hero's best lane. A **Counted as** column shows each hero's record after weighting by age
  (for example 6-8 counting as 3.2-3.0), marked ▲ when its recent games went better than its older
  ones and ▼ when they went worse (a difference of 3+ points), so you can see when recency is
  lifting or lowering a rating. Other heroes are listed separately under "Not enough games yet" with how
  many more games they need, and heroes held back because their games are mostly old are marked so. A GET form lets you rank by rating, the safe (low-end) estimate, win rate
  (all games, unadjusted), games played or KDA. The first three can give different orders:
  - **Rating** is the best single guess at how good you are on a hero now
  - **Safe estimate** puts the heroes you're surest about first, so a big solid record (65-35)
    beats a short hot streak (8-2) even when their ratings are close
  - **Win rate (all games, unadjusted)** is your all-time record with nothing adjusted. It differs
    most from rating when results have changed over time: a hero you went 30-10 on months ago and
    3-7 on recently still shows 66% here but rates around 46%
- Dark Bootstrap 5 theme, responsive down to phone width

## How the rating works

A plain win rate is misleading in two ways: on small samples (win your only game on a hero and it
reads 100%) and over time (a game from months ago counts the same as last night's). The app's
**rating** (in `deadlocktracker/ratings.py`) handles both, the same way for every player. Nothing in
it is tuned to a particular player or data set; every setting is either worked out from the
player's own games or was chosen by testing on many different kinds of player (see below).

1. **Recent games count more.** Each game is weighted by its age, measured from the player's most
   recent game. Games from the 30 days before it count fully; after that a game's weight halves
   every 60 days, so a game 90 days older counts half, 150 days a quarter, and so on. Ratings
   follow how you play now and the current patch, and because age is measured from your latest game
   rather than today's date, a break from the game doesn't erase your history. W-L records and game
   counts on every page still include every game.
2. **Each rating starts from the level above it.** Ratings form a chain:

   ```
   50%  ->  your average  ->  your rating on a hero  ->  that hero's lanes and matchups
   ```

   Your average starts at 50% (what matchmaking aims every player at) and moves to your real average
   as games add up, with 20 games of pull towards 50%. Each hero starts from your average, and each
   lane or matchup from your rating on that hero. A record is treated as if it already had *k*
   games at its starting point, then your games are added:

   ```
   rating = (recency-weighted wins + k × starting point) / (recency-weighted games + k)
   ```

3. **The data decides how strong the starting point is (empirical Bayes).** Instead of picking *k*
   by hand, the app estimates it from the player's own records each time (method of moments): if the
   records' win rates differ by more than luck alone would explain, the differences are real and *k*
   is small; if the spread looks like luck, *k* is large. *k* is kept between 3 and 15 games, and is 10
   when there are fewer than 4 records to estimate it from.
4. **Every rating comes with a range.** The rating is the mean of a Beta distribution, which also
   gives an **80% range**: where the true win rate probably is. The bars on the Rankings, hero and
   Matchups pages show it, coloured green when the whole range is above the starting point and red
   when it's all below. More games means a narrower range.

How each list uses the rating:

| List | Starting point | Ordered by | Minimum games |
|---|---|---|---|
| Rankings page | your average | rating (or another option in the form) | 10, counting as 5+ after weighting |
| A hero's best lane | your rating on that hero | low end of the range | — |
| Best lane matchups / partners / teammates | your rating on that hero | low end of the range | 3 |
| Toughest lane matchups / partners / enemies | your rating on that hero | high end of the range | 3 |

Ordering the best by the low end of the range, and the toughest by the high end, puts the records
we're surest about first: a 5-1 matchup outranks a 1-0 one even though 1-0 is a "perfect" record.
The 10-game minimum for the Rankings page is needed whatever kind of player you are: a hero with one
or two games is rated "probably about average", which would otherwise outrank any hero that's proven
slightly below average. The same happens to a hero whose games are mostly months old: weighted by
age, its 10+ games may count as only 3 or 4, so its rating falls back towards your average (for
example, 12 games all played 200 days before your latest count as about 1.7). So a ranked hero's
games must also count as at least **5 effective games**. At the
largest *k* (15) that makes the hero's own games at least a quarter of its rating, while a hero
you play about twice a month still qualifies (a steady rate of *r* games a day settles at about
(30 + 86.6) × *r* = 116.6 × *r* effective games). Records are also tagged **Low** (under 3 games), **Medium** (3–9) or
**High** (10+).

### How it was validated

The settings were chosen and checked by simulation, where each simulated hero's **true** win rate is
known, so the ratings can be scored against the truth. The simulations covered ten very different
kinds of player: newcomers (15 games), casual players (60), one-tricks (300 games on one hero), flex
players (12 heroes evenly), players with a few mains and some one-off games, strong (62% average)
and struggling (38%) players, players whose heroes are all equal or very different, and long
histories (1,500 games). Each was simulated 400 times.

- **Accuracy:** for every kind of player, ratings were closer to the true win rate than the plain
  win rate was (7–77% less error, most for players with many small samples).
- **Honest ranges:** the true win rate fell inside the "80%" range 79–91% of the time for every kind
  of player, so the ranges are trustworthy and lean slightly cautious. Two choices made this hold
  for everyone: capping *k* at 15 (with no cap, ranges were overconfident, catching the true value
  only 47–72% of the time) and starting your average at 50% (which lifted newcomers from 71% to 86%).
- **Recency:** a 60-day half-life was compared with 15, 30, 120 and 240 days and no recency at all,
  for players who play daily, every few days or weekly, with stable skill, slowly changing skill, or a
  sudden change from a patch. No single half-life is best for everyone, but 60 days had the smallest
  worst-case error. Letting the most recent 30 days count fully before the halving starts was then
  compared with halving from day one and with 30-, 45- and 90-day half-lives after the 30 days:
  30 full days then a 60-day half-life had the smallest worst-case error (6.9 points, against 7.3)
  and a lower average error (5.7 against 5.8).
- **Matchups:** with effects planted on specific matchups (for example ±25% win chance against one
  hero in lane), the method put the planted matchup in a hero page's top 3 about 80% of the time with
  45 games on the hero and about 95% with 150 games, compared with about 75% and 80% for a simple
  fixed-weight average. Any method needs games to work with: with few games on a hero, many matchups
  have only one or two games and luck can still hide a real effect, which is why each one shows a range.
- **Limits:** with around 40 games on a hero, its true win rate is still uncertain by roughly
  ±8 percentage points (80% range). When a player's heroes are close in strength, no method can
  reliably say which is best, and the overlapping range bars show this.
- **Maths:** the Beta-distribution functions are written by hand (no SciPy dependency) and checked
  against 200,000 random samples from Python's `random.betavariate` (largest difference 0.1 percentage
  points).

## Assignment requirements

| Requirement | Where it's met |
|-------------|----------------|
| Header comments | Every `.py` file in `deadlocktracker/` starts with the class, name and project |
| Imports | Standard library, then Flask/Werkzeug, then the app's own modules, at the top of each file |
| Folder structure | Application factory package modeled on the Flask tutorial (see [Project structure](#project-structure)) |
| 5+ pages with templates | 13 page templates extending `base.html`, with shared partials pulled in by `include` (see [Pages](#pages)) |
| Form with GET and POST | Log match / edit match (`/match/new`, `/match/<id>/edit`), register, log in and hero notes |
| SQLite, 2+ tables with a foreign key | 5 tables; `match_log`, `match_player` and `hero_note` link to `user` and `hero` (see [Database](#database)) |
| Bootstrap with a modal | Bootstrap 5.3.3; Quick log modal in `base.html` and delete confirmation modal in `_delete_modal.html` |
| Register and login | `auth.py`: register, log in, log out, hashed passwords, `login_required` |
| requirements.txt | Pinned Flask 3.1.3 and its dependencies |
| README | Installation, `init-db` and running the server below, plus an AI Usage section |

## Error handling

- **Form input:** every form is checked on the server, and problems are shown as a message above
  the form with your input kept. This covers missing fields, non-numeric or negative numbers,
  unrealistically large numbers (for example more than 200 kills), notes over 2,000 characters,
  a missing lane, a length that isn't minutes:seconds, hero notes over 5,000 characters,
  missing teammates or enemies, a missing lane partner, anything other than 2 lane opponents,
  duplicate heroes, and usernames/passwords that are too long or too short.
- **Error pages:** 400, 403, 404, 405, 409, 500 and 503 errors show a styled page with a plain-English explanation
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
| Rankings | `/rankings?sort=<rating\|low\|win_rate\|games\|kda>` | Your heroes ranked by rating, with a GET form to change the order |
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

Requires Python 3 (tested with Python 3.11) and Git.

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

## Using it for the first time

A new account starts empty, and the pages fill in as you play:

- **After 1 game:** match history, stats and a page for that hero, where you can keep notes.
- **After 3 games with or against a hero:** it can appear in a hero page's best/toughest lists.
- **After 10 games on a hero:** it's ranked on the Rankings page, as long as you've played it
  recently enough (before that it's listed under "Not enough games yet" with how many more it needs).

Every rating starts at an even 50% and only moves as your record builds, so the first few games
change little. The match history page has a short getting-started guide, and the Rankings page
explains the full system even before you've logged anything.

## Updating the hero roster

The roster has 44 heroes, including the six from **Old Gods, New Blood** (January 2026) and the
six from **City Never Sleeps** (September 2026). Valve adds heroes regularly. Add new names to the
`INSERT INTO hero` statements at the bottom of `deadlocktracker/schema.sql`, then re-run `init-db`
(this clears existing data).

## AI Usage

This project was built with Claude (Anthropic), used through Claude Code in the Claude desktop app.

**Claude wrote all of the code and documentation.** That includes every Python file, the SQL schema
and hero list, all templates, CSS and JavaScript, `requirements.txt` and this README. Claude also:

- planned the project against the rubric and designed the database and page structure
- designed the rating system (recency weighting, empirical-Bayes prior, ranges, ranking rules) and
  chose its settings by writing and running simulations
- researched the current hero roster on the web
- wrote and ran the tests, and generated the sample and stress-test match data used for testing
- set up the environment, made every commit (authored as Claude) and pushed them to GitHub

**My part was directing the project.** I chose the idea (a Deadlock match tracker) and decided what
it should do and how it should behave, through requests and feedback, including:

- what to record: souls per minute, both teams, the lane played, a lane partner and two lane
  opponents, every match having all 12 heroes, and no duplicate heroes
- the game's current rules and names: no solo lanes, the Hidden King and Archmother sides, and
  which update heroes were missing
- how stats should work: match length as minutes:seconds, matchups kept separate per hero, and
  souls/min never averaged across heroes
- hero pages with notes, best matchups, pairings and lanes
- weighting ratings by experience, a Rankings page, and fixing heroes with one won game topping it
- which suggested rating improvements to adopt, and that the system should work for any player
- requiring recent games for a hero to be ranked, counting games fully for their first 30 days,
  and showing how each rating is built
- the wording and sort-option changes I asked for after reviewing the pages

I tested the app in the browser and reviewed Claude's results and explanations before accepting
changes.

## Credits

- Structure based on the [Flask tutorial](https://flask.palletsprojects.com/en/stable/tutorial/)
- Styling with [Bootstrap 5](https://getbootstrap.com/)
- *Deadlock* is a trademark of Valve Corporation. This is an unofficial fan project for a class assignment.
