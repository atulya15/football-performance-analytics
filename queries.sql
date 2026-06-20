-- ============================================================
-- Q1: Top Scorers by Team
-- Business Question: Who are the top goal scorers for each team?
-- SQL Concepts: INNER JOIN (match_events -> players -> teams), GROUP BY,
--               ROW_NUMBER() PARTITION BY team for "top N per team"
--               (instead of a single global LIMIT, which would bias
--               toward a handful of high-scoring teams)
-- ============================================================
WITH player_goals AS (
    SELECT e.team_id, e.player_id, p.player_name, COUNT(*) AS goals
    FROM match_events e
    JOIN players p ON p.player_id = e.player_id
    WHERE e.event_type = 'goal' AND e.player_id IS NOT NULL
    GROUP BY e.team_id, e.player_id, p.player_name
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY goals DESC) AS rn
    FROM player_goals
)
SELECT t.team_name, r.player_name, r.goals
FROM ranked r
JOIN teams t ON t.team_id = r.team_id
WHERE r.rn <= 3
ORDER BY t.team_name, r.goals DESC;


-- ============================================================
-- Q2: Team Season Performance Summary
-- Business Question: What are each team's wins/draws/losses/goals
--                     for/against/goal difference per season?
-- SQL Concepts: Aggregation, CASE WHEN for W/D/L classification,
--               UNION ALL to unify home/away perspective, GROUP BY
-- ============================================================
WITH team_matches AS (
    SELECT season, home_team_id AS team_id, home_score AS goals_for, away_score AS goals_against,
        CASE WHEN home_score > away_score THEN 'W'
             WHEN home_score = away_score THEN 'D'
             ELSE 'L' END AS result
    FROM matches
    UNION ALL
    SELECT season, away_team_id AS team_id, away_score AS goals_for, home_score AS goals_against,
        CASE WHEN away_score > home_score THEN 'W'
             WHEN away_score = home_score THEN 'D'
             ELSE 'L' END AS result
    FROM matches
)
SELECT t.team_name, tm.season,
    COUNT(*) AS matches_played,
    SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN result = 'D' THEN 1 ELSE 0 END) AS draws,
    SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) AS losses,
    SUM(goals_for) AS goals_for,
    SUM(goals_against) AS goals_against,
    SUM(goals_for) - SUM(goals_against) AS goal_difference
FROM team_matches tm
JOIN teams t ON t.team_id = tm.team_id
GROUP BY t.team_name, tm.season
ORDER BY t.team_name, tm.season;


-- ============================================================
-- Q3: Home vs Away Advantage
-- Business Question: How much stronger is a team at home vs away,
--                     league-wide and per team?
-- SQL Concepts: CASE WHEN, aggregation, CTEs, comparison across
--               two derived rates
-- ============================================================
-- League-wide
SELECT
    ROUND(100.0 * SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) / COUNT(*), 2) AS home_win_pct,
    ROUND(100.0 * SUM(CASE WHEN away_score > home_score THEN 1 ELSE 0 END) / COUNT(*), 2) AS away_win_pct,
    ROUND(100.0 * SUM(CASE WHEN home_score = away_score THEN 1 ELSE 0 END) / COUNT(*), 2) AS draw_pct
FROM matches;

-- Per team
WITH home_stats AS (
    SELECT home_team_id AS team_id, COUNT(*) AS home_played,
        SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) AS home_wins
    FROM matches GROUP BY home_team_id
),
away_stats AS (
    SELECT away_team_id AS team_id, COUNT(*) AS away_played,
        SUM(CASE WHEN away_score > home_score THEN 1 ELSE 0 END) AS away_wins
    FROM matches GROUP BY away_team_id
)
SELECT t.team_name,
    h.home_played, h.home_wins, ROUND(100.0 * h.home_wins / h.home_played, 2) AS home_win_pct,
    a.away_played, a.away_wins, ROUND(100.0 * a.away_wins / a.away_played, 2) AS away_win_pct,
    ROUND(100.0 * h.home_wins / h.home_played - 100.0 * a.away_wins / a.away_played, 2) AS home_advantage_pct
