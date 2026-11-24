import os
import ast
import uuid
import json
import time
import random
<<<<<<< HEAD
import re
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, date

import flet as ft
<<<<<<< HEAD
from openai import OpenAI
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f

# ============================================================
# НАСТРОЙКА ДЛЯ RENDER (headless-среда)
# ============================================================
os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")

# ============================================================
<<<<<<< HEAD
# ЦВЕТОВАЯ ПАЛИТРА
=======
# ЦВЕТОВАЯ ПАЛИТРА (акцент — телеграмовский синий)
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
# ============================================================
ACCENT = ft.Colors.BLUE_400
ACCENT_MED = ft.Colors.BLUE_600
ACCENT_DEEP = ft.Colors.BLUE_700
ONLINE_CLR = ft.Colors.GREEN_400
<<<<<<< HEAD
SUPPORT_CLR = ft.Colors.CYAN_400

# ============================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ
# ============================================================
PARTICIPANTS: dict[str, dict] = {}
PENDING_CODES: dict[str, dict] = {}
=======

# ============================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ (один процесс — один хаб pubsub)
# ============================================================
PARTICIPANTS: dict[str, dict] = {}          # phone -> {"name", "session_id"}
PENDING_CODES: dict[str, dict] = {}         # phone -> {"code", "expires"}
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
CODE_TTL = 300

LOBBY_HISTORY: list[dict] = []
DM_HISTORY: dict[str, list[dict]] = {}
<<<<<<< HEAD
SUPPORT_HISTORY: dict[str, list[dict]] = {}
SUPPORT_CONTEXT: dict[str, list[dict]] = {}   # phone -> messages для API
MAX_HISTORY = 200
MAX_SUPPORT_HISTORY = 300
MAX_CONTEXT_MESSAGES = 20                      # сколько последних сообщений отправлять в API
=======
MAX_HISTORY = 200
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f

PALETTE = [
    ft.Colors.BLUE_400, ft.Colors.ORANGE_400, ft.Colors.PURPLE_400,
    ft.Colors.TEAL_400, ft.Colors.PINK_400, ft.Colors.AMBER_400,
    ft.Colors.CYAN_400, ft.Colors.LIME_400, ft.Colors.INDIGO_400,
    ft.Colors.DEEP_ORANGE_400,
]

BOT_NAME = "Бот"
<<<<<<< HEAD
SUPPORT_NAME = "🛟 Ассистент"
LOBBY_KEY = "lobby"
SUPPORT_KEY = "support"

# ============================================================
# НАСТРОЙКИ ИИ-АГЕНТА (DeepSeek / OpenAI)
# ============================================================
# DeepSeek API совместим с OpenAI SDK.
# Если используете OpenAI — замените base_url на "https://api.openai.com/v1"
# и model на "gpt-4o-mini" (или другую доступную модель).
AI_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
AI_BASE_URL = "https://api.deepseek.com"
AI_MODEL = "deepseek-flash"

AI_CLIENT: OpenAI | None = None
if AI_API_KEY:
    AI_CLIENT = OpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL)
else:
    print("⚠️ DEEPSEEK_API_KEY не задан — ИИ-поддержка будет недоступна.")

# Системный промпт: роль + база знаний + правила
SUPPORT_SYSTEM_PROMPT = """Ты — ИИ-ассистент технической поддержки чат-приложения. Отвечай кратко, дружелюбно, по делу. Если вопрос не по теме приложения — вежливо верни к теме.

О приложении:
- Вход по номеру телефона + 6-значный код (демо: код показывается на экране).
- Команды бота: /help (список), /users (кто онлайн), /whoami (мой профиль), /stats, /time, /roll, /dice, /flip, /8ball, /choose, /joke, /quote, /calc <выражение>, /weather <город>, /remind <сек> <текст>, /nick <имя>, /me <действие>, /clear.
- Личные сообщения: сайдбар → Контакты → нажать на имя.
- Реакции: меню сообщения (⋯) → Нравится / Сердце.
- Выход: иконка 🚪 в шапке.
- Мобильная версия: кнопка «←» возвращает к списку чатов.
- Данные хранятся в памяти и пропадают при перезапуске сервера.

Правила:
1. Если не знаешь ответа — предложи написать /human для связи с оператором.
2. Не выдумывай функций, которых нет.
3. Если пользователь злится или проблема серьёзная — сразу предложи /human.
4. Отвечай на русском.
"""
=======
LOBBY_KEY = "lobby"
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f

BOT_COMMANDS = {
    "/help": "Список всех команд",
    "/users": "Кто сейчас в чате",
    "/whoami": "Ваше имя и телефон",
    "/stats": "Статистика активного чата",
    "/time": "Текущее время сервера",
    "/ping": "Проверка связи",
    "/roll": "Случайное число 1–100",
    "/dice": "Бросок кубика 1–6",
    "/flip": "Орёл или решка",
    "/8ball <вопрос>": "Магический шар ответит",
    "/choose a b c": "Случайный вариант из списка",
    "/joke": "Случайная шутка",
    "/quote": "Случайная цитата",
    "/calc <выражение>": "Калькулятор: /calc 2*(3+4)",
    "/weather <город>": "Погода через wttr.in",
    "/remind <сек> <текст>": "Напоминание через N секунд",
    "/nick <имя>": "Сменить отображаемое имя",
    "/me <действие>": "Действие от третьего лица",
    "/clear": "Очистить ленту у себя",
<<<<<<< HEAD
    "/support": "Открыть чат техподдержки",
    "/human": "Позвать живого оператора",
    "/reset_support": "Сбросить диалог с поддержкой",
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
}

MAX_MSG_LEN = 500

JOKES = [
<<<<<<< HEAD
    "Программист идёт в магазин: «Купи батон, если будут яйца — возьми десяток». Возвращается с 10 батонами.",
    "Сколько программистов нужно, чтобы вкрутить лампочку? Ни одного — это аппаратная проблема.",
    "Есть 10 типов людей: те, кто понимает двоичную систему, и те, кто нет.",
    "Почему программисты путают Хэллоуин и Рождество? Потому что 31 OCT = 25 DEC.",
    "Отлаживать код — это как быть детективом, где ты и убийца.",
=======
    "Программист идёт в магазин: «Купи батон, если будут яйца — возьми десяток». "
    "Возвращается с 10 батонами.",
    "Сколько программистов нужно, чтобы вкрутить лампочку? Ни одного — "
    "это аппаратная проблема.",
    "Есть 10 типов людей: те, кто понимает двоичную систему, и те, кто нет.",
    "Почему программисты путают Хэллоуин и Рождество? Потому что 31 OCT = 25 DEC.",
    "Отлаживать код — это как быть детективом, где ты и убийца.",
    "Сын программиста: «Пап, а почему солнце всходит?» — «Всё работает, не трогай».",
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
]

QUOTES = [
    "«Простота — залог надёжности.» — Эдсгер Дейкстра",
    "«Сначала заставь работать, затем сделай правильным, затем быстрым.» — Кент Бек",
    "«Лучшее — враг хорошего.» — Вольтер",
<<<<<<< HEAD
=======
    "«Код — это поэзия.» — Неизвестный",
    "«Любой дурак напишет код для компьютера. Хороший программист пишет для людей.» "
    "— Мартин Фаулер",
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
]

EIGHT_BALL = [
    "Определённо да", "Мои источники говорят: да", "Без сомнений", "Да, точно",
    "Скорее всего", "Спроси позже", "Лучше не рассказывать", "Сейчас неясно",
    "Сконцентрируйся и спроси снова", "Не рассчитывай на это", "Мой ответ — нет",
<<<<<<< HEAD
]

REACTION_ICONS = [
=======
    "По моим данным — нет", "Очень сомнительно",
]

REACTION_ICONS = [  # key, icon, активный цвет
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    ("like", ft.Icons.THUMB_UP, ACCENT),
    ("heart", ft.Icons.FAVORITE, ft.Colors.RED_400),
]

<<<<<<< HEAD
SUPPORT_GREETING = (
    "Здравствуйте! Я ИИ-ассистент техподдержки 🤖\n"
    "Помогу с входом, командами бота, личными чатами и настройками.\n\n"
    "Опишите вопрос своими словами. Для связи с человеком — `/human`."
)

SUPPORT_FALLBACK = (
    "Не могу разобраться с этим вопросом 😔\n"
    "Попробуйте переформулировать или напишите `/human` — передам оператору."
)

SUPPORT_ESCALATED = (
    "✅ Заявка передана оператору.\n"
    "Опишите проблему подробнее — оператор увидит историю. Среднее время ответа: до 15 минут (демо)."
)

SUPPORT_THANKS = "Рад был помочь! Если что-то ещё — пишите."


# ============================================================
# УТИЛИТЫ (без изменений)
=======

# ============================================================
# УТИЛИТЫ
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
# ============================================================
def normalize_phone(raw: str) -> str | None:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if not digits:
        return None
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if not (10 <= len(digits) <= 15):
        return None
    return "+" + digits


def format_phone(p: str) -> str:
    d = p.lstrip("+")
    if len(d) == 11 and d.startswith("7"):
        return f"+7 {d[1:4]} {d[4:7]}-{d[7:9]}-{d[9:11]}"
    return "+" + d


def dm_topic(a: str, b: str) -> str:
    return "dm:" + "_".join(sorted([a, b]))


def get_user_color(key: str) -> str:
    return PALETTE[sum(ord(c) for c in key) % len(PALETTE)]


def get_initials(name: str) -> str:
    parts = (name or "").strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper() if name else "?"


def format_date_label(d: date) -> str:
    today = date.today()
    if d == today:
        return "Сегодня"
    if (today - d).days == 1:
        return "Вчера"
    return d.strftime("%d.%m.%Y")


def now_time() -> str:
    return datetime.now().strftime("%H:%M")


def today_iso() -> str:
    return date.today().isoformat()


def new_msg_id() -> str:
    return uuid.uuid4().hex[:12]


