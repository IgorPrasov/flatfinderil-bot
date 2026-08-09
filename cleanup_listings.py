import psycopg2
from datetime import datetime, timedelta

DB_URL = "postgresql://postgres:NOgPcBAEMFuWIwVhLDtOJvxscXeEhtgI@kodama.proxy.rlwy.net:38517/railway"

print("🧹 Очистка базы объявлений...\n")

conn = psycopg2.connect(DB_URL, connect_timeout=15)
cur = conn.cursor()

# Статистика ДО
cur.execute("SELECT COUNT(*) FROM listings")
before = cur.fetchone()[0]
print(f"📊 ДО: {before} объявлений")

# Статистика по источникам ДО
cur.execute("SELECT source, COUNT(*) FROM listings GROUP BY source ORDER BY COUNT(*) DESC")
for source, count in cur.fetchall():
    print(f"   {source}: {count}")

print("\n🗑️  Удаляю старые объявления (старше 1 месяца)...")
# Удалить объявления старше 1 месяца
cur.execute("DELETE FROM listings WHERE date_added < NOW() - INTERVAL '1 month'")
old_deleted = cur.rowcount
print(f"   Удалено старых: {old_deleted}")

print("\n🗑️  Удаляю дублики (одинаковые source_url)...")
# Удалить дублики - оставить только первое объявление для каждого URL
cur.execute("""
    DELETE FROM listings WHERE id NOT IN (
        SELECT MIN(id) FROM listings 
        WHERE source_url IS NOT NULL AND source_url != ''
        GROUP BY source_url
    )
    AND source_url IS NOT NULL AND source_url != ''
""")
dupes_deleted = cur.rowcount
print(f"   Удалено дубликов: {dupes_deleted}")

conn.commit()

# Статистика ПОСЛЕ
cur.execute("SELECT COUNT(*) FROM listings")
after = cur.fetchone()[0]
print(f"\n✅ ПОСЛЕ: {after} объявлений")
print(f"   Удалено всего: {before - after}")

print("\n📊 По источникам ПОСЛЕ:")
cur.execute("SELECT source, COUNT(*), MAX(date_added) FROM listings GROUP BY source ORDER BY COUNT(*) DESC")
for source, count, last in cur.fetchall():
    print(f"   {source}: {count} (последнее: {last})")

conn.close()
print("\n✅ Очистка завершена!")
