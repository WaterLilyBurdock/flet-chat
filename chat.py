import os
import ast
import uuid
import json
import time
import random
import re
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, date

import flet as ft
import requests
from openai import OpenAI

# ============================================================
# НАСТРОЙКА ДЛЯ RENDER (headless-среда)
# ============================================================
os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")

# ============================================================
# ЦВЕТОВАЯ ПАЛИТРА
# ============================================================
ACCENT = ft.Colors.BLUE_400
ACCENT_MED = ft.Colors.BLUE_600
ACCENT_DEEP = ft.Colors.BLUE_700
ONLINE_CLR = ft.Colors.GREEN_400
SUPPORT_CLR = ft.Colors.CYAN_400

# ============================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ
# ============================================================
PARTICIPANTS: dict[str, dict] = {}
PENDING_CODES: dict[str, dict] = {}
CODE_TTL = 300

LOBBY_HISTORY: list[dict] = []
DM_HISTORY: dict[str, list[dict]] = {}
SUPPORT_HISTORY: dict[str, list[dict]] = {}
SUPPORT_CONTEXT: dict[str, list[dict]] = {}
MAX_HISTORY = 200
MAX_SUPPORT_HISTORY = 300
MAX_CONTEXT_MESSAGES = 20

PALETTE = [
    ft.Colors.BLUE_400, ft.Colors.ORANGE_400, ft.Colors.PURPLE_400,
    ft.Colors.TEAL_400, ft.Colors.PINK_400, ft.Colors.AMBER_400,
    ft.Colors.CYAN_400, ft.Colors.LIME_400, ft.Colors.INDIGO_400,
    ft.Colors.DEEP_ORANGE_400,
]

BOT_NAME = "Бот"
SUPPORT_NAME = "🛟 Ассистент"
LOBBY_KEY = "lobby"
SUPPORT_KEY = "support"

# ============================================================
# НАСТРОЙКИ ИИ-АГЕНТА (GigaChat)
# ============================================================
# Authorization Key из личного кабинета GigaChat (Studio)
# НЕ Client Secret! Authorization Key = Base64(Client ID:Client Secret)
GIGACHAT_AUTH_KEY = os.environ.get("GIGACHAT_AUTH_KEY", "")

GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_API_URL = "https://api.giga.chat/v1"
AI_MODEL = "GigaChat"

_gigachat_token = {"access_token": None, "expires_at": 0.0}


def get_gigachat_token() -> str | None:
    """Получает или обновляет Access Token GigaChat (живёт 30 минут)."""
    global _gigachat_token
    if (_gigachat_token["access_token"]
            and time.time() < _gigachat_token["expires_at"] - 60):
        return _gigachat_token["access_token"]

    if not GIGACHAT_AUTH_KEY:
        print("⚠️ GIGACHAT_AUTH_KEY не задан.")
        return None

    try:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {GIGACHAT_AUTH_KEY}",
        }
        data = {"scope": "GIGACHAT_API_PERS"}
        resp = requests.post(GIGACHAT_AUTH_URL, headers=headers,
                             data=data, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        _gigachat_token["access_token"] = payload["access_token"]
        _gigachat_token["expires_at"] = time.time() + 1800
        return _gigachat_token["access_token"]
    except Exception as e:
        print(f"[GIGACHAT AUTH ERROR] {e}")
        return None


SUPPORT_SYSTEM_PROMPT = """Ты — ИИ-ассистент технической поддержки чат-приложения. Отвечай кратко, дружелюбно, по делу. Если вопрос не по теме приложения — вежливо верни к теме.

О приложении:
- Вход по номеру телефона + 6-значный код (демо: код показывается на экране).
- Команды бота: /help, /users, /whoami, /stats, /time, /roll, /dice, /flip, /8ball, /choose, /joke, /quote, /calc, /weather, /remind, /nick, /me, /clear.
- Личные сообщения: сайдбар → Контакты → нажать на имя.
- Выход: иконка 🚪 в шапке.
- Мобильная версия: кнопка «←» возвращает к списку чатов.
- Данные хранятся в памяти и пропадают при перезапуске сервера.

Правила:
1. Если не знаешь ответа — предложи написать /human для связи с оператором.
2. Не выдумывай функций, которых нет.
3. Если пользователь злится или проблема серьёзная — сразу предложи /human.
4. Отвечай на русском.
"""

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
    "/support": "Открыть чат техподдержки",
    "/human": "Позвать живого оператора",
    "/reset_support": "Сбросить диалог с поддержкой",
}

