CREATE TABLE countries (
    country_id   INTEGER PRIMARY KEY,
    country_name VARCHAR(100) NOT NULL
);

CREATE TABLE leagues (
    league_id   INTEGER PRIMARY KEY,
    league_name VARCHAR(100) NOT NULL,
    country_id  INTEGER REFERENCES countries(country_id)
);

CREATE TABLE teams (
    team_id          INTEGER PRIMARY KEY,
    team_name        VARCHAR(100) NOT NULL,
    team_fifa_api_id INTEGER
);

CREATE TABLE team_attributes (
    attr_id                  SERIAL PRIMARY KEY,
    team_id                  INTEGER REFERENCES teams(team_id),
    season_date              DATE,
    build_up_play_speed      INTEGER,
    chance_creation_passing  INTEGER,
    defence_pressure         INTEGER
    -- add other attribute columns only if trivially available from source;
    -- this table is lightly used (1-2 bonus queries), don't over-invest
);

CREATE TABLE players (
    player_id   INTEGER PRIMARY KEY,
    player_name VARCHAR(100) NOT NULL,
    birthday    DATE,
    height      NUMERIC,
    weight      NUMERIC
);

CREATE TABLE player_attributes (
    attr_id         SERIAL PRIMARY KEY,
    player_id       INTEGER REFERENCES players(player_id),
    date            DATE,
    overall_rating  INTEGER,
    potential       INTEGER,
    finishing       INTEGER
    -- lightly used, same as team_attributes — don't over-invest
);

CREATE TABLE matches (
    match_id      INTEGER PRIMARY KEY,
    season        VARCHAR(20),
    stage         INTEGER,
    match_date    DATE,
    league_id     INTEGER REFERENCES leagues(league_id),
    home_team_id  INTEGER REFERENCES teams(team_id),
    away_team_id  INTEGER REFERENCES teams(team_id),
    home_score    INTEGER,
    away_score    INTEGER
);

CREATE TABLE match_events (
    event_id    SERIAL PRIMARY KEY,
    match_id    INTEGER REFERENCES matches(match_id),
    event_type  VARCHAR(10) CHECK (event_type IN ('goal', 'card')),
    minute      INTEGER,
    player_id   INTEGER REFERENCES players(player_id),
    team_id     INTEGER REFERENCES teams(team_id),
    detail      VARCHAR(50)  -- goal: header/normal/penalty etc. if present;
                              -- card: yellow/red
);

-- Indexes worth adding once data is loaded (mention in README under
-- "performance considerations"):
-- CREATE INDEX idx_match_events_match ON match_events(match_id);
-- CREATE INDEX idx_match_events_player ON match_events(player_id);
-- CREATE INDEX idx_matches_season ON matches(season);
-- CREATE INDEX idx_matches_teams ON matches(home_team_id, away_team_id);
