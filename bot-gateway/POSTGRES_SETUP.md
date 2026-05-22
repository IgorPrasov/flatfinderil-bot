# PostgreSQL Setup

## 1. Add PostgreSQL to your Railway project

In your Railway project dashboard:

1. Click **+ New** → **Database** → **PostgreSQL**
2. Railway automatically injects the `DATABASE_URL` environment variable into every service in the same project.

## 2. Initialise the schema

The schema is created automatically the first time the bot starts when `DATABASE_URL` is set, because `database_pg._init_db()` is called on import.

You can also run it manually:

```bash
DATABASE_URL="postgresql://..." python -c "import database_pg; database_pg._init_db()"
```

## 3. Migrate existing data from listings_db.json

Run the migration script **once** after the schema is ready:

```bash
DATABASE_URL="postgresql://..." python migrate_to_pg.py
```

The script is idempotent — it skips records that already exist.

## 4. Switch to the PostgreSQL backend

In every file that currently imports the JSON-based database layer, change the import:

```python
# Before
import database as db

# After
import database_pg as db
```

Files that typically need this change:

- `bot.py`
- `mini_app_api.py`
- `subscription.py`
- `alert_checker.py`
- `search_handler.py`
- `listing_handler.py`
- `handlers.py`
- `backoffice_server.py`
- any other module that does `import database`

## 5. Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string — set automatically by Railway |

## 6. Gradual rollout (optional)

If you want to switch incrementally, you can use a small shim:

```python
# database_router.py
import os
if os.environ.get("USE_PG") == "1":
    from database_pg import *
else:
    from database import *
```

Then change all callers to `import database_router as db`, and flip
`USE_PG=1` in Railway when you are ready.

## 7. Verifying the migration

```sql
-- Count listings
SELECT COUNT(*) FROM listings;

-- Check a listing
SELECT id, title, city, price FROM listings LIMIT 5;

-- Check favorites
SELECT COUNT(*) FROM favorites;
```
