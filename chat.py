import os
import ast
import uuid
import json
import time
import random
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, date

import flet as ft

# ============================================================
# НАСТРОЙКА ДЛЯ RENDER (headless-среда)
# ============================================================
os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")

# ============================================================
# ЦВЕТОВАЯ ПАЛИТРА (акцент — телеграмовский синий)
# ============================================================
ACCENT = ft.Colors.BLUE_400
ACCENT_MED = ft.Colors.BLUE_600
ACCENT_DEEP = ft.Colors.BLUE_700
ONLINE_CLR = ft.Colors.GREEN_400

# ============================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ (один процесс — один хаб pubsub)
# ============================================================
PARTICIPANTS: dict[str, dict] = {}          # phone -> {"name", "session_id"}
PENDING_CODES: dict[str, dict] = {}         # phone -> {"code", "expires"}
CODE_TTL = 300

LOBBY_HISTORY: list[dict] = []
DM_HISTORY: dict[str, list[dict]] = {}
MAX_HISTORY = 200

PALETTE = [
    ft.Colors.BLUE_400, ft.Colors.ORANGE_400, ft.Colors.PURPLE_400,
    ft.Colors.TEAL_400, ft.Colors.PINK_400, ft.Colors.AMBER_400,
    ft.Colors.CYAN_400, ft.Colors.LIME_400, ft.Colors.INDIGO_400,
    ft.Colors.DEEP_ORANGE_400,
]

BOT_NAME = "Бот"
LOBBY_KEY = "lobby"

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
}

MAX_MSG_LEN = 500

JOKES = [
    "Программист идёт в магазин: «Купи батон, если будут яйца — возьми десяток». "
    "Возвращается с 10 батонами.",
    "Сколько программистов нужно, чтобы вкрутить лампочку? Ни одного — "
    "это аппаратная проблема.",
    "Есть 10 типов людей: те, кто понимает двоичную систему, и те, кто нет.",
    "Почему программисты путают Хэллоуин и Рождество? Потому что 31 OCT = 25 DEC.",
    "Отлаживать код — это как быть детективом, где ты и убийца.",
    "Сын программиста: «Пап, а почему солнце всходит?» — «Всё работает, не трогай».",
]

QUOTES = [
    "«Простота — залог надёжности.» — Эдсгер Дейкстра",
    "«Сначала заставь работать, затем сделай правильным, затем быстрым.» — Кент Бек",
    "«Лучшее — враг хорошего.» — Вольтер",
    "«Код — это поэзия.» — Неизвестный",
    "«Любой дурак напишет код для компьютера. Хороший программист пишет для людей.» "
    "— Мартин Фаулер",
]

EIGHT_BALL = [
    "Определённо да", "Мои источники говорят: да", "Без сомнений", "Да, точно",
    "Скорее всего", "Спроси позже", "Лучше не рассказывать", "Сейчас неясно",
    "Сконцентрируйся и спроси снова", "Не рассчитывай на это", "Мой ответ — нет",
    "По моим данным — нет", "Очень сомнительно",
]

REACTION_ICONS = [  # key, icon, активный цвет
    ("like", ft.Icons.THUMB_UP, ACCENT),
    ("heart", ft.Icons.FAVORITE, ft.Colors.RED_400),
]


# ============================================================
# УТИЛИТЫ
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
            f"(ощущается {cur['FeelsLikeC']}°C), "
            f"влажность {cur['humidity']}%, ветер {cur['windspeedKmph']} км/ч")


