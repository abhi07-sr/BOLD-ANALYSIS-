import sqlite3

conn = sqlite3.connect("nifty100.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"Total tables: {len(tables)}")
for t in sorted(tables):
    cur.execute(f"SELECT COUNT(1) FROM {t}")
    cnt = cur.fetchone()[0]
    print(f"  - {t}: {cnt} rows")

cur.execute("PRAGMA foreign_key_check")
fk = cur.fetchall()
print(f"Foreign Key Violations: {len(fk)}")
conn.close()

