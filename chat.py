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
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ
# ============================================================
HISTORY: list[dict] = []
MAX_HISTORY = 50

PARTICIPANTS: dict[str, str] = {}       # имя -> session_id
SESSION_NAMES: dict[str, str] = {}      # session_id -> имя

PALETTE = [
    ft.Colors.BLUE_400, ft.Colors.ORANGE_400, ft.Colors.PURPLE_400,
    ft.Colors.TEAL_400, ft.Colors.PINK_400, ft.Colors.AMBER_400,
    ft.Colors.CYAN_400, ft.Colors.LIME_400, ft.Colors.INDIGO_400,
    ft.Colors.DEEP_ORANGE_400,
]

BOT_NAME = "Бот"
BOT_COMMANDS = {
    "/help": "Показать список команд",
    "/users": "Кто сейчас в чате",
    "/time": "Текущее время сервера",
    "/roll": "Случайное число 1–100",
    "/me <действие>": "Эмодзи-действие, например /me машет рукой",
    "/clear": "Очистить ленту у себя",
}

MAX_MSG_LEN = 500


def get_user_color(name: str) -> str:
    return PALETTE[sum(ord(c) for c in name) % len(PALETTE)]


def get_initials(name: str) -> str:
    parts = name.strip().split()
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


# ============================================================
# МОДЕЛЬ
# ============================================================
@dataclass
class Message:
    user: str
    text: str
    timestamp: str
    type: str = "message"
    target_session_id: str | None = None
    date: str = ""