MAX_MSG_LEN = 500

JOKES = [
    "Программист идёт в магазин: «Купи батон, если будут яйца — возьми десяток». Возвращается с 10 батонами.",
    "Сколько программистов нужно, чтобы вкрутить лампочку? Ни одного — это аппаратная проблема.",
    "Есть 10 типов людей: те, кто понимает двоичную систему, и те, кто нет.",
    "Почему программисты путают Хэллоуин и Рождество? Потому что 31 OCT = 25 DEC.",
]

QUOTES = [
    "«Простота — залог надёжности.» — Эдсгер Дейкстра",
    "«Сначала заставь работать, затем сделай правильным, затем быстрым.» — Кент Бек",
]

EIGHT_BALL = [
    "Определённо да", "Мои источники говорят: да", "Без сомнений", "Да, точно",
    "Скорее всего", "Спроси позже", "Лучше не рассказывать", "Сейчас неясно",
    "Сконцентрируйся и спроси снова", "Не рассчитывай на это", "Мой ответ — нет",
]

REACTION_ICONS = [
    ("like", ft.Icons.THUMB_UP, ACCENT),
    ("heart", ft.Icons.FAVORITE, ft.Colors.RED_400),
]

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
    "Опишите проблему подробнее — оператор увидит историю."
)


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
            f"(ощущается {cur['FeelsLikeC']}°C), влажность {cur['humidity']}%, "
            f"ветер {cur['windspeedKmph']} км/ч")


# ============================================================
# ИИ-АГЕНТ ТЕХПОДДЕРЖКИ (GigaChat API)
# ============================================================
def ai_support_answer(phone: str, user_text: str) -> tuple[str, bool]:
    token = get_gigachat_token()
    if not token:
        return ("ИИ-поддержка временно недоступна (ошибка авторизации GigaChat).\n"
                "Напишите `/human` — оператор свяжется с вами.", True)

    client = OpenAI(api_key=token, base_url=GIGACHAT_API_URL)

    ctx = SUPPORT_CONTEXT.setdefault(phone, [])
    ctx.append({"role": "user", "content": user_text})
    if len(ctx) > MAX_CONTEXT_MESSAGES:
        ctx[:] = ctx[-MAX_CONTEXT_MESSAGES:]

    messages = [{"role": "system", "content": SUPPORT_SYSTEM_PROMPT}] + ctx

    try:
        resp = client.chat.completions.create(
            model=AI_MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=600,
        )
        answer = (resp.choices[0].message.content or "").strip()
        ctx.append({"role": "assistant", "content": answer})
        if len(ctx) > MAX_CONTEXT_MESSAGES:
            ctx[:] = ctx[-MAX_CONTEXT_MESSAGES:]

        escalate = any(w in answer.lower() for w in
                       ["оператор", "человек", "не могу помочь", "не знаю",
                        "/human", "передам"])
        return answer, escalate
    except Exception as e:
        print(f"[GIGACHAT API ERROR] {e}")
        return (SUPPORT_FALLBACK, False)


@dataclass
class Message:
    user: str
    text: str
    timestamp: str
    sender_phone: str = ""
    kind: str = "message"
    date: str = ""
    id: str = ""
    reactions: dict = field(default_factory=dict)
    reply_to_id: str = ""
    reply_to_user: str = ""
    reply_to_text: str = ""
    quick: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


