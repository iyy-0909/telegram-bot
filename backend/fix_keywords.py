import sqlite3

DB_PATH = "data/clonebot.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(channel_rules)")
cols = [row[1] for row in cur.fetchall()]

print("当前 channel_rules 字段：")
print(cols)

if "keywords" not in cols:
    cur.execute("ALTER TABLE channel_rules ADD COLUMN keywords TEXT DEFAULT '[]'")
    print("已添加字段：channel_rules.keywords")
else:
    print("字段已存在：channel_rules.keywords")

conn.commit()

cur.execute("PRAGMA table_info(channel_rules)")
cols = [row[1] for row in cur.fetchall()]

print("更新后 channel_rules 字段：")
print(cols)

conn.close()
print("完成")