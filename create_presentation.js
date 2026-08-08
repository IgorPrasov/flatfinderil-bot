const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "FinderIL Ecosystem — Business Plan 2026";
pres.author = "FinderIL Team";

// ─── PALETTE ──────────────────────────────────────────────────────────────────
const C = {
  bg:       "FFFFFF",   // white
  bg2:      "F8FAFC",   // near white
  bg3:      "F1F5F9",   // light card bg
  border:   "CBD5E1",   // light border
  flat:     "1D4ED8",   // FlatFinderIL blue (darker for readability on white)
  flatL:    "2563EB",   // medium blue
  cars:     "0F766E",   // CarsFinderIL teal (darker)
  carsL:    "0D9488",   // teal
  jobs:     "B45309",   // JobFinderIL amber (darker)
  jobsL:    "D97706",   // amber
  eco:      "6D28D9",   // ecosystem purple (darker)
  ecoL:     "7C3AED",   // purple
  green:    "059669",   // positive/growth (darker)
  greenL:   "10B981",
  white:    "0F172A",   // dark text (inverted for light theme)
  gray:     "475569",   // medium dark text
  darkgray: "94A3B8",   // muted/secondary
  gold:     "D97706",
};

// ─── HELPERS ─────────────────────────────────────────────────────────────────
function bg(slide, color) {
  slide.background = { color: color || C.bg };
}
function title(slide, text, opts = {}) {
  slide.addText(text, {
    x: 0.45, y: opts.y ?? 0.28, w: 9.1, h: 0.6,
    fontSize: opts.fontSize ?? 28, bold: true,
    color: opts.color ?? C.white, fontFace: "Calibri",
    align: opts.align ?? "left", margin: 0,
    ...opts,
  });
}
function subtitle(slide, text, opts = {}) {
  slide.addText(text, {
    x: 0.45, y: opts.y ?? 0.92, w: 9.1, h: 0.32,
    fontSize: 13, color: C.gray, fontFace: "Calibri",
    align: "left", margin: 0, ...opts,
  });
}
function card(slide, x, y, w, h, color) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: C.bg3 },
    line: { color: color || C.border, width: 1 },
  });
}
function accentBar(slide, x, y, h, color) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 0.055, h,
    fill: { color: color || C.flat },
    line: { color: color || C.flat, width: 0 },
  });
}
function makeShadow() {
  return { type: "outer", color: "000000", blur: 8, offset: 2, angle: 135, opacity: 0.2 };
}
function dividerLine(slide, y) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.45, y, w: 9.1, h: 0.015,
    fill: { color: C.border }, line: { color: C.border, width: 0 },
  });
}
function smallTag(slide, x, y, text, color) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.2, h: 0.26, fill: { color: "F1F5F9" }, line: { color: color, width: 1.5 }, rectRadius: 0.04 });
  slide.addText(text, { x, y: y + 0.02, w: 1.2, h: 0.24, fontSize: 9.5, color, fontFace: "Calibri", bold: true, align: "center", margin: 0 });
}
function statBox(slide, x, y, w, h, num, label, color, bgColor) {
  slide.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: bgColor || C.bg3 }, line: { color: color, width: 1 } });
  slide.addText(num, { x, y: y + 0.12, w, h: 0.42, fontSize: 30, bold: true, color, fontFace: "Calibri", align: "center", margin: 0 });
  slide.addText(label, { x, y: y + 0.56, w, h: 0.28, fontSize: 9.5, color: C.gray, fontFace: "Calibri", align: "center", margin: 0 });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 1 — COVER
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };

  // Side accent strip
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.18, h: 5.625, fill: { color: C.flat }, line: { color: C.flat, width: 0 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.18, y: 0, w: 0.06, h: 5.625, fill: { color: C.cars }, line: { color: C.cars, width: 0 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.24, y: 0, w: 0.06, h: 5.625, fill: { color: C.jobs }, line: { color: C.jobs, width: 0 } });

  // Bottom bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 4.88, w: 10, h: 0.745, fill: { color: "EFF6FF" }, line: { color: C.border, width: 0 } });

  // Main title
  s.addText("FinderIL", {
    x: 0.6, y: 0.7, w: 9, h: 1.4,
    fontSize: 72, bold: true, color: C.white, fontFace: "Calibri", align: "left", margin: 0,
  });
  s.addText("ECOSYSTEM", {
    x: 0.6, y: 1.9, w: 9, h: 0.55,
    fontSize: 26, bold: false, color: C.gray, fontFace: "Calibri", align: "left", margin: 0,
    charSpacing: 8,
  });

  // Tagline
  dividerLine(s, 2.62);
  s.addText("Платформа недвижимости, авто и работы в Израиле", {
    x: 0.6, y: 2.72, w: 8, h: 0.45,
    fontSize: 16, color: C.gray, fontFace: "Calibri", align: "left", margin: 0,
  });

  // Three product pills
  const products = [
    { label: "🏠 FlatFinderIL", color: C.flat },
    { label: "🚗 CarsFinderIL", color: C.cars },
    { label: "💼 JobFinderIL",  color: C.jobs },
  ];
  products.forEach((p, i) => {
    const x = 0.6 + i * 2.8;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 3.28, w: 2.5, h: 0.44, fill: { color: C.bg3 }, line: { color: p.color, width: 1.5 } });
    s.addText(p.label, { x, y: 3.28, w: 2.5, h: 0.44, fontSize: 12, bold: true, color: p.color, fontFace: "Calibri", align: "center", valign: "middle", margin: 0 });
  });

  // Bottom info
  s.addText("БИЗНЕС-ПЛАН · 2026–2028", { x: 0.6, y: 5.03, w: 5, h: 0.3, fontSize: 10, color: C.darkgray, fontFace: "Calibri", align: "left", margin: 0, charSpacing: 2 });
  s.addText("flatfinder.co.il  ·  t.me/FlatFinderIL_bot", { x: 5.5, y: 5.03, w: 4.1, h: 0.3, fontSize: 10, color: C.darkgray, fontFace: "Calibri", align: "right", margin: 0 });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 2 — PROBLEM
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  title(s, "Проблема: поиск жилья, авто и работы в Израиле");
  subtitle(s, "Рынок фрагментирован — нет единой русскоязычной платформы");
  dividerLine(s, 1.32);

  const problems = [
    {
      icon: "🏠", color: C.flat,
      title: "Недвижимость",
      text: "Объявления разбросаны по 50+ Telegram-каналам. Нет фильтров, нет алертов, нет единой базы. Репатрианты тратят недели на поиск жилья.",
      stat: "500K", statLabel: "переездов/год",
    },
    {
      icon: "🚗", color: C.cars,
      title: "Авто",
      text: "Yad2 полностью на иврите. Русскоязычные покупатели не понимают интерфейс, боятся мошенников. Нет агрегатора на их языке.",
      stat: "300K", statLabel: "авто продаётся/год",
    },
    {
      icon: "💼", color: C.jobs,
      title: "Работа",
      text: "LinkedIn дорог. HeadHunter не работает в Израиле. Русскоязычные специалисты ищут работу через знакомых и устаревшие чаты.",
      stat: "1.5M", statLabel: "русскоязычных",
    },
  ];

  problems.forEach((p, i) => {
    const x = 0.45 + i * 3.1;
    card(s, x, 1.48, 2.88, 3.5, p.color);
    accentBar(s, x, 1.48, 3.5, p.color);
    s.addText(p.icon, { x: x + 0.2, y: 1.62, w: 0.5, h: 0.5, fontSize: 28, align: "left", margin: 0 });
    s.addText(p.title, { x: x + 0.2, y: 2.15, w: 2.55, h: 0.35, fontSize: 15, bold: true, color: C.white, fontFace: "Calibri", align: "left", margin: 0 });
    s.addText(p.text, { x: x + 0.2, y: 2.54, w: 2.55, h: 1.5, fontSize: 11, color: C.gray, fontFace: "Calibri", align: "left", valign: "top", margin: 0 });
    // stat
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.2, y: 4.15, w: 2.55, h: 0.62, fill: { color: "EFF6FF" }, line: { color: p.color, width: 1 } });
    s.addText(p.stat, { x: x + 0.2, y: 4.17, w: 1.2, h: 0.35, fontSize: 22, bold: true, color: p.color, fontFace: "Calibri", align: "left", margin: 0 });
    s.addText(p.statLabel, { x: x + 1.42, y: 4.22, w: 1.3, h: 0.32, fontSize: 9.5, color: C.gray, fontFace: "Calibri", align: "left", margin: 0 });
  });

  s.addText("💡 Один Telegram-бот на трёх языках (RU/EN/HE) решает все три проблемы", {
    x: 0.45, y: 5.12, w: 9.1, h: 0.35,
    fontSize: 12, color: C.green, fontFace: "Calibri", bold: true, align: "center", margin: 0,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 3 — SOLUTION OVERVIEW
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  title(s, "Решение: экосистема FinderIL");
  subtitle(s, "Единая платформа — три вертикали, один бренд");
  dividerLine(s, 1.32);

  // Large ecosystem visual
  // Center hub
  s.addShape(pres.shapes.OVAL, { x: 3.9, y: 2.0, w: 2.2, h: 2.2, fill: { color: C.eco }, line: { color: C.ecoL, width: 2 } });
  s.addText("FinderIL\nEcosystem", { x: 3.9, y: 2.3, w: 2.2, h: 1.5, fontSize: 14, bold: true, color: C.white, fontFace: "Calibri", align: "center", valign: "middle", margin: 0 });

  // Three satellites
  const sats = [
    { x: 0.5, y: 1.5, color: C.flat, bg: "EFF6FF", label: "🏠 FlatFinderIL", desc: "Аренда и покупка\nнедвижимости", tag: "РАБОТАЕТ" },
    { x: 0.3, y: 3.5, color: C.cars, bg: "F0FDFA", label: "🚗 CarsFinderIL", desc: "Покупка и продажа\nавтомобилей", tag: "Q4 2026" },
    { x: 7.0, y: 2.4, color: C.jobs, bg: "FFFBEB", label: "💼 JobFinderIL",  desc: "Поиск работы\nи специалистов", tag: "Q1 2027" },
  ];
  sats.forEach(sat => {
    card(s, sat.x, sat.y, 2.8, 1.65, sat.color);
    accentBar(s, sat.x, sat.y, 1.65, sat.color);
    s.addText(sat.label, { x: sat.x + 0.18, y: sat.y + 0.12, w: 2.5, h: 0.35, fontSize: 13, bold: true, color: sat.color, fontFace: "Calibri", margin: 0 });
    s.addText(sat.desc, { x: sat.x + 0.18, y: sat.y + 0.5, w: 2.5, h: 0.6, fontSize: 11, color: C.gray, fontFace: "Calibri", margin: 0 });
    s.addShape(pres.shapes.RECTANGLE, { x: sat.x + 0.18, y: sat.y + 1.2, w: 1.0, h: 0.24, fill: { color: sat.color }, line: { color: sat.color, width: 0 } });
    s.addText(sat.tag, { x: sat.x + 0.18, y: sat.y + 1.2, w: 1.0, h: 0.24, fontSize: 8.5, bold: true, color: "FFFFFF", fontFace: "Calibri", align: "center", valign: "middle", margin: 0 });
  });

  // Channels row
  const channels = ["Telegram Bot", "Mini App", "Web .co.il", "Web .com"];
  const chColors = [C.flat, C.cars, C.jobs, C.eco];
  channels.forEach((ch, i) => {
    const x = 0.5 + i * 2.25;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 5.08, w: 2.0, h: 0.36, fill: { color: C.bg3 }, line: { color: chColors[i], width: 1 } });
    s.addText(ch, { x, y: 5.08, w: 2.0, h: 0.36, fontSize: 10.5, color: chColors[i], fontFace: "Calibri", bold: true, align: "center", valign: "middle", margin: 0 });
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 4 — FLATFINDERIL TODAY
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  // Header bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 1.18, fill: { color: "EFF6FF" }, line: { color: C.border, width: 0 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 1.18, w: 10, h: 0.04, fill: { color: C.flat }, line: { color: C.flat, width: 0 } });
  title(s, "🏠 FlatFinderIL — Состояние сегодня", { y: 0.28, color: C.flat });
  subtitle(s, "Работающий продукт · 5 000+ объявлений · 20 городов · PostgreSQL на Railway", { y: 0.75 });

  // Stats row
  const stats = [
    { n: "5K+", l: "Объявлений", c: C.flatL },
    { n: "20",  l: "Городов",    c: C.green },
    { n: "3",   l: "Языка (RU/EN/HE)", c: C.jobsL },
    { n: "4",   l: "Источника дохода", c: C.ecoL },
    { n: "24/7", l: "Парсинг Telegram", c: C.carsL },
  ];
  stats.forEach((st, i) => {
    statBox(s, 0.45 + i * 1.83, 1.38, 1.65, 0.98, st.n, st.l, st.c, C.bg3);
  });

  // Two column features
  const features = [
    { icon: "🔍", title: "Умный поиск", text: "12 фильтров: тип, район, город, комнаты, цена, парковка, бассейн, лифт, инфраструктура, фото, частник/агент" },
    { icon: "🔔", title: "Алерты", text: "Push-уведомления при появлении нового объявления по фильтру пользователя. Работают в фоне." },
    { icon: "🚚", title: "Маркетплейс услуг", text: "Перевозчики, клининг, упаковка. Триггерные лиды после закрытия сделки: до 310₪ с одного переезда." },
    { icon: "🏢", title: "Кабинет агента", text: "CRM, публикация пакетами (1–безлимит), редактирование, статистика просмотров, закрытие сделок." },
    { icon: "💳", title: "Монетизация", text: "Telegram Stars · PayPlus карта · Криптовалюта. Подписки 19.9–39.9₪/нед–мес." },
    { icon: "📊", title: "Аналитика", text: "Дашборд: пользователи, объявления, доходы, лиды. API аналитики в реальном времени." },
  ];

  features.forEach((f, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.45 + col * 4.6;
    const y = 2.5 + row * 0.98;
    s.addText(f.icon + "  " + f.title, { x: x + 0.15, y: y + 0.06, w: 4.2, h: 0.32, fontSize: 12, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });
    s.addText(f.text, { x: x + 0.15, y: y + 0.4, w: 4.2, h: 0.52, fontSize: 9.5, color: C.gray, fontFace: "Calibri", margin: 0 });
    if (row < 2) {
      s.addShape(pres.shapes.RECTANGLE, { x: x, y: y + 0.88, w: 4.4, h: 0.02, fill: { color: C.border }, line: { color: C.border, width: 0 } });
    }
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 5 — BUSINESS MODEL
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  title(s, "Бизнес-модель FlatFinderIL");
  subtitle(s, "4 независимых потока дохода — B2C подписки + B2B маркетплейс лидов");
  dividerLine(s, 1.32);

  const streams = [
    {
      color: C.flat, icon: "🏢", name: "Агенты", price: "от 70₪",
      unit: "за объявление/мес",
      items: ["1 объявление — 70₪/мес", "5 объявлений — 300₪/мес", "10 объявлений — 550₪/мес", "Безлимит — 3 000₪/мес"],
    },
    {
      color: C.cars, icon: "🚚", name: "Перевозчики", price: "70₪",
      unit: "подписка/мес",
      items: ["База в платформе — 70₪/мес", "ТОП в городе — 100₪/нед", "Пакет: база + ТОП ≈ 470₪/мес", ""],
    },
    {
      color: C.jobs, icon: "🧹", name: "Клининг-лиды", price: "50₪",
      unit: "за лид",
      items: ["Горячий лид (после переезда)", "До 3 компаний на лид", "Макс. доход с лида — 150₪", "Баланс: 100/200/500₪"],
    },
    {
      color: C.eco, icon: "📦", name: "Упаковка-лиды", price: "30₪",
      unit: "за лид",
      items: ["Триггер: сразу после закрытия", "До 3 компаний на лид", "Макс. доход с лида — 90₪", "Задержка — 0 секунд ⚡"],
    },
  ];

  streams.forEach((st, i) => {
    const x = 0.45 + i * 2.32;
    card(s, x, 1.45, 2.1, 3.88, st.color);
    // Header
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.45, w: 2.1, h: 1.0, fill: { color: "EFF6FF" }, line: { color: st.color, width: 1 } });
    s.addText(st.icon + "  " + st.name, { x: x + 0.12, y: 1.55, w: 1.88, h: 0.32, fontSize: 11.5, bold: true, color: st.color, fontFace: "Calibri", margin: 0 });
    s.addText(st.price, { x: x + 0.12, y: 1.88, w: 1.2, h: 0.38, fontSize: 22, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });
    s.addText(st.unit, { x: x + 0.12, y: 2.32, w: 1.88, h: 0.22, fontSize: 9, color: C.gray, fontFace: "Calibri", margin: 0 });
    // Items
    st.items.forEach((it, j) => {
      if (!it) return;
      s.addText("• " + it, { x: x + 0.12, y: 2.65 + j * 0.5, w: 1.88, h: 0.42, fontSize: 9.5, color: C.gray, fontFace: "Calibri", margin: 0 });
    });
  });

  // Bottom formula
  s.addShape(pres.shapes.RECTANGLE, { x: 0.45, y: 5.06, w: 9.1, h: 0.42, fill: { color: "F0FDF4" }, line: { color: C.green, width: 1 } });
  s.addText("💰  Доход с одного переезда: Упаковка (90₪) + Клининг (150₪) + Агент (70₪)  =  до 310₪", {
    x: 0.45, y: 5.06, w: 9.1, h: 0.42, fontSize: 12, bold: true, color: C.green, fontFace: "Calibri", align: "center", valign: "middle", margin: 0,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 6 — MARKET ISRAEL
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  title(s, "Рынок Израиля");
  subtitle(s, "Один из самых активных рынков недвижимости и труда на Ближнем Востоке");
  dividerLine(s, 1.32);

  const kpis = [
    { n: "9.8M",  l: "Население Израиля",     c: C.flatL },
    { n: "500K",  l: "Переездов в год",        c: C.carsL },
    { n: "1.5M",  l: "Русскоязычных жителей",  c: C.jobsL },
    { n: "85%",   l: "Аренда vs. покупка",     c: C.ecoL },
    { n: "2.1T₪", l: "Объём рынка недвижимости", c: C.green },
  ];
  kpis.forEach((k, i) => {
    statBox(s, 0.45 + i * 1.84, 1.45, 1.65, 0.98, k.n, k.l, k.c, C.bg3);
  });

  // Left: segments
  card(s, 0.45, 2.6, 4.5, 2.8, C.flat);
  accentBar(s, 0.45, 2.6, 2.8, C.flat);
  s.addText("👥 Пользователи (B2C)", { x: 0.65, y: 2.72, w: 4.1, h: 0.35, fontSize: 13, bold: true, color: C.flatL, fontFace: "Calibri", margin: 0 });
  const b2c = [
    "🔸 Репатрианты и мигранты — не знают рынка",
    "🔸 Молодые семьи — переезжают раз в 1–3 года",
    "🔸 Покупатели инвест. недвижимости",
    "🔸 Наёмные работники — ищут жильё при переезде",
  ];
  b2c.forEach((t, i) => {
    s.addText(t, { x: 0.65, y: 3.15 + i * 0.5, w: 4.1, h: 0.42, fontSize: 10.5, color: C.gray, fontFace: "Calibri", margin: 0 });
  });

  // Right: B2B
  card(s, 5.15, 2.6, 4.4, 2.8, C.eco);
  accentBar(s, 5.15, 2.6, 2.8, C.eco);
  s.addText("🏢 Партнёры (B2B)", { x: 5.35, y: 2.72, w: 4.0, h: 0.35, fontSize: 13, bold: true, color: C.ecoL, fontFace: "Calibri", margin: 0 });
  const b2b = [
    "🔹 Агенты по недвижимости — размещение объявлений",
    "🔹 Перевозчики — подписка + ТОП-позиция",
    "🔹 Клининговые компании — горячие лиды",
    "🔹 Компании по упаковке — триггерные заявки",
  ];
  b2b.forEach((t, i) => {
    s.addText(t, { x: 5.35, y: 3.15 + i * 0.5, w: 4.0, h: 0.42, fontSize: 10.5, color: C.gray, fontFace: "Calibri", margin: 0 });
  });

  // Competitors
  s.addText("Конкуренты: Yad2.co.il (иврит, нет RU) · Madlan (нет Telegram) · Facebook Groups (нет фильтров) — ни один не закрывает русскоязычный сегмент", {
    x: 0.45, y: 5.1, w: 9.1, h: 0.36,
    fontSize: 10, color: C.darkgray, fontFace: "Calibri", align: "center", margin: 0, italic: true,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 7 — FINANCIAL PROJECTIONS (FlatFinderIL)
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  title(s, "Финансовый прогноз — FlatFinderIL");
  subtitle(s, "Консервативный сценарий · CAC = 0 (органический рост через Telegram)");
  dividerLine(s, 1.32);

  // Revenue chart
  const chartData = [{
    name: "Доход ₪/мес",
    labels: ["Мес 1", "Мес 3", "Мес 6", "Мес 9", "Мес 12"],
    values: [1500, 9450, 32100, 65000, 109200],
  }];
  s.addChart(pres.charts.BAR, chartData, {
    x: 0.45, y: 1.45, w: 5.5, h: 3.2,
    barDir: "col",
    chartColors: [C.flat],
    chartArea: { fill: { color: C.bg3 }, roundedCorners: false },
    catAxisLabelColor: C.gray,
    valAxisLabelColor: C.gray,
    valGridLine: { color: C.border, size: 0.5 },
    catGridLine: { style: "none" },
    showValue: true,
    dataLabelColor: C.white,
    dataLabelFontSize: 9,
    dataLabelFontBold: true,
    showLegend: false,
    valAxisNumFmt: '₪#,##0',
  });

  // Table on right
  const rows = [
    [{ text: "Метрика", options: { bold: true, color: C.white, fill: { color: "DBEAFE" } } },
     { text: "Мес 3", options: { bold: true, color: C.white, fill: { color: "DBEAFE" } } },
     { text: "Мес 6", options: { bold: true, color: C.white, fill: { color: "DBEAFE" } } },
     { text: "Мес 12", options: { bold: true, color: C.white, fill: { color: "DBEAFE" } } }],
    ["Активных польз.", "500", "2 000", "8 000"],
    ["Агентов", "10", "40", "120"],
    ["Перевозчиков", "5", "20", "60"],
    ["Клининг-лидов/мес", "30", "100", "350"],
    [{ text: "Доход/мес (₪)", options: { bold: true, color: C.white, fill: { color: C.bg3 } } },
     { text: "~9 450", options: { bold: true, color: C.green, fill: { color: C.bg3 } } },
     { text: "~32 100", options: { bold: true, color: C.green, fill: { color: C.bg3 } } },
     { text: "~109 200", options: { bold: true, color: C.green, fill: { color: C.bg3 } } }],
    [{ text: "Доход/мес ($)", options: { bold: true, color: C.white, fill: { color: C.bg3 } } },
     { text: "~$2 550", options: { bold: true, color: C.jobsL, fill: { color: C.bg3 } } },
     { text: "~$8 700", options: { bold: true, color: C.jobsL, fill: { color: C.bg3 } } },
     { text: "~$29 500", options: { bold: true, color: C.jobsL, fill: { color: C.bg3 } } }],
  ];
  s.addTable(rows, {
    x: 6.15, y: 1.45, w: 3.4, h: 3.2,
    fontSize: 10, fontFace: "Calibri",
    border: { pt: 1, color: C.border },
    fill: { color: C.bg3 },
    color: C.gray,
    colW: [1.5, 0.62, 0.62, 0.66],
  });

  // Break-even
  s.addShape(pres.shapes.RECTANGLE, { x: 0.45, y: 4.82, w: 9.1, h: 0.62, fill: { color: "F0FDF4" }, line: { color: C.green, width: 1 } });
  s.addText([
    { text: "Точка безубыточности: ", options: { color: C.gray, fontSize: 12 } },
    { text: "Месяц 2–3", options: { color: C.green, fontSize: 12, bold: true } },
    { text: "  ·  Break-even при 15 агентах + 30 лидах/мес  ·  ", options: { color: C.gray, fontSize: 12 } },
    { text: "Годовой ARR (мес 12): ~1.3M₪", options: { color: C.jobsL, fontSize: 12, bold: true } },
  ], { x: 0.45, y: 4.82, w: 9.1, h: 0.62, align: "center", valign: "middle", margin: 0, fontFace: "Calibri" });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 8 — CARSFINDER IL
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 1.18, fill: { color: "F0FDFA" }, line: { color: C.border, width: 0 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 1.18, w: 10, h: 0.04, fill: { color: C.cars }, line: { color: C.cars, width: 0 } });
  title(s, "🚗 CarsFinderIL — Запуск Q4 2026", { y: 0.28, color: C.cars });
  subtitle(s, "Платформа покупки и продажи авто для русскоязычного рынка Израиля", { y: 0.75 });

  // Market stat
  const carStats = [
    { n: "300K", l: "Авто продаётся/год", c: C.carsL },
    { n: "80K",  l: "Средняя цена авто ₪", c: C.green },
    { n: "1.5M", l: "Потенциальных пользователей", c: C.jobsL },
    { n: "0",    l: "Аналогов на русском", c: "DC2626" },
  ];
  carStats.forEach((k, i) => {
    statBox(s, 0.45 + i * 2.3, 1.38, 2.1, 0.98, k.n, k.l, k.c, C.bg3);
  });

  // Features
  const carFeatures = [
    { icon: "🔍", title: "Умный поиск авто", text: "Марка, модель, год, пробег, цена, коробка, привод, объём двигателя. Парсинг Yad2Cars + частные Telegram-каналы.", color: C.cars },
    { icon: "📝", title: "Добавить объявление", text: "Частники и автосалоны. Платная публикация 49₪/мес или лид-модель для салонов. Фото обязательны.", color: C.carsL },
    { icon: "🔔", title: "Алерты на авто", text: "Уведомление при появлении авто по фильтру. Для пользователей бесплатно — источник трафика.", color: C.green },
    { icon: "🏢", title: "Кабинет автосалона", text: "Пакеты от 10 объявлений. ТОП-размещение. CRM для заявок от покупателей. Email/Telegram уведомления.", color: C.jobsL },
    { icon: "🔧", title: "Сервис и запчасти", text: "Маркетплейс СТО и автозапчастей. Лиды для автосервисов (горячий момент — после покупки авто).", color: C.eco },
    { icon: "📊", title: "История цен", text: "AI-анализ рынка: справедливая цена, история продаж по модели, прогноз ликвидности.", color: C.ecoL },
  ];

  carFeatures.forEach((f, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.45 + col * 3.1;
    const y = 2.52 + row * 1.35;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.88, h: 1.2, fill: { color: C.bg3 }, line: { color: f.color, width: 1 } });
    accentBar(s, x, y, 1.2, f.color);
    s.addText(f.icon + "  " + f.title, { x: x + 0.18, y: y + 0.1, w: 2.55, h: 0.3, fontSize: 11.5, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });
    s.addText(f.text, { x: x + 0.18, y: y + 0.44, w: 2.55, h: 0.65, fontSize: 9.5, color: C.gray, fontFace: "Calibri", margin: 0 });
  });

  // Revenue model
  s.addShape(pres.shapes.RECTANGLE, { x: 0.45, y: 5.1, w: 9.1, h: 0.38, fill: { color: "F0FDFA" }, line: { color: C.cars, width: 1 } });
  s.addText("💰 Монетизация: объявления салонов (79₪/авто) + лиды для СТО (40₪) + ТОП-позиции (200₪/нед) · Прогноз мес 6: ~45 000₪/мес", {
    x: 0.45, y: 5.1, w: 9.1, h: 0.38, fontSize: 10.5, color: C.carsL, fontFace: "Calibri", align: "center", valign: "middle", margin: 0, bold: true,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 9 — JOBFINDER IL
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 1.18, fill: { color: "FFFBEB" }, line: { color: C.border, width: 0 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 1.18, w: 10, h: 0.04, fill: { color: C.jobs }, line: { color: C.jobs, width: 0 } });
  title(s, "💼 JobFinderIL — Запуск Q1 2027", { y: 0.28, color: C.jobs });
  subtitle(s, "Платформа поиска работы и подбора персонала для рынка Израиля", { y: 0.75 });

  const jobStats = [
    { n: "350K",  l: "Активных вакансий", c: C.jobsL },
    { n: "12%",   l: "Безработица среди новых репатриантов", c: "DC2626" },
    { n: "5–15K₪", l: "Зарплата по рекомендации", c: C.green },
    { n: "$4.2B",  l: "Hi-Tech экспорт Израиля", c: C.ecoL },
  ];
  jobStats.forEach((k, i) => {
    statBox(s, 0.45 + i * 2.3, 1.38, 2.1, 0.98, k.n, k.l, k.c, C.bg3);
  });

  // Two columns
  const leftFeats = [
    { icon: "🔍", title: "Поиск вакансий", text: "Фильтр по профессии, городу, зарплате, графику. Вакансии на иврите и русском. Алерты на новые вакансии." },
    { icon: "📄", title: "Резюме", text: "Создание резюме прямо в боте (шаблоны). Отклик одной кнопкой. История откликов и статус." },
    { icon: "🏢", title: "Кабинет работодателя", text: "Публикация вакансий (49₪/вакансия/мес). ATS: просмотр откликов, фильтрация, статусы кандидатов." },
  ];
  const rightFeats = [
    { icon: "🤝", title: "Агентства рекрутинга", text: "Подписка агентств (999₪/мес). Доступ к базе резюме. Экспорт в Excel. CRM для кандидатов." },
    { icon: "💡", title: "AI-подбор", text: "Автоматическая рекомендация вакансий на основе профиля. GPT-помощь с составлением резюме и cover letter." },
    { icon: "📚", title: "Курсы и обучение", text: "Партнёрская программа с образовательными платформами. Реферальные комиссии 5–15% от стоимости курса." },
  ];

  [leftFeats, rightFeats].forEach((feats, col) => {
    feats.forEach((f, i) => {
      const x = 0.45 + col * 4.8;
      const y = 2.5 + i * 1.04;
      s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.55, h: 0.92, fill: { color: C.bg3 }, line: { color: C.jobs, width: 1 } });
      accentBar(s, x, y, 0.92, C.jobs);
      s.addText(f.icon + "  " + f.title, { x: x + 0.18, y: y + 0.08, w: 4.2, h: 0.3, fontSize: 12, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });
      s.addText(f.text, { x: x + 0.18, y: y + 0.44, w: 4.2, h: 0.4, fontSize: 9.5, color: C.gray, fontFace: "Calibri", margin: 0 });
    });
  });

  s.addShape(pres.shapes.RECTANGLE, { x: 0.45, y: 5.1, w: 9.1, h: 0.38, fill: { color: "FFFBEB" }, line: { color: C.jobs, width: 1 } });
  s.addText("💰 Монетизация: вакансии (49₪/мес) + кабинет агентства (999₪/мес) + AI-подбор (199₪/мес) · Прогноз мес 6: ~60 000₪/мес", {
    x: 0.45, y: 5.1, w: 9.1, h: 0.38, fontSize: 10.5, color: C.jobsL, fontFace: "Calibri", align: "center", valign: "middle", margin: 0, bold: true,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 10 — WEB + DOMAIN STRATEGY
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  title(s, "Веб-платформа и доменная стратегия");
  subtitle(s, "Telegram-бот + сайты + Mini App — омниканальное присутствие");
  dividerLine(s, 1.32);

  const domains = [
    {
      color: C.flat, title: "FlatFinderIL.com", sub: "flatfinderil.co.il",
      desc: "Международная + локальная аудитория. SEO на английском и русском. Карточки объявлений, поиск с фильтрами, карта.",
      features: ["Полный каталог объявлений", "SEO под Google IL", "Регистрация агентов", "API для партнёров"],
    },
    {
      color: C.cars, title: "CarsFinderIL.com", sub: "carsfinderil.co.il",
      desc: "Авто-вертикаль на отдельном домене. Интеграция с Yad2Cars. Фото-галерея, история цен, проверка VIN.",
      features: ["Каталог авто", "Кабинет автосалона", "Сравнение авто", "Проверка истории"],
    },
    {
      color: C.jobs, title: "JobFinderIL.com", sub: "jobfinderil.co.il",
      desc: "HR-платформа. Вакансии и резюме на иврите и русском. Интеграция с LinkedIn. ATS для работодателей.",
      features: ["Поиск вакансий + резюме", "ATS для работодателей", "Профиль кандидата", "Экспорт в PDF"],
    },
  ];

  domains.forEach((d, i) => {
    const x = 0.45 + i * 3.1;
    card(s, x, 1.5, 2.88, 3.15, d.color);
    accentBar(s, x, 1.5, 3.15, d.color);
    s.addText(d.title, { x: x + 0.18, y: 1.58, w: 2.55, h: 0.33, fontSize: 13, bold: true, color: d.color, fontFace: "Calibri", margin: 0 });
    s.addText(d.sub, { x: x + 0.18, y: 1.93, w: 2.55, h: 0.24, fontSize: 10, color: C.gray, fontFace: "Calibri", margin: 0, italic: true });
    s.addText(d.desc, { x: x + 0.18, y: 2.22, w: 2.55, h: 0.85, fontSize: 9.5, color: C.gray, fontFace: "Calibri", margin: 0 });
    d.features.forEach((f, j) => {
      s.addText("✓  " + f, { x: x + 0.18, y: 3.12 + j * 0.36, w: 2.55, h: 0.33, fontSize: 9.5, color: C.white, fontFace: "Calibri", margin: 0 });
    });
  });

  // Mini App row
  s.addShape(pres.shapes.RECTANGLE, { x: 0.45, y: 4.8, w: 9.1, h: 0.7, fill: { color: C.bg3 }, line: { color: C.eco, width: 1 } });
  accentBar(s, 0.45, 4.8, 0.7, C.eco);
  s.addText("📱  Telegram Mini App  (WebApp)", { x: 0.65, y: 4.88, w: 2.5, h: 0.3, fontSize: 13, bold: true, color: C.ecoL, fontFace: "Calibri", margin: 0 });
  s.addText("Полнофункциональный интерфейс внутри Telegram — без перехода в браузер. Авторизация через Telegram, кнопка «Открыть» в боте. Работает на iOS и Android. Общая база данных с ботом.", {
    x: 3.3, y: 4.88, w: 6.1, h: 0.54, fontSize: 9.5, color: C.gray, fontFace: "Calibri", margin: 0,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 11 — TELEGRAM MINI APP
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  title(s, "Telegram Mini App — интерфейс внутри мессенджера");
  subtitle(s, "Кнопка в боте → WebApp открывается прямо в Telegram, авторизация автоматическая");
  dividerLine(s, 1.32);

  // Phone mockup (simplified)
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 3.4, y: 1.45, w: 3.2, h: 4.0, fill: { color: "E2E8F0" }, line: { color: C.eco, width: 2 }, rectRadius: 0.2 });
  s.addShape(pres.shapes.RECTANGLE, { x: 3.55, y: 1.72, w: 2.9, h: 3.42, fill: { color: "F8FAFC" }, line: { color: "F8FAFC", width: 0 } });
  // Phone header
  s.addShape(pres.shapes.RECTANGLE, { x: 3.55, y: 1.72, w: 2.9, h: 0.42, fill: { color: C.eco }, line: { color: C.eco, width: 0 } });
  s.addText("🏠 FlatFinderIL", { x: 3.55, y: 1.72, w: 2.9, h: 0.42, fontSize: 11, bold: true, color: "FFFFFF", fontFace: "Calibri", align: "center", valign: "middle", margin: 0 });  // stays white on purple header
  // Search bar mockup
  s.addShape(pres.shapes.RECTANGLE, { x: 3.65, y: 2.22, w: 2.7, h: 0.34, fill: { color: "FFFFFF" }, line: { color: C.border, width: 1 } });
  s.addText("🔍  Тель-Авив, 2–3 комн, до 8000₪", { x: 3.65, y: 2.22, w: 2.7, h: 0.34, fontSize: 8.5, color: C.gray, fontFace: "Calibri", align: "center", valign: "middle", margin: 0 });
  // Cards
  const mockCards = ["🏠 3 комн · ₪6500 · Тель-Авив", "🏠 2.5 комн · ₪5200 · Бат-Ям", "🚗 Honda Civic · 2019 · ₪62K"];
  mockCards.forEach((mc, i) => {
    s.addShape(pres.shapes.RECTANGLE, { x: 3.65, y: 2.68 + i * 0.78, w: 2.7, h: 0.68, fill: { color: C.bg3 }, line: { color: C.border, width: 1 } });
    s.addText(mc, { x: 3.75, y: 2.75 + i * 0.78, w: 2.5, h: 0.55, fontSize: 8.5, color: C.white, fontFace: "Calibri", margin: 0 });
  });

  // Left features
  const leftItems = [
    { icon: "🔐", title: "Авторизация через Telegram", text: "Пользователь не создаёт аккаунт — всё через Telegram ID. Безопасно и мгновенно." },
    { icon: "📱", title: "Нативный UX", text: "Открывается кнопкой внутри чата. Работает на iOS и Android без установки приложения." },
    { icon: "🔄", title: "Синхронизация с ботом", text: "Избранное, алерты и история — синхронизируются между ботом и Mini App в реальном времени." },
  ];
  leftItems.forEach((item, i) => {
    card(s, 0.45, 1.45 + i * 1.36, 2.7, 1.22, C.eco);
    accentBar(s, 0.45, 1.45 + i * 1.36, 1.22, C.eco);
    s.addText(item.icon + "  " + item.title, { x: 0.65, y: 1.56 + i * 1.36, w: 2.38, h: 0.3, fontSize: 11, bold: true, color: C.ecoL, fontFace: "Calibri", margin: 0 });
    s.addText(item.text, { x: 0.65, y: 1.9 + i * 1.36, w: 2.38, h: 0.62, fontSize: 9.5, color: C.gray, fontFace: "Calibri", margin: 0 });
  });

  // Right features
  const rightItems = [
    { icon: "🗺", title: "Карта объявлений", text: "Интерактивная карта с кластеризацией. Вид улицы и инфраструктура рядом." },
    { icon: "📊", title: "Аналитика для агентов", text: "Статистика показов, просмотры, конверсии в реальном времени прямо в Mini App." },
    { icon: "💳", title: "Оплата внутри Telegram", text: "Telegram Stars или карта через Telegram Payments. Без редиректов." },
  ];
  rightItems.forEach((item, i) => {
    card(s, 6.85, 1.45 + i * 1.36, 2.7, 1.22, C.eco);
    accentBar(s, 6.85, 1.45 + i * 1.36, 1.22, C.eco);
    s.addText(item.icon + "  " + item.title, { x: 7.05, y: 1.56 + i * 1.36, w: 2.38, h: 0.3, fontSize: 11, bold: true, color: C.ecoL, fontFace: "Calibri", margin: 0 });
    s.addText(item.text, { x: 7.05, y: 1.9 + i * 1.36, w: 2.38, h: 0.62, fontSize: 9.5, color: C.gray, fontFace: "Calibri", margin: 0 });
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 12 — FULL ECOSYSTEM REVENUE
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  title(s, "Прогноз доходов — полная экосистема FinderIL");
  subtitle(s, "Три вертикали к Q2 2028 · Консервативный сценарий");
  dividerLine(s, 1.32);

  // Chart
  const chartDataEco = [
    { name: "FlatFinderIL", labels: ["Q3 2026", "Q4 2026", "Q1 2027", "Q2 2027", "Q3 2027", "Q4 2027", "Q1 2028", "Q2 2028"], values: [60000, 90000, 109200, 130000, 155000, 185000, 220000, 260000] },
    { name: "CarsFinderIL", labels: ["Q3 2026", "Q4 2026", "Q1 2027", "Q2 2027", "Q3 2027", "Q4 2027", "Q1 2028", "Q2 2028"], values: [0, 15000, 35000, 60000, 85000, 110000, 140000, 175000] },
    { name: "JobFinderIL",  labels: ["Q3 2026", "Q4 2026", "Q1 2027", "Q2 2027", "Q3 2027", "Q4 2027", "Q1 2028", "Q2 2028"], values: [0, 0, 10000, 30000, 55000, 80000, 110000, 145000] },
  ];
  s.addChart(pres.charts.BAR, chartDataEco, {
    x: 0.45, y: 1.45, w: 9.1, h: 2.7,
    barDir: "col",
    barGrouping: "stacked",
    chartColors: [C.flat, C.cars, C.jobs],
    chartArea: { fill: { color: C.bg3 }, roundedCorners: false },
    catAxisLabelColor: C.gray,
    valAxisLabelColor: C.gray,
    valGridLine: { color: C.border, size: 0.5 },
    catGridLine: { style: "none" },
    showLegend: true,
    legendPos: "t",
    legendFontSize: 10,
    legendFontColor: C.gray,
    valAxisNumFmt: '₪#,##0',
  });

  // Summary stats
  const totals = [
    { q: "Q4 2026", flat: "90K", cars: "15K", jobs: "—",   total: "105K ₪/мес",  c: C.flat },
    { q: "Q2 2027", flat: "130K", cars: "60K", jobs: "30K", total: "220K ₪/мес", c: C.cars },
    { q: "Q2 2028", flat: "260K", cars: "175K", jobs: "145K", total: "580K ₪/мес", c: C.jobs },
  ];
  totals.forEach((t, i) => {
    const x = 0.45 + i * 3.1;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 4.3, w: 2.88, h: 0.82, fill: { color: C.bg3 }, line: { color: t.c, width: 1 } });
    s.addText(t.q, { x: x + 0.1, y: 4.34, w: 2.65, h: 0.26, fontSize: 11, bold: true, color: t.c, fontFace: "Calibri", margin: 0 });
    s.addText(`Flat: ${t.flat} · Cars: ${t.cars} · Jobs: ${t.jobs}`, { x: x + 0.1, y: 4.6, w: 2.65, h: 0.2, fontSize: 9, color: C.gray, fontFace: "Calibri", margin: 0 });
    s.addText("= " + t.total, { x: x + 0.1, y: 4.8, w: 2.65, h: 0.28, fontSize: 13, bold: true, color: C.green, fontFace: "Calibri", margin: 0 });
  });

  s.addText("ARR Q2 2028: ~6.9M₪/год  (~$1.9M)", {
    x: 0.45, y: 5.22, w: 9.1, h: 0.26,
    fontSize: 11, color: C.darkgray, fontFace: "Calibri", align: "right", margin: 0, italic: true,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 13 — ROADMAP
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  title(s, "Роадмап 2026–2028");
  subtitle(s, "Последовательное масштабирование: Flat → Cars → Jobs → Ecosystem");
  dividerLine(s, 1.32);

  // Timeline bar
  const quarters = ["Q2 2026\n(сейчас)", "Q3 2026", "Q4 2026", "Q1 2027", "Q2 2027", "Q3–Q4 2027", "Q1–Q2 2028"];
  const qColors = [C.flat, C.flat, C.cars, C.jobs, C.eco, C.eco, C.green];
  const qW = 1.25;
  quarters.forEach((q, i) => {
    s.addShape(pres.shapes.RECTANGLE, { x: 0.45 + i * qW, y: 1.45, w: qW - 0.04, h: 0.5, fill: { color: qColors[i] }, line: { color: qColors[i], width: 0 } });
    s.addText(q, { x: 0.45 + i * qW, y: 1.45, w: qW - 0.04, h: 0.5, fontSize: 8.5, color: "FFFFFF", fontFace: "Calibri", align: "center", valign: "middle", margin: 0, bold: true });
  });

  // Milestones
  const milestones = [
    {
      quarter: "Q2 2026 (сейчас)", color: C.flat,
      items: [
        "✅ 5 000+ объявлений, 20 городов",
        "✅ Поиск, алерты, кабинет агента",
        "✅ Маркетплейс лидов (клининг/упаковка)",
        "✅ Фильтр частник/агент",
        "✅ PostgreSQL + Railway deploy",
        "🔄 Facebook page контент",
      ],
    },
    {
      quarter: "Q3 2026 — FlatFinderIL", color: C.flat,
      items: [
        "🔜 Yad2 парсер — рынок продажи",
        "🔜 Telegram Mini App v1",
        "🔜 flatfinderil.co.il + flatfinderil.com",
        "🔜 Платные объявления агентов",
        "🔜 WhatsApp уведомления",
        "🔜 Маркетинг: Telegram-каналы",
      ],
    },
    {
      quarter: "Q4 2026 — CarsFinderIL", color: C.cars,
      items: [
        "🆕 carsfinderil.co.il + .com",
        "🆕 Поиск авто: марка/модель/год/цена",
        "🆕 Парсинг Yad2Cars",
        "🆕 Кабинет автосалона",
        "🆕 История цен (AI)",
        "🆕 Mini App: авто-вкладка",
      ],
    },
    {
      quarter: "Q1 2027 — JobFinderIL", color: C.jobs,
      items: [
        "🆕 jobfinderil.co.il + .com",
        "🆕 Вакансии + резюме",
        "🆕 ATS для работодателей",
        "🆕 AI-подбор (GPT)",
        "🆕 Партнёрство с курсами",
        "🆕 Агентства рекрутинга",
      ],
    },
  ];

  milestones.forEach((m, i) => {
    const x = 0.45 + i * 2.38;
    card(s, x, 2.1, 2.22, 3.3, m.color);
    accentBar(s, x, 2.1, 3.3, m.color);
    s.addText(m.quarter, { x: x + 0.18, y: 2.18, w: 1.9, h: 0.35, fontSize: 9.5, bold: true, color: m.color, fontFace: "Calibri", margin: 0 });
    m.items.forEach((item, j) => {
      s.addText(item, { x: x + 0.18, y: 2.57 + j * 0.43, w: 1.9, h: 0.38, fontSize: 8.5, color: C.gray, fontFace: "Calibri", margin: 0 });
    });
  });

  // 2027-2028 bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0.45, y: 5.2, w: 9.1, h: 0.32, fill: { color: "F0FDF4" }, line: { color: C.green, width: 1 } });
  s.addText("Q2 2027: единый бренд FinderIL.com · Экосистема из 3 продуктов · Раунд инвестиций · Расширение на другие регионы (Кипр, Германия)", {
    x: 0.45, y: 5.2, w: 9.1, h: 0.32, fontSize: 9.5, color: C.green, fontFace: "Calibri", align: "center", valign: "middle", margin: 0, bold: true,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 14 — COMPETITIVE ADVANTAGES
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  title(s, "Конкурентные преимущества");
  subtitle(s, "Почему FinderIL выигрывает в русскоязычном сегменте Израиля");
  dividerLine(s, 1.32);

  const advantages = [
    { icon: "🌍", title: "Язык — барьер для конкурентов", text: "Yad2, Madlan, LinkedIn работают на иврите. 1.5M русскоязычных пользователей не охвачены. Мы единственные с полным RU/EN/HE интерфейсом.", color: C.flat },
    { icon: "⚡", title: "Telegram-нативность", text: "Не нужен сайт или приложение. Бот работает там, где уже есть аудитория. Telegram — главный канал информации для русскоязычных в Израиле.", color: C.cars },
    { icon: "💰", title: "Триггерные лиды", text: "Мы знаем точный момент переезда. Конверсия горячего лида в 5–10× выше холодного. Клининговые компании платят 150₪ за лид, который невозможно получить в другом месте.", color: C.jobs },
    { icon: "🔗", title: "Экосистемный эффект", text: "FlatFinder → CarseFinder → JobFinder. Один пользователь монетизируется трижды. Клиент ищет жильё → покупает авто → находит работу. CAC делится на 3 продукта.", color: C.eco },
    { icon: "📱", title: "Омниканальность", text: "Telegram Bot + Mini App + Web .com + Web .co.il. Каждый канал привлекает свою аудиторию. SEO в Google + органика в Telegram = нулевой CAC.", color: C.green },
    { icon: "📊", title: "Данные и аналитика", text: "Каждый поиск, просмотр и сделка сохраняются. AI-аналитика рынка недвижимости и авто. Агенты платят за инсайты, которых нет нигде.", color: C.flatL },
  ];

  advantages.forEach((a, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.45 + col * 3.12;
    const y = 1.48 + row * 1.88;
    card(s, x, y, 2.9, 1.72, a.color);
    accentBar(s, x, y, 1.72, a.color);
    s.addText(a.icon + "  " + a.title, { x: x + 0.18, y: y + 0.1, w: 2.58, h: 0.35, fontSize: 12, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });
    s.addText(a.text, { x: x + 0.18, y: y + 0.5, w: 2.58, h: 1.1, fontSize: 9.5, color: C.gray, fontFace: "Calibri", margin: 0 });
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 15 — INVESTMENT / TEAM / CTA
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };

  // Left side — dark panel
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 4.8, h: 5.625, fill: { color: "EFF6FF" }, line: { color: "EFF6FF", width: 0 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 4.8, y: 0, w: 0.04, h: 5.625, fill: { color: C.flat }, line: { color: C.flat, width: 0 } });

  s.addText("FinderIL", { x: 0.4, y: 0.5, w: 4.1, h: 0.8, fontSize: 44, bold: true, color: C.white, fontFace: "Calibri", align: "left", margin: 0 });
  s.addText("Инвестиционное предложение", { x: 0.4, y: 1.32, w: 4.1, h: 0.4, fontSize: 14, color: C.gray, fontFace: "Calibri", align: "left", margin: 0 });
  dividerLine(s, 1.88);

  const ask = [
    { label: "Раунд",    val: "Pre-Seed", color: C.flatL },
    { label: "Сумма",    val: "$150K",    color: C.green },
    { label: "Equity",   val: "15–20%",   color: C.jobsL },
    { label: "Use of funds", val: "Команда + Маркетинг", color: C.ecoL },
  ];
  ask.forEach((a, i) => {
    s.addText(a.label + ":", { x: 0.4, y: 2.05 + i * 0.58, w: 1.7, h: 0.45, fontSize: 11, color: C.gray, fontFace: "Calibri", margin: 0 });
    s.addText(a.val, { x: 2.1, y: 2.05 + i * 0.58, w: 2.3, h: 0.45, fontSize: 13, bold: true, color: a.color, fontFace: "Calibri", margin: 0 });
  });

  dividerLine(s, 4.4);
  s.addText("t.me/FlatFinderIL_bot", { x: 0.4, y: 4.5, w: 4.1, h: 0.32, fontSize: 11, color: C.flatL, fontFace: "Calibri", margin: 0 });
  s.addText("flatfinderil.co.il", { x: 0.4, y: 4.85, w: 4.1, h: 0.32, fontSize: 11, color: C.gray, fontFace: "Calibri", margin: 0, italic: true });
  s.addText("Израиль · Разработка на русском и иврите · 2026", { x: 0.4, y: 5.2, w: 4.1, h: 0.3, fontSize: 9, color: C.darkgray, fontFace: "Calibri", margin: 0 });

  // Right side — use of funds
  const funds = [
    { pct: "40%", label: "Команда", sub: "Backend, Frontend, Mobile разработчики", color: C.flat },
    { pct: "30%", label: "Маркетинг", sub: "Telegram-каналы, Google Ads, SEO, SMM", color: C.cars },
    { pct: "20%", label: "Продукт", sub: "Mini App, AI-функции, CRM, интеграции", color: C.jobs },
    { pct: "10%", label: "Операционные", sub: "Хостинг, домены, юридические услуги", color: C.eco },
  ];
  funds.forEach((f, i) => {
    card(s, 5.1, 0.45 + i * 1.18, 4.5, 1.04, f.color);
    accentBar(s, 5.1, 0.45 + i * 1.18, 1.04, f.color);
    s.addText(f.pct, { x: 5.28, y: 0.55 + i * 1.18, w: 0.9, h: 0.58, fontSize: 28, bold: true, color: f.color, fontFace: "Calibri", margin: 0 });
    s.addText(f.label, { x: 6.28, y: 0.58 + i * 1.18, w: 3.1, h: 0.3, fontSize: 13, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });
    s.addText(f.sub, { x: 6.28, y: 0.9 + i * 1.18, w: 3.1, h: 0.36, fontSize: 10, color: C.gray, fontFace: "Calibri", margin: 0 });
  });

  // Bottom CTA (card 4 ends at 0.45+3*1.18+1.04 = 5.03 → CTA starts at 5.12 with safe gap)
  s.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 5.12, w: 4.5, h: 0.38, fill: { color: C.flat }, line: { color: C.flat, width: 0 } });
  s.addText("🚀  Попробуйте бот прямо сейчас: t.me/FlatFinderIL_bot", {
    x: 5.1, y: 5.12, w: 4.5, h: 0.38, fontSize: 11, bold: true, color: "FFFFFF", fontFace: "Calibri", align: "center", valign: "middle", margin: 0,
  });
}

// ─── WRITE ────────────────────────────────────────────────────────────────────
pres.writeFile({ fileName: "FinderIL_BusinessPlan_2026.pptx" })
  .then(() => console.log("✅ FinderIL_BusinessPlan_2026.pptx created!"))
  .catch(e => { console.error("❌", e); process.exit(1); });
