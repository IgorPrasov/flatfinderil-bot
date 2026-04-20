from datetime import datetime, timedelta
import database as db

# Тестовый период — бесплатно для всех до 15 мая 2026
TRIAL_END_DATE = datetime(2026, 5, 15)

# Лимит бесплатного поиска после окончания триала
FREE_SEARCH_LIMIT = 3

# Планы подписки
PLANS = {
    "week":         {"name_ru": "1 неделя",              "name_en": "1 week",           "name_he": "שבוע 1",          "days": 7,  "price": 19.90, "stars": 399},
    "two_weeks":    {"name_ru": "2 недели",               "name_en": "2 weeks",          "name_he": "2 שבועות",        "days": 14, "price": 29.90, "stars": 599},
    "month":        {"name_ru": "1 месяц",                "name_en": "1 month",          "name_he": "חודש 1",          "days": 30, "price": 39.90, "stars": 799},
    "search_alert": {"name_ru": "🔔 Подписка на поиск",  "name_en": "🔔 Search alerts", "name_he": "🔔 התראות חיפוש", "days": 7,  "price": 39.90, "stars": 799},
}


def is_trial_active() -> bool:
    """Проверяет активен ли тестовый период."""
    return datetime.now() < TRIAL_END_DATE


def _get_expiry_from_db(user_id: int, plan_type: str = "main"):
    """Загружает дату окончания подписки из БД."""
    try:
        subs = db.get_user_paid_subscriptions(user_id)
        entry = subs.get(plan_type)
        if entry:
            return datetime.fromisoformat(entry)
    except Exception:
        pass
    return None


def _save_expiry_to_db(user_id: int, expiry: datetime, plan_type: str = "main"):
    """Сохраняет дату окончания подписки в БД."""
    try:
        db.set_user_paid_subscription(user_id, plan_type, expiry.isoformat())
    except Exception:
        pass


def has_access(user_id: int) -> bool:
    """
    Полный доступ: безлимитный поиск + добавление объявлений.
    Активен во время триала или при наличии любой оплаченной подписки.
    """
    if is_trial_active():
        return True
    # Бонусные дни из БД
    try:
        bonus_exp = db.get_bonus_expiry(user_id)
        if bonus_exp and datetime.now() < bonus_exp:
            return True
    except Exception:
        pass
    # Оплаченная подписка
    expiry = _get_expiry_from_db(user_id, "main")
    if expiry and datetime.now() < expiry:
        return True
    return False


def has_search_alert(user_id: int) -> bool:
    """Премиум: подписка на поиск (уведомления о новых объявлениях)."""
    if is_trial_active():
        return True
    if has_access(user_id):
        return True
    expiry = _get_expiry_from_db(user_id, "search_alert")
    return expiry is not None and datetime.now() < expiry


def get_expiry(user_id: int, plan_type: str = "main") -> datetime | None:
    """Возвращает дату окончания подписки."""
    return _get_expiry_from_db(user_id, plan_type)


def activate_subscription(user_id: int, plan_key: str) -> datetime:
    """Активирует подписку для пользователя и сохраняет в БД."""
    plan = PLANS.get(plan_key)
    if not plan:
        return None

    plan_type = "search_alert" if plan_key == "search_alert" else "main"

    # Продлить если уже есть активная
    current = _get_expiry_from_db(user_id, plan_type)
    base = max(datetime.now(), current) if current and current > datetime.now() else datetime.now()
    expiry = base + timedelta(days=plan["days"])

    _save_expiry_to_db(user_id, expiry, plan_type)
    return expiry


def days_left_trial() -> int:
    """Сколько дней осталось в тестовом периоде."""
    delta = TRIAL_END_DATE - datetime.now()
    return max(0, delta.days)


def get_status_text(user_id: int, lang: str) -> str:
    """Текст статуса подписки для пользователя."""
    if is_trial_active():
        days = days_left_trial()
        if lang == "ru":
            return f"🎁 Тестовый период активен ещё {days} дн. (до 15 мая)"
        elif lang == "en":
            return f"🎁 Trial period active for {days} more days (until May 15)"
        else:
            return f"🎁 תקופת ניסיון פעילה עוד {days} ימים (עד 15 במאי)"

    main_expiry = get_expiry(user_id, "main")
    alert_expiry = get_expiry(user_id, "search_alert")
    lines = []

    if main_expiry and datetime.now() < main_expiry:
        exp_str = main_expiry.strftime("%d.%m.%Y")
        if lang == "ru":   lines.append(f"✅ Подписка активна до {exp_str}")
        elif lang == "en": lines.append(f"✅ Subscription active until {exp_str}")
        else:              lines.append(f"✅ מנוי פעיל עד {exp_str}")
    else:
        if lang == "ru":   lines.append("❌ Нет активной подписки")
        elif lang == "en": lines.append("❌ No active subscription")
        else:              lines.append("❌ אין מנוי פעיל")

    if alert_expiry and datetime.now() < alert_expiry:
        exp_str = alert_expiry.strftime("%d.%m.%Y")
        if lang == "ru":   lines.append(f"🔔 Подписка на поиск до {exp_str}")
        elif lang == "en": lines.append(f"🔔 Search alerts until {exp_str}")
        else:              lines.append(f"🔔 התראות חיפוש עד {exp_str}")

    return "\n".join(lines)
