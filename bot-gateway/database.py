"""
database.py — smart router.

If DATABASE_URL is set → use PostgreSQL (database_pg).
Otherwise             → use JSON file (database_json).

All callers keep `import database as db` unchanged.
"""
import os as _os

_USE_PG = bool(_os.environ.get("DATABASE_URL", "").strip())

if _USE_PG:
    from database_pg import *          # noqa: F401, F403
    from database_pg import (          # explicit re-exports for type checkers
        search_listings,
        get_listing,
        add_listing,
        get_user_listings,
        count_user_private_listings_this_month,
        toggle_favorite,
        get_favorites,
        get_all_listings,
        increment_views,
        increment_view_requests,
        add_search_subscription,
        get_user_subscriptions,
        remove_search_subscription,
        get_all_subscriptions,
        update_subscription_last_checked,
        is_alert_active,
        set_alert_expiry,
        get_alert_expiry,
        add_alert,
        get_user_alerts,
        delete_alert,
        get_all_alerts,
        update_alert_sent,
        get_all_favorites_with_prices,
        update_favorite_price,
        add_review,
        get_reviews,
        get_average_rating,
        user_has_reviewed,
        add_referral,
        get_referral_count,
        add_bonus_days,
        get_bonus_days,
        get_bonus_expiry,
        get_user_paid_subscriptions,
        set_user_paid_subscription,
        was_trial_warning_sent,
        mark_trial_warning_sent,
        get_listing_credits,
        add_listing_credits,
        use_listing_credit,
        has_used_free_listing,
        mark_free_listing_used,
        upsert_bot_user,
        get_bot_users_count,
        get_all_bot_users,
        get_sources_stats,
        _load,
        _init_db,
        _text_fingerprint,
        _migrate_sublet_deal_type,
    )
    import logging as _logging
    _logging.getLogger(__name__).info("[DB] Using PostgreSQL backend")
else:
    from database_json import *        # noqa: F401, F403
    import logging as _logging
    _logging.getLogger(__name__).info("[DB] Using JSON file backend")
