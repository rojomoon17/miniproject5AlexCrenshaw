DROP TABLE IF EXISTS match_player;
DROP TABLE IF EXISTS match_log;
DROP TABLE IF EXISTS hero;
DROP TABLE IF EXISTS user;

CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL
);

CREATE TABLE hero (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL
);

-- "match" is an SQLite keyword, so the table is called match_log.
CREATE TABLE match_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  hero_id INTEGER NOT NULL,
  result TEXT NOT NULL CHECK (result IN ('Win', 'Loss')),
  team TEXT CHECK (team IN ('Amber Hand', 'Sapphire Flame')),
  kills INTEGER NOT NULL DEFAULT 0,
  deaths INTEGER NOT NULL DEFAULT 0,
  assists INTEGER NOT NULL DEFAULT 0,
  souls INTEGER,
  duration_min INTEGER,
  notes TEXT,
  played TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES user (id),
  FOREIGN KEY (hero_id) REFERENCES hero (id)
);

-- The other heroes in a match: your teammates (side = 'ally') and the enemy
-- team (side = 'enemy'). in_lane marks your lane partner (an ally) or your
-- lane opponents (enemies). Your own hero stays on match_log.hero_id.
-- A hero can only be picked once per match, across both teams.
CREATE TABLE match_player (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  hero_id INTEGER NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('ally', 'enemy')),
  in_lane INTEGER NOT NULL DEFAULT 0 CHECK (in_lane IN (0, 1)),
  FOREIGN KEY (match_id) REFERENCES match_log (id) ON DELETE CASCADE,
  FOREIGN KEY (hero_id) REFERENCES hero (id),
  UNIQUE (match_id, hero_id)
);

-- Hero roster. Valve adds heroes regularly; add new ones here and re-run init-db.
INSERT INTO hero (name) VALUES
  ('Abrams'), ('Bebop'), ('Billy'), ('Calico'), ('The Doorman'), ('Drifter'),
  ('Dynamo'), ('Grey Talon'), ('Haze'), ('Holliday'), ('Infernus'), ('Ivy'),
  ('Kelvin'), ('Lady Geist'), ('Lash'), ('McGinnis'), ('Mina'), ('Mirage'),
  ('Mo & Krill'), ('Paige'), ('Paradox'), ('Pocket'), ('Seven'), ('Shiv'),
  ('Sinclair'), ('Victor'), ('Vindicta'), ('Viscous'), ('Vyper'), ('Warden'),
  ('Wraith'), ('Yamato');

-- Old Gods, New Blood (January 2026)
INSERT INTO hero (name) VALUES
  ('Apollo'), ('Celeste'), ('Graves'), ('Rem'), ('Silver'), ('Venator');

-- City Never Sleeps (September 2026)
INSERT INTO hero (name) VALUES
  ('Baba'), ('Deadman Danny'), ('Nurse Harrow'), ('Rat King'), ('Solomon'), ('Violet');
