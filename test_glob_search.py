"""测试 GLOB 搜索的 UNION 去重问题"""
import sqlite3

DB_PATH = "The little dict/TLD.mdx.index.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 测试 3 个模式
patterns = ['cain', 'cayn', 'coin']

sub_queries = []
params = []
for gp in patterns:
    sub_queries.append(
        "SELECT DISTINCT LOWER(word), frequency FROM coca_words "
        "WHERE LOWER(word) GLOB ?"
    )
    params.append(gp)

sql = " UNION ".join(sub_queries)
sql += " ORDER BY frequency ASC LIMIT ?"
params.append(3)

print("SQL:")
print(sql)
print()
print("Params:", params)
print()

cursor.execute(sql, params)
results = cursor.fetchall()
print("Results:")
for r in results:
    print(f"  word={r[0]}, frequency={r[1]}")

# 检查是否有重复
words = [r[0] for r in results]
print(f"\n单词列表: {words}")
print(f"去重后: {list(set(words))}")
print(f"有重复: {len(words) != len(set(words))}")

conn.close()