def safe_calc(expr: str):
    allowed = {
        ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b,
        ast.UAdd: lambda a: +a, ast.USub: lambda a: -a,
    }
    node = ast.parse(expr, mode="eval")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in allowed:
            return allowed[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in allowed:
            return allowed[type(n.op)](ev(n.operand))
        raise ValueError("недопустимое выражение")

    return ev(node)


def fetch_weather(city: str) -> str:
    url = "https://wttr.in/" + urllib.parse.quote(city) + "?format=j1&lang=ru"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=6) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    cur = data["current_condition"][0]
    desc = cur.get("lang_ru", [{"value": cur["weatherDesc"][0]["value"]}])[0]["value"]
    return (f"Погода, {city}: {desc}, {cur['temp_C']}°C "
<<<<<<< HEAD
            f"(ощущается {cur['FeelsLikeC']}°C), влажность {cur['humidity']}%, "
            f"ветер {cur['windspeedKmph']} км/ч")


# ============================================================
# ИИ-АГЕНТ ТЕХПОДДЕРЖКИ (API-based)
# ============================================================
def ai_support_answer(phone: str, user_text: str) -> tuple[str, bool]:
    """
    Возвращает (ответ_модели, нужно_ли_эскалировать).
    Если API недоступен — возвращает fallback и False.
    """
    if not AI_CLIENT:
        return ("ИИ-поддержка временно недоступна (не настроен API-ключ).\n"
                "Напишите `/human` — оператор свяжется с вами.", True)

    ctx = SUPPORT_CONTEXT.setdefault(phone, [])
    # добавляем сообщение пользователя
    ctx.append({"role": "user", "content": user_text})
    # обрезаем историю
    if len(ctx) > MAX_CONTEXT_MESSAGES:
        ctx[:] = ctx[-MAX_CONTEXT_MESSAGES:]

    messages = [{"role": "system", "content": SUPPORT_SYSTEM_PROMPT}] + ctx

    try:
        resp = AI_CLIENT.chat.completions.create(
            model=AI_MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=600,
        )
        answer = (resp.choices[0].message.content or "").strip()
        # сохраняем ответ в контекст
        ctx.append({"role": "assistant", "content": answer})
        if len(ctx) > MAX_CONTEXT_MESSAGES:
            ctx[:] = ctx[-MAX_CONTEXT_MESSAGES:]

        # определяем эскалацию по ключевым словам в ответе
        escalate = any(w in answer.lower() for w in
                       ["оператор", "человек", "не могу помочь", "не знаю",
                        "/human", "передам"])
        return answer, escalate
    except Exception as e:
        print(f"[AI ERROR] {e}")
        return (SUPPORT_FALLBACK, False)
=======
            f"(ощущается {cur['FeelsLikeC']}°C), "
            f"влажность {cur['humidity']}%, ветер {cur['windspeedKmph']} км/ч")
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f


# ============================================================
# МОДЕЛЬ СООБЩЕНИЯ
# ============================================================
@dataclass
class Message:
    user: str
    text: str
    timestamp: str
    sender_phone: str = ""
<<<<<<< HEAD
    kind: str = "message"
=======
    kind: str = "message"            # message | system | me
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    date: str = ""
    id: str = ""
    reactions: dict = field(default_factory=dict)
    reply_to_id: str = ""
    reply_to_user: str = ""
    reply_to_text: str = ""
<<<<<<< HEAD
    quick: list = field(default_factory=list)
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


# ============================================================
# ОСНОВНОЕ ПРИЛОЖЕНИЕ
# ============================================================
def main(page: ft.Page) -> None:
    page.title = "Чат"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.GREY_900

<<<<<<< HEAD
=======
    # --- состояние пользователя ---
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    my_phone: list[str | None] = [None]
    my_name: list[str | None] = [None]
    my_session_id = page.session.id
    my_dm_topics: set[str] = set()

<<<<<<< HEAD
=======
    # --- состояние UI ---
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    active_chat: list[str] = [LOBBY_KEY]
    unread: dict[str, int] = {}
    mobile_show_sidebar: list[bool] = [True]
    last_rendered_date: list[str] = [""]
    last_author: list[str] = [""]
    last_typing_sent = [0.0]
<<<<<<< HEAD
    rendered_msg_rows: dict[str, ft.Row] = {}
    reply_state: dict[str, str] = {"id": "", "user": "", "text": ""}

    # ============================================================
    # ШАПКА
=======
    rendered_msg_rows: dict[str, ft.Row] = {}   # msg_id -> строка реакций
    reply_state: dict[str, str] = {"id": "", "user": "", "text": ""}

    # ============================================================
    # ШАПКА ЧАТА
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    # ============================================================
    back_btn = ft.IconButton(
        ft.Icons.ARROW_BACK_IOS_NEW, icon_color=ft.Colors.WHITE,
        icon_size=18, tooltip="К списку чатов", visible=False,
    )

    header_icon = ft.Container(
        content=ft.Icon(ft.Icons.PUBLIC, color=ft.Colors.WHITE, size=20),
        width=38, height=38, border_radius=12,
        bgcolor=ACCENT_MED, alignment=ft.Alignment.CENTER,
    )

    header_title = ft.Text("Общий чат", size=16,
                           weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    header_subtitle = ft.Text("Все участники", size=11,
                              color=ft.Colors.GREY_400)

    online_badge = ft.Container(
        content=ft.Row([
<<<<<<< HEAD
            ft.Container(width=8, height=8, border_radius=4, bgcolor=ONLINE_CLR),
=======
            ft.Container(width=8, height=8, border_radius=4,
                         bgcolor=ONLINE_CLR),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
            ft.Text("0 онлайн", size=11, color=ft.Colors.GREY_300),
        ], spacing=6, tight=True),
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.15, ONLINE_CLR),
    )

<<<<<<< HEAD
=======
    # ---------- Меню команд ----------
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    def make_cmd_item(label: str, icon, cmd: str, needs_arg: bool):
        return ft.PopupMenuItem(
            content=ft.Text(label, size=13, color=ft.Colors.WHITE),
            icon=icon,
            on_click=lambda e: on_command_menu(cmd, needs_arg),
        )

    def cmd_header(text: str):
        return ft.PopupMenuItem(
            content=ft.Text(text, size=11, italic=True,
                            weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_500),
            height=24,
        )

    commands_menu = ft.PopupMenuButton(
        icon=ft.Icons.MORE_VERT,
        icon_color=ft.Colors.WHITE,
        icon_size=22,
        tooltip="Команды бота",
        items=[
<<<<<<< HEAD
            cmd_header("Поддержка"),
            make_cmd_item("Открыть поддержку — /support", ft.Icons.SUPPORT_AGENT, "/support", False),
            make_cmd_item("Позвать оператора — /human", ft.Icons.HEAD_SUPPORT_AGENT, "/human", False),
            make_cmd_item("Сбросить диалог — /reset_support", ft.Icons.RESTART_ALT, "/reset_support", False),
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
            cmd_header("Информация"),
            make_cmd_item("Помощь — /help", ft.Icons.HELP_OUTLINE, "/help", False),
            make_cmd_item("Кто онлайн — /users", ft.Icons.GROUP, "/users", False),
            make_cmd_item("Кто я — /whoami", ft.Icons.PERSON, "/whoami", False),
            make_cmd_item("Статистика — /stats", ft.Icons.BAR_CHART, "/stats", False),
            make_cmd_item("Время — /time", ft.Icons.ACCESS_TIME, "/time", False),
            make_cmd_item("Связь — /ping", ft.Icons.WIFI, "/ping", False),
            cmd_header("Развлечения"),
            make_cmd_item("Число 1–100 — /roll", ft.Icons.CASINO, "/roll", False),
<<<<<<< HEAD
            make_cmd_item("Кубик — /dice", ft.Icons.CASINO, "/dice", False),
            make_cmd_item("Орёл/решка — /flip", ft.Icons.FLIP_CAMERA_ANDROID, "/flip", False),
            make_cmd_item("Магический шар — /8ball", ft.Icons.HELP, "/8ball", True),
            make_cmd_item("Выбор — /choose", ft.Icons.LIST, "/choose", True),
=======
            make_cmd_item("Кубик 1–6 — /dice", ft.Icons.CASINO, "/dice", False),
            make_cmd_item("Орёл/решка — /flip", ft.Icons.FLIP_CAMERA_ANDROID, "/flip", False),
            make_cmd_item("Магический шар — /8ball", ft.Icons.HELP, "/8ball", True),
            make_cmd_item("Выбор из списка — /choose", ft.Icons.LIST, "/choose", True),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
            make_cmd_item("Шутка — /joke", ft.Icons.EMOJI_EMOTIONS, "/joke", False),
            make_cmd_item("Цитата — /quote", ft.Icons.FORMAT_QUOTE, "/quote", False),
            cmd_header("Утилиты"),
            make_cmd_item("Калькулятор — /calc", ft.Icons.CALCULATE, "/calc", True),
            make_cmd_item("Погода — /weather", ft.Icons.WB_SUNNY, "/weather", True),
            make_cmd_item("Напоминание — /remind", ft.Icons.NOTIFICATIONS, "/remind", True),
            make_cmd_item("Сменить имя — /nick", ft.Icons.BADGE, "/nick", True),
            make_cmd_item("Действие — /me", ft.Icons.WAVING_HAND, "/me", True),
<<<<<<< HEAD
            make_cmd_item("Очистить — /clear", ft.Icons.CLEAR_ALL, "/clear", False),
=======
            make_cmd_item("Очистить ленту — /clear", ft.Icons.CLEAR_ALL, "/clear", False),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        ],
    )

    logout_btn = ft.IconButton(
        ft.Icons.LOGOUT, icon_color=ft.Colors.GREY_300,
        icon_size=20, tooltip="Выйти", visible=False,
    )

    header = ft.Container(
        content=ft.Row([
<<<<<<< HEAD
            back_btn, header_icon,
            ft.Column([header_title, header_subtitle], spacing=0, expand=True),
            online_badge, commands_menu, logout_btn,
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
=======
            back_btn,
            header_icon,
            ft.Column([header_title, header_subtitle],
                      spacing=0, expand=True),
            online_badge,
            commands_menu,
            logout_btn,
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
            colors=[ft.Colors.GREY_900, ft.Colors.GREY_800],
        ),
        border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_800)),
    )

    # ============================================================
<<<<<<< HEAD
    # ЛЕНТА И ВВОД
