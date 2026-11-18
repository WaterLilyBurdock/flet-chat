import os
import time
import random
from dataclasses import dataclass
from datetime import datetime, date

import flet as ft

# ============================================================
# НАСТРОЙКА ДЛЯ RENDER (headless-среда)
# ============================================================
os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")

# ============================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ (один процесс — один хаб pubsub)
# ============================================================
# phone -> {"name": str, "session_id": str}
PARTICIPANTS: dict[str, dict] = {}

# История сообщений
LOBBY_HISTORY: list[dict] = []
DM_HISTORY: dict[str, list[dict]] = {}     # topic -> [msg, ...]
MAX_HISTORY = 100

PALETTE = [
    ft.Colors.BLUE_400, ft.Colors.ORANGE_400, ft.Colors.PURPLE_400,
    ft.Colors.TEAL_400, ft.Colors.PINK_400, ft.Colors.AMBER_400,
    ft.Colors.CYAN_400, ft.Colors.LIME_400, ft.Colors.INDIGO_400,
    ft.Colors.DEEP_ORANGE_400,
]

BOT_NAME = "Бот"
LOBBY_KEY = "lobby"

BOT_COMMANDS = {
    "/help": "Показать список команд",
    "/users": "Кто сейчас в чате",
    "/time": "Текущее время сервера",
    "/roll": "Случайное число 1–100",
    "/me <действие>": "Эмодзи-действие, например /me машет рукой",
    "/clear": "Очистить ленту у себя",
}

MAX_MSG_LEN = 500


# ============================================================
# УТИЛИТЫ
# ============================================================
def normalize_phone(raw: str) -> str | None:
    """Приводит телефон к виду +<digits>. Возвращает None, если невалиден."""
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if not digits:
        return None
    # российские правила: 8... -> 7..., 10 цифр -> добить 7 спереди
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if not (10 <= len(digits) <= 15):
        return None
    return "+" + digits


def format_phone(p: str) -> str:
    """Красивое отображение: +7 999 123-45-67."""
    d = p.lstrip("+")
    if len(d) == 11 and d.startswith("7"):
        return f"+7 {d[1:4]} {d[4:7]}-{d[7:9]}-{d[9:11]}"
    return "+" + d


def dm_topic(a: str, b: str) -> str:
    """Общий топик для пары собеседников (порядок не важен)."""
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


# ============================================================
# МОДЕЛЬ СООБЩЕНИЯ
# ============================================================
@dataclass
class Message:
    user: str
    text: str
    timestamp: str
    sender_phone: str = ""        # кто отправил (для выравнивания bubble)
    kind: str = "message"         # message | system | me
    date: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


