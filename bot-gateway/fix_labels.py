import re

with open('search_handler.py', 'r') as f:
    content = f.read()

helper = """
def _lbl(context, ru, en, he):
    lang = get_lang(context)
    d = {"ru": ru, "en": en, "he": he}
    return d.get(lang, ru)

"""

if '_lbl' not in content:
    content = content.replace(
        'import database as db\n',
        'import database as db\n' + helper
    )

pairs = [
    ('"\u2705 <b>\u0422\u0438\u043f \u0441\u0434\u0435\u043b\u043a\u0438:</b> ', '"\u2705 <b>" + _lbl(context,"\u0422\u0438\u043f \u0441\u0434\u0435\u043b\u043a\u0438","Deal type","\u05e1\u05d5\u05d2 \u05e2\u05e1\u05e7\u05d4") + ":</b> '),
    ('"\u2705 <b>\u0422\u0438\u043f \u0436\u0438\u043b\u044c\u044f:</b> ', '"\u2705 <b>" + _lbl(context,"\u0422\u0438\u043f \u0436\u0438\u043b\u044c\u044f","Property type","\u05e1\u05d5\u05d2 \u05e0\u05db\u05e1") + ":</b> '),
    ('"\u2705 <b>\u041e\u043a\u0440\u0443\u0433:</b> ', '"\u2705 <b>" + _lbl(context,"\u041e\u043a\u0440\u0443\u0433","District","\u05de\u05d7\u05d5\u05d6") + ":</b> '),
    ('"\u2705 <b>\u0413\u043e\u0440\u043e\u0434:</b> ', '"\u2705 <b>" + _lbl(context,"\u0413\u043e\u0440\u043e\u0434","City","\u05e2\u05d9\u05e8") + ":</b> '),
    ('"\u2705 <b>\u041a\u043e\u043c\u043d\u0430\u0442 \u043e\u0442:</b> ', '"\u2705 <b>" + _lbl(context,"\u041a\u043e\u043c\u043d\u0430\u0442 \u043e\u0442","Rooms from","\u05d7\u05d3\u05e8\u05d9\u05dd \u05de") + ":</b> '),
    ('"\u2705 <b>\u041a\u043e\u043c\u043d\u0430\u0442 \u0434\u043e:</b> ', '"\u2705 <b>" + _lbl(context,"\u041a\u043e\u043c\u043d\u0430\u0442 \u0434\u043e","Rooms up to","\u05d7\u05d3\u05e8\u05d9\u05dd \u05e2\u05d3") + ":</b> '),
    ('"\u2705 <b>\u0426\u0435\u043d\u0430 \u043e\u0442:</b> ', '"\u2705 <b>" + _lbl(context,"\u0426\u0435\u043d\u0430 \u043e\u0442","Price from","\u05de\u05d7\u05d9\u05e8 \u05de") + ":</b> '),
    ('"\u2705 <b>\u0426\u0435\u043d\u0430 \u0434\u043e:</b> ', '"\u2705 <b>" + _lbl(context,"\u0426\u0435\u043d\u0430 \u0434\u043e","Price up to","\u05de\u05d7\u05d9\u05e8 \u05e2\u05d3") + ":</b> '),
    ('"\u2705 <b>\u041f\u0430\u0440\u043a\u043e\u0432\u043a\u0430:</b> ', '"\u2705 <b>" + _lbl(context,"\u041f\u0430\u0440\u043a\u043e\u0432\u043a\u0430","Parking","\u05d7\u05e0\u05d9\u05d4") + ":</b> '),
    ('"\u2705 <b>\u0411\u0430\u0441\u0441\u0435\u0439\u043d:</b> ', '"\u2705 <b>" + _lbl(context,"\u0411\u0430\u0441\u0441\u0435\u0439\u043d","Pool","\u05d1\u05e8\u05d9\u05db\u05d4") + ":</b> '),
    ('"\u2705 <b>\u0417\u0430\u0449\u0438\u0442\u043d\u043e\u0435 \u043f\u043e\u043c\u0435\u0449\u0435\u043d\u0438\u0435:</b> ', '"\u2705 <b>" + _lbl(context,"\u0417\u0430\u0449\u0438\u0442\u043d\u043e\u0435 \u043f\u043e\u043c\u0435\u0449\u0435\u043d\u0438\u0435","Shelter","\u05de\u05e8\u05d7\u05d1 \u05de\u05d5\u05d2\u05df") + ":</b> '),
    ('"\u2705 <b>\u0418\u043d\u0444\u0440\u0430\u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0430:</b> ', '"\u2705 <b>" + _lbl(context,"\u0418\u043d\u0444\u0440\u0430\u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0430","Infrastructure","\u05ea\u05e9\u05ea\u05d9\u05d5\u05ea") + ":</b> '),
]

count = 0
for old, new in pairs:
    if old in content:
        content = content.replace(old, new)
        count += 1

with open('search_handler.py', 'w') as f:
    f.write(content)

print(f"Fixed {count} labels")
