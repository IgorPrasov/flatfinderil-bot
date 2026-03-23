import asyncio
import os
import re
import requests
import database as db
from datetime import datetime

API_ID = 35002061
API_HASH = "e0868efd711084c61c6bdee94006815e"

CHANNELS = [
    # ── Публичные активные каналы ─────────────────────────────────────────
    "israel_rent",
    "tlvapartments",
    "israelrealestate",
    "israel_apartments",
    "nadlan_israel",
    "izrailnedvizimosti",
    "isra_home_arenda",
    "nagariyaapartments",
    "ashdod_rent",
    "happy_home_ashkelon",
    # ── Новые найденные публичные ─────────────────────────────────────────
    "haifa_arenda",
    "realestate_israel",
    "israel_home",
    # ── Приватные — убраны (требуют авторизации) ─────────────────────────
    # "rentapartmentbatyam",   # private
    # "Sublet_Israel",         # private
    # "snyat_kvartiruy",       # private
    # "RealEstateIsraelBot",   # bot, not a channel
]

CITY_KEYWORDS = {
    # ── Тель-Авив и районы ────────────────────────────────────────────────
    "тель-авив": "Тель-Авив", "тель авив": "Тель-Авив",
    "tel aviv": "Тель-Авив", "tel-aviv": "Тель-Авив",
    "תל אביב": "Тель-Авив", "תל-אביב": "Тель-Авив",
    "яффо": "Тель-Авив", "jaffa": "Тель-Авив", "יפו": "Тель-Авив",
    "флорентин": "Тель-Авив", "florentin": "Тель-Авив",
    "неве-цедек": "Тель-Авив", "neve tzedek": "Тель-Авив",
    "неве цедек": "Тель-Авив",
    "тель-барух": "Тель-Авив", "tel baruch": "Тель-Авив",
    "рамат-авив": "Тель-Авив", "ramat aviv": "Тель-Авив",
    "неве-шаанан": "Тель-Авив", "neve shaanan": "Тель-Авив",
    "алленби": "Тель-Авив", "алибей": "Тель-Авив",
    "ротшильд": "Тель-Авив", "dizengoff": "Тель-Авив", "дизенгоф": "Тель-Авив",

    # ── Рамат-Ган ─────────────────────────────────────────────────────────
    "рамат-ган": "Рамат-Ган", "рамат ган": "Рамат-Ган",
    "ramat gan": "Рамат-Ган", "ramat-gan": "Рамат-Ган", "רמת גן": "Рамат-Ган",

    # ── Гиватаим ──────────────────────────────────────────────────────────
    "гиватаим": "Гиватаим", "givatayim": "Гиватаим", "גבעתיים": "Гиватаим",

    # ── Бней-Брак ─────────────────────────────────────────────────────────
    "бней-брак": "Бней-Брак", "бней брак": "Бней-Брак",
    "bnei brak": "Бней-Брак", "בני ברק": "Бней-Брак",

    # ── Бат-Ям ────────────────────────────────────────────────────────────
    "бат-ям": "Бат-Ям", "бат ям": "Бат-Ям",
    "bat yam": "Бат-Ям", "bat-yam": "Бат-Ям", "בת ים": "Бат-Ям",

    # ── Холон ─────────────────────────────────────────────────────────────
    "холон": "Холон", "holon": "Холон", "חולון": "Холон",

    # ── Ор-Иегуда ────────────────────────────────────────────────────────
    "ор-иегуда": "Ор-Иегуда", "or yehuda": "Ор-Иегуда", "אור יהודה": "Ор-Иегуда",

    # ── Иерусалим и районы ────────────────────────────────────────────────
    "иерусалим": "Иерусалим", "jerusalem": "Иерусалим", "ירושלים": "Иерусалим",
    "гило": "Иерусалим", "рамот": "Иерусалим", "рехавия": "Иерусалим",
    "арнона": "Иерусалим", "катамон": "Иерусалим", "бейт-хакерем": "Иерусалим",
    "малха": "Иерусалим", "гиват-мордехай": "Иерусалим",
    "бейт-шемеш": "Бейт-Шемеш", "beit shemesh": "Бейт-Шемеш", "בית שמש": "Бейт-Шемеш",
    "маале-адумим": "Маале-Адумим", "maale adumim": "Маале-Адумим", "מעלה אדומים": "Маале-Адумим",

    # ── Хайфа и районы ────────────────────────────────────────────────────
    "хайфа": "Хайфа", "haifa": "Хайфа", "חיפה": "Хайфа",
    "кирьят-хаим": "Хайфа", "кирьят хаим": "Хайфа",
    "kiryat haim": "Хайфа", "קריית חיים": "Хайфа", "קרית חיים": "Хайфа",
    "кирьят-ям": "Хайфа", "кирьят ям": "Хайфа",
    "kiryat yam": "Хайфа", "קריית ים": "Хайфа", "קרית ים": "Хайфа",
    "кирьят-моцкин": "Хайфа", "кирьят моцкин": "Хайфа",
    "kiryat motzkin": "Хайфа", "קריית מוצקין": "Хайфа",
    "неве-шаанан хайфа": "Хайфа", "неве шаанан": "Хайфа",
    "адар": "Хайфа", "adar": "Хайфа",
    "рамат-шапира": "Хайфа", "כרמל": "Хайфа", "кармель": "Хайфа",
    "кирьят-ата": "Кирьят-Ата", "kiryat ata": "Кирьят-Ата", "קריית אתא": "Кирьят-Ата",
    "кирьят-бялик": "Кирьят-Бялик", "kiryat bialik": "Кирьят-Бялик", "קריית ביאליק": "Кирьят-Бялик",

    # ── Север ─────────────────────────────────────────────────────────────
    "нагария": "Нагария", "nahariya": "Нагария", "נהריה": "Нагария",
    "тиверия": "Тиверия", "tiberias": "Тиверия", "טבריה": "Тиверия",
    "акко": "Акко", "akko": "Акко", "acre": "Акко", "עכו": "Акко",
    "хадера": "Хадера", "hadera": "Хадера", "חדרה": "Хадера",
    "афула": "Афула", "afula": "Афула", "עפולה": "Афула",
    "цфат": "Цфат", "safed": "Цфат", "tzfat": "Цфат", "צפת": "Цфат",

    # ── Шарон ─────────────────────────────────────────────────────────────
    "нетания": "Нетания", "netanya": "Нетания", "נתניה": "Нетания",
    "герцлия": "Герцлия", "herzliya": "Герцлия", "הרצליה": "Герцлия",
    "кфар-саба": "Кфар-Саба", "кфар саба": "Кфар-Саба",
    "kfar saba": "Кфар-Саба", "כפר סבא": "Кфар-Саба",
    "раанана": "Раанана", "raanana": "Раанана", "רעננה": "Раанана",
    "ход-ха-шарон": "Ход-ха-Шарон", "hod hasharon": "Ход-ха-Шарон", "הוד השרון": "Ход-ха-Шарон",
    "эвен-иегуда": "Эвен-Иегуда", "even yehuda": "Эвен-Иегуда", "אבן יהודה": "Эвен-Иегуда",
    "рош-аин": "Рош-аин", "rosh haayin": "Рош-аин", "ראש העין": "Рош-аин",
    "рамат-ха-шарон": "Рамат-ха-Шарон", "ramat hasharon": "Рамат-ха-Шарон", "רמת השרון": "Рамат-ха-Шарон",
    "тира": "Тира", "tire": "Тира",

    # ── Центральный округ ─────────────────────────────────────────────────
    "петах-тиква": "Петах-Тиква", "петах тиква": "Петах-Тиква",
    "petah tikva": "Петах-Тиква", "פתח תקווה": "Петах-Тиква",
    "петах": "Петах-Тиква",
    "ришон-ле-цион": "Ришон-ле-Цион", "ришон лецион": "Ришон-ле-Цион",
    "rishon lezion": "Ришон-ле-Цион", "ראשון לציון": "Ришон-ле-Цион",
    "ришон": "Ришон-ле-Цион",
    "реховот": "Реховот", "rehovot": "Реховот", "רחובות": "Реховот",
    "нес-циона": "Нес-Циона", "нес циона": "Нес-Циона",
    "nes ziona": "Нес-Циона", "נס ציונה": "Нес-Циона",
    "лод": "Лод", "lod": "Лод", "לוד": "Лод",
    "рамла": "Рамла", "ramla": "Рамла", "רמלה": "Рамла",
    "модиин": "Модиин", "modiin": "Модиин", "מודיעין": "Модиин",
    "явне": "Явне", "yavne": "Явне", "יבנה": "Явне",

    # ── Юг ────────────────────────────────────────────────────────────────
    "ашдод": "Ашдод", "ashdod": "Ашдод", "אשדוד": "Ашдод",
    "ашкелон": "Ашкелон", "ashkelon": "Ашкелон", "אשקלון": "Ашкелон",
    "беэр-шева": "Беэр-Шева", "беэр шева": "Беэр-Шева",
    "beer sheva": "Беэр-Шева", "באר שבע": "Беэр-Шева",
    "эйлат": "Эйлат", "eilat": "Эйлат", "אילת": "Эйлат",
    "нетивот": "Нетивот", "netivot": "Нетивот", "נתיבות": "Нетивот",
    "сдерот": "Сдерот", "sderot": "Сдерот", "שדרות": "Сдерот",
    "димона": "Димона", "dimona": "Димона", "דימונה": "Димона",
    "арад": "Арад", "arad": "Арад", "ערד": "Арад",
    "офаким": "Офаким", "ofakim": "Офаким", "אופקים": "Офаким",
    "кирьят-гат": "Кирьят-Гат", "kiryat gat": "Кирьят-Гат", "קריית גת": "Кирьят-Гат",
    "бейт-шемеш юг": "Бейт-Шемеш",

    # ── Крайот (пригороды Хайфы) ──────────────────────────────────────────
    "крайот": "Хайфа", "kraiot": "Хайфа", "קריות": "Хайфа",

    # ── Дополнительные города и мошавы ────────────────────────────────────
    "зихрон-яаков": "Зихрон-Яаков", "zichron yaakov": "Зихрон-Яаков", "זיכרון יעקב": "Зихрон-Яаков",
    "биньямина": "Биньямина", "binyamina": "Биньямина", "בנימינה": "Биньямина",
    "парdes-хана": "Пардес-Хана", "pardes hanna": "Пардес-Хана", "פרדס חנה": "Пардес-Хана",
    "пардес-хана": "Пардес-Хана",
    "кфар-йона": "Кфар-Йона", "kfar yona": "Кфар-Йона", "כפר יונה": "Кфар-Йона",
    "тель-монд": "Тель-Монд", "tel mond": "Тель-Монд", "תל מונד": "Тель-Монд",
    "гадера": "Гадера", "gadera": "Гадера", "גדרה": "Гадера",
    "мазкерет-батья": "Мазкерет-Батья", "mazkeret batya": "Мазкерет-Батья", "מזכרת בתיה": "Мазкерет-Батья",
    "реэм": "Реэм", "reem": "Реэм",
    "беер-яаков": "Беэр-Яаков", "beer yaakov": "Беэр-Яаков", "באר יעקב": "Беэр-Яаков",
    "рамат-ган север": "Рамат-Ган",
    "гиват-шмуэль": "Гиват-Шмуэль", "givat shmuel": "Гиват-Шмуэль", "גבעת שמואל": "Гиват-Шмуэль",
    "кохав-яир": "Кохав-Яир", "kohav yair": "Кохав-Яир", "כוכב יאיר": "Кохав-Яир",
    "элад": "Элад", "elad": "Элад", "אלעד": "Элад",
    "рош-ха-аин": "Рош-аин", "rosh haayin": "Рош-аин",
    "хашмонаим": "Хашмонаим", "hashmonaim": "Хашмонаим", "חשמונאים": "Хашмонаим",
    "матeh-йехуда": "Матэ-Иегуда",
    "бейт-арье": "Бейт-Арье", "beit arye": "Бейт-Арье", "בית אריה": "Бейт-Арье",
    "орит": "Орит",
    "шохам": "Шохам", "shoham": "Шохам", "שהם": "Шохам",
    "гани-тиква": "Гани-Тиква", "ganei tikva": "Гани-Тиква", "גני תקווה": "Гани-Тиква",
    "азур": "Азур", "azur": "Азур", "אזור": "Азур",
    "савьон": "Савьон", "savyon": "Савьон", "סביון": "Савьон",
    "яhуд": "Яhуд-Моносон", "yahud": "Яhуд-Моносон", "יהוד": "Яhуд-Моносон",
    "кфар-синай": "Кфар-Синай",
    "гаш": "Гаш", "gash": "Гаш", "געש": "Гаш",
    "герцлия-питуах": "Герцлия", "herzliya pituah": "Герцлия", "herzliya pitua": "Герцлия",
    "кфар-шмарьяhу": "Кфар-Шмарьяhу", "kfar shmaryahu": "Кфар-Шмарьяhу", "כפר שמריהו": "Кфар-Шмарьяhу",
    "нир-цви": "Нир-Цви",
    "бат-хефер": "Бат-Хефер",
    # Мошавы и кибуцы рядом с городами
    "гиват-ада": "Гиват-Ада", "givat ada": "Гиват-Ада", "גבעת עדה": "Гиват-Ада",
    "эйн-веред": "Эйн-Веред", "ein vered": "Эйн-Веред", "עין ורד": "Эйн-Веред",
    "нир-элияhу": "Нир-Элияhу",
    "кфар-нетер": "Кфар-Нетер", "kfar netter": "Кфар-Нетер",
    "нагаария": "Нагария",
    # Russian case forms (genitive/prepositional) for common cities
    "нагарии": "Нагария", "нагарию": "Нагария",  # в Нагарии
    "нетании": "Нетания", "нетанию": "Нетания",  # в Нетании
    "ашдоде": "Ашдод", "ашдода": "Ашдод",  # в Ашдоде
    "ашкелоне": "Ашкелон", "ашкелона": "Ашкелон",  # в Ашкелоне
    "хайфе": "Хайфа", "хайфы": "Хайфа",  # в Хайфе
    "тель-авиве": "Тель-Авив", "тель авиве": "Тель-Авив",  # в Тель-Авиве
    "иерусалиме": "Иерусалим", "иерусалима": "Иерусалим",  # в Иерусалиме
    "беэр-шеве": "Беэр-Шева", "беэр шеве": "Беэр-Шева",  # в Беэр-Шеве
    "реховоте": "Реховот", "реховота": "Реховот",  # в Реховоте
    "петах-тикве": "Петах-Тиква", "петах тикве": "Петах-Тиква",  # в Петах-Тикве
    "рамат-гане": "Рамат-Ган", "рамат гане": "Рамат-Ган",  # в Рамат-Гане
    "герцлии": "Герцлия", "герцлию": "Герцлия",  # в Герцлии
    "ришоне": "Ришон-ле-Цион",  # в Ришоне
    "холоне": "Холон", "холона": "Холон",  # в Холоне
    "бат-яме": "Бат-Ям", "бат яме": "Бат-Ям",  # в Бат-Яме
    "бней-браке": "Бней-Брак", "бней браке": "Бней-Брак",  # в Бней-Браке
    "рамле": "Рамла", "рамлы": "Рамла",  # в Рамле
    "нес-ционе": "Нес-Циона", "нес ционе": "Нес-Циона",  # в Нес-Ционе
    "лоде": "Лод", "лода": "Лод",  # в Лоде
    "модиине": "Модиин", "модиина": "Модиин",  # в Модиине
    "хадере": "Хадера", "хадеры": "Хадера",  # в Хадере
    "акко": "Акко", "акке": "Акко",  # в Акко
    "тиверии": "Тиверия", "тиверию": "Тиверия",  # в Тиверии
    "афуле": "Афула", "афулы": "Афула",  # в Афуле
    "цфате": "Цфат", "цфата": "Цфат",  # в Цфате
    "раанане": "Раанана", "рааны": "Раанана",  # в Раанане
    "кфар-сабе": "Кфар-Саба", "кфар сабе": "Кфар-Саба",  # в Кфар-Сабе
    "эйлате": "Эйлат", "эйлата": "Эйлат",  # в Эйлате
    "нетивоте": "Нетивот", "нетивота": "Нетивот",  # в Нетивоте
    "сдероте": "Сдерот", "сдерота": "Сдерот",  # в Сдероте
    "арад": "Арад", "араде": "Арад",  # в Арад/Ариде
    "кирьят-ате": "Кирьят-Ата", "кирьят ате": "Кирьят-Ата",
    "кирьят-бялике": "Кирьят-Бялик", "кирьят бялике": "Кирьят-Бялик",
    "кирьят-гате": "Кирьят-Гат", "кирьят гате": "Кирьят-Гат",
    "зихрон-яакове": "Зихрон-Яаков", "зихроне": "Зихрон-Яаков",
    "кармиэле": "Кармиэль", "кармиэля": "Кармиэль",
    "нешере": "Нешер", "нешера": "Нешер",
    "явне": "Явне",  # already nominative but also used in various forms
    "явнее": "Явне",
    "гиват-шмуэле": "Гиват-Шмуэль",
    "мевасерет-ционе": "Мевасерет-Цион",
    "бейт-шемеше": "Бейт-Шемеш",
    "акко": "Акко", "akko": "Акко", "עכו": "Акко",
    "маалот-таршиха": "Маалот-Таршиха", "maalot tarshiha": "Маалот-Таршиха", "מעלות-תרשיחא": "Маалот-Таршиха",
    "кармиэль": "Кармиэль", "karmiel": "Кармиэль", "כרמיאל": "Кармиэль",
    "йокнеам": "Йокнеам", "yokneam": "Йокнеам", "יקנעם": "Йокнеам",
    "нешер": "Нешер", "nesher": "Нешер", "נשר": "Нешер",
    "тират-кармель": "Тират-Кармель", "tirat carmel": "Тират-Кармель", "טירת כרמל": "Тират-Кармель",
    "далият-эль-кармель": "Далият-эль-Кармель",
    "усфия": "Усфия",
    "мегидо": "Мегидо",
    "рамат-ишай": "Рамат-Ишай", "ramat yishay": "Рамат-Ишай", "רמת ישי": "Рамат-Ишай",
    "кфар-хасидим": "Кфар-Хасидим",
    "эвен-шмуэль": "Эвен-Шмуэль",
    "мевасерет-цион": "Мевасерет-Цион", "mevaseret zion": "Мевасерет-Цион", "מבשרת ציון": "Мевасерет-Цион",
    "бейт-шемеш": "Бейт-Шемеш",
    "эфрата": "Эфрата", "efrat": "Эфрата", "אפרת": "Эфрата",
    "модиин-илит": "Модиин-Илит", "modiin ilit": "Модиин-Илит", "מודיעין עילית": "Модиин-Илит",
    "беэр-шева юг": "Беэр-Шева",
    "лакия": "Лакия", "omer": "Омер", "омер": "Омер", "עומר": "Омер",
    "тель-шева": "Тель-Шева",
    "рахат": "Рахат", "rahat": "Рахат", "רהט": "Рахат",
    "арара-бнегев": "Арара",
    "мицпе-рамон": "Мицпе-Рамон", "mitzpe ramon": "Мицпе-Рамон", "מצפה רמון": "Мицпе-Рамон",
    "йерухам": "Йерухам", "yeruham": "Йерухам", "ירוחם": "Йерухам",
    "ашдот-яаков": "Ашдот-Яаков",
    "гдера": "Гдера", "gedera": "Гдера", "גדרה": "Гдера",
    "явне": "Явне", "yavne": "Явне", "יבנה": "Явне",

    # ── Субаренда без указания города ─────────────────────────────────────
    "субаренда": "Тель-Авив", "sublet": "Тель-Авив", "саблет": "Тель-Авив",
}