FROM teams t
JOIN home_stats h ON h.team_id = t.team_id
JOIN away_stats a ON a.team_id = t.team_id
ORDER BY home_advantage_pct DESC;


-- ============================================================
-- Q4: Teams Averaging More Than X Goals
-- Business Question: Which teams average more than 1.7 goals per match
--                     (combining home and away matches)?
-- SQL Concepts: GROUP BY, HAVING, UNION ALL to combine home/away goals
-- ============================================================
WITH team_goals AS (
    SELECT home_team_id AS team_id, home_score AS goals_for FROM matches
    UNION ALL
    SELECT away_team_id AS team_id, away_score AS goals_for FROM matches
)
SELECT t.team_name, COUNT(*) AS matches_played, ROUND(AVG(goals_for), 2) AS avg_goals_per_match
FROM team_goals tg
JOIN teams t ON t.team_id = tg.team_id
GROUP BY t.team_name
HAVING AVG(goals_for) > 1.7
ORDER BY avg_goals_per_match DESC;


-- ============================================================
-- Q5: Top Scorer Per League (All-Time)
-- Business Question: Who is the single top scorer in each league,
--                     across all seasons in the dataset?
-- SQL Concepts: CTE + RANK() PARTITION BY league_id (grain: league only)
-- ============================================================
WITH player_league_goals AS (
    SELECT m.league_id, e.player_id, p.player_name, COUNT(*) AS goals
    FROM match_events e
    JOIN matches m ON m.match_id = e.match_id
    JOIN players p ON p.player_id = e.player_id
    WHERE e.event_type = 'goal' AND e.player_id IS NOT NULL
    GROUP BY m.league_id, e.player_id, p.player_name
),
ranked AS (
    SELECT *, RANK() OVER (PARTITION BY league_id ORDER BY goals DESC) AS rnk
    FROM player_league_goals
)
SELECT l.league_name, r.player_name, r.goals
FROM ranked r
JOIN leagues l ON l.league_id = r.league_id
WHERE r.rnk = 1
ORDER BY r.goals DESC;


-- ============================================================
-- Q6: Top Scorer Per League Per Season
-- Business Question: Who is the top scorer in each league, in each
--                     individual season?
-- SQL Concepts: CTE + RANK() PARTITION BY league_id, season
--               (different grain from Q5 — Q5 ranks all-time totals
--               within a league; Q6 resets the ranking every season,
--               so a player can appear multiple times here, once per
--               season they led their league, whereas Q5 has exactly
--               one row per league. These are NOT duplicates of each
--               other — see README interpretation.)
-- ============================================================
WITH player_league_season_goals AS (
    SELECT m.league_id, m.season, e.player_id, p.player_name, COUNT(*) AS goals
    FROM match_events e
    JOIN matches m ON m.match_id = e.match_id
    JOIN players p ON p.player_id = e.player_id
    WHERE e.event_type = 'goal' AND e.player_id IS NOT NULL
    GROUP BY m.league_id, m.season, e.player_id, p.player_name
),
ranked AS (
    SELECT *, RANK() OVER (PARTITION BY league_id, season ORDER BY goals DESC) AS rnk
    FROM player_league_season_goals
)
SELECT l.league_name, r.season, r.player_name, r.goals
FROM ranked r
JOIN leagues l ON l.league_id = r.league_id
WHERE r.rnk = 1
ORDER BY l.league_name, r.season;


