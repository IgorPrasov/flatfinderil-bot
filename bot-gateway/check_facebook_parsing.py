#!/usr/bin/env python3
"""
Проверка статистики Facebook парсинга в базе Railway
Запуск: python3 check_facebook_parsing.py
"""
import psycopg2
from datetime import datetime, timedelta
from urllib.parse import urlparse

# CONNECTION STRING из Railway
DB_URL = "postgresql://postgres:NOgPcBAEMFuWIwVhLDtOJvxscXeEhtgI@kodama.proxy.rlwy.net:38517/railway"

try:
    print("🔗 Подключение к базе Railway...\n")
    conn = psycopg2.connect(DB_URL, connect_timeout=15)
    cur = conn.cursor()

    # 1. Общая статистика по источникам
    print("=" * 70)
    print("📊 СТАТИСТИКА ОБЪЯВЛЕНИЙ ПО ИСТОЧНИКАМ")
    print("=" * 70)

    cur.execute("""
        SELECT source, COUNT(*) as count, MAX(date_added) as last_added
        FROM listings
        GROUP BY source
        ORDER BY count DESC
    """)

    for source, count, last_added in cur.fetchall():
        print(f"  {source:15} | {count:8} объявлений | Последнее: {last_added}")

    # 2. Статистика Facebook за последние дни
    print("\n" + "=" * 70)
    print("📱 СТАТИСТИКА FACEBOOK ПАРСИНГА")
    print("=" * 70)

    cur.execute("""
        SELECT
            DATE(date_added) as day,
            COUNT(*) as count
        FROM listings
        WHERE source='facebook'
        GROUP BY DATE(date_added)
        ORDER BY day DESC
        LIMIT 7
    """)

    print("\n  По дням (последние 7 дней):")
    for day, count in cur.fetchall():
        print(f"    {day} → {count} объявлений")

    # 3. Статистика за 24 часа
    cur.execute("""
        SELECT COUNT(*) as count_24h
        FROM listings
        WHERE source='facebook' AND date_added > NOW() - INTERVAL '24 hours'
    """)

    count_24h = cur.fetchone()[0]
    print(f"\n  За последние 24 часа: {count_24h} объявлений")

    # 4. Статистика за последний час
    cur.execute("""
        SELECT COUNT(*) as count_1h
        FROM listings
        WHERE source='facebook' AND date_added > NOW() - INTERVAL '1 hour'
    """)

    count_1h = cur.fetchone()[0]
    print(f"  За последний час: {count_1h} объявлений")

    # 5. Последние добавленные объявления Facebook
    print("\n" + "=" * 70)
    print("🆕 ПОСЛЕДНИЕ 10 ОБЪЯВЛЕНИЙ ИЗ FACEBOOK")
    print("=" * 70 + "\n")

    cur.execute("""
        SELECT id, title, price, city, date_added
        FROM listings
        WHERE source='facebook'
        ORDER BY date_added DESC
        LIMIT 10
    """)

    results = cur.fetchall()
    if results:
        for idx, (lid, title, price, city, date_added) in enumerate(results, 1):
            print(f"  {idx}. [{lid}] {title[:60]}")
            print(f"     💰 {price} | 📍 {city}")
            print(f"     ⏰ {date_added}\n")
    else:
        print("  Нет объявлений из Facebook")

    # 6. Проверка: есть ли объявления добавленные в последний час
    print("=" * 70)
    if count_1h > 0:
        print(f"✅ ПАРСЕР АКТИВЕН! Добавлено в последний час: {count_1h} объявлений")
    else:
        if count_24h > 0:
            print(f"⚠️  Нет новых объявлений за последний час (всего за 24ч: {count_24h})")
        else:
            print("❌ ПАРСЕР НЕ АКТИВЕН - нет новых объявлений за день")
    print("=" * 70)

    conn.close()

except psycopg2.OperationalError as e:
    print(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ:")
    print(f"   {e}")
    print("\n💡 Проверь что:")
    print("   1. CONNECTION STRING правильный")
    print("   2. Интернет соединение активно")
    print("   3. Railway PostgreSQL онлайн")
except Exception as e:
    print(f"❌ Ошибка: {e}")
