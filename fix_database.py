"""
データベースのamountカラムをINTEGERからREALに変更
"""
import sqlite3

print("データベース修正開始...")

conn = sqlite3.connect("greenfunding.db")
c = conn.cursor()

# 新しいテーブルを作成（amountをREAL型に）
c.execute("""
    CREATE TABLE IF NOT EXISTS projects_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT UNIQUE,
        title TEXT,
        description TEXT,
        amount REAL DEFAULT 0,
        achievement_rate INTEGER DEFAULT 0,
        supporters INTEGER DEFAULT 0,
        category TEXT DEFAULT '',
        status TEXT DEFAULT '',
        url TEXT,
        image_url TEXT,
        portal TEXT DEFAULT '',
        end_date TEXT DEFAULT ''
    )
""")

# 既存データをコピー
print("データをコピー中...")
c.execute("""
    INSERT INTO projects_new 
    SELECT * FROM projects
""")

# 古いテーブルを削除
c.execute("DROP TABLE projects")

# 新しいテーブルをリネーム
c.execute("ALTER TABLE projects_new RENAME TO projects")

conn.commit()
conn.close()

print("✅ 修正完了！")