-- ============================================================
-- Q7: Most Efficient Players (Goals per Appearance)
-- Business Question: Which players score most efficiently?
-- SQL Concepts: CTE, aggregation, ratio metric, minimum-sample filter
-- NOTE — deliberate redefinition: this is goals PER MATCH APPEARANCE,
--   not goals per 90 minutes. The source Match table has no per-match
--   minutes-played field for individual players, so a true "per-90"
--   metric isn't computable from this dataset.
-- NOTE — second limitation, found while building this query: the 115
--   player lineup/position columns (home_player_1..11, etc.) were
--   dropped in Phase 4 as out of scope, which means there is no direct
--   "did this player appear in this match" table either. "Appearance"
--   here is therefore approximated as "a distinct match in which the
--   player has at least one recorded goal or card event" — this
--   UNDERCOUNTS true appearances (a player who played 90 minutes with
--   no goal/card has zero recorded events and isn't counted at all),
--   so goals-per-appearance here is a biased-high estimate of true
--   scoring efficiency. Flagging this explicitly rather than presenting
--   it as a precise rate stat.
-- ============================================================
WITH player_appearances AS (
    SELECT player_id, COUNT(DISTINCT match_id) AS appearances
    FROM match_events
    WHERE player_id IS NOT NULL
    GROUP BY player_id
),
player_goals AS (
    SELECT player_id, COUNT(*) AS goals
    FROM match_events
    WHERE event_type = 'goal' AND player_id IS NOT NULL
    GROUP BY player_id
)
SELECT p.player_name, pg.goals, pa.appearances,
    ROUND(pg.goals::numeric / pa.appearances, 3) AS goals_per_appearance
FROM player_goals pg
JOIN player_appearances pa ON pa.player_id = pg.player_id
JOIN players p ON p.player_id = pg.player_id
WHERE pa.appearances >= 10  -- minimum sample size to avoid small-N noise (e.g. 1 goal / 1 appearance = 1.0)
ORDER BY goals_per_appearance DESC
LIMIT 20;


-- ============================================================
-- Q8: Player Ranking Within Team
-- Business Question: How do players rank within their own team by
--                     total goals scored?
-- SQL Concepts: RANK() PARTITION BY team_id ORDER BY goals DESC
-- ============================================================
WITH player_goals AS (
    SELECT e.team_id, e.player_id, p.player_name, COUNT(*) AS goals
    FROM match_events e
    JOIN players p ON p.player_id = e.player_id
    WHERE e.event_type = 'goal' AND e.player_id IS NOT NULL
    GROUP BY e.team_id, e.player_id, p.player_name
)
SELECT t.team_name, pg.player_name, pg.goals,
    RANK() OVER (PARTITION BY pg.team_id ORDER BY pg.goals DESC) AS team_rank
FROM player_goals pg
JOIN teams t ON t.team_id = pg.team_id
ORDER BY t.team_name, team_rank;


-- ============================================================
-- Q9: Rolling Form Over Last 5 Matches
-- Business Question: How many points has each team earned across its
--                     trailing 5 matches, as of each match date?
-- SQL Concepts: Window function with ROWS BETWEEN 4 PRECEDING AND
--               CURRENT ROW, PARTITION BY team, ORDER BY match_date
-- ============================================================
WITH team_matches AS (
    SELECT match_id, season, match_date, home_team_id AS team_id,
        CASE WHEN home_score > away_score THEN 3
             WHEN home_score = away_score THEN 1
             ELSE 0 END AS points
    FROM matches
    UNION ALL
    SELECT match_id, season, match_date, away_team_id AS team_id,
        CASE WHEN away_score > home_score THEN 3
             WHEN away_score = home_score THEN 1
             ELSE 0 END AS points
    FROM matches
)
SELECT t.team_name, tm.match_date, tm.points,
    SUM(tm.points) OVER (
        PARTITION BY tm.team_id ORDER BY tm.match_date
        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ) AS rolling_5_match_points
FROM team_matches tm
JOIN teams t ON t.team_id = tm.team_id
ORDER BY t.team_name, tm.match_date;


-- ============================================================
-- Q10: Running Total of Team Points
-- Business Question: What is each team's cumulative points total
--                     across a season, match by match?
-- SQL Concepts: SUM() OVER (PARTITION BY team, season ORDER BY match_date)
-- ============================================================
WITH team_matches AS (
    SELECT match_id, season, match_date, home_team_id AS team_id,
        CASE WHEN home_score > away_score THEN 3
             WHEN home_score = away_score THEN 1
             ELSE 0 END AS points
    FROM matches
    UNION ALL
    SELECT match_id, season, match_date, away_team_id AS team_id,
        CASE WHEN away_score > home_score THEN 3
             WHEN away_score = home_score THEN 1
             ELSE 0 END AS points
    FROM matches
)
SELECT t.team_name, tm.season, tm.match_date, tm.points,
    SUM(tm.points) OVER (
        PARTITION BY tm.team_id, tm.season ORDER BY tm.match_date
    ) AS running_total_points
FROM team_matches tm
JOIN teams t ON t.team_id = tm.team_id
ORDER BY t.team_name, tm.season, tm.match_date;


-- ============================================================
-- Q11: Longest Winning Streak
-- Business Question: What is the longest consecutive run of wins
--                     for each team across the dataset?
-- SQL Concepts: Gaps-and-islands via the ROW_NUMBER() difference trick:
--               rn (overall sequence per team) minus
--               row_number() within (team, is_win) ordered the same way
--               stays constant for a consecutive run of the same
--               is_win value, so it groups each unbroken streak into
--               one "island" we can COUNT(*) and MAX() over.
-- ============================================================
WITH team_matches AS (
    SELECT match_id, match_date, home_team_id AS team_id,
        CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS is_win
    FROM matches
    UNION ALL
    SELECT match_id, match_date, away_team_id AS team_id,
        CASE WHEN away_score > home_score THEN 1 ELSE 0 END AS is_win
    FROM matches
),
ordered AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY match_date) AS rn
    FROM team_matches
),
streak_groups AS (
    SELECT *, rn - ROW_NUMBER() OVER (PARTITION BY team_id, is_win ORDER BY match_date) AS grp
    FROM ordered
),
streaks AS (
    SELECT team_id, grp, COUNT(*) AS streak_length
    FROM streak_groups
    WHERE is_win = 1
    GROUP BY team_id, grp
)
SELECT t.team_name, MAX(s.streak_length) AS longest_win_streak
FROM streaks s
JOIN teams t ON t.team_id = s.team_id
GROUP BY t.team_name
ORDER BY longest_win_streak DESC
LIMIT 20;


