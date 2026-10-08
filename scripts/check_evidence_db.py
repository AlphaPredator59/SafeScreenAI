from sqlalchemy import text
from app.db.database import get_engine


def main():
    engine = get_engine()

    with engine.connect() as conn:
        print("\n=== DATABASE CONNECTION ===")
        print("Engine:", engine.url)
        print(
            "Database:",
            conn.execute(text("SELECT current_database()")).scalar(),
        )
        print(
            "User:",
            conn.execute(text("SELECT current_user")).scalar(),
        )
        print(
            "Schema:",
            conn.execute(text("SELECT current_schema()")).scalar(),
        )
        print(
            "Search path:",
            conn.execute(text("SHOW search_path")).scalar(),
        )

        print("\n=== EVIDENCE COLUMNS ===")

        rows = conn.execute(
            text(
                """
                SELECT
                    table_schema,
                    table_name,
                    column_name,
                    data_type,
                    character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'evidence'
                ORDER BY table_schema, ordinal_position
                """
            )
        ).fetchall()

        for row in rows:
            print(row)

        print("\n=== ACTUAL POSTGRES TYPES ===")

        rows = conn.execute(
            text(
                """
                SELECT
                    n.nspname AS schema_name,
                    c.relname AS table_name,
                    a.attname AS column_name,
                    format_type(a.atttypid, a.atttypmod) AS postgres_type
                FROM pg_attribute a
                JOIN pg_class c
                    ON c.oid = a.attrelid
                JOIN pg_namespace n
                    ON n.oid = c.relnamespace
                WHERE c.relname = 'evidence'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                ORDER BY n.nspname, a.attnum
                """
            )
        ).fetchall()

        for row in rows:
            print(row)


if __name__ == "__main__":
    main()