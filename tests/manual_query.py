import json
import os
import sqlite3
import sys
from pathlib import Path

try:
    import readline
except ImportError:
    readline = None


def execute_query(conn, sql):
    cursor = conn.execute(sql)

    if cursor.description is not None:
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return {
            "ok": True,
            "type": "select",
            "columns": columns,
            "rows": rows,
        }

    conn.commit()
    return {
        "ok": True,
        "type": "statement",
        "rowcount": cursor.rowcount,
        "message": "Statement executed successfully",
    }


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else ""

    if not db_path:
        print("Usage: python test.py <db_path>")
        return

    repo_root = Path(__file__).resolve().parents[1]
    hist_dir = repo_root / "data"
    hist_dir.mkdir(exist_ok=True)
    db_name = Path(db_path).name
    hist_file = hist_dir / f".{db_name}_query_history"

    if readline is not None:
        if hist_file.exists():
            readline.read_history_file(str(hist_file))
        readline.set_history_length(1000)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    print(json.dumps({"status": "connected", "database": db_path}))

    while True:
        try:
            sql = input("SQL> ").strip()
        except EOFError:
            print()
            break

        if not sql:
            continue

        if readline is not None:
            readline.write_history_file(str(hist_file))

        if sql.lower() in {"exit", "quit"}:
            break

        try:
            result = execute_query(conn, sql)
            print(json.dumps(result, default=str, indent=2))
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))

    conn.close()


if __name__ == "__main__":
    main()
