-- Encounter Atlas reports + "Real or hoax?" voting. All times are unix seconds (UTC).
-- Apply: npx wrangler@4 d1 execute encounters --remote --file schema.sql   (safe to re-run)

-- Accounts: email magic-link sign-in only, nothing secret stored.
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL DEFAULT '',
  created INTEGER NOT NULL DEFAULT (unixepoch()),
  last_seen INTEGER NOT NULL DEFAULT (unixepoch()),
  banned INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pid TEXT NOT NULL UNIQUE,                 -- public id used in URLs (random, not guessable)
  user_id INTEGER REFERENCES users(id),     -- null when sent without an account or email
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'withdrawn')),
  creature TEXT NOT NULL,                   -- slug from creatures.json, or 'other'
  other_what TEXT NOT NULL DEFAULT '',      -- what it was, when creature = 'other'
  seen_date TEXT NOT NULL,                  -- YYYY-MM-DD (witness's local date)
  seen_time TEXT NOT NULL DEFAULT '',       -- HH:MM or ''
  date_approx INTEGER NOT NULL DEFAULT 0,
  lat REAL NOT NULL, lon REAL NOT NULL,     -- EXACT point: private, moderators only
  pub_lat REAL NOT NULL, pub_lon REAL NOT NULL, -- snapped to a ~5 km grid: the only point ever made public
  loc_source TEXT NOT NULL DEFAULT 'map',   -- gps | map | place
  place TEXT NOT NULL DEFAULT '',           -- typed place name (public)
  story TEXT NOT NULL,
  duration TEXT NOT NULL DEFAULT '',
  sounds TEXT NOT NULL DEFAULT '',
  smells TEXT NOT NULL DEFAULT '',
  witnesses INTEGER NOT NULL DEFAULT 1,
  display_name TEXT NOT NULL DEFAULT '',
  anonymous INTEGER NOT NULL DEFAULT 1,
  videos TEXT NOT NULL DEFAULT '[]',        -- JSON [{p: youtube|tiktok|vimeo, id, url}]
  links TEXT NOT NULL DEFAULT '[]',         -- JSON [{url, host}]: photo LINKS (we never take uploads)
  ip_hash TEXT NOT NULL DEFAULT '',
  mod_note TEXT NOT NULL DEFAULT '',
  created INTEGER NOT NULL DEFAULT (unixepoch()),
  updated INTEGER NOT NULL DEFAULT (unixepoch()),
  approved_at INTEGER
);
CREATE INDEX IF NOT EXISTS reports_status ON reports (status, approved_at);
CREATE INDEX IF NOT EXISTS reports_user ON reports (user_id);

-- Photo uploads are switched off (links only, Mike 2026-10-12). Table kept so old code paths stay valid; it stays empty.
CREATE TABLE IF NOT EXISTS photos (
  id TEXT PRIMARY KEY,                      -- random hex, also the R2 key
  report_id INTEGER NOT NULL REFERENCES reports(id),
  idx INTEGER NOT NULL,
  w INTEGER NOT NULL, h INTEGER NOT NULL, bytes INTEGER NOT NULL,
  removed INTEGER NOT NULL DEFAULT 0,
  created INTEGER NOT NULL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS photos_report ON photos (report_id);

-- Votes. item = 'r:<pid>' (report), 'p:<photo id>' or 'v:<pid>:<n>' (video link n).
-- UNIQUE (item, user_id) is the one-vote-per-account rule.
CREATE TABLE IF NOT EXISTS votes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item TEXT NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id),
  choice TEXT NOT NULL CHECK (choice IN ('real', 'hoax', 'mis')),
  reason TEXT NOT NULL DEFAULT '',
  weight REAL NOT NULL,                     -- 0.2 .. 1, from account age and activity at vote time
  ip_hash TEXT NOT NULL,
  net_hash TEXT NOT NULL,                   -- /24 (IPv4) or /48 (IPv6) network
  held INTEGER NOT NULL DEFAULT 0,          -- burst from one network: not counted until a moderator releases it
  voided INTEGER NOT NULL DEFAULT 0,        -- removed by a moderator
  at INTEGER NOT NULL DEFAULT (unixepoch()),
  UNIQUE (item, user_id)
);
CREATE INDEX IF NOT EXISTS votes_item ON votes (item, at);
CREATE INDEX IF NOT EXISTS votes_user ON votes (user_id, at);

-- Per-item moderation state: frozen items take no votes and show no results.
CREATE TABLE IF NOT EXISTS items (
  item TEXT PRIMARY KEY,
  frozen INTEGER NOT NULL DEFAULT 0,
  flag TEXT NOT NULL DEFAULT '',            -- '', swing, burst, ai, surge
  flag_note TEXT NOT NULL DEFAULT '',
  flagged_at INTEGER,
  ai_flags INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS flags (
  item TEXT NOT NULL,
  user_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  at INTEGER NOT NULL DEFAULT (unixepoch()),
  PRIMARY KEY (item, user_id, kind)
);

-- Rate-limit hits (key = what|who). Pruned daily by the cron trigger.
CREATE TABLE IF NOT EXISTS hits (
  k TEXT NOT NULL,
  at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS hits_k ON hits (k, at);

-- Sign-in links already used (single use).
CREATE TABLE IF NOT EXISTS used_links (
  nonce TEXT PRIMARY KEY,
  at INTEGER NOT NULL DEFAULT (unixepoch())
);

-- Emails sent to a reporter from /mod (automatic approve/reject notes and Mike's replies).
CREATE TABLE IF NOT EXISTS mod_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  report_id INTEGER NOT NULL REFERENCES reports(id),
  kind TEXT NOT NULL,                       -- approved | rejected | reply
  body TEXT NOT NULL DEFAULT '',
  ok INTEGER NOT NULL DEFAULT 1,            -- 0 when Resend refused it
  at INTEGER NOT NULL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS mod_messages_report ON mod_messages (report_id, at);

-- /v1/reports/nearby: bounding box on the public point, newest sighting first.
CREATE INDEX IF NOT EXISTS reports_geo ON reports (status, pub_lat, pub_lon);
CREATE INDEX IF NOT EXISTS reports_seen ON reports (status, seen_date, pid);
