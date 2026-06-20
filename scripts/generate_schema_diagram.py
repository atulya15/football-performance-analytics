"""
Render an ER diagram of the football_analytics Postgres schema as a PNG.
Pure matplotlib (no graphviz binary dependency) — draws each table as a
box listing its columns, with arrows for foreign keys.
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT_PATH = "docs/schema_diagram.png"

TABLES = {
    "countries": {
        "pos": (1, 8),
        "cols": ["country_id PK", "country_name"],
    },
    "leagues": {
        "pos": (4.5, 8),
        "cols": ["league_id PK", "league_name", "country_id FK"],
    },
    "teams": {
        "pos": (8, 8),
        "cols": ["team_id PK", "team_name", "team_fifa_api_id"],
    },
    "team_attributes": {
        "pos": (11.5, 8),
        "cols": ["attr_id PK", "team_id FK", "season_date",
                 "build_up_play_speed", "chance_creation_passing", "defence_pressure"],
    },
    "players": {
        "pos": (1, 3),
        "cols": ["player_id PK", "player_name", "birthday", "height", "weight"],
    },
    "player_attributes": {
        "pos": (4.5, 3),
        "cols": ["attr_id PK", "player_id FK", "date",
                 "overall_rating", "potential", "finishing"],
    },
    "matches": {
        "pos": (8, 3),
        "cols": ["match_id PK", "season", "stage", "match_date", "league_id FK",
                 "home_team_id FK", "away_team_id FK", "home_score", "away_score"],
    },
    "match_events": {
        "pos": (11.8, 3),
        "cols": ["event_id PK", "match_id FK", "event_type",
                 "minute", "player_id FK", "team_id FK", "detail"],
    },
}

FKS = [
    ("leagues", "countries"),
    ("team_attributes", "teams"),
    ("player_attributes", "players"),
    ("matches", "leagues"),
    ("matches", "teams"),
    ("match_events", "matches"),
    ("match_events", "teams"),
    ("match_events", "players"),
]

BOX_W = 3.1
ROW_H = 0.32
HEADER_H = 0.42


def box_dims(table):
    n_cols = len(TABLES[table]["cols"])
    return BOX_W, HEADER_H + n_cols * ROW_H


def main():
    fig, ax = plt.subplots(figsize=(16, 11))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 11)
    ax.axis("off")
    ax.set_title("football_analytics — Postgres Schema (ER Diagram)", fontsize=16, fontweight="bold", pad=20)

    centers = {}

    for name, info in TABLES.items():
        x, y = info["pos"]
        w, h = box_dims(name)
        centers[name] = (x + w / 2, y + h / 2)

        # outer box
        box = FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02",
            linewidth=1.5, edgecolor="#2c3e50", facecolor="#ecf0f1", zorder=2,
        )
        ax.add_patch(box)

        # header
        header = FancyBboxPatch(
            (x, y + h - HEADER_H), w, HEADER_H,
            boxstyle="round,pad=0.02",
            linewidth=1.5, edgecolor="#2c3e50", facecolor="#2c3e50", zorder=3,
        )
        ax.add_patch(header)
        ax.text(x + w / 2, y + h - HEADER_H / 2, name, ha="center", va="center",
                fontsize=12, fontweight="bold", color="white", zorder=4)

        for i, col in enumerate(info["cols"]):
            cy = y + h - HEADER_H - (i + 0.5) * ROW_H
            weight = "bold" if "PK" in col else "normal"
            color = "#c0392b" if "FK" in col else "#2c3e50"
            ax.text(x + 0.15, cy, col, ha="left", va="center",
                    fontsize=9.5, fontweight=weight, color=color, zorder=4)

    for src, dst in FKS:
        sx, sy = TABLES[src]["pos"]
        sw, sh = box_dims(src)
        dx, dy = TABLES[dst]["pos"]
        dw, dh = box_dims(dst)

        start = (sx + sw / 2, sy + sh)
        end = (dx + dw / 2, dy + dh)

        # decide a simpler anchor: connect nearest edges
        start = (centers[src][0], TABLES[src]["pos"][1] + box_dims(src)[1])
        if centers[dst][1] > centers[src][1]:
            end = (centers[dst][0], TABLES[dst]["pos"][1])
        else:
            start = (centers[src][0], TABLES[src]["pos"][1])
            end = (centers[dst][0], TABLES[dst]["pos"][1] + box_dims(dst)[1])

        arrow = FancyArrowPatch(
            start, end,
            connectionstyle="arc3,rad=0.15",
            arrowstyle="-|>", mutation_scale=15,
            linewidth=1.3, color="#7f8c8d", zorder=1,
        )
        ax.add_patch(arrow)

    plt.tight_layout()
    plt.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    print(f"Schema diagram written to {OUT_PATH}")


if __name__ == "__main__":
    main()
