from datetime import datetime, timedelta

# Тестовый период — бесплатно для всех до 15 апреля 2025
TRIAL_END_DATE = datetime(2026, 4, 15)

# Планы подписки
PLANS = {
    "week":  {"name_ru": "1 неделя",  "name_en": "1 week",  "name_he": "שבוע 1",  "days": 7,  "price": 19.90},
    "two_weeks": {"name_ru": "2 недели", "name_en": "2 weeks", "name_he": "2 שבועות", "days": 14, "price": 29.90},
    "month": {"name_ru": "1 месяц",   "name_en": "1 month", "name_he": "חודש 1",   "days": 30, "price": 39.90},
}

# Хранилище подписок (user_id -> expiry datetime)
_subscriptions = {}

def is_trial_active() -> bool:
    """Проверяет активен ли тестовый период."""
    return datetime.now() < TRIAL_END_DATE

def has_access(user_id: int) -> bool:
    """Проверяет есть ли у пользователя доступ."""
    if is_trial_active():
        return True
    if user_id in _subscriptions:
        return datetime.now() < _subscriptions[user_id]
    return False

def get_expiry(user_id: int):
    """Возвращает дату окончания подписки."""
    return _subscriptions.get(user_id)

def activate_subscription(user_id: int, plan_key: str) -> datetime:
    """Активирует подписку для пользователя."""
    plan = PLANS.get(plan_key)
    if not plan:
        return None
    expiry = datetime.now() + timedelta(days=plan["days"])
    _subscriptions[user_id] = expiry
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
            return f"🎁 Тестовый период активен ещё {days} дн. (до 15 апреля)"
        elif lang == "en":
            return f"🎁 Trial period active for {days} more days (until April 15)"
        else:
            return f"🎁 תקופת ניסיון פעילה עוד {days} ימים (עד 15 באפריל)"
    expiry = get_expiry(user_id)
    if expiry and datetime.now() < expiry:
        exp_str = expiry.strftime("%d.%m.%Y")
        if lang == "ru": return f"✅ Подписка активна до {exp_str}"
        elif lang == "en": return f"✅ Subscription active until {exp_str}"
        else: return f"✅ מנוי פעיל עד {exp_str}"
    if lang == "ru": return "❌ Подписка не активна"
    elif lang == "en": return "❌ No active subscription"
    else: return "❌ אין מנוי פעיל"