DISTRICT_MAP = {
    "Тель-Авив": "tel_aviv", "Рамат-Ган": "tel_aviv",
    "Холон": "tel_aviv", "Бат-Ям": "tel_aviv",
    "Иерусалим": "jerusalem",
    "Хайфа": "haifa",
    "Нетания": "sharon", "Герцлия": "sharon",
    "Кфар-Саба": "sharon", "Раанана": "sharon",
    "Петах-Тиква": "center", "Ришон-ле-Цион": "center",
    "Реховот": "center", "Модиин": "center",
    "Нагария": "haifa",
    "Ашдод": "south", "Ашкелон": "south",
    "Беэр-Шева": "south", "Эйлат": "south",
}

# ─── helpers ────────────────────────────────────────────────────────────────

def extract_parking(text):
    """Extract parking count from text. Returns int 0-3."""
    t = text.lower()
    # No parking
    if re.search(r'без\s*парк|no\s*park|ללא\s*חניה', t):
        return 0
    # Count: "2 места парковки", "2 паркинга", "2 חניות"
    m = re.search(r'(\d)\s*(?:мест[аео]?\s*парк|паркинг|парков|חניות|parking\s*space)', t)
    if m:
        n = int(m.group(1))
        return min(n, 3)
    # Any parking mention
    if re.search(r'парков|паркинг|машиноместо|חניה|חניון|parking', t):
        return 1
    return 0