=======
    # ЛЕНТА СООБЩЕНИЙ
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    # ============================================================
    chat_list = ft.ListView(
        expand=True, spacing=4,
        padding=ft.Padding.symmetric(horizontal=16, vertical=16),
        auto_scroll=True,
    )

    typing_status = ft.Container(
        content=ft.Row([], spacing=6, tight=True),
        padding=ft.Padding.only(left=16, bottom=4),
        visible=False,
    )

<<<<<<< HEAD
    message_input = ft.TextField(
        hint_text="Сообщение…", expand=True,
        border_color=ft.Colors.GREY_700, focused_border_color=ACCENT,
        bgcolor=ft.Colors.GREY_800, border_radius=22,
=======
    # ============================================================
    # ПОЛЕ ВВОДА + ПРЕВЬЮ ОТВЕТА
    # ============================================================
    message_input = ft.TextField(
        hint_text="Сообщение…",
        expand=True,
        border_color=ft.Colors.GREY_700,
        focused_border_color=ACCENT,
        bgcolor=ft.Colors.GREY_800,
        border_radius=22,
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        content_padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        multiline=True, min_lines=1, max_lines=4,
        shift_enter=True, autofocus=True,
    )

    char_counter = ft.Text("0/500", size=10, color=ft.Colors.GREY_600)

    send_btn = ft.Container(
        content=ft.Icon(ft.Icons.SEND_ROUNDED, color=ft.Colors.WHITE, size=20),
        width=44, height=44, border_radius=22,
        bgcolor=ACCENT_MED, alignment=ft.Alignment.CENTER,
        on_click=lambda e: send_message(), ink=True,
    )

    reply_preview_text = ft.Text("", size=12, color=ft.Colors.WHITE,
<<<<<<< HEAD
                                 weight=ft.FontWeight.BOLD, max_lines=1,
=======
                                 weight=ft.FontWeight.BOLD,
                                 max_lines=1,
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                                 overflow=ft.TextOverflow.ELLIPSIS)

    def cancel_reply(update: bool = True) -> None:
        reply_state.update({"id": "", "user": "", "text": ""})
        reply_bar.visible = False
        if update:
            page.update()

    reply_bar = ft.Container(
        content=ft.Row([
            ft.Container(width=3, height=26, bgcolor=ACCENT, border_radius=2),
            ft.Column([
                ft.Text("Ответ", size=10, color=ft.Colors.GREY_500),
                reply_preview_text,
            ], spacing=0, expand=True),
<<<<<<< HEAD
            ft.IconButton(ft.Icons.CLOSE, icon_size=16, icon_color=ft.Colors.GREY_400,
=======
            ft.IconButton(ft.Icons.CLOSE, icon_size=16,
                          icon_color=ft.Colors.GREY_400,
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                          tooltip="Отменить ответ", on_click=lambda e: cancel_reply()),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=14, vertical=4),
        bgcolor=ft.Colors.GREY_900,
        border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.GREY_800)),
        visible=False,
    )

    input_bar = ft.Container(
        content=ft.Column([
            ft.Row([message_input, send_btn], spacing=8,
                   vertical_alignment=ft.CrossAxisAlignment.END),
            ft.Row([ft.Container(expand=True), char_counter], spacing=8),
        ], spacing=4),
        padding=ft.Padding.symmetric(horizontal=14, vertical=8),
        bgcolor=ft.Colors.GREY_900,
        border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.GREY_800)),
    )

    chat_pane = ft.Container(
        content=ft.Column([
            header, chat_list, typing_status, reply_bar, input_bar,
        ], expand=True, spacing=0),
<<<<<<< HEAD
        expand=True, bgcolor=ft.Colors.GREY_900,
=======
        expand=True,
        bgcolor=ft.Colors.GREY_900,
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    )

    # ============================================================
    # АВАТАРЫ
    # ============================================================
    def make_avatar(name: str, key: str, size: int = 36) -> ft.Container:
        color = ft.Colors.GREY_500
        if key and key != BOT_NAME and key != "self":
            color = get_user_color(key)
        return ft.Container(
            content=ft.Text(get_initials(name), size=size // 3,
                            weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            width=size, height=size, border_radius=size // 2,
            bgcolor=color, alignment=ft.Alignment.CENTER,
        )

<<<<<<< HEAD
    def make_avatar_with_status(name: str, key: str, online: bool, size: int = 36) -> ft.Control:
=======
    def make_avatar_with_status(name: str, key: str, online: bool,
                                 size: int = 36) -> ft.Control:
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        base = make_avatar(name, key, size=size)
        if not online:
            return base
        dot = ft.Container(
            width=size // 4, height=size // 4, border_radius=size // 8,
<<<<<<< HEAD
            bgcolor=ONLINE_CLR, border=ft.Border.all(2, ft.Colors.GREY_900),
=======
            bgcolor=ONLINE_CLR,
            border=ft.Border.all(2, ft.Colors.GREY_900),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
            right=0, bottom=0,
        )
        return ft.Stack([base, dot], width=size, height=size)

    profile_card = ft.Container(
        content=ft.Row([
            make_avatar("Я", "self", size=40),
            ft.Column([
<<<<<<< HEAD
                ft.Text("Гость", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
=======
                ft.Text("Гость", size=14, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                ft.Text("не авторизован", size=11, color=ft.Colors.GREY_400),
            ], spacing=0, expand=True),
            ft.Container(width=8, height=8, border_radius=4, bgcolor=ONLINE_CLR),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=14, vertical=14),
        bgcolor=ft.Colors.with_opacity(0.08, ACCENT),
        border_radius=12,
    )

    chats_list = ft.Column(spacing=2, expand=True, scroll=ft.ScrollMode.AUTO)

    sidebar_header = ft.Row([
        ft.Icon(ft.Icons.FORUM, color=ACCENT, size=18),
<<<<<<< HEAD
        ft.Text("Чаты", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400),
        ft.Container(expand=True), online_badge,
=======
        ft.Text("Чаты", size=12, weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREY_400),
        ft.Container(expand=True),
        online_badge,
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    sidebar_col = ft.Container(
        content=ft.Column([
            profile_card, sidebar_header,
            ft.Divider(height=1, thickness=1, color=ft.Colors.GREY_800),
            chats_list,
        ], spacing=8),
        width=300,
        padding=ft.Padding.only(left=12, right=8, top=12, bottom=12),
        bgcolor=ft.Colors.GREY_900,
        border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.GREY_800)),
    )

    # ============================================================
<<<<<<< HEAD
    # РЕАКЦИИ (без изменений)
=======
    # РЕАКЦИИ И ДЕЙСТВИЯ НА СООБЩЕНИЕ
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    # ============================================================
    def fill_reactions(row: ft.Row, reactions: dict, msg_id: str) -> None:
        row.controls.clear()
        for key, icon, col in REACTION_ICONS:
            phones = (reactions or {}).get(key, [])
            if not phones:
                continue
            active = bool(my_phone[0]) and my_phone[0] in phones
            row.controls.append(ft.Container(
                content=ft.Row([
<<<<<<< HEAD
                    ft.Icon(icon, size=12, color=col if active else ft.Colors.GREY_400),
=======
                    ft.Icon(icon, size=12,
                            color=col if active else ft.Colors.GREY_400),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                    ft.Text(str(len(phones)), size=10, color=ft.Colors.WHITE),
                ], spacing=3, tight=True),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=12,
<<<<<<< HEAD
                bgcolor=ft.Colors.with_opacity(0.25, col) if active else ft.Colors.GREY_700,
=======
                bgcolor=ft.Colors.with_opacity(0.25, col) if active
                        else ft.Colors.GREY_700,
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                on_click=lambda e, k=key: toggle_reaction(msg_id, k),
                ink=True,
            ))
        row.visible = bool(row.controls)

    def toggle_reaction(msg_id: str, key: str) -> None:
        if not my_phone[0] or not msg_id:
            return
        k = active_chat[0]
<<<<<<< HEAD
        if k == SUPPORT_KEY:
            hist = SUPPORT_HISTORY.setdefault(my_phone[0], [])
            for m in hist:
                if m.get("id") == msg_id:
                    reacts = m.setdefault("reactions", {})
                    lst = reacts.setdefault(key, [])
                    if my_phone[0] in lst:
                        lst.remove(my_phone[0])
                    else:
                        lst.append(my_phone[0])
                    if not lst:
                        reacts.pop(key, None)
                    row = rendered_msg_rows.get(msg_id)
                    if row is not None:
                        fill_reactions(row, reacts, msg_id)
                    page.update()
                    return
            return
        topic = LOBBY_KEY if k == LOBBY_KEY else dm_topic(my_phone[0], k)
        page.pubsub.send_all_on_topic(topic, {
            "type": "reaction", "msg_id": msg_id, "emoji": key, "phone": my_phone[0],
        })

    def set_reply(msg: Message) -> None:
        reply_state.update({"id": msg.id, "user": msg.user, "text": (msg.text or "")[:60]})
=======
        topic = LOBBY_KEY if k == LOBBY_KEY else dm_topic(my_phone[0], k)
        page.pubsub.send_all_on_topic(topic, {
            "type": "reaction", "msg_id": msg_id, "emoji": key,
            "phone": my_phone[0],
        })

    def set_reply(msg: Message) -> None:
        reply_state.update({
            "id": msg.id, "user": msg.user,
            "text": (msg.text or "")[:60],
        })
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        reply_preview_text.value = f"{msg.user}: {reply_state['text']}"
        reply_bar.visible = True
        page.update()

    def make_msg_menu(msg: Message) -> ft.PopupMenuButton:
        def item(icon, text, on_click, icon_color=ft.Colors.WHITE):
            return ft.PopupMenuItem(
                content=ft.Row([
                    ft.Icon(icon, size=14, color=icon_color),
                    ft.Text(text, size=12, color=ft.Colors.WHITE),
                ], spacing=8, tight=True),
                on_click=on_click,
            )
        return ft.PopupMenuButton(
<<<<<<< HEAD
            icon=ft.Icons.MORE_HORIZ, icon_size=14, icon_color=ft.Colors.GREY_600,
            tooltip="Действия",
            items=[
                item(ft.Icons.REPLY, "Ответить", lambda e: set_reply(msg)),
                item(ft.Icons.THUMB_UP, "Нравится", lambda e: toggle_reaction(msg.id, "like")),
                item(ft.Icons.FAVORITE, "Сердце", lambda e: toggle_reaction(msg.id, "heart"),
=======
            icon=ft.Icons.MORE_HORIZ,
            icon_size=14,
            icon_color=ft.Colors.GREY_600,
            tooltip="Действия",
            items=[
                item(ft.Icons.REPLY, "Ответить", lambda e: set_reply(msg)),
                item(ft.Icons.THUMB_UP, "Нравится",
                     lambda e: toggle_reaction(msg.id, "like")),
                item(ft.Icons.FAVORITE, "Сердце",
                     lambda e: toggle_reaction(msg.id, "heart"),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                     icon_color=ft.Colors.RED_400),
            ],
        )

    # ============================================================
    # ОТРИСОВКА СООБЩЕНИЙ
    # ============================================================
    def add_date_separator(d_iso: str) -> None:
        try:
            d = date.fromisoformat(d_iso)
        except ValueError:
            d = date.today()
        chat_list.controls.append(
            ft.Container(
<<<<<<< HEAD
                content=ft.Text(format_date_label(d), size=11, color=ft.Colors.GREY_500),
=======
                content=ft.Text(format_date_label(d), size=11,
                                color=ft.Colors.GREY_500),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(vertical=8),
            )
        )

    def add_message_to_ui(msg: Message) -> None:
        is_own = msg.sender_phone == my_phone[0] and msg.kind != "system"
        is_system = msg.kind in ("system", "me")
<<<<<<< HEAD
        is_support = msg.kind == "support"
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f

        msg_date = msg.date or today_iso()
        if msg_date != last_rendered_date[0]:
            add_date_separator(msg_date)
            last_rendered_date[0] = msg_date
            last_author[0] = ""

        if is_system:
            chat_list.controls.append(
                ft.Container(
<<<<<<< HEAD
                    content=ft.Text(msg.text, size=12, italic=True, color=ft.Colors.GREY_400),
=======
                    content=ft.Text(msg.text, size=12, italic=True,
                                    color=ft.Colors.GREY_400),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=4),
                )
            )
            last_author[0] = "Система"
            return

<<<<<<< HEAD
        nick_color = (SUPPORT_CLR if is_support
                      else get_user_color(msg.sender_phone or msg.user))
=======
        nick_color = get_user_color(msg.sender_phone or msg.user)
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        show_header = last_author[0] != msg.sender_phone
        last_author[0] = msg.sender_phone

        bubble_children = []

<<<<<<< HEAD
=======
        # цитата ответа
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        if msg.reply_to_id:
            bubble_children.append(
                ft.Container(
                    content=ft.Column([
<<<<<<< HEAD
                        ft.Text(msg.reply_to_user or "Сообщение", size=11,
                                weight=ft.FontWeight.BOLD, color=ACCENT),
=======
                        ft.Text(msg.reply_to_user or "Сообщение",
                                size=11, weight=ft.FontWeight.BOLD,
                                color=ACCENT),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                        ft.Text(msg.reply_to_text or "", size=11,
                                color=ft.Colors.GREY_400, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=0, tight=True),
                    padding=ft.Padding.only(left=8, top=2, bottom=2, right=4),
                    border=ft.Border.only(left=ft.BorderSide(2, ACCENT)),
<<<<<<< HEAD
                    border_radius=4, margin=ft.Margin.only(bottom=4),
                )
            )

=======
                    border_radius=4,
                    margin=ft.Margin.only(bottom=4),
                )
            )

        # шапка (автор + время)
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        if show_header:
            header_controls = []
            if is_own:
                header_controls.append(ft.Container(
                    content=ft.Text("Вы", size=9, color=ft.Colors.WHITE,
                                    weight=ft.FontWeight.BOLD),
                    padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                    border_radius=6, bgcolor=ACCENT_MED,
                ))
<<<<<<< HEAD
            if is_support:
                header_controls.append(ft.Container(
                    content=ft.Text("ИИ", size=9, color=ft.Colors.BLACK,
                                    weight=ft.FontWeight.BOLD),
                    padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                    border_radius=6, bgcolor=SUPPORT_CLR,
                ))
            header_controls.append(ft.Text(
                msg.user, weight=ft.FontWeight.BOLD, size=12,
                color=SUPPORT_CLR if is_support else (ACCENT if is_own else nick_color)))
            header_controls.append(ft.Text(msg.timestamp, size=10, color=ft.Colors.GREY_500))
=======
            header_controls.append(ft.Text(
                msg.user, weight=ft.FontWeight.BOLD, size=12,
                color=ACCENT if is_own else nick_color))
            header_controls.append(ft.Text(msg.timestamp, size=10,
                                           color=ft.Colors.GREY_500))
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
            bubble_children.append(ft.Row(header_controls, spacing=8, tight=True))

        bubble_children.append(
            ft.Text(msg.text, size=14, color=ft.Colors.WHITE, selectable=True)
        )

<<<<<<< HEAD
        if is_support and msg.quick:
            qr = ft.Row([], spacing=6, wrap=True)
            for q in msg.quick:
                qr.controls.append(ft.Container(
                    content=ft.Text(q, size=11, color=SUPPORT_CLR),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=12,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.4, SUPPORT_CLR)),
                    on_click=lambda e, t=q: quick_reply(t), ink=True,
                ))
            bubble_children.append(qr)

=======
        # строка реакций (всегда создаётся, заполняется по наличию)
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        reactions_row = ft.Row([], spacing=4, tight=True, visible=False)
        fill_reactions(reactions_row, msg.reactions, msg.id)
        if msg.id:
            rendered_msg_rows[msg.id] = reactions_row
        bubble_children.append(reactions_row)

        bubble = ft.Container(
            content=ft.Column(bubble_children, spacing=2, tight=True),
<<<<<<< HEAD
            bgcolor=(ft.Colors.with_opacity(0.25, SUPPORT_CLR) if is_support
                     else (ACCENT_DEEP if is_own else ft.Colors.GREY_800)),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=ft.BorderRadius.only(
                top_left=16, top_right=16, bottom_left=4, bottom_right=16),
=======
            bgcolor=ACCENT_DEEP if is_own else ft.Colors.GREY_800,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=ft.BorderRadius.only(
                top_left=16, top_right=16, bottom_left=4, bottom_right=16,
            ),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
            max_width=480,
            shadow=ft.BoxShadow(blur_radius=4, spread_radius=0,
                                color=ft.Colors.with_opacity(0.15, ft.Colors.BLACK),
                                offset=ft.Offset(0, 1)),
        )

        avatar = (make_avatar_with_status(msg.user, msg.sender_phone or msg.user,
                                           online=False, size=32)
                  if show_header else ft.Container(width=32))
<<<<<<< HEAD
        menu = (make_msg_menu(msg) if msg.kind == "message" or is_support
                else ft.Container())

        row = ft.Row([avatar, bubble, menu], spacing=6,
                     vertical_alignment=ft.CrossAxisAlignment.START)
=======
        menu = make_msg_menu(msg) if msg.kind == "message" else ft.Container()

        row = ft.Row(
            [avatar, bubble, menu],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        chat_list.controls.append(row)

    def render_active_chat() -> None:
        chat_list.controls.clear()
        rendered_msg_rows.clear()
        last_rendered_date[0] = ""
        last_author[0] = ""
        key = active_chat[0]
        if key == LOBBY_KEY:
            msgs = LOBBY_HISTORY
<<<<<<< HEAD
        elif key == SUPPORT_KEY:
            msgs = SUPPORT_HISTORY.get(my_phone[0], []) if my_phone[0] else []
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        else:
            topic = dm_topic(my_phone[0], key) if my_phone[0] else ""
            msgs = DM_HISTORY.get(topic, [])
        if not msgs:
            chat_list.controls.append(
                ft.Container(
                    content=ft.Text("Нет сообщений. Начните диалог!",
                                    size=12, color=ft.Colors.GREY_600),
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=40),
                )
            )
        else:
            for m in msgs:
                add_message_to_ui(Message.from_dict(m))
        typing_status.visible = False

    # ============================================================
<<<<<<< HEAD
    # ОБНОВЛЕНИЕ UI (сокращённо — как в предыдущей версии)
=======
    # ОБНОВЛЕНИЕ ШАПКИ И БОКОВОЙ ПАНЕЛИ
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    # ============================================================
    def update_header() -> None:
        key = active_chat[0]
        if key == LOBBY_KEY:
<<<<<<< HEAD
            header_icon.content = ft.Icon(ft.Icons.PUBLIC, color=ft.Colors.WHITE, size=20)
            header_icon.bgcolor = ACCENT_MED
            header_title.value = "Общий чат"
            header_subtitle.value = "Все участники"
        elif key == SUPPORT_KEY:
            header_icon.content = ft.Icon(ft.Icons.SUPPORT_AGENT, color=ft.Colors.BLACK, size=20)
            header_icon.bgcolor = SUPPORT_CLR
            header_title.value = "Техподдержка"
            header_subtitle.value = "ИИ-ассистент · отвечает сразу"
=======
            header_icon.content = ft.Icon(ft.Icons.PUBLIC,
                                          color=ft.Colors.WHITE, size=20)
            header_icon.bgcolor = ACCENT_MED
            header_title.value = "Общий чат"
            header_subtitle.value = "Все участники"
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        else:
            info = PARTICIPANTS.get(key, {})
            name = info.get("name", "?")
            header_icon.content = ft.Text(get_initials(name), size=12,
<<<<<<< HEAD
                                          weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
=======
                                          weight=ft.FontWeight.BOLD,
                                          color=ft.Colors.WHITE)
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
            header_icon.bgcolor = get_user_color(key)
            online = "в сети" if key in PARTICIPANTS else "не в сети"
            header_subtitle.value = f"{format_phone(key)} · {online}"
            header_title.value = name

    def update_online_count() -> None:
        n = len(PARTICIPANTS)
        online_badge.content.controls[1].value = f"{n} онлайн"

    def update_profile() -> None:
        if my_phone[0] and my_name[0]:
            row = profile_card.content
            row.controls[0] = make_avatar(my_name[0], my_phone[0], size=40)
            col = row.controls[1]
            col.controls[0].value = my_name[0]
            col.controls[1].value = format_phone(my_phone[0])

    def last_msg_for_key(key: str):
        if key == LOBBY_KEY:
            hist = LOBBY_HISTORY
<<<<<<< HEAD
        elif key == SUPPORT_KEY:
            hist = SUPPORT_HISTORY.get(my_phone[0], []) if my_phone[0] else []
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        else:
            topic = dm_topic(my_phone[0], key) if my_phone[0] else ""
            hist = DM_HISTORY.get(topic, [])
        if not hist:
            return None, None
        m = hist[-1]
        txt = m.get("text", "")
        if m.get("kind") == "me":
            preview = f"{m.get('user', '')} {txt}"
<<<<<<< HEAD
        elif m.get("kind") == "support":
            preview = "🛟 " + txt
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        elif m.get("sender_phone") == my_phone[0]:
            preview = "Вы: " + txt
        else:
            preview = txt
        preview = (preview[:30] + "…") if len(preview) > 30 else preview
        return preview, m.get("timestamp", "")

    def build_sidebar_chats() -> None:
        chats_list.controls.clear()
        key = active_chat[0]

<<<<<<< HEAD
        def chat_row(icon_or_avatar, title, preview, time_text, n_unread, active, on_click):
=======
        def chat_row(icon_or_avatar, title, preview, time_text, n_unread,
                     active, on_click):
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
            badge = (ft.Container(
                content=ft.Text(str(n_unread), size=10, color=ft.Colors.WHITE,
                                weight=ft.FontWeight.BOLD),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=10, bgcolor=ACCENT_MED,
            ) if n_unread > 0 else ft.Container(width=10))
            return ft.Container(
                content=ft.Row([
                    icon_or_avatar,
                    ft.Column([
                        ft.Text(title, size=13, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(preview, size=11, color=ft.Colors.GREY_500,
<<<<<<< HEAD
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
=======
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                    ], spacing=1, expand=True),
                    ft.Column([
                        ft.Text(time_text, size=10, color=ft.Colors.GREY_500),
                        badge,
<<<<<<< HEAD
                    ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.END),
=======
                    ], spacing=4,
                       horizontal_alignment=ft.CrossAxisAlignment.END),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.18, ACCENT) if active else None,
                on_click=on_click, ink=True,
            )

<<<<<<< HEAD
        l_preview, l_time = last_msg_for_key(LOBBY_KEY)
        chats_list.controls.append(chat_row(
            ft.Container(content=ft.Icon(ft.Icons.PUBLIC, color=ft.Colors.WHITE, size=18),
=======
        # Общий чат
        l_preview, l_time = last_msg_for_key(LOBBY_KEY)
        chats_list.controls.append(chat_row(
            ft.Container(content=ft.Icon(ft.Icons.PUBLIC,
                                         color=ft.Colors.WHITE, size=18),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                         width=36, height=36, border_radius=18,
                         bgcolor=ACCENT_MED, alignment=ft.Alignment.CENTER),
            "Общий чат", l_preview or "Нет сообщений", l_time or "",
            unread.get(LOBBY_KEY, 0), key == LOBBY_KEY,
            lambda e: open_chat(LOBBY_KEY),
        ))

<<<<<<< HEAD
        s_preview, s_time = last_msg_for_key(SUPPORT_KEY)
        chats_list.controls.append(chat_row(
            ft.Container(content=ft.Icon(ft.Icons.SUPPORT_AGENT,
                                         color=ft.Colors.BLACK, size=18),
                         width=36, height=36, border_radius=18,
                         bgcolor=SUPPORT_CLR, alignment=ft.Alignment.CENTER),
            "🛟 Техподдержка", s_preview or "ИИ-ассистент на связи",
            s_time or "", unread.get(SUPPORT_KEY, 0), key == SUPPORT_KEY,
            lambda e: open_chat(SUPPORT_KEY),
        ))

=======
        # Контакты
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        others = [p for p in PARTICIPANTS if p != my_phone[0]]
        if others:
            chats_list.controls.append(
                ft.Container(
<<<<<<< HEAD
                    content=ft.Text(f"Контакты · {len(others)}", size=11,
                                    color=ft.Colors.GREY_500),
                    padding=ft.Padding.only(left=10, top=10, bottom=4),
                )
            )
            for phone in sorted(others, key=lambda p: PARTICIPANTS[p]["name"].lower()):
=======
                    content=ft.Text(f"Контакты · {len(others)}",
                                    size=11, color=ft.Colors.GREY_500),
                    padding=ft.Padding.only(left=10, top=10, bottom=4),
                )
            )
            for phone in sorted(others,
                                key=lambda p: PARTICIPANTS[p]["name"].lower()):
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                info = PARTICIPANTS[phone]
                name = info.get("name", "?")
                c_preview, c_time = last_msg_for_key(phone)
                chats_list.controls.append(chat_row(
<<<<<<< HEAD
                    make_avatar_with_status(name, phone, online=phone in PARTICIPANTS, size=36),
=======
                    make_avatar_with_status(name, phone,
                                            online=phone in PARTICIPANTS, size=36),
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                    name, c_preview or format_phone(phone), c_time or "",
                    unread.get(phone, 0), key == phone,
                    lambda e, p=phone: open_chat(p),
                ))
        else:
            chats_list.controls.append(
                ft.Container(
<<<<<<< HEAD
                    content=ft.Text("Пока никого нет в сети.\nПригласите друга войти!",
=======
                    content=ft.Text("Пока никого нет в сети.\n"
                                    "Пригласите друга войти!",
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
                                    size=11, color=ft.Colors.GREY_600),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=12),
                )
            )

    # ============================================================
    # ПЕРЕКЛЮЧЕНИЕ ЧАТОВ
    # ============================================================
    def open_chat(key: str) -> None:
        active_chat[0] = key
        unread[key] = 0
        cancel_reply(update=False)
<<<<<<< HEAD
        if key == SUPPORT_KEY and my_phone[0]:
            hist = SUPPORT_HISTORY.setdefault(my_phone[0], [])
            if not hist:
                _push_support_msg(my_phone[0], SUPPORT_GREETING,
                                  quick=["Как войти", "Команды бота",
                                         "Кто онлайн", "Связаться с оператором"])
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        render_active_chat()
        update_header()
        build_sidebar_chats()
        mobile_show_sidebar[0] = False
        apply_layout()
        page.update()

    def apply_layout() -> None:
        is_desktop = (page.width or 0) >= 760
        back_btn.visible = False
        if is_desktop:
            sidebar_col.visible = True
            sidebar_col.width = 300
            sidebar_col.expand = False
            chat_pane.visible = True
        else:
            sidebar_col.visible = mobile_show_sidebar[0]
            sidebar_col.width = None
            sidebar_col.expand = mobile_show_sidebar[0]
            chat_pane.visible = not mobile_show_sidebar[0]
            back_btn.visible = not mobile_show_sidebar[0]

    def on_resize(e=None) -> None:
        apply_layout()
        page.update()

    page.on_resize = on_resize

    # ============================================================
<<<<<<< HEAD
    # ИИ-ПОДДЕРЖКА: ВСПОМОГАТЕЛЬНЫЕ
    # ============================================================
    def _push_support_msg(phone: str, text: str, quick: list[str] | None = None,
                          kind: str = "support") -> dict:
        msg = {
            "id": new_msg_id(), "user": SUPPORT_NAME, "text": text,
            "timestamp": now_time(), "sender_phone": "SUPPORT",
            "kind": kind, "date": today_iso(), "reactions": {},
            "reply_to_id": "", "reply_to_user": "", "reply_to_text": "",
            "quick": quick or [],
        }
        hist = SUPPORT_HISTORY.setdefault(phone, [])
        hist.append(msg)
        if len(hist) > MAX_SUPPORT_HISTORY:
            del hist[:-MAX_SUPPORT_HISTORY]
        return msg

    def _show_support_typing(phone: str, on: bool) -> None:
        if not my_phone[0] or my_phone[0] != phone:
            return
        if active_chat[0] != SUPPORT_KEY:
            return
        if on:
            typing_status.content = ft.Row([
                ft.Container(content=ft.Icon(ft.Icons.SUPPORT_AGENT, size=14,
                                             color=ft.Colors.BLACK),
                             width=18, height=18, border_radius=9,
                             bgcolor=SUPPORT_CLR, alignment=ft.Alignment.CENTER),
                ft.Text("Ассистент печатает…", size=11, italic=True,
                        color=ft.Colors.GREY_400),
            ], spacing=6, tight=True)
            typing_status.visible = True
        else:
            typing_status.visible = False

    def _process_support_query(phone: str, text: str) -> None:
        """Вызывает ИИ-агента и добавляет ответ в чат."""
        _show_support_typing(phone, True)
        try:
            page.update()
        except Exception:
            pass

        # вызов API (может занять время)
        answer, escalate = ai_support_answer(phone, text)

        def _apply():
            try:
                _show_support_typing(phone, False)
                if active_chat[0] == SUPPORT_KEY and my_phone[0] == phone:
                    msg = _push_support_msg(phone, answer, quick=None)
                    add_message_to_ui(Message.from_dict(msg))
                else:
                    _push_support_msg(phone, answer, quick=None)
                    unread[SUPPORT_KEY] = unread.get(SUPPORT_KEY, 0) + 1
                    build_sidebar_chats()
                if escalate:
                    page.pubsub.send_all_on_topic(LOBBY_KEY, {
                        "id": new_msg_id(), "user": "Система",
                        "text": f"🛟 Заявка в поддержку от {my_name[0]} "
                                f"({format_phone(phone)})",
                        "timestamp": now_time(), "sender_phone": "",
                        "kind": "system", "date": today_iso(),
                        "reactions": {}, "reply_to_id": "",
                        "reply_to_user": "", "reply_to_text": "",
                    })
                page.update()
            except Exception as ex:
                print(f"[SUPPORT APPLY ERROR] {ex}")

        _apply()

    def quick_reply(text: str) -> None:
        if not my_phone[0]:
            return
        message_input.value = text
        send_message()

    # ============================================================
    # ПРИСУТСТВИЕ / ЧАТ (без изменений — сокращённо)
=======
    # ПРИСУТСТВИЕ
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    # ============================================================
    def announce_hello() -> None:
        page.pubsub.send_all_on_topic("presence", {
            "type": "hello", "phone": my_phone[0], "name": my_name[0],
        })

    def announce_here() -> None:
        page.pubsub.send_all_on_topic("presence", {
            "type": "here", "phone": my_phone[0], "name": my_name[0],
        })

    def announce_bye() -> None:
        if not my_phone[0]:
            return
        page.pubsub.send_all_on_topic("presence", {
            "type": "bye", "phone": my_phone[0], "name": my_name[0],
        })

    def on_presence(topic: str, data: dict) -> None:
        t = data.get("type")
        phone = data.get("phone")
        name = data.get("name", "?")
        if not my_phone[0] or not phone or phone == my_phone[0]:
            return
        if t in ("hello", "here"):
<<<<<<< HEAD
            PARTICIPANTS[phone] = {"name": name, "session_id": data.get("session_id", "")}
=======
            PARTICIPANTS[phone] = {"name": name,
                                   "session_id": data.get("session_id", "")}
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
            tkey = dm_topic(my_phone[0], phone)
            if tkey not in my_dm_topics:
                page.pubsub.subscribe_topic(tkey, on_chat_message)
                my_dm_topics.add(tkey)
            if t == "hello":
                announce_here()
            update_online_count()
            build_sidebar_chats()
            update_header()
            page.update()
        elif t == "bye":
            PARTICIPANTS.pop(phone, None)
            update_online_count()
            build_sidebar_chats()
            update_header()
            page.update()

<<<<<<< HEAD
=======
    # ============================================================
    # ПРИЁМ СООБЩЕНИЙ (лобби + личные + реакции)
    # ============================================================
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    def chat_key_for_topic(topic: str) -> str:
        if topic == LOBBY_KEY:
            return LOBBY_KEY
        body = topic[len("dm:"):]
        a, _, b = body.partition("_")
<<<<<<< HEAD
        return b if a == my_phone[0] else a
=======
        if a == my_phone[0]:
            return b
        return a
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f

    def history_for_key(key: str) -> list[dict]:
        if key == LOBBY_KEY:
            return LOBBY_HISTORY
        topic = dm_topic(my_phone[0], key) if my_phone[0] else ""
        return DM_HISTORY.setdefault(topic, [])

    def on_chat_message(topic: str, data: dict) -> None:
        if not my_phone[0]:
            return

<<<<<<< HEAD
=======
        # реакция на сообщение
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        if data.get("type") == "reaction":
            msg_id = data.get("msg_id")
            emoji = data.get("emoji")
            phone = data.get("phone", "")
            if not msg_id or not emoji:
                return
            key = chat_key_for_topic(topic)
            hist = history_for_key(key)
            for m in hist:
                if m.get("id") == msg_id:
                    reacts = m.setdefault("reactions", {})
                    lst = reacts.setdefault(emoji, [])
                    if phone in lst:
                        lst.remove(phone)
                    else:
                        lst.append(phone)
                    if not lst:
                        reacts.pop(emoji)
                    row = rendered_msg_rows.get(msg_id)
                    if row is not None and active_chat[0] == key:
                        fill_reactions(row, reacts, msg_id)
<<<<<<< HEAD
                    elif active_chat[0] != key:
                        build_sidebar_chats()
                    page.update()
                    break
            return

=======
                        page.update()
                    elif active_chat[0] != key:
                        build_sidebar_chats()
                        page.update()
                    break
            return

        # индикатор набора
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        if data.get("type") == "typing":
            sender = data.get("name", "?")
            sender_phone = data.get("sender_phone", "")
            if sender_phone == my_phone[0]:
                return
            key = chat_key_for_topic(topic)
            if active_chat[0] == key:
                typing_status.content = ft.Row([
                    make_avatar(sender, sender_phone, size=18),
                    ft.Text(f"{sender} печатает…", size=11, italic=True,
                            color=ft.Colors.GREY_400),
                ], spacing=6, tight=True)
                typing_status.visible = True
                page.update()
            return

<<<<<<< HEAD
=======
        # обычное сообщение
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        msg = {
            "id": data.get("id") or new_msg_id(),
            "user": data.get("user", "?"),
            "text": data.get("text", ""),
            "timestamp": data.get("timestamp", now_time()),
            "sender_phone": data.get("sender_phone", ""),
            "kind": data.get("kind", "message"),
            "date": data.get("date", today_iso()),
            "reactions": data.get("reactions", {}),
            "reply_to_id": data.get("reply_to_id", ""),
            "reply_to_user": data.get("reply_to_user", ""),
            "reply_to_text": data.get("reply_to_text", ""),
<<<<<<< HEAD
            "quick": data.get("quick", []),
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        }
        key = chat_key_for_topic(topic)
        history = history_for_key(key)
        history.append(msg)
        if len(history) > MAX_HISTORY:
            del history[:-MAX_HISTORY]

        if active_chat[0] == key:
            add_message_to_ui(Message.from_dict(msg))
            typing_status.visible = False
        else:
            unread[key] = unread.get(key, 0) + 1
            build_sidebar_chats()
        page.update()

    # ============================================================
<<<<<<< HEAD
    # БОТ / КОМАНДЫ (сокращённо — ключевые)
    # ============================================================
    def bot_send(text: str, kind: str = "message") -> None:
        payload = {
            "id": new_msg_id(), "user": BOT_NAME, "text": text,
            "timestamp": now_time(), "sender_phone": BOT_NAME,
            "kind": kind, "date": today_iso(), "reactions": {},
            "reply_to_id": "", "reply_to_user": "", "reply_to_text": "", "quick": [],
=======
    # БОТ / КОМАНДЫ
    # ============================================================
    def bot_send(text: str, kind: str = "message") -> None:
        payload = {
            "id": new_msg_id(),
            "user": BOT_NAME,
            "text": text,
            "timestamp": now_time(),
            "sender_phone": BOT_NAME,
            "kind": kind,
            "date": today_iso(),
            "reactions": {},
            "reply_to_id": "", "reply_to_user": "", "reply_to_text": "",
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        }
        key = active_chat[0]
        if key == LOBBY_KEY:
            page.pubsub.send_all_on_topic(LOBBY_KEY, payload)
<<<<<<< HEAD
        elif key == SUPPORT_KEY:
            msg = _push_support_msg(my_phone[0], text, kind="system")
            add_message_to_ui(Message.from_dict(msg))
            page.update()
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        else:
            if key not in PARTICIPANTS:
                add_system_locally("Собеседник не в сети — сообщение не отправлено.")
                page.update()
                return
            page.pubsub.send_all_on_topic(dm_topic(my_phone[0], key), payload)

    def add_system_locally(text: str) -> None:
        msg = {
<<<<<<< HEAD
            "id": new_msg_id(), "user": "Система", "text": text,
            "timestamp": now_time(), "sender_phone": "",
            "kind": "system", "date": today_iso(),
            "reactions": {}, "reply_to_id": "", "reply_to_user": "",
            "reply_to_text": "", "quick": [],
=======
            "id": new_msg_id(),
            "user": "Система", "text": text,
            "timestamp": now_time(), "sender_phone": "",
            "kind": "system", "date": today_iso(),
            "reactions": {}, "reply_to_id": "", "reply_to_user": "",
            "reply_to_text": "",
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        }
        history = history_for_key(active_chat[0])
        history.append(msg)
        add_message_to_ui(Message.from_dict(msg))

    def handle_bot_command(text: str) -> bool:
        low = text.strip().lower()
        if not low.startswith("/"):
            return False
        cmd, _, arg = low.partition(" ")
        arg = arg.strip()
        raw_arg = text.strip()[len(cmd):].strip()

<<<<<<< HEAD
        if cmd == "/support":
            open_chat(SUPPORT_KEY)
        elif cmd == "/human":
            if my_phone[0]:
                if active_chat[0] != SUPPORT_KEY:
                    open_chat(SUPPORT_KEY)
                _push_support_msg(my_phone[0], SUPPORT_ESCALATED,
                                  quick=["Спасибо", "Отменить"])
                render_active_chat()
                page.pubsub.send_all_on_topic(LOBBY_KEY, {
                    "id": new_msg_id(), "user": "Система",
                    "text": f"🛟 Заявка в поддержку от {my_name[0]} "
                            f"({format_phone(my_phone[0])})",
                    "timestamp": now_time(), "sender_phone": "",
                    "kind": "system", "date": today_iso(),
                    "reactions": {}, "reply_to_id": "",
                    "reply_to_user": "", "reply_to_text": "",
                })
                page.update()
        elif cmd == "/reset_support":
            if my_phone[0]:
                SUPPORT_CONTEXT.pop(my_phone[0], None)
                SUPPORT_HISTORY[my_phone[0]] = []
                if active_chat[0] == SUPPORT_KEY:
                    open_chat(SUPPORT_KEY)
                page.update()
        elif cmd == "/help":
=======
        if cmd == "/help":
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
            lines = ["Команды бота:"]
            for k, v in BOT_COMMANDS.items():
                lines.append(f"  {k} — {v}")
            bot_send("\n".join(lines), kind="system")
        elif cmd == "/users":
            names = [PARTICIPANTS[p]["name"] for p in PARTICIPANTS]
            bot_send(f"Сейчас в сети ({len(names)}): "
                     + (", ".join(sorted(names)) if names else "только вы"),
                     kind="system")
        elif cmd == "/whoami":
<<<<<<< HEAD
            bot_send(f"Вы: {my_name[0]} · {format_phone(my_phone[0])}", kind="system")
        elif cmd == "/time":
            bot_send(f"Время сервера: {datetime.now().strftime('%H:%M:%S')}", kind="system")
=======
            bot_send(f"Вы: {my_name[0]} · {format_phone(my_phone[0])}",
                     kind="system")
        elif cmd == "/stats":
            hist = history_for_key(active_chat[0])
            total = len(hist)
            authors: dict[str, int] = {}
            for m in hist:
                if m.get("kind") in ("system", "me"):
                    continue
                a = m.get("user", "?")
                authors[a] = authors.get(a, 0) + 1
            top = sorted(authors.items(), key=lambda x: -x[1])[:3]
            top_s = ", ".join(f"{n} ({c})" for n, c in top) or "—"
            label = ("Общий чат" if active_chat[0] == LOBBY_KEY
                     else "Личный чат")
            bot_send(f"Статистика · {label}: сообщений {total}, "
                     f"авторов {len(authors)}. Топ: {top_s}", kind="system")
        elif cmd == "/time":
            bot_send(f"Время сервера: "
                     f"{datetime.now().strftime('%H:%M:%S')}", kind="system")
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        elif cmd == "/ping":
            bot_send("понг", kind="system")
        elif cmd == "/roll":
            bot_send(f"Выпало: {random.randint(1, 100)}")
        elif cmd == "/dice":
            bot_send(f"Кубик: {random.randint(1, 6)}")
        elif cmd == "/flip":
            bot_send(random.choice(["Орёл", "Решка"]))
<<<<<<< HEAD
=======
        elif cmd == "/8ball":
            if not arg:
                add_system_locally("Использование: /8ball <вопрос>")
                page.update()
            else:
                bot_send(random.choice(EIGHT_BALL), kind="system")
        elif cmd == "/choose":
            opts = [o for o in arg.split() if o]
            if len(opts) < 2:
                add_system_locally("Использование: /choose a b c …")
                page.update()
            else:
                bot_send(f"Выбрано: {random.choice(opts)}", kind="system")
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        elif cmd == "/joke":
            bot_send(random.choice(JOKES), kind="system")
        elif cmd == "/quote":
            bot_send(random.choice(QUOTES), kind="system")
<<<<<<< HEAD
=======
        elif cmd == "/calc":
            if not arg:
                add_system_locally("Использование: /calc <выражение>")
                page.update()
            else:
                try:
                    res = safe_calc(arg)
                    bot_send(f"{arg} = {res}", kind="system")
                except ZeroDivisionError:
                    add_system_locally("Деление на ноль!")
                    page.update()
                except Exception:
                    add_system_locally("Не удалось вычислить (только числа "
                                       "и + - * / % // **)")
                    page.update()
        elif cmd == "/weather":
            city = raw_arg
            if not city:
                add_system_locally("Использование: /weather <город>")
                page.update()
            else:
                add_system_locally(f"Запрашиваю погоду: {city}…")
                page.update()

                def _w(c=city):
                    try:
                        bot_send(fetch_weather(c), kind="system")
                    except Exception:
                        bot_send(f"Не удалось узнать погоду для «{c}». "
                                 "Возможно, нет сети или город не найден.",
                                 kind="system")

                threading.Thread(target=_w, daemon=True).start()
        elif cmd == "/remind":
            parts = arg.split(maxsplit=1)
            if len(parts) != 2:
                add_system_locally("Использование: /remind <секунды> <текст>")
                page.update()
            else:
                try:
                    secs = int(parts[0])
                except ValueError:
                    add_system_locally("Секунды должны быть числом")
                    page.update()
                    return True
                if not (1 <= secs <= 600):
                    add_system_locally("Задержка от 1 до 600 секунд")
                    page.update()
                    return True
                rem_text = parts[1]
                add_system_locally(f"Напомню через {secs}с: {rem_text}")
                page.update()
                key = active_chat[0]
                topic = (LOBBY_KEY if key == LOBBY_KEY
                         else dm_topic(my_phone[0], key))

                def _fire():
                    payload = {
                        "id": new_msg_id(),
                        "user": BOT_NAME,
                        "text": f"Напоминание для {my_name[0]}: {rem_text}",
                        "timestamp": now_time(),
                        "sender_phone": BOT_NAME,
                        "kind": "system",
                        "date": today_iso(),
                        "reactions": {},
                        "reply_to_id": "", "reply_to_user": "",
                        "reply_to_text": "",
                    }
                    try:
                        page.pubsub.send_all_on_topic(topic, payload)
                    except Exception:
                        pass

                threading.Timer(secs, _fire).start()
        elif cmd == "/nick":
            new = raw_arg
            if not new or len(new) > 24:
                add_system_locally("Имя: 1–24 символа")
                page.update()
            else:
                my_name[0] = new
                PARTICIPANTS[my_phone[0]]["name"] = new
                update_profile()
                build_sidebar_chats()
                update_header()
                announce_here()
                add_system_locally(f"Вы сменили имя на «{new}»")
                page.update()
        elif cmd == "/me":
            if not raw_arg:
                add_system_locally("Использование: /me <действие>")
                page.update()
            else:
                bot_send(f"{my_name[0]} {raw_arg}", kind="me")
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        elif cmd == "/clear":
            history = history_for_key(active_chat[0])
            history.clear()
            render_active_chat()
            page.update()
        else:
<<<<<<< HEAD
            bot_send(f"Неизвестная команда: {cmd}. Попробуйте /help.", kind="system")
=======
            bot_send(f"Неизвестная команда: {cmd}. Попробуйте /help.",
                     kind="system")
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        return True

    def on_command_menu(cmd: str, needs_arg: bool) -> None:
        if needs_arg:
            message_input.value = cmd + " "
            on_input_change()
            page.update()
        else:
            handle_bot_command(cmd)

    # ============================================================
    # ОТПРАВКА СООБЩЕНИЯ
    # ============================================================
    def send_message(e=None) -> None:
        text = (message_input.value or "").strip()
        if not text or not my_phone[0]:
            return
        if len(text) > MAX_MSG_LEN:
            text = text[:MAX_MSG_LEN]

        if text.startswith("/"):
            if handle_bot_command(text):
                message_input.value = ""
                char_counter.value = f"0/{MAX_MSG_LEN}"
                char_counter.color = ft.Colors.GREY_600
                page.update()
            return

<<<<<<< HEAD
        if active_chat[0] == SUPPORT_KEY:
            user_msg = {
                "id": new_msg_id(), "user": my_name[0], "text": text,
                "timestamp": now_time(), "sender_phone": my_phone[0],
                "kind": "message", "date": today_iso(), "reactions": {},
                "reply_to_id": "", "reply_to_user": "", "reply_to_text": "", "quick": [],
            }
            hist = SUPPORT_HISTORY.setdefault(my_phone[0], [])
            hist.append(user_msg)
            add_message_to_ui(Message.from_dict(user_msg))
            message_input.value = ""
            char_counter.value = f"0/{MAX_MSG_LEN}"
            char_counter.color = ft.Colors.GREY_600
            cancel_reply(update=False)
            page.update()
            threading.Thread(target=_process_support_query,
                             args=(my_phone[0], text), daemon=True).start()
            return

        payload = {
            "id": new_msg_id(), "user": my_name[0], "text": text,
            "timestamp": now_time(), "sender_phone": my_phone[0],
            "kind": "message", "date": today_iso(), "reactions": {},
            "reply_to_id": reply_state["id"],
            "reply_to_user": reply_state["user"],
            "reply_to_text": reply_state["text"], "quick": [],
=======
        payload = {
            "id": new_msg_id(),
            "user": my_name[0],
            "text": text,
            "timestamp": now_time(),
            "sender_phone": my_phone[0],
            "kind": "message",
            "date": today_iso(),
            "reactions": {},
            "reply_to_id": reply_state["id"],
            "reply_to_user": reply_state["user"],
            "reply_to_text": reply_state["text"],
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        }
        key = active_chat[0]
        if key == LOBBY_KEY:
            page.pubsub.send_all_on_topic(LOBBY_KEY, payload)
        else:
            if key not in PARTICIPANTS:
                add_system_locally("Собеседник не в сети — сообщение не отправлено.")
                page.update()
                return
            page.pubsub.send_all_on_topic(dm_topic(my_phone[0], key), payload)

        message_input.value = ""
        char_counter.value = f"0/{MAX_MSG_LEN}"
        char_counter.color = ft.Colors.GREY_600
        cancel_reply(update=False)
        page.update()

    message_input.on_submit = send_message

    def on_input_change(e=None) -> None:
        val = message_input.value or ""
        char_counter.value = f"{len(val)}/{MAX_MSG_LEN}"
        char_counter.color = (ft.Colors.RED_400 if len(val) > MAX_MSG_LEN
                              else ft.Colors.GREY_600)
        if not my_phone[0] or not val.strip() or val.startswith("/"):
            page.update()
            return
<<<<<<< HEAD
        if active_chat[0] == SUPPORT_KEY:
            page.update()
            return
=======
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        now = time.monotonic()
        if now - last_typing_sent[0] < 2.0:
            page.update()
            return
        last_typing_sent[0] = now
        key = active_chat[0]
        topic = LOBBY_KEY if key == LOBBY_KEY else dm_topic(my_phone[0], key)
        page.pubsub.send_others_on_topic(topic, {
<<<<<<< HEAD
            "type": "typing", "name": my_name[0], "sender_phone": my_phone[0],
=======
            "type": "typing", "name": my_name[0],
            "sender_phone": my_phone[0],
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        })
        page.update()

    message_input.on_change = on_input_change

    def go_back(e=None) -> None:
        mobile_show_sidebar[0] = True
        apply_layout()
        page.update()

    back_btn.on_click = go_back

    # ============================================================
<<<<<<< HEAD
    # ДИАЛОГ ВХОДА (без изменений)
    # ============================================================
    name_field = ft.TextField(label="Имя (необязательно)", width=300,
                               border_color=ACCENT, focused_border_color=ACCENT,
                               bgcolor=ft.Colors.GREY_900)
    phone_field = ft.TextField(label="Номер телефона", width=300,
                                hint_text="+7 999 123-45-67",
                                border_color=ACCENT, focused_border_color=ACCENT,
                                bgcolor=ft.Colors.GREY_900,
                                keyboard_type=ft.KeyboardType.PHONE)
    code_field = ft.TextField(label="Код из SMS", width=300, hint_text="000000",
                               border_color=ACCENT, focused_border_color=ACCENT,
                               bgcolor=ft.Colors.GREY_900,
                               keyboard_type=ft.KeyboardType.NUMBER, max_length=6)
=======
    # ДИАЛОГ ВХОДА — двухшаговый: телефон → SMS-код
    # ============================================================
    name_field = ft.TextField(
        label="Имя (необязательно)", width=300,
        border_color=ACCENT, focused_border_color=ACCENT,
        bgcolor=ft.Colors.GREY_900,
    )
    phone_field = ft.TextField(
        label="Номер телефона", width=300,
        hint_text="+7 999 123-45-67",
        border_color=ACCENT, focused_border_color=ACCENT,
        bgcolor=ft.Colors.GREY_900,
        keyboard_type=ft.KeyboardType.PHONE,
    )
    code_field = ft.TextField(
        label="Код из SMS", width=300, hint_text="000000",
        border_color=ACCENT, focused_border_color=ACCENT,
        bgcolor=ft.Colors.GREY_900,
        keyboard_type=ft.KeyboardType.NUMBER, max_length=6,
    )
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    error_text = ft.Text("", size=12, color=ft.Colors.RED_400, visible=False)
    code_notice = ft.Container(
        content=ft.Text("", size=12, color=ft.Colors.AMBER_400),
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_400),
    )

    enter_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.Icons.LOCK_PERSON, color=ACCENT),
<<<<<<< HEAD
            ft.Text("Вход в чат", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        ], spacing=8),
        content=ft.Column([], tight=True, spacing=10),
        actions=[], bgcolor=ft.Colors.GREY_800,
=======
            ft.Text("Вход в чат", weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE),
        ], spacing=8),
        content=ft.Column([], tight=True, spacing=10),
        actions=[],
        bgcolor=ft.Colors.GREY_800,
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    )

    pending = {"phone": None, "name": "", "code": None, "expires": 0.0}
    core_subscribed = [False]

    def subscribe_core() -> None:
        if core_subscribed[0]:
            return
        page.pubsub.subscribe_topic("presence", on_presence)
        page.pubsub.subscribe_topic(LOBBY_KEY, on_chat_message)
        core_subscribed[0] = True

    def set_login_step(step: int, update: bool = True) -> None:
        error_text.value = ""
        error_text.visible = False
        if step == 1:
            enter_dialog.content = ft.Column([
                ft.Text("Введите номер телефона — на него придёт SMS-код. "
                        "Имя можно оставить пустым.",
                        size=12, color=ft.Colors.GREY_400),
                name_field, phone_field, error_text,
            ], tight=True, spacing=10)
            enter_dialog.actions = [
                ft.TextButton("Получить код", on_click=send_code,
                              style=ft.ButtonStyle(color=ACCENT)),
            ]
            name_field.autofocus = True
        else:
            enter_dialog.content = ft.Column([
                ft.Text(f"Код отправлен на {format_phone(pending['phone'])}",
                        size=12, color=ft.Colors.GREY_400),
                code_notice, code_field, error_text,
            ], tight=True, spacing=10)
            enter_dialog.actions = [
                ft.TextButton("Назад", on_click=back_to_step1),
                ft.TextButton("Повторить код", on_click=resend_code),
                ft.TextButton("Войти", on_click=verify_code,
                              style=ft.ButtonStyle(color=ACCENT)),
            ]
            code_field.value = ""
            code_field.autofocus = True
        if update:
            page.update()

    def send_code(e: ft.ControlEvent = None) -> None:
        name = (name_field.value or "").strip()
<<<<<<< HEAD
        phone = normalize_phone(phone_field.value or "")
=======
        raw_phone = phone_field.value or ""
        phone = normalize_phone(raw_phone)
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        if name and len(name) > 24:
            error_text.value = "Имя слишком длинное (макс. 24)"
            error_text.visible = True
            page.update()
            return
        if not phone:
            error_text.value = "Введите корректный номер (10–15 цифр)"
            error_text.visible = True
            page.update()
            return
        if (phone in PARTICIPANTS
                and PARTICIPANTS[phone]["session_id"] != my_session_id):
            error_text.value = "Этот номер уже в сети"
            error_text.visible = True
            page.update()
            return
        code = f"{random.randint(0, 999999):06d}"
<<<<<<< HEAD
        pending.update({"phone": phone, "name": name, "code": code,
                        "expires": time.time() + CODE_TTL})
        PENDING_CODES[phone] = {"code": code, "expires": pending["expires"]}
        code_notice.content.value = (f"Демо-режим: реальная SMS не отправляется.\n"
                                     f"Ваш код: {code}")
=======
        pending["phone"] = phone
        pending["name"] = name
        pending["code"] = code
        pending["expires"] = time.time() + CODE_TTL
        PENDING_CODES[phone] = {"code": code, "expires": pending["expires"]}
        code_notice.content.value = (
            "Демо-режим: реальная SMS не отправляется.\n"
            f"Ваш код: {code}"
        )
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        set_login_step(2)

    def resend_code(e: ft.ControlEvent = None) -> None:
        if not pending["phone"]:
            set_login_step(1)
            return
        code = f"{random.randint(0, 999999):06d}"
        pending["code"] = code
        pending["expires"] = time.time() + CODE_TTL
<<<<<<< HEAD
        PENDING_CODES[pending["phone"]] = {"code": code, "expires": pending["expires"]}
        code_notice.content.value = (f"Демо-режим: реальная SMS не отправляется.\n"
                                     f"Новый код: {code}")
=======
        PENDING_CODES[pending["phone"]] = {"code": code,
                                           "expires": pending["expires"]}
        code_notice.content.value = (
            "Демо-режим: реальная SMS не отправляется.\n"
            f"Новый код: {code}"
        )
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        code_field.value = ""
        error_text.visible = False
        page.update()

    def back_to_step1(e: ft.ControlEvent = None) -> None:
<<<<<<< HEAD
        pending.update({"phone": None, "code": None})
=======
        pending["phone"] = None
        pending["code"] = None
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        set_login_step(1)

    def verify_code(e: ft.ControlEvent = None) -> None:
        if not pending["phone"]:
            set_login_step(1)
            return
        entered = (code_field.value or "").strip()
        if time.time() > pending["expires"]:
            error_text.value = "Код истёк — запросите новый"
            error_text.visible = True
            page.update()
            return
        if entered != pending["code"]:
            error_text.value = "Неверный код"
            error_text.visible = True
            page.update()
            return
        phone = pending["phone"]
        name = pending["name"] or f"Пользователь {phone[-4:]}"
        my_name[0] = name
        my_phone[0] = phone
        PARTICIPANTS[phone] = {"name": name, "session_id": my_session_id}
        PENDING_CODES.pop(phone, None)
        pending.update({"phone": None, "name": "", "code": None, "expires": 0.0})

        update_profile()
        update_online_count()
        build_sidebar_chats()
        logout_btn.visible = True
        subscribe_core()
        page.pop_dialog()

        active_chat[0] = LOBBY_KEY
        unread.clear()
        render_active_chat()
        update_header()
        apply_layout()

        page.pubsub.send_all_on_topic(LOBBY_KEY, {
<<<<<<< HEAD
            "id": new_msg_id(), "user": "Система",
            "text": f"{name} присоединился к чату",
            "timestamp": now_time(), "sender_phone": "",
            "kind": "system", "date": today_iso(),
            "reactions": {}, "reply_to_id": "",
            "reply_to_user": "", "reply_to_text": "",
=======
            "id": new_msg_id(),
            "user": "Система",
            "text": f"{name} присоединился к чату",
            "timestamp": now_time(), "sender_phone": "",
            "kind": "system", "date": today_iso(),
            "reactions": {}, "reply_to_id": "", "reply_to_user": "",
            "reply_to_text": "",
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        })
        announce_hello()
        page.update()

    name_field.on_submit = send_code
    phone_field.on_submit = send_code
    code_field.on_submit = verify_code

    def show_login() -> None:
        name_field.value = ""
        phone_field.value = ""
        code_field.value = ""
        pending.update({"phone": None, "name": "", "code": None, "expires": 0.0})
        set_login_step(1, update=False)
        page.show_dialog(enter_dialog)

    show_login()

    # ============================================================
<<<<<<< HEAD
    # ВЫХОД
=======
    # ВЫХОД / ОТКЛЮЧЕНИЕ
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    # ============================================================
    def do_logout(e=None) -> None:
        name = my_name[0]
        phone = my_phone[0]
        if not phone:
            return
        announce_bye()
        page.pubsub.send_all_on_topic(LOBBY_KEY, {
<<<<<<< HEAD
            "id": new_msg_id(), "user": "Система",
            "text": f"{name} покинул чат",
            "timestamp": now_time(), "sender_phone": "",
            "kind": "system", "date": today_iso(),
            "reactions": {}, "reply_to_id": "",
            "reply_to_user": "", "reply_to_text": "",
=======
            "id": new_msg_id(),
            "user": "Система",
            "text": f"{name} покинул чат",
            "timestamp": now_time(), "sender_phone": "",
            "kind": "system", "date": today_iso(),
            "reactions": {}, "reply_to_id": "", "reply_to_user": "",
            "reply_to_text": "",
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
        })
        PARTICIPANTS.pop(phone, None)
        core_subscribed[0] = False
        try:
            page.pubsub.unsubscribe_all()
        except Exception:
            pass
        my_dm_topics.clear()
        my_phone[0] = None
        my_name[0] = None
        logout_btn.visible = False
        chat_list.controls.clear()
        chats_list.controls.clear()
        rendered_msg_rows.clear()
        cancel_reply(update=False)
        update_profile()
        update_online_count()
        show_login()
        page.update()

    logout_btn.on_click = do_logout

    def on_disconnect(e=None) -> None:
        phone = my_phone[0]
        if not phone:
            return
        PARTICIPANTS.pop(phone, None)
        announce_bye()
        core_subscribed[0] = False
        try:
            page.pubsub.unsubscribe_all()
        except Exception:
            pass

    page.on_disconnect = on_disconnect

<<<<<<< HEAD
=======
    # ============================================================
    # РАСКЛАДКА
    # ============================================================
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
    page.add(ft.Row([sidebar_col, chat_pane], spacing=0, expand=True))
    apply_layout()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
<<<<<<< HEAD
    ft.run(main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)
=======
    ft.run(main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)
>>>>>>> 2bad9eccf5ab814775b5b6815a5ced64390cfc9f
