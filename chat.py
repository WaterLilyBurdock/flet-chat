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
import urllib3

# Отключаем предупреждения о самоподписанном/российском сертификате Сбера
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Опциональная загрузка переменных из локального файла .env (если установлен python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================
# НАСТРОЙКА ДЛЯ RENDER (headless-среда)
# ============================================================
os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")

# ============================================================
# ЦВЕТОВАЯ ПАЛИТРА (Современная тёмная тема)
# ============================================================
BG_MAIN = "#0E1117"
BG_SIDEBAR = "#151922"
BG_CARD = "#1C212B"
BG_INPUT = "#1B202A"
BORDER_CLR = "#283040"
TEXT_MUTED = "#8B949E"
BUBBLE_MINE = "#1F6FEB"
BUBBLE_OTHER = "#1F2633"
BUBBLE_SUPPORT = "#142936"

ACCENT = ft.Colors.BLUE_400
ACCENT_MED = ft.Colors.BLUE_600
ACCENT_DEEP = ft.Colors.BLUE_700
ONLINE_CLR = ft.Colors.GREEN_400
SUPPORT_CLR = ft.Colors.CYAN_400
GREY_850 = BG_SIDEBAR  # алиас для совместимости

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
def _read_gigachat_key() -> str:
    """Читает ключ авторизации GigaChat из переменных окружения и очищает его от кавычек и префикса Basic."""
    raw = (
        os.environ.get("GIGACHAT_AUTH_KEY")
        or os.environ.get("GIGACHAT_CREDENTIALS")
        or os.environ.get("GIGACHAT_API_KEY")
        or ""
    ).strip().strip('"').strip("'")
    if raw.lower().startswith("basic "):
        raw = raw[6:].strip()
    return raw


GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
GIGACHAT_SCOPE = os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip()
AI_MODEL = os.environ.get("GIGACHAT_MODEL", "GigaChat").strip()
# Если задан путь к сертификату Минцифры — используем его, иначе отключаем проверку SSL
GIGACHAT_VERIFY: bool | str = os.environ.get("GIGACHAT_CA_BUNDLE", "").strip() or False

_gigachat_token = {"access_token": None, "expires_at": 0.0}
_gigachat_lock = threading.Lock()


def get_gigachat_token(force_refresh: bool = False) -> str | None:
    """Получает или обновляет Access Token GigaChat (живёт 30 минут)."""
    with _gigachat_lock:
        if (
            not force_refresh
            and _gigachat_token["access_token"]
            and time.time() < _gigachat_token["expires_at"] - 60
        ):
            return _gigachat_token["access_token"]

        auth_key = _read_gigachat_key()
        if not auth_key:
            print("⚠️ GIGACHAT_AUTH_KEY не задан в переменных окружения.")
            return None

        try:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {auth_key}",
            }
            data = {"scope": GIGACHAT_SCOPE}
            resp = requests.post(
                GIGACHAT_AUTH_URL,
                headers=headers,
                data=data,
                timeout=15,
                verify=GIGACHAT_VERIFY,
            )
            if not resp.ok:
                print(f"[GIGACHAT AUTH ERROR] HTTP {resp.status_code}: {resp.text}")
                return None

            payload = resp.json()
            access_token = payload.get("access_token")
            if not access_token:
                print(f"[GIGACHAT AUTH ERROR] В ответе нет access_token: {payload}")
                return None

            # GigaChat возвращает expires_at в миллисекундах
            raw_exp = payload.get("expires_at")
            if isinstance(raw_exp, (int, float)) and raw_exp > 1e11:
                expires_at = raw_exp / 1000.0
            elif isinstance(raw_exp, (int, float)) and raw_exp > 0:
                expires_at = float(raw_exp)
            else:
                expires_at = time.time() + 1800

            _gigachat_token["access_token"] = access_token
            _gigachat_token["expires_at"] = expires_at
            return access_token
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
    ("like", "👍", ACCENT),
    ("heart", "❤️", ft.Colors.RED_400),
    ("fire", "🔥", ft.Colors.ORANGE_400),
]

