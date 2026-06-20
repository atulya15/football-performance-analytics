"""
Load source SQLite data into the Postgres football_analytics schema.

Key mapping decision: teams.team_id uses Team.team_api_id (not the
internal Team.id) and players.player_id uses Player.player_api_id,
because those are the IDs referenced inside the Match table's goal/card
XML blobs (already parsed into data/match_events_staged.csv by
scripts/parse_events.py). Using api_id as the natural key keeps
match_events' team_id/player_id joins trivial.

The 115 player position/lineup columns and 40 betting-odds columns on
Match are dropped entirely — not part of the target schema.
"""

import csv
import sqlite3

import psycopg2

SRC_DB = "data/database.sqlite"
STAGED_EVENTS_CSV = "data/match_events_staged.csv"

PG_DSN = dict(host="localhost", port=5432, dbname="football_analytics", user="postgres", password="postgres")


def get_sqlite():
    return sqlite3.connect(SRC_DB)


def main():
    sconn = get_sqlite()
    scur = sconn.cursor()

    pconn = psycopg2.connect(**PG_DSN)
    pcur = pconn.cursor()

    counts = {}

    # countries
    scur.execute("SELECT id, name FROM Country;")
    rows = scur.fetchall()
    pcur.executemany("INSERT INTO countries (country_id, country_name) VALUES (%s, %s)", rows)
    counts["countries"] = len(rows)

    # leagues
    scur.execute("SELECT id, name, country_id FROM League;")
    rows = [(r[0], r[1], r[2]) for r in scur.fetchall()]
    pcur.executemany(
        "INSERT INTO leagues (league_id, league_name, country_id) VALUES (%s, %s, %s)", rows
    )
    counts["leagues"] = len(rows)

    # teams (team_id = team_api_id)
    scur.execute("SELECT team_api_id, team_long_name, team_fifa_api_id FROM Team;")
    rows = scur.fetchall()
    pcur.executemany(
        "INSERT INTO teams (team_id, team_name, team_fifa_api_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        rows,
    )
    counts["teams"] = len(rows)

    # team_attributes
    scur.execute(
        "SELECT team_api_id, date, buildUpPlaySpeed, chanceCreationPassing, defencePressure FROM Team_Attributes;"
    )
    rows = scur.fetchall()
    pcur.executemany(
        """INSERT INTO team_attributes (team_id, season_date, build_up_play_speed, chance_creation_passing, defence_pressure)
           VALUES (%s, %s, %s, %s, %s)""",
        rows,
    )
    counts["team_attributes"] = len(rows)

    # players (player_id = player_api_id)
    scur.execute("SELECT player_api_id, player_name, birthday, height, weight FROM Player;")
    rows = scur.fetchall()
    pcur.executemany(
        "INSERT INTO players (player_id, player_name, birthday, height, weight) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        rows,
    )
    counts["players"] = len(rows)

    # player_attributes
    scur.execute(
        "SELECT player_api_id, date, overall_rating, potential, finishing FROM Player_Attributes;"
    )
    rows = scur.fetchall()
    pcur.executemany(
        """INSERT INTO player_attributes (player_id, date, overall_rating, potential, finishing)
           VALUES (%s, %s, %s, %s, %s)""",
        rows,
    )
    counts["player_attributes"] = len(rows)

    # matches — drop 115 lineup columns + 40 betting-odds columns
    scur.execute(
        """SELECT id, season, stage, date, league_id, home_team_api_id, away_team_api_id,
                  home_team_goal, away_team_goal
           FROM Match;"""
    )
    rows = scur.fetchall()
    pcur.executemany(
        """INSERT INTO matches (match_id, season, stage, match_date, league_id, home_team_id, away_team_id, home_score, away_score)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        rows,
    )
    counts["matches"] = len(rows)

    pconn.commit()

    # match_events — load from staged CSV (Phase 3.5 output).
    # 609/102094 rows reference a player_id not present in the Player
    # source table (likely officials/edge-case IDs embedded in the XML,
    # not actual roster players). The event itself is real and kept;
    # only the unresolvable player_id is nulled out rather than dropping
    # the row.
    pcur.execute("SELECT player_id FROM players;")
    valid_players = {r[0] for r in pcur.fetchall()}
    orphan_player_id_count = 0

    with open(STAGED_EVENTS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        event_rows = []
        for r in reader:
            player_id = int(r["player_id"]) if r["player_id"] else None
            if player_id is not None and player_id not in valid_players:
                player_id = None
                orphan_player_id_count += 1
            event_rows.append(
                (
                    int(r["match_id"]),
                    r["event_type"],
                    int(r["minute"]) if r["minute"] else None,
                    player_id,
                    int(r["team_id"]) if r["team_id"] else None,
                    r["detail"] or None,
                )
            )
    print(f"match_events: nulled {orphan_player_id_count} unresolvable player_id values (not in players table)")
    pcur.executemany(
        """INSERT INTO match_events (match_id, event_type, minute, player_id, team_id, detail)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        event_rows,
    )
    counts["match_events"] = len(event_rows)

    pconn.commit()

    print("Rows loaded:")
    for table, n in counts.items():
        print(f"  {table}: {n}")

    scur.close()
    sconn.close()
    pcur.close()
    pconn.close()


if __name__ == "__main__":
    main()