-- ============================================================
-- Q12: Advanced Multi-Step Analysis — Most Improved Home/Away
--      Goal Differential, Season Over Season
-- Business Question: Which teams most improved the gap between their
--                     home and away goal differential from one season
--                     to the next? (A team closing that gap is getting
--                     relatively stronger on the road; a team widening
--                     it is leaning more on home-field advantage.)
-- SQL Concepts: CTEs + UNION ALL + aggregation + LAG() window function
--               + join, layered together
-- ============================================================
WITH team_season_split AS (
    SELECT team_id, season,
        SUM(CASE WHEN is_home THEN goals_for - goals_against ELSE 0 END) AS home_gd,
        SUM(CASE WHEN NOT is_home THEN goals_for - goals_against ELSE 0 END) AS away_gd
    FROM (
        SELECT home_team_id AS team_id, season, home_score AS goals_for, away_score AS goals_against, TRUE AS is_home FROM matches
        UNION ALL
        SELECT away_team_id AS team_id, season, away_score AS goals_for, home_score AS goals_against, FALSE AS is_home FROM matches
    ) x
    GROUP BY team_id, season
),
home_away_gap AS (
    SELECT team_id, season, home_gd - away_gd AS gap
    FROM team_season_split
),
with_prev AS (
    SELECT team_id, season, gap,
        LAG(gap) OVER (PARTITION BY team_id ORDER BY season) AS prev_gap
    FROM home_away_gap
)
SELECT t.team_name, w.season, w.prev_gap, w.gap AS current_gap,
    w.prev_gap - w.gap AS gap_closed   -- positive = gap shrank (improved road form relative to home)
FROM with_prev w
JOIN teams t ON t.team_id = w.team_id
WHERE w.prev_gap IS NOT NULL
ORDER BY gap_closed DESC
LIMIT 20;