# ============================================================
# МОДЕЛЬ СООБЩЕНИЯ
# ============================================================
@dataclass
class Message:
    user: str
    text: str
    timestamp: str
    sender_phone: str = ""
    kind: str = "message"            # message | system | me
    date: str = ""
    id: str = ""
    reactions: dict = field(default_factory=dict)
    reply_to_id: str = ""
    reply_to_user: str = ""
    reply_to_text: str = ""

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

    # --- состояние пользователя ---
    my_phone: list[str | None] = [None]
    my_name: list[str | None] = [None]
    my_session_id = page.session.id
    my_dm_topics: set[str] = set()

    # --- состояние UI ---
    active_chat: list[str] = [LOBBY_KEY]
    unread: dict[str, int] = {}
    mobile_show_sidebar: list[bool] = [True]
    last_rendered_date: list[str] = [""]
    last_author: list[str] = [""]
    last_typing_sent = [0.0]
    rendered_msg_rows: dict[str, ft.Row] = {}   # msg_id -> строка реакций
    reply_state: dict[str, str] = {"id": "", "user": "", "text": ""}

    # ============================================================
    # ШАПКА ЧАТА
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
            ft.Container(width=8, height=8, border_radius=4,
                         bgcolor=ONLINE_CLR),
            ft.Text("0 онлайн", size=11, color=ft.Colors.GREY_300),
        ], spacing=6, tight=True),
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.15, ONLINE_CLR),
    )

    # ---------- Меню команд ----------
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
            cmd_header("Информация"),
            make_cmd_item("Помощь — /help", ft.Icons.HELP_OUTLINE, "/help", False),
            make_cmd_item("Кто онлайн — /users", ft.Icons.GROUP, "/users", False),
            make_cmd_item("Кто я — /whoami", ft.Icons.PERSON, "/whoami", False),
            make_cmd_item("Статистика — /stats", ft.Icons.BAR_CHART, "/stats", False),
            make_cmd_item("Время — /time", ft.Icons.ACCESS_TIME, "/time", False),
            make_cmd_item("Связь — /ping", ft.Icons.WIFI, "/ping", False),
            cmd_header("Развлечения"),
            make_cmd_item("Число 1–100 — /roll", ft.Icons.CASINO, "/roll", False),
            make_cmd_item("Кубик 1–6 — /dice", ft.Icons.CASINO, "/dice", False),
            make_cmd_item("Орёл/решка — /flip", ft.Icons.FLIP_CAMERA_ANDROID, "/flip", False),
            make_cmd_item("Магический шар — /8ball", ft.Icons.HELP, "/8ball", True),
            make_cmd_item("Выбор из списка — /choose", ft.Icons.LIST, "/choose", True),
            make_cmd_item("Шутка — /joke", ft.Icons.EMOJI_EMOTIONS, "/joke", False),
            make_cmd_item("Цитата — /quote", ft.Icons.FORMAT_QUOTE, "/quote", False),
            cmd_header("Утилиты"),
            make_cmd_item("Калькулятор — /calc", ft.Icons.CALCULATE, "/calc", True),
            make_cmd_item("Погода — /weather", ft.Icons.WB_SUNNY, "/weather", True),
            make_cmd_item("Напоминание — /remind", ft.Icons.NOTIFICATIONS, "/remind", True),
            make_cmd_item("Сменить имя — /nick", ft.Icons.BADGE, "/nick", True),
            make_cmd_item("Действие — /me", ft.Icons.WAVING_HAND, "/me", True),
            make_cmd_item("Очистить ленту — /clear", ft.Icons.CLEAR_ALL, "/clear", False),
        ],
    )

    logout_btn = ft.IconButton(
        ft.Icons.LOGOUT, icon_color=ft.Colors.GREY_300,
        icon_size=20, tooltip="Выйти", visible=False,
    )

    header = ft.Container(
        content=ft.Row([
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
            colors=[ft.Colors.GREY_900, ft.Colors.GREY_800],
        ),
        border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_800)),
    )

    # ============================================================
    # ЛЕНТА СООБЩЕНИЙ
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
                                 weight=ft.FontWeight.BOLD,
                                 max_lines=1,
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
            ft.IconButton(ft.Icons.CLOSE, icon_size=16,
                          icon_color=ft.Colors.GREY_400,
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
        expand=True,
        bgcolor=ft.Colors.GREY_900,
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

    def make_avatar_with_status(name: str, key: str, online: bool,
                                 size: int = 36) -> ft.Control:
        base = make_avatar(name, key, size=size)
        if not online:
            return base
        dot = ft.Container(
            width=size // 4, height=size // 4, border_radius=size // 8,
            bgcolor=ONLINE_CLR,
            border=ft.Border.all(2, ft.Colors.GREY_900),
            right=0, bottom=0,
        )
        return ft.Stack([base, dot], width=size, height=size)

    profile_card = ft.Container(
        content=ft.Row([
            make_avatar("Я", "self", size=40),
            ft.Column([
                ft.Text("Гость", size=14, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE),
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
        ft.Text("Чаты", size=12, weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREY_400),
        ft.Container(expand=True),
        online_badge,
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
    # РЕАКЦИИ И ДЕЙСТВИЯ НА СООБЩЕНИЕ
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
                    ft.Icon(icon, size=12,
                            color=col if active else ft.Colors.GREY_400),
                    ft.Text(str(len(phones)), size=10, color=ft.Colors.WHITE),
                ], spacing=3, tight=True),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.25, col) if active
                        else ft.Colors.GREY_700,
                on_click=lambda e, k=key: toggle_reaction(msg_id, k),
                ink=True,
            ))
        row.visible = bool(row.controls)

    def toggle_reaction(msg_id: str, key: str) -> None:
        if not my_phone[0] or not msg_id:
            return
        k = active_chat[0]
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
                content=ft.Text(format_date_label(d), size=11,
                                color=ft.Colors.GREY_500),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(vertical=8),
            )
        )

    def add_message_to_ui(msg: Message) -> None:
        is_own = msg.sender_phone == my_phone[0] and msg.kind != "system"
        is_system = msg.kind in ("system", "me")

        msg_date = msg.date or today_iso()
        if msg_date != last_rendered_date[0]:
            add_date_separator(msg_date)
            last_rendered_date[0] = msg_date
            last_author[0] = ""

        if is_system:
            chat_list.controls.append(
                ft.Container(
                    content=ft.Text(msg.text, size=12, italic=True,
                                    color=ft.Colors.GREY_400),
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=4),
                )
            )
            last_author[0] = "Система"
            return

        nick_color = get_user_color(msg.sender_phone or msg.user)
        show_header = last_author[0] != msg.sender_phone
        last_author[0] = msg.sender_phone

        bubble_children = []

        # цитата ответа
        if msg.reply_to_id:
            bubble_children.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(msg.reply_to_user or "Сообщение",
                                size=11, weight=ft.FontWeight.BOLD,
                                color=ACCENT),
                        ft.Text(msg.reply_to_text or "", size=11,
                                color=ft.Colors.GREY_400, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=0, tight=True),
                    padding=ft.Padding.only(left=8, top=2, bottom=2, right=4),
                    border=ft.Border.only(left=ft.BorderSide(2, ACCENT)),
                    border_radius=4,
                    margin=ft.Margin.only(bottom=4),
                )
            )

        # шапка (автор + время)
        if show_header:
            header_controls = []
            if is_own:
                header_controls.append(ft.Container(
                    content=ft.Text("Вы", size=9, color=ft.Colors.WHITE,
                                    weight=ft.FontWeight.BOLD),
                    padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                    border_radius=6, bgcolor=ACCENT_MED,
                ))
            header_controls.append(ft.Text(
                msg.user, weight=ft.FontWeight.BOLD, size=12,
                color=ACCENT if is_own else nick_color))
            header_controls.append(ft.Text(msg.timestamp, size=10,
                                           color=ft.Colors.GREY_500))
            bubble_children.append(ft.Row(header_controls, spacing=8, tight=True))

        bubble_children.append(
            ft.Text(msg.text, size=14, color=ft.Colors.WHITE, selectable=True)
        )

        # строка реакций (всегда создаётся, заполняется по наличию)
        reactions_row = ft.Row([], spacing=4, tight=True, visible=False)
        fill_reactions(reactions_row, msg.reactions, msg.id)
        if msg.id:
            rendered_msg_rows[msg.id] = reactions_row
        bubble_children.append(reactions_row)

        bubble = ft.Container(
            content=ft.Column(bubble_children, spacing=2, tight=True),
            bgcolor=ACCENT_DEEP if is_own else ft.Colors.GREY_800,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=ft.BorderRadius.only(
                top_left=16, top_right=16, bottom_left=4, bottom_right=16,
            ),
            max_width=480,
            shadow=ft.BoxShadow(blur_radius=4, spread_radius=0,
                                color=ft.Colors.with_opacity(0.15, ft.Colors.BLACK),
                                offset=ft.Offset(0, 1)),
        )

        avatar = (make_avatar_with_status(msg.user, msg.sender_phone or msg.user,
                                           online=False, size=32)
                  if show_header else ft.Container(width=32))
        menu = make_msg_menu(msg) if msg.kind == "message" else ft.Container()

        row = ft.Row(
            [avatar, bubble, menu],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        chat_list.controls.append(row)

    def render_active_chat() -> None:
        chat_list.controls.clear()
        rendered_msg_rows.clear()
        last_rendered_date[0] = ""
        last_author[0] = ""
        key = active_chat[0]
        if key == LOBBY_KEY:
            msgs = LOBBY_HISTORY
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
    # ОБНОВЛЕНИЕ ШАПКИ И БОКОВОЙ ПАНЕЛИ
    # ============================================================
    def update_header() -> None:
        key = active_chat[0]
        if key == LOBBY_KEY:
            header_icon.content = ft.Icon(ft.Icons.PUBLIC,
                                          color=ft.Colors.WHITE, size=20)
            header_icon.bgcolor = ACCENT_MED
            header_title.value = "Общий чат"
            header_subtitle.value = "Все участники"
        else:
            info = PARTICIPANTS.get(key, {})
            name = info.get("name", "?")
            header_icon.content = ft.Text(get_initials(name), size=12,
                                          weight=ft.FontWeight.BOLD,
                                          color=ft.Colors.WHITE)
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
        else:
            topic = dm_topic(my_phone[0], key) if my_phone[0] else ""
            hist = DM_HISTORY.get(topic, [])
        if not hist:
            return None, None
        m = hist[-1]
        txt = m.get("text", "")
        if m.get("kind") == "me":
            preview = f"{m.get('user', '')} {txt}"
        elif m.get("sender_phone") == my_phone[0]:
            preview = "Вы: " + txt
        else:
            preview = txt
        preview = (preview[:30] + "…") if len(preview) > 30 else preview
        return preview, m.get("timestamp", "")

    def build_sidebar_chats() -> None:
        chats_list.controls.clear()
        key = active_chat[0]

        def chat_row(icon_or_avatar, title, preview, time_text, n_unread,
                     active, on_click):
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
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True),
                    ], spacing=1, expand=True),
                    ft.Column([
                        ft.Text(time_text, size=10, color=ft.Colors.GREY_500),
                        badge,
                    ], spacing=4,
                       horizontal_alignment=ft.CrossAxisAlignment.END),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.18, ACCENT) if active else None,
                on_click=on_click, ink=True,
            )

        # Общий чат
        l_preview, l_time = last_msg_for_key(LOBBY_KEY)
        chats_list.controls.append(chat_row(
            ft.Container(content=ft.Icon(ft.Icons.PUBLIC,
                                         color=ft.Colors.WHITE, size=18),
                         width=36, height=36, border_radius=18,
                         bgcolor=ACCENT_MED, alignment=ft.Alignment.CENTER),
            "Общий чат", l_preview or "Нет сообщений", l_time or "",
            unread.get(LOBBY_KEY, 0), key == LOBBY_KEY,
            lambda e: open_chat(LOBBY_KEY),
        ))

        # Контакты
        others = [p for p in PARTICIPANTS if p != my_phone[0]]
        if others:
            chats_list.controls.append(
                ft.Container(
                    content=ft.Text(f"Контакты · {len(others)}",
                                    size=11, color=ft.Colors.GREY_500),
                    padding=ft.Padding.only(left=10, top=10, bottom=4),
                )
            )
            for phone in sorted(others,
                                key=lambda p: PARTICIPANTS[p]["name"].lower()):
                info = PARTICIPANTS[phone]
                name = info.get("name", "?")
                c_preview, c_time = last_msg_for_key(phone)
                chats_list.controls.append(chat_row(
                    make_avatar_with_status(name, phone,
                                            online=phone in PARTICIPANTS, size=36),
                    name, c_preview or format_phone(phone), c_time or "",
                    unread.get(phone, 0), key == phone,
                    lambda e, p=phone: open_chat(p),
                ))
        else:
            chats_list.controls.append(
                ft.Container(
                    content=ft.Text("Пока никого нет в сети.\n"
                                    "Пригласите друга войти!",
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
    # ПРИСУТСТВИЕ
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
            PARTICIPANTS[phone] = {"name": name,
                                   "session_id": data.get("session_id", "")}
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

    # ============================================================
    # ПРИЁМ СООБЩЕНИЙ (лобби + личные + реакции)
    # ============================================================
    def chat_key_for_topic(topic: str) -> str:
        if topic == LOBBY_KEY:
            return LOBBY_KEY
        body = topic[len("dm:"):]
        a, _, b = body.partition("_")
        if a == my_phone[0]:
            return b
        return a

    def history_for_key(key: str) -> list[dict]:
        if key == LOBBY_KEY:
            return LOBBY_HISTORY
        topic = dm_topic(my_phone[0], key) if my_phone[0] else ""
        return DM_HISTORY.setdefault(topic, [])

    def on_chat_message(topic: str, data: dict) -> None:
        if not my_phone[0]:
            return

        # реакция на сообщение
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
                        page.update()
                    elif active_chat[0] != key:
                        build_sidebar_chats()
                        page.update()
                    break
            return

        # индикатор набора
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

        # обычное сообщение
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

    def add_system_locally(text: str) -> None:
        msg = {
            "id": new_msg_id(),
            "user": "Система", "text": text,
            "timestamp": now_time(), "sender_phone": "",
            "kind": "system", "date": today_iso(),
            "reactions": {}, "reply_to_id": "", "reply_to_user": "",
            "reply_to_text": "",
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

        if cmd == "/help":
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
        elif cmd == "/ping":
            bot_send("понг", kind="system")
        elif cmd == "/roll":
            bot_send(f"Выпало: {random.randint(1, 100)}")
        elif cmd == "/dice":
            bot_send(f"Кубик: {random.randint(1, 6)}")
        elif cmd == "/flip":
            bot_send(random.choice(["Орёл", "Решка"]))
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
        elif cmd == "/joke":
            bot_send(random.choice(JOKES), kind="system")
        elif cmd == "/quote":
            bot_send(random.choice(QUOTES), kind="system")
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
        elif cmd == "/clear":
            history = history_for_key(active_chat[0])
            history.clear()
            render_active_chat()
            page.update()
        else:
            bot_send(f"Неизвестная команда: {cmd}. Попробуйте /help.",
                     kind="system")
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
        now = time.monotonic()
        if now - last_typing_sent[0] < 2.0:
            page.update()
            return
        last_typing_sent[0] = now
        key = active_chat[0]
        topic = LOBBY_KEY if key == LOBBY_KEY else dm_topic(my_phone[0], key)
        page.pubsub.send_others_on_topic(topic, {
            "type": "typing", "name": my_name[0],
            "sender_phone": my_phone[0],
        })
        page.update()

    message_input.on_change = on_input_change

    def go_back(e=None) -> None:
        mobile_show_sidebar[0] = True
        apply_layout()
        page.update()

    back_btn.on_click = go_back

    # ============================================================
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
            ft.Text("Вход в чат", weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE),
        ], spacing=8),
        content=ft.Column([], tight=True, spacing=10),
        actions=[],
        bgcolor=ft.Colors.GREY_800,
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
        raw_phone = phone_field.value or ""
        phone = normalize_phone(raw_phone)
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
        pending["phone"] = phone
        pending["name"] = name
        pending["code"] = code
        pending["expires"] = time.time() + CODE_TTL
        PENDING_CODES[phone] = {"code": code, "expires": pending["expires"]}
        code_notice.content.value = (
            "Демо-режим: реальная SMS не отправляется.\n"
            f"Ваш код: {code}"
        )
        set_login_step(2)

    def resend_code(e: ft.ControlEvent = None) -> None:
        if not pending["phone"]:
            set_login_step(1)
            return
        code = f"{random.randint(0, 999999):06d}"
        pending["code"] = code
        pending["expires"] = time.time() + CODE_TTL
        PENDING_CODES[pending["phone"]] = {"code": code,
                                           "expires": pending["expires"]}
        code_notice.content.value = (
            "Демо-режим: реальная SMS не отправляется.\n"
            f"Новый код: {code}"
        )
        code_field.value = ""
        error_text.visible = False
        page.update()

    def back_to_step1(e: ft.ControlEvent = None) -> None:
        pending["phone"] = None
        pending["code"] = None
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
            "id": new_msg_id(),
            "user": "Система",
            "text": f"{name} присоединился к чату",
            "timestamp": now_time(), "sender_phone": "",
            "kind": "system", "date": today_iso(),
            "reactions": {}, "reply_to_id": "", "reply_to_user": "",
            "reply_to_text": "",
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
    # ВЫХОД / ОТКЛЮЧЕНИЕ
    # ============================================================
    def do_logout(e=None) -> None:
        name = my_name[0]
        phone = my_phone[0]
        if not phone:
            return
        announce_bye()
        page.pubsub.send_all_on_topic(LOBBY_KEY, {
            "id": new_msg_id(),
            "user": "Система",
            "text": f"{name} покинул чат",
            "timestamp": now_time(), "sender_phone": "",
            "kind": "system", "date": today_iso(),
            "reactions": {}, "reply_to_id": "", "reply_to_user": "",
            "reply_to_text": "",
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

    # ============================================================
    # РАСКЛАДКА
    # ============================================================
    page.add(ft.Row([sidebar_col, chat_pane], spacing=0, expand=True))
    apply_layout()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.run(main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)
