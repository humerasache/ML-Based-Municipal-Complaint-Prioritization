
import sqlite3
from pathlib import Path
import pandas as pd

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "municipal_complaints.db"
RANKED_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "rank_complaints.csv"

# Features displayed on the Priority Queue dashboard
PRIORITY_COLUMNS = [
    "priority_rank",
    "complaint_id",
    "citizen_id",
    "category",
    "sub_category",
    "ward",
    "reported_date",
    "status",
    "people_affected",
    "vulnerable_population",
    "public_safety_risk",
    "recurrence_indicator",
    "severity",
    "complaint_age_days",
    "priority_level",
]

# Additional fields needed internally
DATABASE_COLUMNS = PRIORITY_COLUMNS + [
    "predicted_priority_score"
]


def get_connection():
    """Connect to the permanent SQLite database."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def create_tables():
    """Create the complaints table if it does not exist."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                complaint_id TEXT PRIMARY KEY,
                priority_rank INTEGER,
                citizen_id TEXT,
                category TEXT NOT NULL,
                sub_category TEXT,
                ward TEXT NOT NULL,
                reported_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Registered',
                people_affected INTEGER DEFAULT 1,
                vulnerable_population REAL DEFAULT 0,
                public_safety_risk REAL DEFAULT 0,
                recurrence_indicator INTEGER DEFAULT 0,
                severity TEXT,
                complaint_age_days INTEGER DEFAULT 0,
                priority_level TEXT,
                predicted_priority_score REAL
            )
        """)

    print("Complaints table is ready.")


def migrate_table():
    """Add missing columns to an existing complaints table."""
    required_columns = {
    "priority_rank": "INTEGER",
    "citizen_id": "TEXT",
    "category": "TEXT",
    "sub_category": "TEXT",
    "ward": "TEXT",
    "reported_date": "TEXT",
    "status": "TEXT",
    "people_affected": "INTEGER",
    "vulnerable_population": "REAL",
    "public_safety_risk": "REAL",
    "recurrence_indicator": "INTEGER",
    "severity": "TEXT",
    "complaint_age_days": "INTEGER",
    "priority_level": "TEXT",
    "predicted_priority_score": "REAL",
}

    with get_connection() as connection:
        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(complaints)"
            ).fetchall()
        }

        for column, data_type in required_columns.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE complaints ADD COLUMN {column} {data_type}"
                )
                print(f"Added missing column: {column}")


def import_ranked_complaints():
    """Import existing ranked complaints without overwriting database updates."""
    if not RANKED_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Ranked dataset not found: {RANKED_DATA_PATH}"
        )

    df = pd.read_csv(RANKED_DATA_PATH)

    missing = [
        column for column in DATABASE_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df[DATABASE_COLUMNS].copy()

    # Replace missing optional values with SQL NULL.
    df = df.astype(object).where(pd.notna(df), None)

    placeholders = ", ".join(["?"] * len(DATABASE_COLUMNS))
    columns_sql = ", ".join(DATABASE_COLUMNS)

    insert_sql = f"""
        INSERT OR IGNORE INTO complaints ({columns_sql})
        VALUES ({placeholders})
    """

    records = list(df.itertuples(index=False, name=None))

    with get_connection() as connection:
        connection.executemany(insert_sql, records)

    print(f"Rows found in CSV: {len(df)}")
    print("Import completed. Existing database records were preserved.")


def get_complaints():
    """Return all complaints from the database."""
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM complaints
            ORDER BY priority_rank ASC
        """).fetchall()

    return [dict(row) for row in rows]



if __name__ == "__main__":
    create_tables()
    migrate_table()
    import_ranked_complaints()

    complaints = get_complaints()
    print(f"Complaints currently in database: {len(complaints)}")
    print(f"Database location: {DATABASE_PATH}")

