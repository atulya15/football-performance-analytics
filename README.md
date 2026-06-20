# Football Performance Analytics

Portfolio project analyzing 8 seasons of European football match, team, and
player data sourced from the [Kaggle "European Soccer Database"](https://www.kaggle.com/datasets/hugomathien/soccer)
(Hugo Mathien). Raw SQLite data is parsed, cleaned, and loaded into a
normalized PostgreSQL schema, then queried with 12 analysis queries covering
joins, window functions, CTEs, and gaps-and-islands logic.

## Status

Complete: environment setup, schema design, XML event parsing, data load,
validation, all 12 queries with real captured output, and a statistical
sanity pass. This README documents the full pipeline.

## Dataset overview

The raw `database.sqlite` (not committed — see `.gitignore`) contains 8 tables:

| Table | Rows | Notes |
|---|---|---|
| Country | 11 | Reference table |
| League | 11 | Reference table |
| Team | 299 | `team_fifa_api_id` has ~3.7% nulls |
| Team_Attributes | 1,458 | `buildUpPlayDribbling` ~66.5% null |
| Player | 11,060 | Clean, no nulls |
| Player_Attributes | 183,978 | Sparse nulls (0.5%–1.8%) across rating columns |
| Match | 25,979 | Wide table; 40 betting-odds columns 13–57% null; 8 XML blob columns (`goal`, `card`, `shoton`, `shotoff`, `foulcommit`, `cross`, `corner`, `possession`) ~45% null; 115 player lineup/position columns ~5–7% null |
| sqlite_sequence | 7 | SQLite internal, not part of the data model |

## Pipeline

### 1. Setup

```bash
pip install kaggle psycopg2-binary
mkdir -p ~/.kaggle
# place your Kaggle access token at ~/.kaggle/access_token (chmod 600)
kaggle datasets download -d hugomathien/soccer -p data
unzip data/soccer.zip -d data && rm data/soccer.zip
```

PostgreSQL 17, database `football_analytics`, schema applied from
[`schema.sql`](schema.sql):

```bash
psql -U postgres -h localhost -p 5432 -c "CREATE DATABASE football_analytics;"
psql -U postgres -h localhost -p 5432 -d football_analytics -f schema.sql
```

### 2. XML event parsing — [`scripts/parse_events.py`](scripts/parse_events.py)

The `Match` table embeds 8 XML blob columns. Only `goal` and `card` are
parsed (shoton/shotoff/foulcommit/cross/corner/possession are skipped —
noisier, not needed for any of the 12 queries). Output: a staging CSV
(`data/match_events_staged.csv`, gitignored) later loaded into `match_events`.

**Honest bug documentation — the reconciliation metric that initially looked broken:**

My first reconciliation check compared parsed goal events against the
scoreboard total (`home_score + away_score`) across *all* 25,979 matches and
got **56.88%** — below the 80% sanity threshold, which should mean "something
is wrong with the parsing, not the data." Investigating before assuming the
parser was broken: ~45% of matches structurally have no goal/card blob at
all (the same null rate already flagged during the initial dataset
inspection), so they contribute zero parsed events while still counting
toward the denominator. Restricting the comparison to the 14,217 matches that
*do* have a goal blob gives **103.49%** reconciliation — a healthy result
(the small ~3.5% over-count is plausibly disallowed/VAR-style goal entries
occasionally appearing in the XML). The bug was in my first reconciliation
query, not the parser.

| Metric | Value |
|---|---|
| Total events parsed | 102,094 (39,980 goals + 62,114 cards) |
| Null `player_id` rate | 0.43% (440 events — team-level entries with no `player1`) |
| Parse failure rate | 0.00% (all 14,217 goal blobs + 14,217 card blobs parsed cleanly) |
| Goal-count reconciliation (blob-present matches only) | **103.49%** |

### 3. Data load — [`scripts/load_data.py`](scripts/load_data.py)

Loads `countries`, `leagues`, `teams`, `team_attributes`, `players`,
`player_attributes`, `matches` from SQLite, plus `match_events` from the
Phase 2 staging CSV.

**Key mapping decision:** `teams.team_id` uses the source `Team.team_api_id`
(not the internal `Team.id`), and `players.player_id` uses
`Player.player_api_id` — because those are the IDs referenced inside the
`Match` table's goal/card XML blobs. Using the api_id as the natural key
keeps `match_events` joins trivial instead of requiring an extra id-mapping
table.

**Dropped per scope:** all 115 player lineup/position columns and all 40
betting-odds columns from `matches` — not part of the target schema.

**Second bug found during load:** the first load attempt failed with a
`ForeignKeyViolation` — 609 of 102,094 `match_events` rows (0.6%) reference a
`player_id` not present in the `Player` source table (likely officials or
edge-case IDs embedded in the XML, not roster players). Fix: null out just
the unresolvable `player_id` rather than dropping the row, since the
goal/card event itself is real and worth keeping.

**Row counts loaded (match source exactly):**

| Table | Rows |
|---|---|
| countries | 11 |
| leagues | 11 |
| teams | 299 |
| team_attributes | 1,458 |
| players | 11,060 |
| player_attributes | 183,978 |
| matches | 25,979 |
| match_events | 102,094 |

**Validation:** zero real orphaned foreign keys across every relationship
(`matches`→teams/leagues, `leagues`→countries, `match_events`→matches/teams/players,
`team_attributes`→teams, `player_attributes`→players). Manual spot-check on
3 matches confirmed parsed goal events (grouped by team) match
`home_score`/`away_score` exactly:

| match_id | home_score | away_score | parsed goals by team |
|---|---|---|---|
| 1729 | 1 | 1 | 1 + 1 ✓ |
| 1732 | 2 | 1 | 2 + 1 ✓ |
| 1733 | 4 | 2 | 4 + 2 ✓ |

### 4. Queries — [`queries.sql`](queries.sql), outputs in [`docs/query_outputs/`](docs/query_outputs/)

All 12 queries run against the live database; outputs below are real, not
illustrative.

| # | Query | Concepts | Notable real result |
|---|---|---|---|
| Q1 | Top scorers by team | INNER JOIN, `ROW_NUMBER()` PARTITION BY team | Köln: Novakovic 46, Podolski 33 |
| Q2 | Team season W/D/L/GD | `CASE WHEN`, `UNION ALL`, aggregation | wins+draws+losses = matches_played, every row |
| Q3 | Home vs away advantage | `CASE WHEN`, CTEs, `HAVING` | League-wide: 45.87% home win / 28.74% away — see sample-size fix below |
| Q4 | Teams averaging >1.7 goals/match | `GROUP BY`, `HAVING` | Barcelona 2.79, Real Madrid 2.77 |
| Q5 | Top scorer per league, all-time | CTE + `RANK()` PARTITION BY league | **Messi 295 goals (Spain), Di Natale 156 (Italy), Rooney 135 (England)** |
| Q6 | Top scorer per league per season | CTE + `RANK()` PARTITION BY league, season | Real Golden Boot winners: Drogba '09/10, van Persie x2, Suarez, Aguero, Kane |
| Q7 | Player's share of team goals/season | correlated subquery **and** window function, side by side | Papiss Cisse: 58.5% of SC Freiburg's 2010/11 goals |
| Q8 | Player rank within team | `RANK()` PARTITION BY team | Correctly produces tied ranks |
| Q9 | Rolling 5-match form | `SUM() OVER (... ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)` | Barcelona window correctly caps at 15 (5 wins) |
| Q10 | Running season points total | `SUM() OVER (PARTITION BY team, season ORDER BY match_date)` | Resets cleanly at each new season |
| Q11 | Longest winning streak | gaps-and-islands (see below) | **Bayern Munich 19** (their real 2013/14 streak), Celtic 17 |
| Q12 | Most improved home/away goal differential | CTE + `UNION ALL` + aggregation + `LAG()` + join | Multi-layer synthesis query |

**Q5 vs Q6 — these look similar but aren't duplicates.** Q5 ranks
all-time career totals within a league (one row per league). Q6 resets the
ranking every season (`PARTITION BY league_id, season`), so the same player
can appear multiple times if they led the league in several different
seasons. Different grain, different question.

**Q7 — two implementations, kept as separate files on purpose.**
[`q7a_goal_share_correlated_subquery.txt`](docs/query_outputs/q7a_goal_share_correlated_subquery.txt)
and
[`q7b_goal_share_window_function.txt`](docs/query_outputs/q7b_goal_share_window_function.txt)
are both committed — they produce identical results (2,658 rows), which is
the point. The correlated subquery re-aggregates each team/season's total
goals from scratch for every output row (O(rows × scan)). The window
function (`SUM() OVER (PARTITION BY team_id, season)`) computes each
team/season total exactly once, then broadcasts it to every row in that
partition — one aggregation pass instead of N re-aggregations. The window
function version is what should be used in practice; the correlated
subquery is kept for comparison since both forms are common interview asks.

**Q7 redefinition, stated explicitly:** "efficiency" here is *share of team
goals*, deliberately scoped to a season/team grain rather than a per-90-minutes
rate — the source data has no per-match minutes-played field for individual
players, so per-90 isn't computable from this dataset.

**Q11 — gaps-and-islands technique.** For each team's match sequence ordered
by date, `is_win` is 1 or 0. `rn` (the team's overall sequence number) minus
`ROW_NUMBER() OVER (PARTITION BY team_id, is_win ORDER BY match_date)` stays
constant for every match inside one unbroken streak of the same result —
each unbroken run becomes one "island" with a shared group id, which can
then be `COUNT(*)`'d and `MAX()`'d per team. This is the classic gaps-and-
islands pattern and the most likely query in this set to come up as an
interview follow-up.

### 5. Statistical sanity pass (Phase 6)

Most validation happened organically while building the queries — Messi's
295 career goals, Bayern's 19-game streak, and the real Premier League
Golden Boot winners by season are all independent confirmation the
parsing/joins are correct. A focused pass specifically for things that
wouldn't look "wrong" but would look statistically off on a quick read
found two real issues:

**Fixed — Q3 small-sample bias.** The original per-team home-advantage
leaderboard was topped by teams with only 15–19 home matches (single-season
cameo teams in the dataset) — e.g. CD Numancia's 19-game sample (42.11%)
outranked Manchester City's 152-game record (33.55%). Added
`HAVING COUNT(*) >= 50` (roughly 1.5 seasons) to the home-match CTE. After
the fix, Catania (113 games, 41.43%) and Manchester City (152 games, 33.55%)
top the list — results backed by enough matches to mean something.
League-wide percentages still sum to exactly 100.00% (45.87 + 28.74 + 25.39)
after the fix.

**Investigated, not a bug — two `matches_played` outliers in Q2:**
- *Belgium Jupiler League, 2013/2014*: only 4 teams and 12 total matches in
  the source data (a full season should have 16 teams). This is a genuine
  **gap in the source scrape**, not something broken in this pipeline —
  flagged honestly rather than silently included.
- *Neuchâtel Xamax, Switzerland Super League 2011/2012*: 18 matches vs.
  every other team's 34. This checks out against real history — Xamax was
  **expelled mid-season in January 2012** after a financial collapse, and
  their remaining fixtures were voided. The data is correctly reflecting a
  real event, not a loading error.

## Repo structure

```
football-performance-analytics/
├── README.md
├── schema.sql              # Postgres schema (8 tables)
├── queries.sql              # All 12 analysis queries, commented
├── scripts/
│   ├── parse_events.py      # XML goal/card blob parser -> staging CSV
│   └── load_data.py         # SQLite -> Postgres loader
├── docs/
│   ├── schema_diagram.png
│   ├── query_outputs/       # Real captured output per query
│   └── screenshots/
├── data/                     # gitignored — raw SQLite dataset + staging CSV
└── assets/
```

## Performance considerations

Indexes worth adding once data volume grows beyond this dataset's scale
(not yet applied — `match_events` and `matches` are small enough that
sequential scans are fine here, but these are the right indexes for a
larger load):

```sql
CREATE INDEX idx_match_events_match ON match_events(match_id);
CREATE INDEX idx_match_events_player ON match_events(player_id);
CREATE INDEX idx_matches_season ON matches(season);
CREATE INDEX idx_matches_teams ON matches(home_team_id, away_team_id);
```

## Known limitations

- **Q7 "appearance"/"share" metrics are scoped to attributed goals only.**
  A small number of parsed goal events have no resolvable `player_id` (see
  the 609-row orphan fix above) and are excluded from per-player share
  calculations — "share of team goals" means share of *attributed* goals.
- **No true per-90-minutes metrics are possible** from this dataset — there
  is no per-match minutes-played field for individual players.
- **Belgian Jupiler League 2013/2014 is incomplete** in the source data
  (12 matches instead of a full ~240-match season).
- **Betting-odds columns and full goal/card detail (assists, exact card
  reason beyond yellow/red) were intentionally out of scope** for this
  pass — dropped at load time, not lost track of.

## Next steps

- Schema diagram (`docs/schema_diagram.png`)
- GitHub polish / repo description, topics, badges
