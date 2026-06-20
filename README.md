# Football Performance Analytics

Portfolio project analyzing European football match, team, and player data
sourced from the [Kaggle "European Soccer Database"](https://www.kaggle.com/datasets/hugomathien/soccer)
(Hugo Mathien).

## Status

Environment setup complete. Raw dataset downloaded and inspected. Postgres
schema design and analysis queries are in progress.

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
| Match | 25,979 | Wide table; betting odds columns 13–57% null; XML blob columns (`goal`, `card`, `shoton`, `shotoff`, `foulcommit`, `cross`, `corner`, `possession`) ~45% null and require parsing |
| sqlite_sequence | 7 | SQLite internal, not part of the data model |

See conversation history / `docs/` for full column-level inspection notes.

## Setup

```bash
pip install kaggle
mkdir -p ~/.kaggle
# place your Kaggle access token at ~/.kaggle/access_token (chmod 600)
kaggle datasets download -d hugomathien/soccer -p data
unzip data/soccer.zip -d data && rm data/soccer.zip
```

## Repo structure

```
football-performance-analytics/
├── README.md
├── schema.sql           # Postgres schema (TBD)
├── queries.sql           # Analysis queries (TBD)
├── docs/
│   ├── schema_diagram.png
│   ├── query_outputs/
│   └── screenshots/
├── data/                 # gitignored — raw SQLite dataset
└── assets/
```

## Next steps

- Design normalized Postgres schema, including a plan for parsing the
  XML blob columns in `Match` (goals, cards, shots, possession, etc.)
- Write analysis queries
- Build visualizations / dashboard
