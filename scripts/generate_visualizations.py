"""
Generate a handful of chart visualizations from the loaded Postgres data,
backing the README with real numbers (not mockups). Saves PNGs to
docs/visualizations/.
"""

import matplotlib.pyplot as plt
import psycopg2

PG_DSN = dict(host="localhost", port=5432, dbname="football_analytics", user="postgres", password="postgres")
OUT_DIR = "docs/visualizations"

plt.rcParams["font.size"] = 10


def fetch(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return cols, cur.fetchall()


def chart_top_scorers_alltime(conn):
    _, rows = fetch(conn, """
        SELECT p.player_name, COUNT(*) AS goals
        FROM match_events e JOIN players p ON p.player_id = e.player_id
        WHERE e.event_type = 'goal' AND e.player_id IS NOT NULL
        GROUP BY p.player_name ORDER BY goals DESC LIMIT 10;
    """)
    names = [r[0] for r in rows][::-1]
    goals = [r[1] for r in rows][::-1]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(names, goals, color="#2980b9")
    ax.set_xlabel("Total goals (all leagues, 2008-2016)")
    ax.set_title("Top 10 All-Time Goal Scorers")
    for bar, g in zip(bars, goals):
        ax.text(bar.get_width() + 3, bar.get_y() + bar.get_height() / 2, str(g), va="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/top_10_scorers_alltime.png", dpi=150)
    plt.close()


def chart_home_away_winrate(conn):
    _, rows = fetch(conn, """
        SELECT
            ROUND(100.0*SUM(CASE WHEN home_score>away_score THEN 1 ELSE 0 END)/COUNT(*),1) AS home_win,
            ROUND(100.0*SUM(CASE WHEN home_score=away_score THEN 1 ELSE 0 END)/COUNT(*),1) AS draw,
            ROUND(100.0*SUM(CASE WHEN away_score>home_score THEN 1 ELSE 0 END)/COUNT(*),1) AS away_win
        FROM matches;
    """)
    home_win, draw, away_win = rows[0]

    fig, ax = plt.subplots(figsize=(6, 6))
    labels = [f"Home win\n{home_win}%", f"Draw\n{draw}%", f"Away win\n{away_win}%"]
    ax.pie([home_win, draw, away_win], labels=labels, colors=["#27ae60", "#95a5a6", "#c0392b"],
           autopct=None, startangle=90, textprops={"fontsize": 11})
    ax.set_title(f"Match Outcomes League-Wide\n(n = 25,979 matches)")
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/home_away_outcome_split.png", dpi=150)
    plt.close()


def chart_goals_per_season(conn):
    _, rows = fetch(conn, """
        SELECT season, SUM(home_score) + SUM(away_score) AS total_goals, COUNT(*) AS matches,
               ROUND((SUM(home_score)+SUM(away_score))::numeric / COUNT(*), 2) AS goals_per_match
        FROM matches GROUP BY season ORDER BY season;
    """)
    seasons = [r[0] for r in rows]
    gpm = [float(r[3]) for r in rows]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(seasons, gpm, marker="o", color="#8e44ad", linewidth=2)
    ax.set_ylabel("Goals per match (all leagues combined)")
    ax.set_title("Goals-Per-Match Trend by Season")
    ax.set_ylim(min(gpm) - 0.1, max(gpm) + 0.1)
    plt.xticks(rotation=45, ha="right")
    for x, y in zip(seasons, gpm):
        ax.annotate(f"{y}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/goals_per_match_by_season.png", dpi=150)
    plt.close()


def chart_longest_win_streaks(conn):
    _, rows = fetch(conn, """
        WITH team_matches AS (
            SELECT match_id, match_date, home_team_id AS team_id, CASE WHEN home_score>away_score THEN 1 ELSE 0 END AS is_win FROM matches
            UNION ALL
            SELECT match_id, match_date, away_team_id AS team_id, CASE WHEN away_score>home_score THEN 1 ELSE 0 END AS is_win FROM matches
        ), ordered AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY match_date) AS rn FROM team_matches
        ), streak_groups AS (
            SELECT *, rn - ROW_NUMBER() OVER (PARTITION BY team_id, is_win ORDER BY match_date) AS grp FROM ordered
        ), streaks AS (
            SELECT team_id, grp, COUNT(*) AS streak_length FROM streak_groups WHERE is_win=1 GROUP BY team_id, grp
        )
        SELECT t.team_name, MAX(s.streak_length) AS longest_win_streak
        FROM streaks s JOIN teams t ON t.team_id=s.team_id
        GROUP BY t.team_name ORDER BY longest_win_streak DESC LIMIT 10;
    """)
    names = [r[0] for r in rows][::-1]
    streaks = [r[1] for r in rows][::-1]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(names, streaks, color="#d35400")
    ax.set_xlabel("Longest consecutive wins")
    ax.set_title("Top 10 Longest Winning Streaks")
    for bar, s in zip(bars, streaks):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2, str(s), va="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/top_10_winning_streaks.png", dpi=150)
    plt.close()


def main():
    conn = psycopg2.connect(**PG_DSN)
    chart_top_scorers_alltime(conn)
    chart_home_away_winrate(conn)
    chart_goals_per_season(conn)
    chart_longest_win_streaks(conn)
    conn.close()
    print("Visualizations written to docs/visualizations/")


if __name__ == "__main__":
    main()