SUPPORT_QUICK_REPLIES = [
    "Какие есть команды?",
    "Как написать в ЛС?",
    "Позвать оператора",
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


def get_dm_peer(topic: str, my_phone: str) -> str | None:
    """Возвращает номер собеседника из ключа личного чата."""
    if not topic.startswith("dm:"):
        return None
    parts = topic[3:].split("_")
    for p in parts:
        if p != my_phone:
            return p
    return parts[0] if parts else None


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
        return (
            "ИИ-поддержка временно недоступна (ошибка авторизации GigaChat).\n"
            "Напишите `/human` — оператор свяжется с вами.",
            True,
        )

    ctx = SUPPORT_CONTEXT.setdefault(phone, [])
    ctx.append({"role": "user", "content": user_text})
    if len(ctx) > MAX_CONTEXT_MESSAGES:
        ctx[:] = ctx[-MAX_CONTEXT_MESSAGES:]

    messages = [{"role": "system", "content": SUPPORT_SYSTEM_PROMPT}] + ctx
    body = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 600,
    }

    try:
        resp = None
        # Делаем до 2 попыток: если токен протух (401), принудительно обновляем его
        for attempt in range(2):
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            }
            resp = requests.post(
                GIGACHAT_CHAT_URL,
                headers=headers,
                json=body,
                timeout=30,
                verify=GIGACHAT_VERIFY,
            )
            if resp.status_code == 401 and attempt == 0:
                token = get_gigachat_token(force_refresh=True)
                if not token:
                    break
                continue
            break

        if resp is None or not resp.ok:
            status = resp.status_code if resp is not None else "NO_RESPONSE"
            text_err = resp.text if resp is not None else ""
            print(f"[GIGACHAT API ERROR] HTTP {status}: {text_err}")
            return (SUPPORT_FALLBACK, False)

        data = resp.json()
        answer = (data["choices"][0]["message"]["content"] or "").strip()
        if not answer:
            return (SUPPORT_FALLBACK, False)

        ctx.append({"role": "assistant", "content": answer})
        if len(ctx) > MAX_CONTEXT_MESSAGES:
            ctx[:] = ctx[-MAX_CONTEXT_MESSAGES:]

        escalate = any(
            w in answer.lower()
            for w in ["оператор", "человек", "не могу помочь", "не знаю", "/human", "передам"]
        )
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
    page.title = "Flet Chat · Мессенджер"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG_MAIN

    # ---- Состояние страницы ----
    page.session.store.set("phone", None)
    page.session.store.set("name", None)
    page.session.store.set("active_chat", LOBBY_KEY)
    page.session.store.set("auth_step", "phone")
    page.session.store.set("pending_phone", None)

    # ---- UI-контейнеры ----
    root = ft.Column(expand=True, spacing=0)
    page.add(root)

    def safe_update():
        try:
            page.update()
        except Exception:
            pass

    def show_login():
        root.controls.clear()
        root.controls.append(build_login_view())
        safe_update()

    def show_chat():
        root.controls.clear()
        root.controls.append(build_chat_view())
        safe_update()

    # ---- Логин ----
    def build_login_view():
        phone_field = ft.TextField(
            label="Номер телефона",
            hint_text="+7 999 123-45-67",
            prefix_icon=ft.Icons.PHONE,
            width=340,
            border_radius=12,
            bgcolor=BG_INPUT,
            border_color=BORDER_CLR,
            focused_border_color=ACCENT,
            keyboard_type=ft.KeyboardType.PHONE,
        )
        nick_field = ft.TextField(
            label="Ваше имя (необязательно)",
            hint_text="Например, Владислав",
            prefix_icon=ft.Icons.PERSON_OUTLINE,
            width=340,
            border_radius=12,
            bgcolor=BG_INPUT,
            border_color=BORDER_CLR,
            focused_border_color=ACCENT,
            max_length=32,
        )
        code_field = ft.TextField(
            label="Код из SMS",
            hint_text="6 цифр",
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            width=340,
            border_radius=12,
            bgcolor=BG_INPUT,
            border_color=BORDER_CLR,
            focused_border_color=ACCENT,
            keyboard_type=ft.KeyboardType.NUMBER,
            max_length=6,
            visible=False,
        )
        status = ft.Text("", color=ft.Colors.RED_400, size=13, text_align=ft.TextAlign.CENTER)
        info_badge = ft.Container(
            content=ft.Text("", color=SUPPORT_CLR, size=13, weight=ft.FontWeight.W_600),
            bgcolor=ft.Colors.with_opacity(0.12, SUPPORT_CLR),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, SUPPORT_CLR)),
            border_radius=10,
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            visible=False,
        )
        send_btn = ft.Button(
            "Получить код",
            width=340,
            height=46,
            style=ft.ButtonStyle(
                bgcolor=BUBBLE_MINE,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )
        verify_btn = ft.Button(
            "Войти в чат",
            width=340,
            height=46,
            visible=False,
            style=ft.ButtonStyle(
                bgcolor=ONLINE_CLR,
                color=BG_MAIN,
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )
        reset_phone_btn = ft.Button(
            "Изменить номер",
            width=340,
            visible=False,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.TRANSPARENT,
                color=TEXT_MUTED,
            ),
        )

        def on_send(e=None):
            raw = phone_field.value or ""
            phone = normalize_phone(raw)
            if not phone:
                status.value = "Неверный номер. Введите 10–15 цифр."
                safe_update()
                return
            code = f"{random.randint(0, 999999):06d}"
            PENDING_CODES[phone] = {"code": code, "exp": time.time() + CODE_TTL}
            page.session.store.set("pending_phone", phone)
            page.session.store.set("auth_step", "code")
            status.value = ""
            info_badge.content.value = f"🔑 Демо-код для входа: {code}"
            info_badge.visible = True
            phone_field.disabled = True
            nick_field.disabled = True
            send_btn.visible = False
            code_field.visible = True
            verify_btn.visible = True
            reset_phone_btn.visible = True
            safe_update()
            code_field.focus()

        def on_reset_phone(e=None):
            phone_field.disabled = False
            nick_field.disabled = False
            send_btn.visible = True
            code_field.visible = False
            code_field.value = ""
            verify_btn.visible = False
            reset_phone_btn.visible = False
            info_badge.visible = False
            status.value = ""
            safe_update()

        def on_verify(e=None):
            phone = page.session.store.get("pending_phone")
            entry = PENDING_CODES.get(phone)
            if not entry or time.time() > entry["exp"]:
                status.value = "Код истёк. Запросите новый."
                safe_update()
                return
            if (code_field.value or "").strip() != entry["code"]:
                status.value = "Неверный код. Проверьте цифры выше."
                safe_update()
                return

            del PENDING_CODES[phone]
            custom_nick = (nick_field.value or "").strip()[:32]
            name = custom_nick or f"User_{phone[-4:]}"
            PARTICIPANTS[phone] = {"name": name, "phone": phone, "joined": now_time()}
            page.session.store.set("phone", phone)
            page.session.store.set("name", name)
            try:
                page.pubsub.send_all({"type": "presence", "phone": phone, "name": name, "action": "join"})
            except Exception:
                pass
            show_chat()

        send_btn.on_click = on_send
        verify_btn.on_click = on_verify
        reset_phone_btn.on_click = on_reset_phone
        phone_field.on_submit = on_send
        nick_field.on_submit = on_send
        code_field.on_submit = on_verify

        card = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.CHAT_BUBBLE_ROUNDED, color=ft.Colors.WHITE, size=32),
                        width=64,
                        height=64,
                        border_radius=18,
                        bgcolor=BUBBLE_MINE,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Text("Flet Chat", size=26, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ft.Text(
                        "Общий чат, личные сообщения и ИИ-ассистент GigaChat",
                        color=TEXT_MUTED,
                        size=13,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    phone_field,
                    nick_field,
                    info_badge,
                    code_field,
                    status,
                    send_btn,
                    verify_btn,
                    reset_phone_btn,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                tight=True,
            ),
            width=400,
            padding=32,
            bgcolor=BG_SIDEBAR,
            border_radius=20,
            border=ft.Border.all(1, BORDER_CLR),
            shadow=ft.BoxShadow(blur_radius=32, color=ft.Colors.with_opacity(0.45, ft.Colors.BLACK)),
        )

        return ft.Container(
            content=card,
            alignment=ft.Alignment.CENTER,
            expand=True,
            bgcolor=BG_MAIN,
            padding=16,
        )

    # ---- Чат ----
    def build_chat_view():
        phone = page.session.store.get("phone")
        state = {
            "reply_to": None,       # dict с id, user, text
            "search_query": "",     # фильтр сообщений
            "chat_filter": "",      # фильтр контактов
            "unread": {},           # chat_key -> int
            "ai_typing": False,     # индикатор набора ИИ
            "mobile_show_chat": True,
        }

        def is_mobile() -> bool:
            w = getattr(page, "width", None)
            return bool(w and w < 720)

        # --- Поиск чатов в сайдбаре ---
        chat_search = ft.TextField(
            hint_text="Поиск чатов…",
            prefix_icon=ft.Icons.SEARCH,
            height=38,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=10,
            bgcolor=BG_INPUT,
            border_color=BORDER_CLR,
            focused_border_color=ACCENT,
        )

        contacts_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)

        # Карточка профиля внизу сайдбара
        profile_name_txt = ft.Text(
            page.session.store.get("name") or "User",
            size=13,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.WHITE,
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        profile_avatar_txt = ft.Text(
            get_initials(page.session.store.get("name") or "U"),
            size=12,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE,
        )

        def prompt_nick_change(e=None):
            input_field.value = "/nick "
            safe_update()
            input_field.focus()

        profile_card = ft.Container(
            content=ft.Row(
                [
                    ft.Stack(
                        [
                            ft.CircleAvatar(
                                content=profile_avatar_txt,
                                bgcolor=get_user_color(phone or "me"),
                                radius=18,
                            ),
                            ft.Container(
                                width=10,
                                height=10,
                                border_radius=5,
                                bgcolor=ONLINE_CLR,
                                border=ft.Border.all(2, BG_SIDEBAR),
                                right=0,
                                bottom=0,
                            ),
                        ],
                        width=36,
                        height=36,
                    ),
                    ft.Column(
                        [
                            profile_name_txt,
                            ft.Text(format_phone(phone), size=11, color=TEXT_MUTED),
                        ],
                        spacing=1,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_OUTLINED,
                        icon_size=18,
                        icon_color=TEXT_MUTED,
                        tooltip="Сменить имя (/nick)",
                        on_click=prompt_nick_change,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=10),
            bgcolor=BG_CARD,
            border_radius=12,
            border=ft.Border.all(1, BORDER_CLR),
        )

        sidebar = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CHAT_BUBBLE_ROUNDED, color=ACCENT, size=22),
                            ft.Text("Flet Chat", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ],
                        spacing=8,
                    ),
                    chat_search,
                    contacts_col,
                    profile_card,
                ],
                spacing=10,
                expand=True,
            ),
            width=270,
            bgcolor=BG_SIDEBAR,
            padding=12,
            border=ft.Border.only(right=ft.BorderSide(1, BORDER_CLR)),
        )

        def last_preview(key: str) -> str:
            hist = get_history(key)
            if not hist:
                return "Нет сообщений"
            txt = (hist[-1].get("text") or "").replace("\n", " ").strip()
            return (txt[:28] + "…") if len(txt) > 28 else txt

        def unread_badge(key: str):
            cnt = state["unread"].get(key, 0)
            if cnt <= 0:
                return ft.Container()
            return ft.Container(
                content=ft.Text(str(cnt if cnt < 100 else "99+"), size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                bgcolor=BUBBLE_MINE,
                border_radius=10,
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            )

        def build_chat_tile(key: str, title: str, subtitle: str, leading: ft.Control, accent_color=ACCENT):
            is_active = page.session.store.get("active_chat") == key
            return ft.Container(
                content=ft.Row(
                    [
                        leading,
                        ft.Column(
                            [
                                ft.Text(
                                    title,
                                    size=13,
                                    color=ft.Colors.WHITE,
                                    weight=ft.FontWeight.W_600,
                                    no_wrap=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    subtitle,
                                    size=11,
                                    color=TEXT_MUTED,
                                    no_wrap=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=1,
                            expand=True,
                        ),
                        unread_badge(key),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.16, accent_color) if is_active else ft.Colors.TRANSPARENT,
                border=ft.Border.all(
                    1,
                    ft.Colors.with_opacity(0.35, accent_color) if is_active else ft.Colors.TRANSPARENT,
                ),
                on_click=lambda e, k=key: switch_chat(k),
            )

        def refresh_contacts():
            q = (state["chat_filter"] or "").strip().lower()
            contacts_col.controls.clear()

            # Лобби
            if not q or "общий" in q or "чат" in q:
                lobby_avatar = ft.CircleAvatar(
                    content=ft.Icon(ft.Icons.GROUPS_ROUNDED, color=ft.Colors.WHITE, size=18),
                    bgcolor=BUBBLE_MINE,
                    radius=18,
                )
                contacts_col.controls.append(
                    build_chat_tile(LOBBY_KEY, "Общий чат", last_preview(LOBBY_KEY), lobby_avatar, ACCENT)
                )

            # Поддержка
            if not q or "ассистент" in q or "поддержк" in q or "gigachat" in q or "ии" in q:
                sup_avatar = ft.CircleAvatar(
                    content=ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.WHITE, size=18),
                    bgcolor=ft.Colors.CYAN_700,
                    radius=18,
                )
                contacts_col.controls.append(
                    build_chat_tile(SUPPORT_KEY, SUPPORT_NAME, last_preview(SUPPORT_KEY), sup_avatar, SUPPORT_CLR)
                )

            # Контакты (ЛС)
            others = [
                (p, d) for p, d in PARTICIPANTS.items()
                if p != phone and (not q or q in d["name"].lower() or q in p)
            ]
            if others:
                contacts_col.controls.append(
                    ft.Container(
                        content=ft.Text(
                            f"В СЕТИ · {len(others)}",
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color=TEXT_MUTED,
                        ),
                        padding=ft.Padding.only(left=6, top=8, bottom=2),
                    )
                )
            for p, d in others:
                topic = dm_topic(phone, p)
                dm_avatar = ft.Stack(
                    [
                        ft.CircleAvatar(
                            content=ft.Text(get_initials(d["name"]), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            bgcolor=get_user_color(p),
                            radius=18,
                        ),
                        ft.Container(
                            width=10,
                            height=10,
                            border_radius=5,
                            bgcolor=ONLINE_CLR,
                            border=ft.Border.all(2, BG_SIDEBAR),
                            right=0,
                            bottom=0,
                        ),
                    ],
                    width=36,
                    height=36,
                )
                contacts_col.controls.append(
                    build_chat_tile(topic, d["name"], last_preview(topic), dm_avatar, ACCENT)
                )

            # Обновляем карточку профиля
            cur_name = page.session.store.get("name") or "User"
            profile_name_txt.value = cur_name
            profile_avatar_txt.value = get_initials(cur_name)
            safe_update()

        def on_chat_search(e):
            state["chat_filter"] = chat_search.value or ""
            refresh_contacts()

        chat_search.on_change = on_chat_search

        # --- Лента сообщений ---
        messages_list = ft.ListView(
            expand=True,
            spacing=8,
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            auto_scroll=True,
        )

        # --- Индикатор набора ИИ ---
        typing_indicator = ft.Container(
            content=ft.Row(
                [
                    ft.ProgressRing(width=14, height=14, stroke_width=2, color=SUPPORT_CLR),
                    ft.Text("Ассистент GigaChat печатает…", size=12, color=SUPPORT_CLR, italic=True),
                ],
                spacing=8,
            ),
            padding=ft.Padding.symmetric(horizontal=18, vertical=6),
            visible=False,
        )

        # --- Панель ответа (цитирования) ---
        reply_user_txt = ft.Text("", size=11, weight=ft.FontWeight.BOLD, color=ACCENT)
        reply_body_txt = ft.Text("", size=12, color=TEXT_MUTED, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)

        def clear_reply(e=None):
            state["reply_to"] = None
            reply_bar.visible = False
            safe_update()

        reply_bar = ft.Container(
            content=ft.Row(
                [
                    ft.Container(width=3, height=32, bgcolor=ACCENT, border_radius=2),
                    ft.Column([reply_user_txt, reply_body_txt], spacing=1, expand=True),
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_size=16, icon_color=TEXT_MUTED, on_click=clear_reply),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=6),
            bgcolor=BG_CARD,
            border=ft.Border.only(top=ft.BorderSide(1, BORDER_CLR)),
            visible=False,
        )

        def set_reply(msg: dict):
            state["reply_to"] = {
                "id": msg.get("id", ""),
                "user": msg.get("user", ""),
                "text": (msg.get("text", "") or "").replace("\n", " ")[:90],
            }
            reply_user_txt.value = f"Ответ для {state['reply_to']['user']}"
            reply_body_txt.value = state["reply_to"]["text"]
            reply_bar.visible = True
            safe_update()
            input_field.focus()

        # --- Поле ввода ---
        char_counter = ft.Text(f"0/{MAX_MSG_LEN}", size=10, color=TEXT_MUTED)
        input_field = ft.TextField(
            hint_text="Напишите сообщение или /help…",
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=4,
            shift_enter=True,
            max_length=MAX_MSG_LEN,
            border_radius=22,
            filled=True,
            bgcolor=BG_INPUT,
            border_color=BORDER_CLR,
            focused_border_color=ACCENT,
            content_padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        )

        def on_input_change(e):
            ln = len(input_field.value or "")
            char_counter.value = f"{ln}/{MAX_MSG_LEN}"
            char_counter.color = ft.Colors.ORANGE_400 if ln > MAX_MSG_LEN - 50 else TEXT_MUTED
            safe_update()

        input_field.on_change = on_input_change

        def insert_help_cmd(e=None):
            send_text("/help")

        cmd_btn = ft.IconButton(
            icon=ft.Icons.TERMINAL_ROUNDED,
            icon_color=TEXT_MUTED,
            icon_size=20,
            tooltip="Команды бота (/help)",
            on_click=insert_help_cmd,
        )
        send_btn = ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.SEND_ROUNDED,
                icon_color=ft.Colors.WHITE,
                icon_size=20,
                tooltip="Отправить (Enter)",
            ),
            bgcolor=BUBBLE_MINE,
            border_radius=22,
            width=42,
            height=42,
            alignment=ft.Alignment.CENTER,
        )

        # --- Поиск по сообщениям ---
        msg_search_field = ft.TextField(
            hint_text="Найти в этом чате…",
            prefix_icon=ft.Icons.SEARCH,
            expand=True,
            height=36,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=10,
            bgcolor=BG_INPUT,
            border_color=BORDER_CLR,
            focused_border_color=ACCENT,
        )

        def on_msg_search(e):
            state["search_query"] = (msg_search_field.value or "").strip().lower()
            render_messages()

        msg_search_field.on_change = on_msg_search

        def toggle_msg_search(e=None):
            search_bar.visible = not search_bar.visible
            if not search_bar.visible:
                msg_search_field.value = ""
                state["search_query"] = ""
                render_messages()
            else:
                safe_update()
                msg_search_field.focus()
            safe_update()

        search_bar = ft.Container(
            content=ft.Row(
                [
                    msg_search_field,
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_size=18, icon_color=TEXT_MUTED, on_click=toggle_msg_search),
                ],
                spacing=6,
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=6),
            bgcolor=BG_SIDEBAR,
            border=ft.Border.only(bottom=ft.BorderSide(1, BORDER_CLR)),
            visible=False,
        )

        # --- Шапка чата ---
        header_avatar = ft.CircleAvatar(
            content=ft.Icon(ft.Icons.GROUPS_ROUNDED, color=ft.Colors.WHITE, size=18),
            bgcolor=BUBBLE_MINE,
            radius=18,
        )
        chat_title = ft.Text("Общий чат", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        chat_subtitle = ft.Text("Онлайн", size=11, color=ONLINE_CLR)

        def on_mobile_back(e=None):
            state["mobile_show_chat"] = False
            apply_responsive_layout()

        back_btn = ft.IconButton(
            ft.Icons.ARROW_BACK,
            icon_color=ft.Colors.WHITE,
            visible=False,
            tooltip="К списку чатов",
            on_click=on_mobile_back,
        )
        search_toggle_btn = ft.IconButton(
            ft.Icons.SEARCH,
            icon_color=TEXT_MUTED,
            tooltip="Поиск сообщений",
            on_click=toggle_msg_search,
        )
        logout_btn = ft.IconButton(
            ft.Icons.LOGOUT_ROUNDED,
            icon_color=ft.Colors.RED_300,
            tooltip="Выйти",
            on_click=lambda e: do_logout(),
        )

        header = ft.Container(
            content=ft.Row(
                [
                    back_btn,
                    header_avatar,
                    ft.Column([chat_title, chat_subtitle], spacing=1, expand=True),
                    search_toggle_btn,
                    logout_btn,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            bgcolor=BG_SIDEBAR,
            border=ft.Border.only(bottom=ft.BorderSide(1, BORDER_CLR)),
        )

        input_bar = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [cmd_btn, input_field, send_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Row([ft.Container(expand=True), char_counter], spacing=0),
                ],
                spacing=2,
                tight=True,
            ),
            padding=ft.Padding.only(left=10, right=14, top=10, bottom=6),
            bgcolor=BG_SIDEBAR,
            border=ft.Border.only(top=ft.BorderSide(1, BORDER_CLR)),
        )

        chat_area = ft.Container(
            content=ft.Column(
                [header, search_bar, messages_list, typing_indicator, reply_bar, input_bar],
                expand=True,
                spacing=0,
            ),
            expand=True,
            bgcolor=BG_MAIN,
        )

        main_row = ft.Row([sidebar, chat_area], expand=True, spacing=0)

        def apply_responsive_layout(e=None):
            mob = is_mobile()
            if mob:
                sidebar.width = None
                sidebar.expand = True
                sidebar.visible = not state["mobile_show_chat"]
                chat_area.visible = state["mobile_show_chat"]
                back_btn.visible = True
            else:
                sidebar.width = 270
                sidebar.expand = False
                sidebar.visible = True
                chat_area.visible = True
                back_btn.visible = False
            safe_update()

        page.on_resize = apply_responsive_layout

        # ---- Логика сообщений ----
        def get_history(key: str) -> list[dict]:
            if key == LOBBY_KEY:
                return LOBBY_HISTORY
            if key == SUPPORT_KEY:
                return SUPPORT_HISTORY.setdefault(phone, [])
            return DM_HISTORY.setdefault(key, [])

        def update_header_info():
            key = page.session.store.get("active_chat")
            if key == LOBBY_KEY:
                header_avatar.content = ft.Icon(ft.Icons.GROUPS_ROUNDED, color=ft.Colors.WHITE, size=18)
                header_avatar.bgcolor = BUBBLE_MINE
                chat_title.value = "Общий чат"
                cnt = len(PARTICIPANTS)
                chat_subtitle.value = f"Участников в сети: {cnt}"
                chat_subtitle.color = ONLINE_CLR
            elif key == SUPPORT_KEY:
                header_avatar.content = ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.WHITE, size=18)
                header_avatar.bgcolor = ft.Colors.CYAN_700
                chat_title.value = SUPPORT_NAME
                chat_subtitle.value = "ИИ-поддержка · GigaChat"
                chat_subtitle.color = SUPPORT_CLR
            else:
                peer = get_dm_peer(key, phone)
                peer_data = PARTICIPANTS.get(peer or "")
                other_name = peer_data["name"] if peer_data else format_phone(peer or "")
                header_avatar.content = ft.Text(get_initials(other_name), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
                header_avatar.bgcolor = get_user_color(peer or other_name)
                chat_title.value = other_name
                chat_subtitle.value = "В сети · Личные сообщения" if peer_data else "Не в сети"
                chat_subtitle.color = ONLINE_CLR if peer_data else TEXT_MUTED

        def add_message(
            key: str,
            user: str,
            text: str,
            sender_phone: str = "",
            kind: str = "message",
            quick: list | None = None,
            reply_to: dict | None = None,
            broadcast: bool = True,
        ):
            hist = get_history(key)
            msg = Message(
                user=user,
                text=text,
                timestamp=now_time(),
                sender_phone=sender_phone,
                kind=kind,
                date=today_iso(),
                id=new_msg_id(),
                reply_to_id=(reply_to or {}).get("id", ""),
                reply_to_user=(reply_to or {}).get("user", ""),
                reply_to_text=(reply_to or {}).get("text", ""),
                quick=quick or [],
            )
            hist.append(msg.__dict__)
            limit = MAX_SUPPORT_HISTORY if key == SUPPORT_KEY else MAX_HISTORY
            if len(hist) > limit:
                hist[:] = hist[-limit:]

            if broadcast and key != SUPPORT_KEY:
                try:
                    page.pubsub.send_all({"type": "msg", "chat": key, "sender": phone})
                except Exception:
                    pass
            render_messages()
            refresh_contacts()

        def toggle_reaction(chat_key: str, msg_id: str, reaction_key: str):
            hist = get_history(chat_key)
            for m in hist:
                if m.get("id") == msg_id:
                    reacs = m.setdefault("reactions", {})
                    users = reacs.setdefault(reaction_key, [])
                    if phone in users:
                        users.remove(phone)
                        if not users:
                            del reacs[reaction_key]
                    else:
                        users.append(phone)
                    break
            if chat_key != SUPPORT_KEY:
                try:
                    page.pubsub.send_all({"type": "reaction", "chat": chat_key})
                except Exception:
                    pass
            render_messages()

        def render_messages():
            key = page.session.store.get("active_chat")
            hist = get_history(key)
            q = state["search_query"]
            messages_list.controls.clear()

            filtered = [
                m for m in hist
                if not q or q in (m.get("text") or "").lower() or q in (m.get("user") or "").lower()
            ]

            if not filtered:
                empty_txt = "Ничего не найдено по запросу." if q else "Сообщений пока нет. Напишите первым!"
                messages_list.controls.append(
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.FORUM_OUTLINED, size=40, color=TEXT_MUTED),
                                ft.Text(empty_txt, size=13, color=TEXT_MUTED),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                        alignment=ft.Alignment.CENTER,
                        padding=40,
                    )
                )
                safe_update()
                return

            last_date = None
            for m in filtered:
                m_date = m.get("date", "")
                if m_date and m_date != last_date:
                    last_date = m_date
                    label = format_date_label(date.fromisoformat(m_date))
                    messages_list.controls.append(
                        ft.Container(
                            content=ft.Container(
                                content=ft.Text(label, size=11, color=TEXT_MUTED, weight=ft.FontWeight.W_500),
                                bgcolor=BG_CARD,
                                border=ft.Border.all(1, BORDER_CLR),
                                border_radius=12,
                                padding=ft.Padding.symmetric(horizontal=12, vertical=3),
                            ),
                            alignment=ft.Alignment.CENTER,
                            padding=ft.Padding.symmetric(vertical=6),
                        )
                    )

                is_mine = m.get("sender_phone") == phone
                user_name = m.get("user", "")
                text = m.get("text", "")
                kind = m.get("kind", "message")
                msg_id = m.get("id", "")

                if kind == "system":
                    messages_list.controls.append(
                        ft.Container(
                            content=ft.Text(text, size=11, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER, italic=True),
                            alignment=ft.Alignment.CENTER,
                            padding=ft.Padding.symmetric(vertical=2),
                        )
                    )
                    continue

                if kind == "action":
                    messages_list.controls.append(
                        ft.Container(
                            content=ft.Text(f"* {user_name} {text}", size=12, color=TEXT_MUTED, italic=True, text_align=ft.TextAlign.CENTER),
                            alignment=ft.Alignment.CENTER,
                            padding=ft.Padding.symmetric(vertical=2),
                        )
                    )
                    continue

                is_support_msg = user_name == SUPPORT_NAME
                if is_mine:
                    bubble_color = BUBBLE_MINE
                    bubble_border = ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE))
                    radius = ft.BorderRadius.only(top_left=16, top_right=16, bottom_left=16, bottom_right=4)
                elif is_support_msg:
                    bubble_color = BUBBLE_SUPPORT
                    bubble_border = ft.Border.all(1, ft.Colors.with_opacity(0.35, SUPPORT_CLR))
                    radius = ft.BorderRadius.only(top_left=16, top_right=16, bottom_left=4, bottom_right=16)
                else:
                    bubble_color = BUBBLE_OTHER
                    bubble_border = ft.Border.all(1, BORDER_CLR)
                    radius = ft.BorderRadius.only(top_left=16, top_right=16, bottom_left=4, bottom_right=16)

                avatar = ft.CircleAvatar(
                    content=ft.Icon(ft.Icons.AUTO_AWESOME, size=15, color=ft.Colors.WHITE)
                    if is_support_msg
                    else ft.Text(get_initials(user_name), size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.CYAN_700 if is_support_msg else get_user_color(m.get("sender_phone") or user_name),
                    radius=16,
                )

                header_row = ft.Row(
                    [
                        ft.Text(
                            user_name,
                            size=11,
                            color=ft.Colors.BLUE_100 if is_mine else (SUPPORT_CLR if is_support_msg else ACCENT),
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.Text(
                            m.get("timestamp", ""),
                            size=10,
                            color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE) if is_mine else TEXT_MUTED,
                        ),
                    ],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )

                bubble_content = [header_row]

                # Блок цитируемого сообщения (Reply)
                if m.get("reply_to_text"):
                    bubble_content.append(
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(m.get("reply_to_user", ""), size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    ft.Text(
                                        m.get("reply_to_text", ""),
                                        size=11,
                                        color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                                        no_wrap=True,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                spacing=1,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
                            border=ft.Border.only(left=ft.BorderSide(3, ft.Colors.WHITE if is_mine else ACCENT)),
                            border_radius=6,
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        )
                    )

                bubble_content.append(ft.Text(text, size=13, color=ft.Colors.WHITE, selectable=True))

                # Быстрые ответы
                if m.get("quick"):
                    quick_row = ft.Row(spacing=6, wrap=True)
                    for q_text in m["quick"]:
                        quick_row.controls.append(
                            ft.Button(
                                q_text,
                                height=28,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.with_opacity(0.18, SUPPORT_CLR),
                                    color=ft.Colors.WHITE,
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                                    text_style=ft.TextStyle(size=11),
                                    shape=ft.RoundedRectangleBorder(radius=14),
                                ),
                                on_click=lambda e, txt=q_text: send_text(txt),
                            )
                        )
                    bubble_content.append(quick_row)

                # Реакции и кнопка «Ответить»
                reacs = m.get("reactions") or {}
                actions_controls = []
                for r_key, r_emoji, r_clr in REACTION_ICONS:
                    users_list = reacs.get(r_key, [])
                    active_r = phone in users_list
                    label_r = f"{r_emoji} {len(users_list)}" if users_list else r_emoji
                    actions_controls.append(
                        ft.Container(
                            content=ft.Text(label_r, size=11, color=ft.Colors.WHITE if active_r else TEXT_MUTED),
                            bgcolor=ft.Colors.with_opacity(0.25, r_clr) if active_r else ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                            border=ft.Border.all(1, r_clr if active_r else ft.Colors.TRANSPARENT),
                            border_radius=10,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            on_click=lambda e, ck=key, mid=msg_id, rk=r_key: toggle_reaction(ck, mid, rk),
                        )
                    )
                actions_controls.append(
                    ft.Container(
                        content=ft.Icon(ft.Icons.REPLY_ROUNDED, size=14, color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE) if is_mine else TEXT_MUTED),
                        padding=ft.Padding.symmetric(horizontal=4, vertical=2),
                        tooltip="Ответить",
                        on_click=lambda e, msg_obj=m: set_reply(msg_obj),
                    )
                )
                bubble_content.append(ft.Row(actions_controls, spacing=4, wrap=True))

                bubble = ft.Container(
                    content=ft.Column(bubble_content, spacing=5, tight=True),
                    bgcolor=bubble_color,
                    border=bubble_border,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border_radius=radius,
                    width=360 if not is_mobile() else 260,
                )

                if is_mine:
                    row = ft.Row([ft.Container(expand=True), bubble], spacing=6, vertical_alignment=ft.CrossAxisAlignment.END)
                else:
                    row = ft.Row([avatar, bubble], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END)

                messages_list.controls.append(row)

            safe_update()

        # ---- Реалтайм-подписка (PubSub) ----
        def on_pubsub_event(ev):
            if not isinstance(ev, dict):
                return
            ev_type = ev.get("type")
            if ev_type == "presence":
                update_header_info()
                refresh_contacts()
            elif ev_type == "msg":
                chat_k = ev.get("chat")
                sender = ev.get("sender")
                if chat_k == LOBBY_KEY or (chat_k and chat_k.startswith("dm:") and phone in chat_k):
                    if page.session.store.get("active_chat") == chat_k:
                        render_messages()
                    elif sender != phone:
                        state["unread"][chat_k] = state["unread"].get(chat_k, 0) + 1
                    refresh_contacts()
            elif ev_type == "reaction":
                if page.session.store.get("active_chat") == ev.get("chat"):
                    render_messages()

        page.pubsub.subscribe(on_pubsub_event)

        def on_disconnect(e):
            try:
                page.pubsub.unsubscribe(on_pubsub_event)
            except Exception:
                pass
            if phone and phone in PARTICIPANTS:
                PARTICIPANTS.pop(phone, None)
                try:
                    page.pubsub.send_all({"type": "presence", "phone": phone, "action": "leave"})
                except Exception:
                    pass

        page.on_disconnect = on_disconnect

        # ---- Отправка ----
        def send_text(text: str):
            text = text.strip()[:MAX_MSG_LEN]
            if not text:
                return
            key = page.session.store.get("active_chat")
            my_name = page.session.store.get("name") or "User"
            reply_ctx = state["reply_to"]
            if reply_ctx:
                clear_reply()

            # Команды
            if text.startswith("/"):
                handle_command(key, text, my_name)
                return

            if key == SUPPORT_KEY:
                add_message(key, my_name, text, phone, reply_to=reply_ctx, broadcast=False)
                state["ai_typing"] = True
                typing_indicator.visible = True
                safe_update()

                def ai_worker():
                    answer, escalated = ai_support_answer(phone, text)
                    state["ai_typing"] = False
                    typing_indicator.visible = False
                    quick = ["/human", "/reset_support"] if escalated else None
                    add_message(key, SUPPORT_NAME, answer, kind="message", quick=quick, broadcast=False)

                threading.Thread(target=ai_worker, daemon=True).start()
            else:
                add_message(key, my_name, text, phone, reply_to=reply_ctx, broadcast=True)

        def send_current(e=None):
            text = (input_field.value or "").strip()
            if not text:
                return
            input_field.value = ""
            char_counter.value = f"0/{MAX_MSG_LEN}"
            char_counter.color = TEXT_MUTED
            safe_update()
            send_text(text)

        send_btn.content.on_click = send_current
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
                    add_message(key, BOT_NAME, "Укажите город: `/weather Москва`", kind="message", broadcast=False)
                else:
                    def weather_worker():
                        try:
                            res = fetch_weather(arg)
                        except Exception:
                            res = "Не удалось получить погоду. Проверьте название города."
                        add_message(key, BOT_NAME, res, kind="message", broadcast=(key != SUPPORT_KEY))
                    threading.Thread(target=weather_worker, daemon=True).start()
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
                    add_message(key, BOT_NAME, "Укажите новое имя: `/nick Имя`", kind="message", broadcast=False)
                else:
                    new_name = arg.strip()[:32]
                    PARTICIPANTS[phone]["name"] = new_name
                    page.session.store.set("name", new_name)
                    try:
                        page.pubsub.send_all({"type": "presence", "phone": phone, "name": new_name, "action": "nick"})
                    except Exception:
                        pass
                    add_message(key, BOT_NAME, f"Имя изменено на {new_name}.", kind="message", broadcast=False)
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
            page.session.store.set("active_chat", key)
            state["unread"][key] = 0
            state["mobile_show_chat"] = True
            clear_reply()
            if key == SUPPORT_KEY:
                hist = SUPPORT_HISTORY.setdefault(phone, [])
                if not hist:
                    add_message(
                        key,
                        SUPPORT_NAME,
                        SUPPORT_GREETING,
                        kind="message",
                        quick=SUPPORT_QUICK_REPLIES,
                        broadcast=False,
                    )
            update_header_info()
            refresh_contacts()
            render_messages()
            apply_responsive_layout()

        def do_logout():
            try:
                page.pubsub.unsubscribe(on_pubsub_event)
            except Exception:
                pass
            p = page.session.store.get("phone")
            if p:
                PARTICIPANTS.pop(p, None)
                try:
                    page.pubsub.send_all({"type": "presence", "phone": p, "action": "leave"})
                except Exception:
                    pass
            page.session.store.set("phone", None)
            page.session.store.set("name", None)
            page.session.store.set("active_chat", LOBBY_KEY)
            show_login()

        # ---- Инициализация ----
        update_header_info()
        refresh_contacts()
        render_messages()
        apply_responsive_layout()
        input_field.focus()

        return ft.Container(content=main_row, expand=True, padding=0)

    # ---- Старт ----
    phone = page.session.store.get("phone")
    if phone:
        show_chat()
    else:
        show_login()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.run(main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)