def extract_pool(text):
    """Returns True if pool is mentioned (without negation context)."""
    t = text.lower()
    # Check for negation: "без бассейна", "no pool", "אין בריכה" etc.
    if re.search(r'без\s+бассейн|нет\s+бассейн|no\s+pool|without\s+pool|אין\s+בריכה', t):
        return False
    return bool(re.search(r'бассейн|swimming\s*pool|pool|בריכה', t))


def extract_property_type(text):
    """Detect property type from text."""
    t = text.lower()
    if re.search(r'пентхаус|penthouse|פנטהאוז', t):
        return "penthouse"
    if re.search(r'вилл[ауыеой]?|villa|וילה', t):
        return "villa"
    if re.search(r'дуплекс|duplex|דופלקס', t):
        return "duplex"
    if re.search(r'студи[яюей]|studio|סטודיו|חדר\s*אחד', t):
        return "studio"
    if re.search(r'котедж|коттедж|частный\s*дом|бунгало|בית\s*פרטי|cottage|house', t):
        return "house"
    return "apartment"


def extract_deal_type(text):
    """Detect deal type: rent or buy."""
    t = text.lower()
    if re.search(r'продаж|продаётся|продается|למכירה|for\s*sale|מכירה|купить', t):
        return "buy"
    return "rent"