# ============================================================
# ОСНОВНОЕ ПРИЛОЖЕНИЕ
# ============================================================
def main(page: ft.Page) -> None:
    page.title = "Flet Chat"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.GREY_900

    user_name: list[str | None] = [None]
    my_session_id = page.session.id
    last_rendered_date: list[str] = [""]
    last_author: list[str] = [""]
    unread_count: list[int] = [0]
    original_title = "Flet Chat"

    # ---------- Шапка ----------
    online_badge = ft.Container(
        content=ft.Row([
            ft.Container(width=8, height=8, border_radius=4,
                         bgcolor=ft.Colors.GREEN_400),
            ft.Text("0 онлайн", size=12, color=ft.Colors.GREY_300),
        ], spacing=6, tight=True),
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.GREEN_400),
    )

    logout_btn = ft.IconButton(
        ft.Icons.LOGOUT, icon_color=ft.Colors.GREY_400,
        icon_size=20, tooltip="Выйти",
        visible=False,
    )

    header = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(ft.Icons.CHAT_BUBBLE_ROUNDED,
                                color=ft.Colors.WHITE, size=22),
                width=40, height=40, border_radius=12,
                bgcolor=ft.Colors.GREEN_600,
                alignment=ft.Alignment.CENTER,
            ),
            ft.Column([
                ft.Text("Flet Chat", size=18, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE),
                ft.Text("Общайтесь в реальном времени", size=11,
                        color=ft.Colors.GREY_400),
            ], spacing=0, expand=True),
            online_badge,
            logout_btn,
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[ft.Colors.GREY_900, ft.Colors.GREY_800],
        ),
        border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_800)),
    )

    # ---------- Лента ----------
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

    # ---------- Поле ввода ----------
    message_input = ft.TextField(
        hint_text="Введите сообщение…",
        expand=True,
        border_color=ft.Colors.GREY_700,
        focused_border_color=ft.Colors.GREEN_400,
        bgcolor=ft.Colors.GREY_800,
        border_radius=24,
        content_padding=ft.Padding.symmetric(horizontal=18, vertical=14),
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
        on_click=lambda e: send_message(e),
        ink=True,
    )

    recipient_dropdown = ft.Dropdown(
        width=150,
        options=[ft.dropdown.Option("all", "Всем")],
        value="all",
        text_size=13,
        bgcolor=ft.Colors.GREY_800,
        border_color=ft.Colors.GREY_700,
        border_radius=12,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
    )

    input_bar = ft.Container(
        content=ft.Column([
            ft.Row([
                message_input,
                send_btn,
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END),
            ft.Row([
                recipient_dropdown,
                ft.Container(expand=True),
                char_counter,
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=6),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        bgcolor=ft.Colors.GREY_900,
        border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.GREY_800)),
    )

    # ============================================================
    # Отрисовка сообщения
    # ============================================================
    def add_date_separator(d_iso: str) -> None:
        try:
            d = date.fromisoformat(d_iso)
        except ValueError:
            d = date.today()
        chat_list.controls.append(
            ft.Container(
                content=ft.Text(format_date_label(d), size=11,
                                color=ft.Colors.GREY_400),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(vertical=8),
            )
        )

    def make_avatar(name: str, size: int = 36) -> ft.Container:
        color = get_user_color(name) if name != "Система" else ft.Colors.GREY_500
        if name == BOT_NAME:
            color = ft.Colors.INDIGO_400
        return ft.Container(
            content=ft.Text(get_initials(name), size=size // 3,
                            weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            width=size, height=size, border_radius=size // 2,
            bgcolor=color, alignment=ft.Alignment.CENTER,
        )

    def add_message_to_ui(msg: Message) -> None:
        is_own = msg.user == user_name[0]
        is_bot = msg.user == BOT_NAME
        is_system = msg.user == "Система"

        msg_date = msg.date or date.today().isoformat()
        if msg_date != last_rendered_date[0]:
            add_date_separator(msg_date)
            last_rendered_date[0] = msg_date
            last_author[0] = ""

        if is_system:
            chat_list.controls.append(
                ft.Container(
                    content=ft.Text(msg.text, size=11, italic=True,
                                    color=ft.Colors.GREY_500),
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=4),
                )
            )
            last_author[0] = "Система"
            return

        nick_color = (get_user_color(msg.user) if not is_bot
                      else ft.Colors.INDIGO_400)

        private_mark = ""
        if msg.target_session_id:
            target_name = SESSION_NAMES.get(msg.target_session_id, "?")
            private_mark = f"  🔒 → {target_name}"

        show_header = last_author[0] != msg.user
        last_author[0] = msg.user

        bubble_children = []
        if show_header:
            bubble_children.append(
                ft.Row([
                    ft.Text(msg.user + private_mark,
                            weight=ft.FontWeight.BOLD, size=12,
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
            bgcolor=(ft.Colors.GREEN_800 if is_own
                     else ft.Colors.GREY_800 if not is_bot
                     else ft.Colors.INDIGO_900),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=ft.BorderRadius.only(
                top_left=16, top_right=16,
                bottom_left=4 if is_own else 16,
                bottom_right=16 if is_own else 4,
            ),
            width=page.width * 0.72 if page.width else 320,
            shadow=ft.BoxShadow(blur_radius=8, spread_radius=0,
                                color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
                                offset=ft.Offset(0, 2)),
        )

        row = ft.Row(
            [
                ft.Container(expand=True),
                bubble,
                ft.Container(),
            ] if is_own else [
                make_avatar(msg.user) if show_header else ft.Container(width=36),
                bubble,
                ft.Container(expand=True),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.END,
        )

        chat_list.controls.append(row)

    # ============================================================
    # Приём сообщений
    # ============================================================
    def on_message(msg_data: dict) -> None:
        if msg_data.get("type") == "typing":
            if msg_data["user"] == user_name[0]:
                return
            typing_status.content = ft.Row([
                make_avatar(msg_data["user"], size=20),
                ft.Text(f"{msg_data['user']} печатает…",
                        size=11, italic=True, color=ft.Colors.GREY_400),
            ], spacing=6, tight=True)
            typing_status.visible = True
            page.update()
            return

        typing_status.visible = False

        msg = Message(**{k: v for k, v in msg_data.items()
                         if k in Message.__dataclass_fields__})

        if msg.target_session_id and msg.target_session_id != my_session_id:
            page.update()
            return

        add_message_to_ui(msg)

        if msg.user != user_name[0] and msg.user != BOT_NAME:
            unread_count[0] += 1
            page.title = f"({unread_count[0]}) {original_title}"

        page.update()

    page.pubsub.subscribe(on_message)

    # ============================================================
    # Бот
    # ============================================================
    def bot_send(text: str) -> None:
        payload = {
            "user": BOT_NAME,
            "text": text,
            "timestamp": datetime.now().strftime("%H:%M"),
            "type": "message",
            "target_session_id": None,
            "date": date.today().isoformat(),
        }
        page.pubsub.send_all(payload)

    def handle_bot_command(text: str) -> bool:
        low = text.strip().lower()

        if "привет" in low or "hello" in low or "hi" in low.split():
            bot_send(f"Привет, {user_name[0]}! 👋 Напиши /help, чтобы узнать команды.")
            return True

        if not low.startswith("/"):
            return False

        cmd, _, arg = low.partition(" ")
        arg = arg.strip()

        if cmd == "/help":
            lines = ["**Команды:**"] + [f"{k} — {v}" for k, v in BOT_COMMANDS.items()]
            bot_send("\n".join(lines))
        elif cmd == "/users":
            if PARTICIPANTS:
                names = ", ".join(sorted(PARTICIPANTS.keys()))
                bot_send(f"👥 Сейчас в чате ({len(PARTICIPANTS)}): {names}")
            else:
                bot_send("В чате пока никого нет.")
        elif cmd == "/time":
            bot_send(f"🕐 Время сервера: {datetime.now().strftime('%H:%M:%S')}")
        elif cmd == "/roll":
            bot_send(f"🎲 Выпало: {random.randint(1, 100)}")
        elif cmd == "/me":
            if not arg:
                bot_send("Использование: /me <действие>")
            else:
                bot_send(f"✨ *{user_name[0]} {arg}*")
        elif cmd == "/clear":
            chat_list.controls.clear()
            last_rendered_date[0] = ""
            last_author[0] = ""
            page.update()
        else:
            bot_send(f"Неизвестная команда: {cmd}. Попробуй /help.")
        return True

    # ============================================================
    # Отправка
    # ============================================================
    last_typing_sent = [0.0]

    def send_message(e=None) -> None:
        text = (message_input.value or "").strip()
        if not text or not user_name[0]:
            return
        if len(text) > MAX_MSG_LEN:
            text = text[:MAX_MSG_LEN]

        if handle_bot_command(text):
            message_input.value = ""
            char_counter.value = f"0/{MAX_MSG_LEN}"
            page.update()
            return

        target_name = recipient_dropdown.value
        target_sid = None
        if target_name and target_name != "all":
            target_sid = PARTICIPANTS.get(target_name)
            if not target_sid:
                return

        payload = {
            "user": user_name[0],
            "text": text,
            "timestamp": datetime.now().strftime("%H:%M"),
            "type": "message",
            "target_session_id": target_sid,
            "date": date.today().isoformat(),
        }

        page.pubsub.send_all(payload)

        if target_sid is None:
            HISTORY.append(payload)
            if len(HISTORY) > MAX_HISTORY:
                HISTORY[:] = HISTORY[-MAX_HISTORY:]

        message_input.value = ""
        char_counter.value = f"0/{MAX_MSG_LEN}"
        page.update()

    message_input.on_submit = send_message

    def on_input_change(e: ft.ControlEvent) -> None:
        val = message_input.value or ""
        char_counter.value = f"{len(val)}/{MAX_MSG_LEN}"
        if len(val) > MAX_MSG_LEN:
            char_counter.color = ft.Colors.RED_400
        else:
            char_counter.color = ft.Colors.GREY_600

        if not user_name[0] or not val.strip():
            return
        now = time.monotonic()
        if now - last_typing_sent[0] < 2.0:
            page.update()
            return
        last_typing_sent[0] = now
        page.pubsub.send_others({
            "user": user_name[0],
            "text": "",
            "timestamp": datetime.now().strftime("%H:%M"),
            "type": "typing",
        })
        page.update()

    message_input.on_change = on_input_change

    # ============================================================
    # Вход
    # ============================================================
    name_field = ft.TextField(
        label="Ваше имя", autofocus=True, width=300,
        border_color=ft.Colors.GREEN_400,
        focused_border_color=ft.Colors.GREEN_400,
        bgcolor=ft.Colors.GREY_800,
    )
    error_text = ft.Text("", size=12, color=ft.Colors.RED_400, visible=False)

    enter_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.Icons.CHAT_BUBBLE_ROUNDED, color=ft.Colors.GREEN_400),
            ft.Text("Вход в чат", weight=ft.FontWeight.BOLD),
        ], spacing=8),
        content=ft.Column([
            ft.Text("Представьтесь, чтобы начать общение",
                    size=12, color=ft.Colors.GREY_400),
            name_field,
            error_text,
        ], tight=True, spacing=10),
        actions=[],
        bgcolor=ft.Colors.GREY_800,
    )

    def update_online() -> None:
        online_badge.content.controls[1].value = f"{len(PARTICIPANTS)} онлайн"

    def enter_chat(e: ft.ControlEvent) -> None:
        name = (name_field.value or "").strip()
        if not name:
            error_text.value = "Введите имя"
            error_text.visible = True
            page.update()
            return
        if len(name) > 20:
            error_text.value = "Имя слишком длинное (макс. 20)"
            error_text.visible = True
            page.update()
            return
        if name in PARTICIPANTS:
            error_text.value = "Это имя уже занято"
            error_text.visible = True
            page.update()
            return

        user_name[0] = name
        PARTICIPANTS[name] = my_session_id
        SESSION_NAMES[my_session_id] = name
        update_online()

        recipient_dropdown.options = [ft.dropdown.Option("all", "Всем")] + [
            ft.dropdown.Option(n, n) for n in PARTICIPANTS if n != name
        ]
        logout_btn.visible = True

        page.pop_dialog()

        for hist_msg in HISTORY:
            add_message_to_ui(Message(**hist_msg))

        sys_payload = {
            "user": "Система",
            "text": f"👋 {name} присоединился к чату",
            "timestamp": datetime.now().strftime("%H:%M"),
            "type": "message",
            "target_session_id": None,
            "date": date.today().isoformat(),
        }
        page.pubsub.send_all(sys_payload)
        page.update()

    enter_dialog.actions = [
        ft.TextButton("Войти", on_click=enter_chat,
                      style=ft.ButtonStyle(color=ft.Colors.GREEN_400)),
    ]
    name_field.on_submit = enter_chat
    page.show_dialog(enter_dialog)

    # ============================================================
    # Выход
    # ============================================================
    def do_logout(e=None) -> None:
        name = user_name[0]
        if not name:
            return
        PARTICIPANTS.pop(name, None)
        SESSION_NAMES.pop(my_session_id, None)
        user_name[0] = None
        update_online()
        logout_btn.visible = False
        recipient_dropdown.value = "all"
        recipient_dropdown.options = [ft.dropdown.Option("all", "Всем")]
        chat_list.controls.clear()
        last_rendered_date[0] = ""
        last_author[0] = ""
        page.pubsub.send_all({
            "user": "Система",
            "text": f"👋 {name} покинул чат",
            "timestamp": datetime.now().strftime("%H:%M"),
            "type": "message",
            "target_session_id": None,
            "date": date.today().isoformat(),
        })
        name_field.value = ""
        error_text.visible = False
        page.show_dialog(enter_dialog)
        page.update()

    logout_btn.on_click = do_logout

    def on_disconnect(e=None) -> None:
        name = user_name[0]
        if not name:
            return
        PARTICIPANTS.pop(name, None)
        SESSION_NAMES.pop(my_session_id, None)
        page.pubsub.send_all({
            "user": "Система",
            "text": f"👋 {name} отключился",
            "timestamp": datetime.now().strftime("%H:%M"),
            "type": "message",
            "target_session_id": None,
            "date": date.today().isoformat(),
        })

    page.on_disconnect = on_disconnect

    def on_connect(e=None) -> None:
        unread_count[0] = 0
        page.title = original_title

    page.on_connect = on_connect

    # ============================================================
    # Раскладка
    # ============================================================
    page.add(
        ft.Column([
            header,
            chat_list,
            typing_status,
            input_bar,
        ], expand=True, spacing=0)
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.run(main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)
