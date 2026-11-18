import os
import time
from dataclasses import dataclass
from datetime import datetime

import flet as ft

# ============================================================
# НАСТРОЙКА ДЛЯ RENDER (headless-среда)
# ============================================================
# Принудительно включаем веб-сервер, чтобы Flet не пытался
# открыть GUI-окно (на Render дисплея нет)
os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")

# ============================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ (живёт в серверном процессе, одно на всех)
# ============================================================
HISTORY: list[dict] = []          # Задание 4: история сообщений
MAX_HISTORY = 50

# Задание 3: словарь участников {имя: session_id}
PARTICIPANTS: dict[str, str] = {}

# Задание 1: палитра цветов для ников
PALETTE = [
    ft.Colors.BLUE_400, ft.Colors.ORANGE_400, ft.Colors.PURPLE_400,
    ft.Colors.TEAL_400, ft.Colors.PINK_400, ft.Colors.AMBER_400,
    ft.Colors.CYAN_400, ft.Colors.LIME_400,
]


def get_user_color(name: str) -> str:
    """Детерминированный цвет по имени (Задание 1)."""
    return PALETTE[sum(ord(c) for c in name) % len(PALETTE)]


# ============================================================
# МОДЕЛЬ
# ============================================================
@dataclass
class Message:
    user: str
    text: str
    timestamp: str
    type: str = "message"                 # "message" | "typing"
    target_session_id: str | None = None  # Задание 3


# ============================================================
# ОСНОВНОЕ ПРИЛОЖЕНИЕ
# ============================================================
def main(page: ft.Page) -> None:
    page.title = "Flet Chat"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK

    user_name: list[str | None] = [None]
    my_session_id = page.session.id

    # ---------- UI ----------
    chat_list = ft.ListView(expand=True, spacing=10, padding=20, auto_scroll=True)

    message_input = ft.TextField(
        hint_text="Введите сообщение…", expand=True,
        border_color=ft.Colors.BLUE_400, autofocus=True,
    )

    typing_status = ft.Text("", size=12, color=ft.Colors.GREY_500, italic=True)

    # Задание 3: выбор получателя
    recipient_dropdown = ft.Dropdown(
        width=160,
        options=[ft.dropdown.Option("all", "Всем")],
        value="all",
        text_size=14,
        content_padding=8,
    )

    # ---------- Отрисовка сообщения ----------
    def add_message_to_ui(msg: Message) -> None:
        is_own = msg.user == user_name[0]

        # Задание 1: цвет ника
        nick_color = (
            get_user_color(msg.user)
            if msg.user != "Система"
            else ft.Colors.GREY_400
        )

        # Задание 3: пометка приватного сообщения
        private_mark = ""
        if msg.target_session_id:
            target_name = next(
                (n for n, sid in PARTICIPANTS.items()
                 if sid == msg.target_session_id),
                "?",
            )
            private_mark = f" [→ {target_name}]"

        chat_list.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(
                            msg.user + private_mark,
                            weight=ft.FontWeight.BOLD, size=12,
                            color=nick_color,
                        ),
                        ft.Text(msg.timestamp, size=10, color=ft.Colors.GREY_500),
                    ], spacing=8),
                    ft.Text(msg.text, size=14, color=ft.Colors.WHITE_70),
                ], spacing=2),
                bgcolor=ft.Colors.GREEN_900 if is_own else ft.Colors.GREY_900,
                padding=10,
                border_radius=8,
                width=page.width * 0.7 if page.width else 300,
                alignment=(
                    ft.Alignment.CENTER_RIGHT if is_own
                    else ft.Alignment.CENTER_LEFT
                ),
            )
        )

    # ---------- Приём сообщений ----------
    def on_message(msg_data: dict) -> None:
        # Задание 2: обработка индикатора набора
        if msg_data.get("type") == "typing":
            typing_status.value = f"{msg_data['user']} печатает…"
            page.update()
            return

        # Обычное сообщение — сбрасываем индикатор набора
        typing_status.value = ""

        msg = Message(**msg_data)

        # Задание 3: фильтрация приватных
        if msg.target_session_id and msg.target_session_id != my_session_id:
            page.update()
            return

        add_message_to_ui(msg)
        page.update()

    page.pubsub.subscribe(on_message)

    # ---------- Отправка ----------
    last_typing_sent = [0.0]

    def send_message(e: ft.ControlEvent) -> None:
        text = (message_input.value or "").strip()
        if not text or not user_name[0]:
            return

        # Задание 3: определяем адресата
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
        }

        page.pubsub.send_all(payload)

        # Задание 4: сохраняем в историю (только публичные)
        if target_sid is None:
            HISTORY.append(payload)
            if len(HISTORY) > MAX_HISTORY:
                HISTORY[:] = HISTORY[-MAX_HISTORY:]

        message_input.value = ""
        page.update()

    message_input.on_submit = send_message

    # ---------- Задание 2: индикатор «печатает…» ----------
    def on_input_change(e: ft.ControlEvent) -> None:
        if not user_name[0]:
            return
        now = time.monotonic()
        if now - last_typing_sent[0] < 2.0:
            return
        last_typing_sent[0] = now
        page.pubsub.send_others({
            "user": user_name[0],
            "text": "",
            "timestamp": datetime.now().strftime("%H:%M"),
            "type": "typing",
        })

    message_input.on_change = on_input_change

    # ---------- Диалог входа ----------
    name_field = ft.TextField(label="Ваше имя", autofocus=True, width=300)
    enter_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Вход в чат"),
        content=ft.Column([name_field], tight=True),
        actions=[],
    )

    def enter_chat(e: ft.ControlEvent) -> None:
        name = (name_field.value or "").strip()
        if not name:
            return
        user_name[0] = name

        # Задание 3: регистрация участника
        PARTICIPANTS[name] = my_session_id

        # Обновляем выпадающий список (все, кроме себя)
        recipient_dropdown.options = [ft.dropdown.Option("all", "Всем")] + [
            ft.dropdown.Option(n, n) for n in PARTICIPANTS if n != name
        ]

        page.pop_dialog()

        # Задание 4: загружаем историю для новичка
        for hist_msg in HISTORY:
            add_message_to_ui(Message(**hist_msg))

        # Системное сообщение
        sys_payload = {
            "user": "Система",
            "text": f"{name} присоединился к чату",
            "timestamp": datetime.now().strftime("%H:%M"),
            "type": "message",
        }
        page.pubsub.send_all(sys_payload)
        page.update()

    enter_dialog.actions = [ft.Button("Войти", on_click=enter_chat)]
    page.show_dialog(enter_dialog)

    # ---------- Раскладка ----------
    page.add(
        ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.CHAT, color=ft.Colors.GREEN_400),
                    ft.Text("Flet Chat", size=20, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE),
                ]),
                ft.Divider(color=ft.Colors.GREY_700),
                chat_list,
                typing_status,
                ft.Row([
                    message_input,
                    recipient_dropdown,
                    ft.IconButton(ft.Icons.SEND, icon_color=ft.Colors.GREEN,
                                  on_click=send_message),
                ]),
            ], expand=True),
            expand=True,
            padding=10,
        )
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=port)