def extract_floor(text):
    """Extract floor number."""
    patterns = [
        r'(\d+)\s*(?:этаж|этажа|этажей)',
        r'этаж\s*[:№]?\s*(\d+)',
        r'קומה\s*(\d+)',
        r'(\d+)\s*קומה',
        r'floor\s*[:№]?\s*(\d+)',
        r'(\d+)\s*(?:st|nd|rd|th)\s*floor',
    ]
    for pattern in patterns:
        m = re.search(pattern, text.lower())
        if m:
            try:
                f = int(m.group(1))
                if 0 <= f <= 50:
                    return str(f)
            except:
                pass
    return "1"


def extract_area(text):
    """Extract area in sqm."""
    patterns = [
        r'(\d{2,4})\s*(?:кв\.?\s*м|м²|m²|sqm|sq\.?m)',
        r'(\d{2,4})\s*מ[\"\'״]',
        r'площадь\s*[:—]?\s*(\d{2,4})',
        r'(\d{2,4})\s*(?:square|метров)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text.lower())
        if m:
            try:
                area = int(m.group(1))
                if 15 <= area <= 1000:
                    return area
            except:
                pass
    return 0


INFRA_KEYWORDS = {
    "school":       ["школ", "school", "בית ספר", "בי\"ס"],
    "kindergarten": ["детский сад", "садик", "גן ילדים", "גן"],
    "mall":         ["торговый центр", "торгц", "молл", "tts", "קניון", "mall", "shopping"],
    "park":         ["парк", "park", "פארק", "גן ציבורי"],
    "gym":          ["спортзал", "фитнес", "gym", "fitness", "חדר כושר"],
    "hospital":     ["больниц", "клиник", "hospital", "clinic", "בית חולים", "מרפאה"],
    "beach":        ["пляж", "море", "beach", "חוף", "ים"],
    "transport":    ["автобус", "трамвай", "метро", "транспорт", "bus", "tram", "metro",
                     "אוטובוס", "רכבת", "תחנה", "תחבורה", "transport"],
    "restaurant":   ["ресторан", "кафе", "restaurant", "cafe", "מסעדה", "מסעדות", "קפה"],
    "synagogue":    ["синагог", "synagogue", "בית כנסת"],
    "public_pool":  ["общественный бассейн", "municipal pool", "בריכה ציבורית"],
}

def extract_infrastructure(text):
    """Extract list of infrastructure tags mentioned in text."""
    t = text.lower()
    found = []
    for tag, keywords in INFRA_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            found.append(tag)
    return found


def extract_neighborhood(text, city):
    """Try to extract neighborhood/area name from text."""
    # Common patterns: "район Х", "квартал Х", "р-н Х", "улица Х"
    for pattern in [
        r'район\s+([А-ЯЁа-яёa-zA-Z\-]+)',
        r'р-н\s+([А-ЯЁа-яёa-zA-Z\-]+)',
        r'квартал\s+([А-ЯЁа-яёa-zA-Z\-]+)',
        r'שכונת\s+([\w\s\-]+)',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if len(val) > 2:
                return val[:40]
    return ""


def detect_city(text):
    """Detect city from text. Checks longer (more specific) keywords first.
    Uses word-boundary matching to avoid false positives (e.g. 'тира' in 'квартира').
    Allows up to 3 trailing Russian chars to handle case endings (хаим→хаиме, авив→авиве).
    """
    import re
    text_lower = text.lower()
    # Sort by keyword length descending — longer/more specific first
    for keyword in sorted(CITY_KEYWORDS.keys(), key=len, reverse=True):
        # Match keyword + optional Russian case ending (up to 3 chars), with word boundaries
        pattern = r'(?<![а-яёa-z\w])' + re.escape(keyword) + r'[а-яё]{0,3}(?![а-яёa-z\w])'
        if re.search(pattern, text_lower):
            return CITY_KEYWORDS[keyword]
    return None  # unknown city

def extract_price(text):
    patterns = [
        r'(\d[\d\s,]{2,6})\s*₪',
        r'(\d[\d\s,]{2,6})\s*[Nn][Ii][Ss]',
        r'(\d[\d\s,]{2,6})\s*шек',
        r'(\d[\d\s,]{2,6})\s*שקל',
        r'מחיר[:\s]+(\d[\d\s,]+)',
        r'цена[:\s]+(\d[\d\s,]+)',
        r'price[:\s]+(\d[\d\s,]+)',
        r'(\d{3,6})\s*לחודש',
        r'(\d{3,6})\s*в\s*мес',
        r'(\d{3,6})\s*/\s*мес',
        r'(\d{4,6})\s*в\s*month',
        r'💰\s*(\d[\d\s,]+)',
        r'(\d{4,6})(?=\s*₪)',
    ]
    found = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                price_str = match.group(1).replace(" ", "").replace(",", "")
                price = int(price_str)
                if 1000 <= price <= 100000:
                    found.append(price)
            except:
                pass
    if found:
        counts = {}
        for p in found:
            counts[p] = counts.get(p, 0) + 1
        return max(counts, key=counts.get)
    return 0

def extract_rooms(text):
    patterns = [
        r'(\d[.,]?\d?)\s*комн',
        r'(\d[.,]?\d?)\s*חד',
        r'(\d[.,]?\d?)\s*room',
        r'(\d[.,]?\d?)-к',
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            try:
                val = float(match.group(1).replace(",", "."))
                if 1 <= val <= 10:
                    return str(val).replace(".0", "")
            except:
                pass
    return "3"

def is_listing(text):
    if len(text) < 40:
        return False
    keywords = [
        # Аренда (ru)
        "аренда", "аренд", "сдам", "сдаю", "сдается", "сдаётся", "снять", "снимаю",
        "субаренда", "саблет", "сублет",
        # Продажа (ru)
        "продает", "продаёт", "продаж", "продам", "продается", "продаётся",
        # Иврит — аренда
        "להשכרה", "שכירות", "מחיר",
        # Иврит — продажа
        "למכירה", "מכירה",
        # Цена / символы
        "цена", "₪", "nis", "ils",
        # English
        "rent", "for rent", "for sale", "lease",
    ]
    t_lower = text.lower()
    return any(w in t_lower for w in keywords)

def url_exists(source_url: str) -> bool:
    """Check if a listing with this source URL already exists in the DB."""
    data = db._load()
    for listing in data["listings"].values():
        if listing.get("source_url") == source_url:
            return True
    return False

# ─── web scraping (no auth required) ────────────────────────────────────────

def scrape_channel_web(channel: str, limit: int = 100) -> list:
    """
    Scrape a public Telegram channel via t.me/s/<channel>.
    Paginates using ?before=<id> to get more historical messages.
    Returns list of (post_id, text, source_url).
    """
    results = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    from lxml import html as lhtml

    seen_ids = set()
    before = None  # start from latest

    for _page in range(3):  # up to 3 pages (~60 messages per page)
        url = f"https://t.me/s/{channel}"
        if before:
            url += f"?before={before}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                break
            # Check if private
            if "This channel is private" in resp.text:
                break

            tree = lhtml.fromstring(resp.text)
            wraps = tree.xpath('//div[contains(@class,"tgme_widget_message_wrap")]')
            if not wraps:
                break

            page_ids = []
            for wrap in wraps:
                post_elems = wrap.xpath('.//*[@data-post]')
                if not post_elems:
                    continue
                data_post = post_elems[0].get("data-post", "")
                post_id = data_post.split("/")[-1]
                if not post_id or not post_id.isdigit():
                    continue
                if post_id in seen_ids:
                    continue
                seen_ids.add(post_id)
                page_ids.append(int(post_id))

                text_elems = wrap.xpath('.//div[contains(@class,"tgme_widget_message_text")]')
                if not text_elems:
                    continue
                text = text_elems[0].text_content().strip()
                if text:
                    source_url = f"https://t.me/{channel}/{post_id}"
                    results.append((post_id, text, source_url))

            if len(results) >= limit:
                break
            if page_ids:
                before = min(page_ids)  # go further back
            else:
                break

        except Exception as e:
            print(f"  Ошибка веб-скрапинга @{channel}: {e}")
            break

    return results[-limit:]


def parse_channel_web(channel: str, limit: int = 50) -> int:
    """Parse one channel via web scraping. Returns count of newly added listings."""
    added = 0
    messages = scrape_channel_web(channel, limit)
    for _post_id, text, source_url in messages:
        if url_exists(source_url):
            continue
        if not is_listing(text):
            continue
        city = detect_city(text) or "Израиль"
        deal_type = extract_deal_type(text)
        prop_type = extract_property_type(text)
        listing = {
            "title": f"📱 {text[:70].replace(chr(10), ' ').strip()}...",
            "description": text[:600],
            "property_type": prop_type,
            "city": city,
            "district": DISTRICT_MAP.get(city, "center"),
            "neighborhood": extract_neighborhood(text, city),
            "rooms": extract_rooms(text),
            "floor": extract_floor(text),
            "area_sqm": extract_area(text),
            "price": extract_price(text),
            "deal_type": deal_type,
            "parking": extract_parking(text),
            "pool": extract_pool(text),
            "infrastructure": extract_infrastructure(text),
            "contact": f"@{channel}",
            "photos": ["🏢"],
            "source": "telegram",
            "source_url": source_url,
        }
        db.add_listing(listing)
        added += 1
    return added

# ─── telethon (optional, requires SESSION_STRING) ───────────────────────────

async def parse_channel_telethon(client, channel: str, limit: int = 50) -> int:
    added = 0
    try:
        async for message in client.iter_messages(channel, limit=limit):
            if not message.text:
                continue
            text = message.text
            source_url = f"https://t.me/{channel}/{message.id}"
            if url_exists(source_url):
                continue
            if not is_listing(text):
                continue
            city = detect_city(text) or "Израиль"
            deal_type = extract_deal_type(text)
            prop_type = extract_property_type(text)
            listing = {
                "title": f"📱 {text[:70].replace(chr(10), ' ').strip()}...",
                "description": text[:600],
                "property_type": prop_type,
                "city": city,
                "district": DISTRICT_MAP.get(city, "center"),
                "neighborhood": extract_neighborhood(text, city),
                "rooms": extract_rooms(text),
                "floor": extract_floor(text),
                "area_sqm": extract_area(text),
                "price": extract_price(text),
                "deal_type": deal_type,
                "parking": extract_parking(text),
                "pool": extract_pool(text),
                "infrastructure": extract_infrastructure(text),
                "contact": f"@{channel}",
                "photos": ["🏢"],
                "source": "telegram",
                "source_url": source_url,
            }
            db.add_listing(listing)
            added += 1
    except Exception as e:
        print(f"  Ошибка Telethon @{channel}: {e}")
    return added

# ─── main loop ───────────────────────────────────────────────────────────────

async def run_parser():
    print("=" * 50)
    print("Telegram Parser — FlatFinderIL")
    print(f"Каналов: {len(CHANNELS)}")
    print("=" * 50)

    session_str = os.environ.get("SESSION_STRING")
    session_file = "flatfinderil_session.session"
    use_telethon = bool(session_str) or os.path.exists(session_file)

    client = None
    if use_telethon:
        try:
            from telethon import TelegramClient
            if session_str:
                from telethon.sessions import StringSession
                client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            else:
                client = TelegramClient(session_file, API_ID, API_HASH)
            await client.start()
            print("✅ Telethon подключён!")
        except Exception as e:
            print(f"⚠️  Telethon ошибка: {e} — переключаемся на веб-скрапинг")
            client = None
    else:
        print("📡 Режим: веб-скрапинг (без авторизации)")

    while True:
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] Запуск парсинга {len(CHANNELS)} каналов...")
        total = 0

        for channel in CHANNELS:
            print(f"  @{channel} ...", end=" ", flush=True)
            try:
                if client:
                    n = await parse_channel_telethon(client, channel)
                else:
                    n = parse_channel_web(channel)
                    await asyncio.sleep(0)   # yield to event loop
                print(f"+{n}")
                total += n
            except Exception as e:
                print(f"❌ {e}")
            await asyncio.sleep(3)   # be polite between channels

        print(f"\n✅ Итого новых: {total} | Следующий запуск через 30 мин.")
        await asyncio.sleep(1800)


if __name__ == "__main__":
    asyncio.run(run_parser())
