"""
Parse goal/card XML blobs from the source Match table into a flat
staging CSV (data/match_events_staged.csv) for later load into
match_events (Phase 4 — match_events has FK to matches/teams/players,
which aren't loaded yet at this point).

Only `goal` and `card` blobs are parsed. shoton/shotoff/foulcommit/cross/
corner/possession are intentionally skipped (not needed for any required
query, noisier to parse).
"""

import csv
import sqlite3
import xml.etree.ElementTree as ET

SRC_DB = "data/database.sqlite"
OUT_CSV = "data/match_events_staged.csv"

CARD_TYPE_MAP = {"y": "yellow", "y2": "yellow", "r": "red"}


def parse_blob(xml_text, match_id, event_type):
    """Yield (match_id, event_type, minute, player_id, team_id, detail) tuples.
    Returns (rows, had_parse_error)."""
    rows = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return rows, True

    for value in root.findall("value"):
        elapsed = value.findtext("elapsed")
        minute = int(elapsed) if elapsed and elapsed.isdigit() else None

        player_text = value.findtext("player1")
        player_id = int(player_text) if player_text and player_text.isdigit() else None

        team_text = value.findtext("team")
        team_id = int(team_text) if team_text and team_text.isdigit() else None

        if event_type == "goal":
            detail = value.findtext("subtype") or value.findtext("goal_type")
        else:  # card
            card_type = value.findtext("card_type")
            detail = CARD_TYPE_MAP.get(card_type, card_type)

        rows.append((match_id, event_type, minute, player_id, team_id, detail))

    return rows, False


def main():
    conn = sqlite3.connect(SRC_DB)
    cur = conn.cursor()
    cur.execute("SELECT id, goal, card, home_team_goal, away_team_goal FROM Match;")
    match_rows = cur.fetchall()
    conn.close()

    out_rows = []
    stats = {
        "goal_events": 0,
        "card_events": 0,
        "null_player_id": 0,
        "parse_failures": 0,
        "rows_with_goal_blob": 0,
        "rows_with_card_blob": 0,
    }

    total_score_sum = 0
    matches_with_score = 0
    score_sum_with_goal_blob = 0

    for match_id, goal_xml, card_xml, home_goal, away_goal in match_rows:
        if home_goal is not None and away_goal is not None:
            total_score_sum += home_goal + away_goal
            matches_with_score += 1
            if goal_xml:
                score_sum_with_goal_blob += home_goal + away_goal

        if goal_xml:
            stats["rows_with_goal_blob"] += 1
            rows, failed = parse_blob(goal_xml, match_id, "goal")
            if failed:
                stats["parse_failures"] += 1
            else:
                out_rows.extend(rows)
                stats["goal_events"] += len(rows)

        if card_xml:
            stats["rows_with_card_blob"] += 1
            rows, failed = parse_blob(card_xml, match_id, "card")
            if failed:
                stats["parse_failures"] += 1
            else:
                out_rows.extend(rows)
                stats["card_events"] += len(rows)

    stats["null_player_id"] = sum(1 for r in out_rows if r[3] is None)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["match_id", "event_type", "minute", "player_id", "team_id", "detail"])
        writer.writerows(out_rows)

    total_events = stats["goal_events"] + stats["card_events"]
    null_player_rate = stats["null_player_id"] / total_events * 100 if total_events else 0
    parse_failure_rate = (
        stats["parse_failures"] / (stats["rows_with_goal_blob"] + stats["rows_with_card_blob"]) * 100
        if (stats["rows_with_goal_blob"] + stats["rows_with_card_blob"]) else 0
    )
    # Naive reconciliation against ALL matches is misleading: ~45% of matches
    # have no goal/card blob at all (a structural data gap, confirmed during
    # Phase 1-2 inspection), so they contribute 0 parsed goals while still
    # counting toward the scoreboard total. The honest comparison is parsed
    # goals vs. scoreboard goals only for matches that actually have a blob.
    blob_coverage_pct = score_sum_with_goal_blob / total_score_sum * 100 if total_score_sum else 0
    reconciliation_pct = (
        stats["goal_events"] / score_sum_with_goal_blob * 100 if score_sum_with_goal_blob else 0
    )
    naive_reconciliation_pct = (
        stats["goal_events"] / total_score_sum * 100 if total_score_sum else 0
    )

    print("=" * 60)
    print("EVENT PARSING REPORT")
    print("=" * 60)
    print(f"Matches in source:              {len(match_rows)}")
    print(f"Matches with goal/card blobs:    goal={stats['rows_with_goal_blob']}  card={stats['rows_with_card_blob']}")
    print(f"Total goal events parsed:        {stats['goal_events']}")
    print(f"Total card events parsed:        {stats['card_events']}")
    print(f"Total events parsed:             {total_events}")
    print(f"Null player_id rate:             {null_player_rate:.2f}% ({stats['null_player_id']} / {total_events})")
    print(f"Parse failure rate:              {parse_failure_rate:.2f}% ({stats['parse_failures']} blobs)")
    print(f"Sum of home+away scores (all):   {total_score_sum} (across {matches_with_score} matches)")
    print(f"Sum of scores (blob present):     {score_sum_with_goal_blob}")
    print(f"Blob coverage (% of goals in matches with a blob): {blob_coverage_pct:.2f}%")
    print(f"Naive reconciliation (parsed / ALL scoreboard goals): {naive_reconciliation_pct:.2f}%  <- misleading, ~45% of matches have no blob at all")
    print(f"Honest reconciliation (parsed / scoreboard goals, blob-present matches only): {reconciliation_pct:.2f}%")
    print(f"Staging CSV written to:          {OUT_CSV}  ({len(out_rows)} rows)")


if __name__ == "__main__":
    main()