# ============================================================
# ОСНОВНОЙ КОД UI / ЧАТА
# ============================================================
def main(page: ft.Page) -> None:
    page.title = "Чат"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.GREY_900

    # ---- Состояние страницы ----
    page.session.set("phone", None)
    page.session.set("name", None)
    page.session.set("active_chat", LOBBY_KEY)
    page.session.set("auth_step", "phone")
    page.session.set("pending_phone", None)

    # ---- UI-контейнеры ----
    root = ft.Column(expand=True, spacing=0)
    page.add(root)

    def show_login():
        root.controls.clear()
        root.controls.append(build_login_view())
        page.update()

    def show_chat():
        root.controls.clear()
        root.controls.append(build_chat_view())
        page.update()

    # ---- Логин ----
    def build_login_view():
        phone_field = ft.TextField(
            label="Номер телефона",
            hint_text="+7 999 123-45-67",
            width=320,
            keyboard_type=ft.KeyboardType.PHONE,
        )
        code_field = ft.TextField(
            label="Код из SMS",
            hint_text="6 цифр",
            width=320,
            keyboard_type=ft.KeyboardType.NUMBER,
            max_length=6,
            visible=False,
        )
        status = ft.Text("", color=ft.Colors.RED_400, size=13)
        info = ft.Text("", color=ft.Colors.GREY_400, size=12)
        send_btn = ft.ElevatedButton("Получить код", width=320)
        verify_btn = ft.ElevatedButton("Войти", width=320, visible=False)

        def on_send(e):
            raw = phone_field.value or ""
            phone = normalize_phone(raw)
            if not phone:
                status.value = "Неверный номер. Введите 10–15 цифр."
                page.update()
                return
            code = f"{random.randint(0, 999999):06d}"
            PENDING_CODES[phone] = {"code": code, "exp": time.time() + CODE_TTL}
            page.session.set("pending_phone", phone)
            page.session.set("auth_step", "code")
            status.value = ""
            info.value = f"Демо-код: {code}"
            phone_field.disabled = True
            send_btn.visible = False
            code_field.visible = True
            verify_btn.visible = True
            page.update()

        def on_verify(e):
            phone = page.session.get("pending_phone")
            entry = PENDING_CODES.get(phone)
            if not entry or time.time() > entry["exp"]:
                status.value = "Код истёк. Запросите новый."
                page.update()
                return
            if (code_field.value or "").strip() != entry["code"]:
                status.value = "Неверный код."
                page.update()
                return

            del PENDING_CODES[phone]
            name = f"User_{phone[-4:]}"
            PARTICIPANTS[phone] = {"name": name, "phone": phone, "joined": now_time()}
            page.session.set("phone", phone)
            page.session.set("name", name)
            show_chat()

        send_btn.on_click = on_send
        verify_btn.on_click = on_verify

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Вход в чат", size=28, weight=ft.FontWeight.BOLD),
                    ft.Text("Введите номер — получите код", color=ft.Colors.GREY_400, size=13),
                    ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                    phone_field,
                    code_field,
                    info,
                    status,
                    send_btn,
                    verify_btn,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
            alignment=ft.alignment.center,
            expand=True,
        )

    # ---- Чат ----
    def build_chat_view():
        phone = page.session.get("phone")
        my_name = page.session.get("name") or "User"

        # --- Сайдбар ---
        contacts_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)
        sidebar = ft.Container(
            content=ft.Column(
                [
                    ft.Text("💬 Чаты", size=18, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=10),
                    contacts_col,
                ],
                spacing=6,
            ),
            width=220,
            bgcolor=ft.Colors.GREY_850,
            padding=12,
            border_radius=ft.border_radius.only(top_right=12, bottom_right=12),
        )

        def refresh_contacts():
            contacts_col.controls.clear()
            # Лобби
            lobby_btn = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.GROUP, color=ACCENT, size=20),
                    ft.Text("Общий чат", size=14, color=ft.Colors.WHITE),
                ], spacing=8),
                padding=ft.padding.symmetric(horizontal=8, vertical=10),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.15, ACCENT) if page.session.get("active_chat") == LOBBY_KEY else None,
                on_click=lambda e: switch_chat(LOBBY_KEY),
            )
            contacts_col.controls.append(lobby_btn)

            # Поддержка
            support_btn = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SUPPORT_AGENT, color=SUPPORT_CLR, size=20),
                    ft.Text(SUPPORT_NAME, size=14, color=ft.Colors.WHITE),
                ], spacing=8),
                padding=ft.padding.symmetric(horizontal=8, vertical=10),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.15, SUPPORT_CLR) if page.session.get("active_chat") == SUPPORT_KEY else None,
                on_click=lambda e: switch_chat(SUPPORT_KEY),
            )
            contacts_col.controls.append(support_btn)

            # Контакты (ЛС)
            others = [(p, d) for p, d in PARTICIPANTS.items() if p != phone]
            if others:
                contacts_col.controls.append(ft.Text("Контакты", size=11, color=ft.Colors.GREY_500))
            for p, d in others:
                topic = dm_topic(phone, p)
                is_active = page.session.get("active_chat") == topic
                avatar = ft.CircleAvatar(
                    content=ft.Text(get_initials(d["name"]), size=11, color=ft.Colors.WHITE),
                    bgcolor=get_user_color(p),
                    radius=16,
                )
                row = ft.Container(
                    content=ft.Row([
                        avatar,
                        ft.Column([
                            ft.Text(d["name"], size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
                            ft.Text(d.get("joined", ""), size=10, color=ft.Colors.GREY_500),
                        ], spacing=0),
                    ], spacing=8),
                    padding=ft.padding.symmetric(horizontal=8, vertical=6),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.12, ACCENT) if is_active else None,
                    on_click=lambda e, t=topic: switch_chat(t),
                )
                contacts_col.controls.append(row)
            page.update()

        # --- Лента сообщений ---
        messages_list = ft.ListView(
            expand=True,
            spacing=6,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            auto_scroll=True,
        )

        # --- Поле ввода ---
        input_field = ft.TextField(
            hint_text="Сообщение…",
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=4,
            shift_enter=True,
            border_radius=20,
            filled=True,
            bgcolor=ft.Colors.GREY_800,
        )
        send_btn = ft.IconButton(
            icon=ft.Icons.SEND,
            icon_color=ACCENT,
            icon_size=22,
            tooltip="Отправить",
        )

        # --- Шапка ---
        chat_title = ft.Text("Общий чат", size=16, weight=ft.FontWeight.BOLD)
        back_btn = ft.IconButton(ft.Icons.ARROW_BACK, visible=False, on_click=lambda e: switch_chat(LOBBY_KEY))
        logout_btn = ft.IconButton(ft.Icons.LOGOUT, tooltip="Выйти", on_click=lambda e: do_logout())

        header = ft.Container(
            content=ft.Row([
                back_btn,
                chat_title,
                ft.Container(expand=True),
                logout_btn,
            ], spacing=4),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            bgcolor=ft.Colors.GREY_850,
            border_radius=ft.border_radius.only(top_left=12, top_right=12),
        )

        # --- Основная область ---
        chat_area = ft.Column(
            [header, messages_list, ft.Container(
                content=ft.Row([input_field, send_btn], spacing=6),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                bgcolor=ft.Colors.GREY_850,
            )],
            expand=True,
            spacing=0,
        )

        main_row = ft.Row([sidebar, chat_area], expand=True, spacing=0)

        # ---- Логика сообщений ----
        def get_history(key: str) -> list[dict]:
            if key == LOBBY_KEY:
                return LOBBY_HISTORY
            if key == SUPPORT_KEY:
                return SUPPORT_HISTORY.setdefault(phone, [])
            return DM_HISTORY.setdefault(key, [])

        def add_message(key: str, user: str, text: str, sender_phone: str = "",
                        kind: str = "message", quick: list | None = None):
            hist = get_history(key)
            msg = Message(
                user=user, text=text, timestamp=now_time(),
                sender_phone=sender_phone, kind=kind,
                date=today_iso(), id=new_msg_id(),
                quick=quick or [],
            )
            hist.append(msg.__dict__)
            if len(hist) > (MAX_SUPPORT_HISTORY if key == SUPPORT_KEY else MAX_HISTORY):
                hist[:] = hist[-(MAX_SUPPORT_HISTORY if key == SUPPORT_KEY else MAX_HISTORY):]
            render_messages()

        def render_messages():
            key = page.session.get("active_chat")
            hist = get_history(key)
            messages_list.controls.clear()

            last_date = None
            for m in hist:
                m_date = m.get("date", "")
                if m_date and m_date != last_date:
                    last_date = m_date
                    label = format_date_label(date.fromisoformat(m_date))
                    messages_list.controls.append(
                        ft.Container(
                            content=ft.Text(label, size=11, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
                            alignment=ft.alignment.center,
                            padding=ft.padding.symmetric(vertical=4),
                        )
                    )

                is_mine = m.get("sender_phone") == phone
                user_name = m.get("user", "")
                text = m.get("text", "")
                kind = m.get("kind", "message")

                if kind == "system":
                    messages_list.controls.append(
                        ft.Container(
                            content=ft.Text(text, size=11, color=ft.Colors.GREY_500,
                                            text_align=ft.TextAlign.CENTER, italic=True),
                            alignment=ft.alignment.center,
                            padding=ft.padding.symmetric(vertical=2),
                        )
                    )
                    continue

                if kind == "action":
                    messages_list.controls.append(
                        ft.Container(
                            content=ft.Text(f"* {user_name} {text}", size=12,
                                            color=ft.Colors.GREY_400, italic=True,
                                            text_align=ft.TextAlign.CENTER),
                            alignment=ft.alignment.center,
                            padding=ft.padding.symmetric(vertical=2),
                        )
                    )
                    continue

                # Обычное сообщение
                bubble_color = ft.Colors.BLUE_800 if is_mine else ft.Colors.GREY_800
                align = ft.MainAxisAlignment.END if is_mine else ft.MainAxisAlignment.START

                avatar = ft.CircleAvatar(
                    content=ft.Text(get_initials(user_name), size=11, color=ft.Colors.WHITE),
                    bgcolor=get_user_color(m.get("sender_phone") or user_name),
                    radius=16,
                )

                header_row = ft.Row([
                    ft.Text(user_name, size=11, color=ACCENT if not is_mine else ft.Colors.BLUE_200,
                            weight=ft.FontWeight.W_600),
                    ft.Text(m.get("timestamp", ""), size=10, color=ft.Colors.GREY_500),
                ], spacing=6)

                bubble_content = [
                    header_row,
                    ft.Text(text, size=13, color=ft.Colors.WHITE, selectable=True),
                ]

                # Быстрые ответы
                if m.get("quick"):
                    quick_row = ft.Row(spacing=4, wrap=True)
                    for q in m["quick"]:
                        quick_row.controls.append(
                            ft.ElevatedButton(q, height=28, style=ft.ButtonStyle(
                                padding=ft.padding.symmetric(horizontal=8, vertical=0),
                                text_style=ft.TextStyle(size=11),
                            ), on_click=lambda e, txt=q: send_text(txt))
                        )
                    bubble_content.append(quick_row)

                bubble = ft.Container(
                    content=ft.Column(bubble_content, spacing=2, tight=True),
                    bgcolor=bubble_color,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=12,
                    width=280,
                )

                if is_mine:
                    row = ft.Row([ft.Container(expand=True), bubble], spacing=4)
                else:
                    row = ft.Row([avatar, bubble], spacing=4)

                messages_list.controls.append(row)

            page.update()

        # ---- Отправка ----
        def send_text(text: str):
            text = text.strip()
            if not text:
                return
            key = page.session.get("active_chat")
            my_name = page.session.get("name") or "User"

            # Команды
            if text.startswith("/"):
                handle_command(key, text, my_name)
                return

            if key == SUPPORT_KEY:
                add_message(key, my_name, text, phone)
                # AI-ответ
                def ai_worker():
                    answer, _ = ai_support_answer(phone, text)
                    add_message(key, SUPPORT_NAME, answer, kind="message")
                threading.Thread(target=ai_worker, daemon=True).start()
            elif key == LOBBY_KEY:
                add_message(key, my_name, text, phone)
            else:
                add_message(key, my_name, text, phone)

        def send_current(e=None):
            text = (input_field.value or "").strip()
            if not text:
                return
            input_field.value = ""
            page.update()
            send_text(text)

        send_btn.on_click = send_current
        input_field.on_submit = send_current

        # ---- Команды ----
        def handle_command(key: str, text: str, my_name: str):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "/help":
                lines = ["**Команды:**"]
                for c, d in BOT_COMMANDS.items():
                    lines.append(f"`{c}` — {d}")
                add_message(key, BOT_NAME, "\n".join(lines), kind="message")
            elif cmd == "/users":
                if not PARTICIPANTS:
                    add_message(key, BOT_NAME, "В чате никого нет.", kind="message")
                else:
                    lines = ["**Участники:**"]
                    for p, d in PARTICIPANTS.items():
                        lines.append(f"• {d['name']} ({format_phone(p)})")
                    add_message(key, BOT_NAME, "\n".join(lines), kind="message")
            elif cmd == "/whoami":
                add_message(key, BOT_NAME,
                            f"Имя: {my_name}\nТелефон: {format_phone(phone)}", kind="message")
            elif cmd == "/stats":
                hist = get_history(key)
                add_message(key, BOT_NAME, f"Сообщений в этом чате: {len(hist)}", kind="message")
            elif cmd == "/time":
                add_message(key, BOT_NAME, f"Серверное время: {datetime.now().strftime('%H:%M:%S')}", kind="message")
            elif cmd == "/ping":
                add_message(key, BOT_NAME, "pong 🏓", kind="message")
            elif cmd == "/roll":
                add_message(key, BOT_NAME, f"🎲 {random.randint(1, 100)}", kind="message")
            elif cmd == "/dice":
                add_message(key, BOT_NAME, f"🎲 {random.randint(1, 6)}", kind="message")
            elif cmd == "/flip":
                add_message(key, BOT_NAME, random.choice(["🪙 Орёл", "🪙 Решка"]), kind="message")
            elif cmd == "/8ball":
                if not arg:
                    add_message(key, BOT_NAME, "Задайте вопрос: `/8ball <вопрос>`", kind="message")
                else:
                    add_message(key, BOT_NAME, f"🎱 {random.choice(EIGHT_BALL)}", kind="message")
            elif cmd == "/choose":
                options = arg.split()
                if len(options) < 2:
                    add_message(key, BOT_NAME, "Укажите минимум 2 варианта.", kind="message")
                else:
                    add_message(key, BOT_NAME, f"Выбираю: **{random.choice(options)}**", kind="message")
            elif cmd == "/joke":
                add_message(key, BOT_NAME, random.choice(JOKES), kind="message")
            elif cmd == "/quote":
                add_message(key, BOT_NAME, random.choice(QUOTES), kind="message")
            elif cmd == "/calc":
                if not arg:
                    add_message(key, BOT_NAME, "Введите выражение: `/calc 2+2`", kind="message")
                else:
                    try:
                        result = safe_calc(arg)
                        add_message(key, BOT_NAME, f"= {result}", kind="message")
                    except Exception:
                        add_message(key, BOT_NAME, "Ошибка в выражении.", kind="message")
            elif cmd == "/weather":
                if not arg:
                    add_message(key, BOT_NAME, "Укажите город: `/weather Москва`", kind="message")
                else:
                    try:
                        add_message(key, BOT_NAME, fetch_weather(arg), kind="message")
                    except Exception:
                        add_message(key, BOT_NAME, "Не удалось получить погоду.", kind="message")
            elif cmd == "/remind":
                rparts = arg.split(maxsplit=1)
                if len(rparts) < 2 or not rparts[0].isdigit():
                    add_message(key, BOT_NAME, "Формат: `/remind <сек> <текст>`", kind="message")
                else:
                    sec = int(rparts[0])
                    reminder = rparts[1]

                    def remind():
                        time.sleep(sec)
                        add_message(key, BOT_NAME, f"⏰ Напоминание: {reminder}", kind="message")

                    threading.Thread(target=remind, daemon=True).start()
                    add_message(key, BOT_NAME, f"Напомню через {sec} сек.", kind="message")
            elif cmd == "/nick":
                if not arg:
                    add_message(key, BOT_NAME, "Укажите новое имя: `/nick Имя`", kind="message")
                else:
                    new_name = arg.strip()[:32]
                    PARTICIPANTS[phone]["name"] = new_name
                    page.session.set("name", new_name)
                    add_message(key, BOT_NAME, f"Имя изменено на **{new_name}**.", kind="message")
                    refresh_contacts()
            elif cmd == "/me":
                if not arg:
                    add_message(key, BOT_NAME, "Укажите действие: `/me танцует`", kind="message")
                else:
                    add_message(key, my_name, arg, phone, kind="action")
            elif cmd == "/clear":
                hist = get_history(key)
                hist.clear()
                render_messages()
                add_message(key, BOT_NAME, "Лента очищена.", kind="message")
            elif cmd == "/support":
                switch_chat(SUPPORT_KEY)
            elif cmd == "/human":
                add_message(key, BOT_NAME, SUPPORT_ESCALATED, kind="message")
            elif cmd == "/reset_support":
                SUPPORT_CONTEXT.pop(phone, None)
                SUPPORT_HISTORY[phone] = []
                add_message(key, BOT_NAME, "Диалог с поддержкой сброшен.", kind="message")
                render_messages()
            else:
                add_message(key, BOT_NAME, f"Неизвестная команда: `{cmd}`. Введите `/help`.", kind="message")

        # ---- Переключение чата ----
        def switch_chat(key: str):
            page.session.set("active_chat", key)
            if key == LOBBY_KEY:
                chat_title.value = "Общий чат"
                back_btn.visible = False
            elif key == SUPPORT_KEY:
                chat_title.value = SUPPORT_NAME
                back_btn.visible = True
                # Приветствие при первом заходе
                hist = SUPPORT_HISTORY.setdefault(phone, [])
                if not hist:
                    add_message(key, SUPPORT_NAME, SUPPORT_GREETING, kind="message")
            else:
                # DM
                other_phone = key.split(":")[1].replace(phone, "").lstrip("_")
                # Извлекаем имя
                other_name = "Чат"
                for p, d in PARTICIPANTS.items():
                    if p != phone:
                        other_name = d["name"]
                        break
                chat_title.value = other_name
                back_btn.visible = True
            refresh_contacts()
            render_messages()

        def do_logout():
            p = page.session.get("phone")
            if p:
                PARTICIPANTS.pop(p, None)
            page.session.set("phone", None)
            page.session.set("name", None)
            page.session.set("active_chat", LOBBY_KEY)
            show_login()

        # ---- Инициализация ----
        refresh_contacts()
        render_messages()
        input_field.focus()

        return ft.Container(content=main_row, expand=True, padding=0)

    # ---- Старт ----
    phone = page.session.get("phone")
    if phone:
        show_chat()
    else:
        show_login()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.run(main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)