# ============================================================
# ОСНОВНОЕ ПРИЛОЖЕНИЕ
# ============================================================
def main(page: ft.Page) -> None:
    page.title = "Flet Chat"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.GREY_900

    # --- состояние текущего пользователя ---
    my_phone: list[str | None] = [None]
    my_name: list[str | None] = [None]
    my_session_id = page.session.id
    my_dm_topics: set[str] = set()

    # --- состояние UI ---
    active_chat: list[str] = [LOBBY_KEY]          # "lobby" или телефон собеседника
    unread: dict[str, int] = {}                    # chat_key -> непрочитано
    mobile_show_sidebar: list[bool] = [True]
    last_rendered_date: list[str] = [""]
    last_author: list[str] = [""]
    last_typing_sent = [0.0]

    original_title = "Flet Chat"

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
        bgcolor=ft.Colors.GREEN_600,
        alignment=ft.Alignment.CENTER,
    )

    header_title = ft.Text("Общий чат", size=16,
                           weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    header_subtitle = ft.Text("Все участники", size=11,
                              color=ft.Colors.GREY_400)

    online_badge = ft.Container(
        content=ft.Row([
            ft.Container(width=8, height=8, border_radius=4,
                         bgcolor=ft.Colors.GREEN_400),
            ft.Text("0 онлайн", size=11, color=ft.Colors.GREY_300),
        ], spacing=6, tight=True),
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.GREEN_400),
    )

    # ---------- Меню команд ----------
    def make_cmd_item(label: str, icon, cmd: str, needs_arg: bool):
        return ft.PopupMenuItem(
            content=ft.Text(label, size=13, color=ft.Colors.WHITE),
            icon=icon,
            on_click=lambda e: on_command_menu(cmd, needs_arg),
        )

    commands_menu = ft.PopupMenuButton(
        icon=ft.Icons.MORE_VERT,
        icon_color=ft.Colors.WHITE,
        icon_size=22,
        tooltip="Команды бота",
        items=[
            make_cmd_item("Помощь — /help", ft.Icons.HELP_OUTLINE, "/help", False),
            make_cmd_item("Кто онлайн — /users", ft.Icons.GROUP, "/users", False),
            make_cmd_item("Время сервера — /time", ft.Icons.ACCESS_TIME, "/time", False),
            make_cmd_item("Случайное число — /roll", ft.Icons.CASINO, "/roll", False),
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
        expand=True, spacing=6,
        padding=ft.Padding.symmetric(horizontal=16, vertical=16),
        auto_scroll=True,
    )

    typing_status = ft.Container(
        content=ft.Row([], spacing=6, tight=True),
        padding=ft.Padding.only(left=16, bottom=4),
        visible=False,
    )

    # ============================================================
    # ПОЛЕ ВВОДА
    # ============================================================
    message_input = ft.TextField(
        hint_text="Введите сообщение…",
        expand=True,
        border_color=ft.Colors.GREY_700,
        focused_border_color=ft.Colors.GREEN_400,
        bgcolor=ft.Colors.GREY_800,
        border_radius=22,
        content_padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        multiline=True,
        min_lines=1,
        max_lines=4,
        shift_enter=True,
        autofocus=True,
    )

    char_counter = ft.Text("0/500", size=10, color=ft.Colors.GREY_600)

    send_btn = ft.Container(
        content=ft.Icon(ft.Icons.SEND_ROUNDED, color=ft.Colors.WHITE, size=20),
        width=44, height=44, border_radius=22,
        bgcolor=ft.Colors.GREEN_600,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: send_message(),
        ink=True,
    )

    input_bar = ft.Container(
        content=ft.Column([
            ft.Row([
                message_input,
                send_btn,
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END),
            ft.Row([
                ft.Container(expand=True),
                char_counter,
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=4),
        padding=ft.Padding.symmetric(horizontal=14, vertical=8),
        bgcolor=ft.Colors.GREY_900,
        border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.GREY_800)),
    )

    chat_pane = ft.Container(
        content=ft.Column([
            header,
            chat_list,
            typing_status,
            input_bar,
        ], expand=True, spacing=0),
        expand=True,
        bgcolor=ft.Colors.GREY_900,
    )

    # ============================================================
    # БОКОВАЯ ПАНЕЛЬ (профиль + список чатов)
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

    profile_card = ft.Container(
        content=ft.Row([
            make_avatar("Я", "self", size=40),
            ft.Column([
                ft.Text("Гость", size=14, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE),
                ft.Text("не авторизован", size=11, color=ft.Colors.GREY_400),
            ], spacing=0, expand=True),
            ft.Container(width=8, height=8, border_radius=4,
                         bgcolor=ft.Colors.GREEN_400),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=14, vertical=14),
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_400),
        border_radius=12,
    )

    chats_list = ft.Column(spacing=2, expand=True, scroll=ft.ScrollMode.AUTO)

    sidebar_header = ft.Row([
        ft.Icon(ft.Icons.FORUM, color=ft.Colors.GREEN_400, size=18),
        ft.Text("Чаты", size=12, weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREY_400),
        ft.Container(expand=True),
        online_badge,
    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    sidebar_col = ft.Container(
        content=ft.Column([
            profile_card,
            sidebar_header,
            ft.Divider(height=1, thickness=1, color=ft.Colors.GREY_800),
            chats_list,
        ], spacing=8),
        width=280,
        padding=ft.Padding.only(left=12, right=8, top=12, bottom=12),
        bgcolor=ft.Colors.GREY_900,
        border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.GREY_800)),
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
        if show_header:
            bubble_children.append(
                ft.Row([
                    ft.Text(msg.user, weight=ft.FontWeight.BOLD, size=12,
                            color=nick_color),
                    ft.Text(msg.timestamp, size=10, color=ft.Colors.GREY_500),
                ], spacing=8, tight=True)
            )
        bubble_children.append(
            ft.Text(msg.text, size=14, color=ft.Colors.WHITE,
                    selectable=True)
        )

        bubble = ft.Container(
            content=ft.Column(bubble_children, spacing=2, tight=True),
            bgcolor=ft.Colors.GREEN_800 if is_own else ft.Colors.GREY_800,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=ft.BorderRadius.only(
                top_left=16, top_right=16,
                bottom_left=4 if is_own else 16,
                bottom_right=16 if is_own else 4,
            ),
            max_width=420,
            shadow=ft.BoxShadow(blur_radius=6, spread_radius=0,
                                color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
                                offset=ft.Offset(0, 1)),
        )

        row = ft.Row(
            [
                ft.Container(expand=True),
                bubble,
                ft.Container(),
            ] if is_own else [
                make_avatar(msg.user, msg.sender_phone or msg.user, size=32)
                if show_header else ft.Container(width=32),
                bubble,
                ft.Container(expand=True),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.END,
        )
        chat_list.controls.append(row)

    def render_active_chat() -> None:
        chat_list.controls.clear()
        last_rendered_date[0] = ""
        last_author[0] = ""
        key = active_chat[0]
        if key == LOBBY_KEY:
            msgs = LOBBY_HISTORY
        else:
            topic = dm_topic(my_phone[0], key) if my_phone[0] else ""
            msgs = DM_HISTORY.get(topic, [])
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
            header_icon.bgcolor = ft.Colors.GREEN_600
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

    def build_sidebar_chats() -> None:
        chats_list.controls.clear()
        key = active_chat[0]

        # Общий чат
        def lobby_row():
            active = key == LOBBY_KEY
            return ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.PUBLIC,
                                        color=ft.Colors.WHITE, size=18),
                        width=36, height=36, border_radius=18,
                        bgcolor=ft.Colors.GREEN_600,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column([
                        ft.Text("Общий чат", size=13,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE),
                        ft.Text("Все участники", size=11,
                                color=ft.Colors.GREY_500),
                    ], spacing=0, expand=True),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.GREEN_400)
                if active else None,
                on_click=lambda e: open_chat(LOBBY_KEY),
                ink=True,
            )

        chats_list.controls.append(lobby_row())

        # Контакты онлайн
        others = [p for p in PARTICIPANTS if p != my_phone[0]]
        if others:
            chats_list.controls.append(
                ft.Container(
                    content=ft.Text(f"Контакты онлайн · {len(others)}",
                                    size=11, color=ft.Colors.GREY_500),
                    padding=ft.Padding.only(left=10, top=10, bottom=4),
                )
            )

        for phone in sorted(others, key=lambda p: PARTICIPANTS[p]["name"].lower()):
            info = PARTICIPANTS[phone]
            name = info.get("name", "?")
            active = key == phone
            n_unread = unread.get(phone, 0)

            badge = (ft.Container(
                content=ft.Text(str(n_unread), size=10,
                                color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=10,
                bgcolor=ft.Colors.RED_400,
            ) if n_unread > 0 else ft.Container())

            chats_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        make_avatar(name, phone, size=36),
                        ft.Column([
                            ft.Text(name, size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE),
                            ft.Text(format_phone(phone), size=11,
                                    color=ft.Colors.GREY_500),
                        ], spacing=0, expand=True),
                        badge,
                    ], spacing=10,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.GREEN_400)
                    if active else None,
                    on_click=lambda e, p=phone: open_chat(p),
                    ink=True,
                )
            )

        if not others:
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
        render_active_chat()
        update_header()
        build_sidebar_chats()
        mobile_show_sidebar[0] = False
        apply_layout()
        page.update()

    def apply_layout() -> None:
        is_desktop = (page.width or 0) >= 720
        back_btn.visible = False
        if is_desktop:
            sidebar_col.visible = True
            sidebar_col.width = 280
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
    # ПРИСУТСТВИЕ (presence через топик "presence")
    # ============================================================
    def announce_hello() -> None:
        page.pubsub.send_all_on_topic("presence", {
            "type": "hello",
            "phone": my_phone[0],
            "name": my_name[0],
        })

    def announce_here() -> None:
        page.pubsub.send_all_on_topic("presence", {
            "type": "here",
            "phone": my_phone[0],
            "name": my_name[0],
        })

    def announce_bye() -> None:
        if not my_phone[0]:
            return
        page.pubsub.send_all_on_topic("presence", {
            "type": "bye",
            "phone": my_phone[0],
            "name": my_name[0],
        })

    def on_presence(topic: str, data: dict) -> None:
        t = data.get("type")
        phone = data.get("phone")
        name = data.get("name", "?")
        if not phone or phone == my_phone[0]:
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
    # ПРИЁМ СООБЩЕНИЙ (лобби + личные)
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
        # typing-события
        if data.get("type") == "typing":
            sender = data.get("name", "?")
            sender_phone = data.get("sender_phone", "")
            if sender_phone == my_phone[0]:
                return
            key = chat_key_for_topic(topic)
            if active_chat[0] == key:
                typing_status.content = ft.Row([
                    make_avatar(sender, sender_phone, size=18),
                    ft.Text(f"{sender} печатает…", size=11,
                            italic=True, color=ft.Colors.GREY_400),
                ], spacing=6, tight=True)
                typing_status.visible = True
                page.update()
            return

        # обычное сообщение
        msg = {
            "user": data.get("user", "?"),
            "text": data.get("text", ""),
            "timestamp": data.get("timestamp", now_time()),
            "sender_phone": data.get("sender_phone", ""),
            "kind": data.get("kind", "message"),
            "date": data.get("date", today_iso()),
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

    # подписки на presence и лобби — после определения on_chat_message
    page.pubsub.subscribe_topic("presence", on_presence)
    page.pubsub.subscribe_topic(LOBBY_KEY, on_chat_message)

    # ============================================================
    # БОТ / КОМАНДЫ
    # ============================================================
    def bot_send(text: str, kind: str = "message") -> None:
        payload = {
            "user": BOT_NAME,
            "text": text,
            "timestamp": now_time(),
            "sender_phone": BOT_NAME,
            "kind": kind,
            "date": today_iso(),
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
            "user": "Система", "text": text,
            "timestamp": now_time(),
            "sender_phone": "", "kind": "system",
            "date": today_iso(),
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
        elif cmd == "/time":
            bot_send(f"Время сервера: "
                     f"{datetime.now().strftime('%H:%M:%S')}", kind="system")
        elif cmd == "/roll":
            bot_send(f"🎲 Выпало: {random.randint(1, 100)}")
        elif cmd == "/me":
            if not arg:
                add_system_locally("Использование: /me <действие>")
                page.update()
            else:
                bot_send(f"✨ *{my_name[0]} {arg}*", kind="me")
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
            message_input.focus()
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

        key = active_chat[0]
        payload = {
            "user": my_name[0],
            "text": text,
            "timestamp": now_time(),
            "sender_phone": my_phone[0],
            "kind": "message",
            "date": today_iso(),
        }

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
            "type": "typing",
            "name": my_name[0],
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
    # ДИАЛОГ ВХОДА (имя + телефон)
    # ============================================================
    name_field = ft.TextField(
        label="Ваше имя", autofocus=True, width=300,
        border_color=ft.Colors.GREEN_400,
        focused_border_color=ft.Colors.GREEN_400,
        bgcolor=ft.Colors.GREY_800,
    )
    phone_field = ft.TextField(
        label="Номер телефона", width=300,
        hint_text="+7 999 123-45-67",
        border_color=ft.Colors.GREEN_400,
        focused_border_color=ft.Colors.GREEN_400,
        bgcolor=ft.Colors.GREY_800,
        keyboard_type=ft.KeyboardType.PHONE,
    )
    error_text = ft.Text("", size=12, color=ft.Colors.RED_400, visible=False)

    enter_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.Icons.CHAT_BUBBLE_ROUNDED, color=ft.Colors.GREEN_400),
            ft.Text("Вход в чат", weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE),
        ], spacing=8),
        content=ft.Column([
            ft.Text("Представьтесь и укажите номер телефона — "
                    "по нему вас найдут для личных сообщений.",
                    size=12, color=ft.Colors.GREY_400),
            name_field,
            phone_field,
            error_text,
        ], tight=True, spacing=10),
        actions=[],
        bgcolor=ft.Colors.GREY_800,
    )

    def enter_chat(e: ft.ControlEvent) -> None:
        name = (name_field.value or "").strip()
        raw_phone = phone_field.value or ""
        phone = normalize_phone(raw_phone)

        if not name:
            error_text.value = "Введите имя"
            error_text.visible = True
            page.update()
            return
        if len(name) > 24:
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

        my_name[0] = name
        my_phone[0] = phone
        PARTICIPANTS[phone] = {"name": name, "session_id": my_session_id}

        update_profile()
        update_online_count()
        build_sidebar_chats()
        logout_btn.visible = True
        page.pop_dialog()

        # показываем общий чат
        active_chat[0] = LOBBY_KEY
        unread.clear()
        render_active_chat()
        update_header()
        apply_layout()

        # приветствие системы в лобби
        page.pubsub.send_all_on_topic(LOBBY_KEY, {
            "user": "Система",
            "text": f"👋 {name} присоединился к чату",
            "timestamp": now_time(),
            "sender_phone": "",
            "kind": "system",
            "date": today_iso(),
        })
        # рассылаем присутствие
        announce_hello()
        page.update()

    enter_dialog.actions = [
        ft.TextButton("Войти", on_click=enter_chat,
                      style=ft.ButtonStyle(color=ft.Colors.GREEN_400)),
    ]
    name_field.on_submit = enter_chat
    phone_field.on_submit = enter_chat

    def show_login() -> None:
        name_field.value = ""
        phone_field.value = ""
        error_text.visible = False
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
            "user": "Система",
            "text": f"👋 {name} покинул чат",
            "timestamp": now_time(),
            "sender_phone": "",
            "kind": "system",
            "date": today_iso(),
        })
        PARTICIPANTS.pop(phone, None)
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
        try:
            page.pubsub.unsubscribe_all()
        except Exception:
            pass

    page.on_disconnect = on_disconnect

    # ============================================================
    # РАСКЛАДКА
    # ============================================================
    page.add(
        ft.Row([
            sidebar_col,
            chat_pane,
        ], spacing=0, expand=True)
    )
    apply_layout()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.run(main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)
