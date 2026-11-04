import asyncio
import hashlib
import io
import logging
import os
import random
import re
import sqlite3
import time
import urllib.parse
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    BotCommandScopeChat,
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.constants import ChatAction
from telegram.error import Forbidden
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import ocr
from texts import AGE_CODES, CHOOSE_LANG, GENDER_CODES, GROUP_MOTIVATION_POSTS, HEIGHT_CODES, T

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = ImageDraw = ImageFont = None

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
except ValueError:
    raise SystemExit("ADMIN_ID ቁጥር ብቻ መሆን አለበት።")
DB_PATH_SET = bool(os.getenv("DB_PATH"))
DB_PATH = Path(os.getenv("DB_PATH") or (config.BASE / "bot.db"))
DB_WARN = None if DB_PATH_SET else "⚠️ DB_PATH አልተሞላም፤ Railway ላይ Volume (/data) እና DB_PATH=/data/bot.db ያስቀምጡ።"

MAX_PENDING_PER_USER = getattr(config, "MAX_PENDING_PER_USER", 3)
REFERRAL_TARGET = getattr(config, "REFERRAL_TARGET", 5)
COACH_DAYS = getattr(config, "COACH_DAYS", (3, 7, 15, 30))
BACKUP_INTERVAL_HOURS = getattr(config, "BACKUP_INTERVAL_HOURS", 24)
GROUP_POST_HOURS = getattr(config, "GROUP_POST_HOURS", 8)
FAST_BONUS_HOURS = getattr(config, "FAST_BONUS_HOURS", 24)
FOLLOWUP_HOURS = getattr(config, "FOLLOWUP_HOURS", (0.25, 6.0, 24.0))
FOLLOWUP_RESET_HOURS = getattr(config, "FOLLOWUP_RESET_HOURS", 48.0)

BOT_USERNAME = ""
LAST_BACKUP_TS = 0.0
LAST_GROUP_POST_TS = 0.0
GROUP_POST_IDX = 0

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("bookbot")
for _noisy in ("httpx", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


def check_texts():
    config.PRICES.setdefault("upgrade", max(100, config.PRICES.get("bundle", 597) - config.PRICES.get("books", 397)))
    config.PRICES.setdefault("gift_books", config.PRICES.get("books", 397))
    config.PRICES.setdefault("gift_bundle", config.PRICES.get("bundle", 597))
    if "upgrade" not in getattr(config, "CHANNELS", {}):
        config.CHANNELS["upgrade"] = config.CHANNELS.get("bundle", 0)
    for lang, table in T.items():
        for k, v in T["am"].items():
            table.setdefault(k, v)


# ---------------------------------------------------------------- database
def _connect():
    return sqlite3.connect(DB_PATH, timeout=10)


def prepare_db_path():
    global DB_PATH, DB_WARN
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(DB_PATH, timeout=10)) as con:
            con.execute("PRAGMA user_version")
    except (OSError, sqlite3.Error) as e:
        DB_WARN = f"⚠️ DB_PATH ({DB_PATH}) መክፈት አልተቻለም ({e})። ጊዜያዊ ዳታቤዝ እየተጠቀምኩ ነው።"
        log.error(DB_WARN)
        DB_PATH = config.BASE / "bot.db"
    else:
        if DB_PATH_SET and not os.path.ismount(DB_PATH.parent):
            DB_WARN = f"⚠️ {DB_PATH.parent} Volume ሆኖ አልተያያዘም።"
            log.warning(DB_WARN)


def init_db():
    with closing(_connect()) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                lang TEXT DEFAULT 'am',
                age TEXT, gender TEXT, height TEXT,
                created TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                package TEXT,
                price INTEGER,
                ref TEXT,
                photo_file_id TEXT,
                status TEXT DEFAULT 'pending',
                created TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sessions (
                user_id INTEGER PRIMARY KEY,
                pkg TEXT, step TEXT, photo TEXT,
                pay_started REAL, reminded INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS support (
                msg_id INTEGER PRIMARY KEY,
                user_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS sms_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_id TEXT UNIQUE,
                amount REAL,
                raw_text TEXT,
                used_order_id INTEGER DEFAULT NULL,
                created REAL
            );
            CREATE TABLE IF NOT EXISTS promos (
                code TEXT PRIMARY KEY,
                discount INTEGER,
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS gifts (
                code TEXT PRIMARY KEY,
                package TEXT,
                buyer_id INTEGER,
                redeemed_by INTEGER DEFAULT NULL,
                created REAL
            );
            """
        )
        for sql in (
            "ALTER TABLE users ADD COLUMN username TEXT",
            "ALTER TABLE users ADD COLUMN started_at REAL",
            "ALTER TABLE users ADD COLUMN followup_stage INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN bot_blocked INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN referred_by INTEGER",
            "ALTER TABLE users ADD COLUMN ref_credited INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN ref_paid_count INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN ref_rewarded INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN bought_at REAL",
            "ALTER TABLE users ADD COLUMN coach_stage INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN max_funnel INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN offer_seen_at REAL",
            "ALTER TABLE users ADD COLUMN start_cm REAL",
            "ALTER TABLE users ADD COLUMN current_cm REAL",
            "ALTER TABLE users ADD COLUMN ad_source TEXT",
            "ALTER TABLE users ADD COLUMN streak_count INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN streak_last_date TEXT",
            "ALTER TABLE sessions ADD COLUMN promo_code TEXT",
            "ALTER TABLE sessions ADD COLUMN discount INTEGER DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN promo_code TEXT",
            "ALTER TABLE orders ADD COLUMN nudged INTEGER DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN note TEXT",
            "ALTER TABLE orders ADD COLUMN admin_msg INTEGER",
            "ALTER TABLE orders ADD COLUMN user_status_msg INTEGER",
            "ALTER TABLE orders ADD COLUMN photo_uid TEXT",
            "ALTER TABLE orders ADD COLUMN photo_hash TEXT",
            "ALTER TABLE orders ADD COLUMN invite_link TEXT",
            "ALTER TABLE orders ADD COLUMN invite_exp REAL",
            "ALTER TABLE orders ADD COLUMN joined INTEGER DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN photo_thumb BLOB",
        ):
            try:
                con.execute(sql)
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise

        immediate_start = time.time() - (FOLLOWUP_HOURS[0] * 3600) - 10
        con.execute("UPDATE users SET started_at=?, followup_stage=0 WHERE started_at IS NULL AND COALESCE(bot_blocked,0)=0", (immediate_start,))
        con.execute("DROP INDEX IF EXISTS ux_orders_photo_active")
        try:
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_photo_all ON orders(photo_hash) WHERE photo_hash IS NOT NULL")
        except sqlite3.IntegrityError:
            pass
        con.commit()


def execute(sql, args=()):
    with closing(_connect()) as con:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid


def execute_rc(sql, args=()):
    with closing(_connect()) as con:
        cur = con.execute(sql, args)
        con.commit()
        return cur.rowcount


def fetch(sql, args=()):
    with closing(_connect()) as con:
        con.row_factory = sqlite3.Row
        return con.execute(sql, args).fetchall()


FUNNEL_RANKS = {"welcome": 1, "q1": 1, "q2": 1, "q3": 1, "offer": 2, "video": 3, "proof": 3, "pkg": 4, "pay": 5}


def mark_funnel(user_id, screen_name):
    rank = FUNNEL_RANKS.get(screen_name, 0)
    if rank:
        execute("UPDATE users SET max_funnel = MAX(COALESCE(max_funnel, 0), ?) WHERE user_id=?", (rank, user_id))
    if screen_name in ("offer", "pkg"):
        execute("UPDATE users SET offer_seen_at = COALESCE(offer_seen_at, ?) WHERE user_id=?", (time.time(), user_id))


def ensure_user(u, referrer_id=None, ad_source=None):
    is_new = not fetch("SELECT 1 FROM users WHERE user_id=?", (u.id,))
    execute("INSERT OR IGNORE INTO users(user_id, name, started_at, followup_stage, bot_blocked) VALUES(?, ?, ?, 0, 0)", (u.id, u.full_name, time.time()))
    execute("UPDATE users SET name=?, username=?, bot_blocked=0 WHERE user_id=?", (u.full_name, getattr(u, "username", None), u.id))
    if is_new and referrer_id and referrer_id != u.id:
        if fetch("SELECT 1 FROM users WHERE user_id=?", (referrer_id,)):
            execute("UPDATE users SET referred_by=? WHERE user_id=? AND referred_by IS NULL", (referrer_id, u.id))
    if ad_source:
        execute("UPDATE users SET ad_source=COALESCE(ad_source, ?) WHERE user_id=?", (ad_source[:30], u.id))


def user_best_package(user_id):
    rows = fetch("SELECT package FROM orders WHERE user_id=? AND status='approved'", (user_id,))
    pkgs = {r["package"] for r in rows}
    if "bundle" in pkgs or "upgrade" in pkgs:
        return "bundle"
    return "books" if "books" in pkgs else None


def st_get(user_id):
    rows = fetch("SELECT * FROM sessions WHERE user_id=?", (user_id,))
    return dict(rows[0]) if rows else {}


def st_set(user_id, **kv):
    allowed = {"pkg", "step", "photo", "pay_started", "reminded", "promo_code", "discount"}
    if not set(kv) <= allowed:
        raise ValueError(f"unknown session field: {set(kv) - allowed}")
    execute("INSERT OR IGNORE INTO sessions(user_id) VALUES(?)", (user_id,))
    if kv:
        cols = ", ".join(f"{k}=?" for k in kv)
        execute(f"UPDATE sessions SET {cols} WHERE user_id=?", (*kv.values(), user_id))


def st_reset_step(user_id):
    execute("UPDATE sessions SET step=NULL WHERE user_id=? AND step IS NOT NULL", (user_id,))


def st_clear(user_id):
    execute("DELETE FROM sessions WHERE user_id=?", (user_id,))


def get_lang(user_id):
    rows = fetch("SELECT lang FROM users WHERE user_id=?", (user_id,))
    return rows[0]["lang"] if rows and rows[0]["lang"] in T else "am"


def referral_link_for(user_id):
    return f"https://t.me/{BOT_USERNAME or 'bot'}?start=ref_{user_id}"


# ---------------------------------------------------------------- Group Motivation & Deep-Link Helpers
def group_deeplink_kb():
    """በ Private ግሩፑ ላይ ከሚለቀቁ ፖስቶች ስር የሚታዩ የ1-ንኪ አዝራሮች (ቀጥታ ወደ ቦቱ ይወስዳሉ)"""
    uname = BOT_USERNAME or "bot"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔥 የዛሬ ልምምዴን ሰርቻለሁ (Streak)", url=f"https://t.me/{uname}?start=streak")],
            [InlineKeyboardButton("📏 የዛሬ ቁመቴን ልመዝግብ (Height Log)", url=f"https://t.me/{uname}?start=log_h")],
        ]
    )


async def post_motivation_to_groups(bot):
    """ቦቱ በራሱ የተለያዩ አነቃቂ ጽሑፎችን እየመረጠ ወደ Private ግሩፖቹ ይለቃል"""
    global LAST_GROUP_POST_TS, GROUP_POST_IDX
    LAST_GROUP_POST_TS = time.time()
    if not GROUP_MOTIVATION_POSTS:
        return 0
    text = GROUP_MOTIVATION_POSTS[GROUP_POST_IDX % len(GROUP_MOTIVATION_POSTS)]
    GROUP_POST_IDX += 1
    kb = group_deeplink_kb()
    chans = {channel_for("books"), channel_for("bundle")} - {0}
    sent = 0
    for cid in chans:
        try:
            await bot.send_message(cid, text, reply_markup=kb)
            sent += 1
        except Exception:
            log.warning("could not post motivation to group %s", cid)
    return sent


async def announce_in_user_group(bot, user_id, msg_text):
    """አንድ አባል ቁመት ሲጨምር ወይም Streak ሲሞላ በግሩፑ ውስጥ ለሌሎች ማነቃቂያ እንዲሆን ይለጥፋል"""
    best = user_best_package(user_id)
    if not best:
        return
    cid = channel_for(best)
    if cid:
        try:
            await bot.send_message(cid, msg_text, reply_markup=group_deeplink_kb())
        except Exception:
            pass


# ---------------------------------------------------------------- Smart Image Check & Auto Progress Card
def check_image_quality(data: bytes) -> bool:
    if Image is None:
        return True
    try:
        img = Image.open(io.BytesIO(data)).convert("L")
        w, h = img.size
        if w < 180 or h < 180:
            return False
        pixels = list(img.resize((64, 64)).getdata())
        mean_val = sum(pixels) / len(pixels)
        variance = sum((p - mean_val) ** 2 for p in pixels) / len(pixels)
        return not (mean_val < 18 or mean_val > 250 or variance < 60)
    except Exception:
        return True


def generate_progress_card(name: str, start_cm: float, current_cm: float) -> bytes:
    if Image is None or ImageDraw is None:
        return None
    try:
        w, h = 800, 450
        img = Image.new("RGB", (w, h), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, w - 20, h - 20], outline=(56, 189, 248), width=4)
        font_lg = ImageFont.load_default()
        diff = round(current_cm - start_cm, 1)
        clean_name = re.sub(r"[^A-Za-z0-9 ]", "", name or "Member").strip()[:22] or "VIP Member"
        draw.text((60, 60), f"{config.BOT_NAME.upper()} — OFFICIAL PROGRESS CARD", fill=(56, 189, 248), font=font_lg)
        draw.text((60, 130), f"Member: {clean_name}", fill=(248, 250, 252), font=font_lg)
        draw.text((60, 190), f"Starting Height: {start_cm:g} CM", fill=(148, 163, 184), font=font_lg)
        draw.text((60, 240), f"Current Height:  {current_cm:g} CM", fill=(248, 250, 252), font=font_lg)
        draw.rectangle([60, 300, 460, 370], fill=(16, 185, 129))
        draw.text((85, 328), f"TOTAL GAIN: +{diff:g} CM VERIFIED", fill=(255, 255, 255), font=font_lg)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def get_social_and_bonus_footer(user_id, lang):
    today_real = fetch("SELECT COUNT(*) AS n FROM orders WHERE status='approved' AND date(created)=date('now')")[0]["n"]
    today_count = today_real + (int(time.strftime("%j")) % 7 + 9)
    mins_ago = (int(time.time() // 60) % 14) + 3
    social = T[lang]["social_proof_line"].format(today_count=today_count, mins_ago=mins_ago)
    rows = fetch("SELECT offer_seen_at FROM users WHERE user_id=?", (user_id,))
    seen_at = rows[0]["offer_seen_at"] if rows and rows[0]["offer_seen_at"] else time.time()
    rem_sec = max(0.0, (FAST_BONUS_HOURS * 3600) - (time.time() - seen_at))
    bonus = T[lang]["fast_bonus_line"].format(rem_hr=f"{int(rem_sec // 3600)}h {int((rem_sec % 3600) // 60)}m") if rem_sec > 0 else ""
    return social + bonus


# ---------------------------------------------------------------- screen helpers
def keyboard(prefix, codes, labels, cols=1, back=None, lang="am"):
    buttons = [InlineKeyboardButton(label, callback_data=f"{prefix}:{code}") for code, label in zip(codes, labels)]
    rows = [buttons[i : i + cols] for i in range(0, len(buttons), cols)]
    if back:
        rows.append([back_button(lang, back)])
    return InlineKeyboardMarkup(rows)


def back_button(lang, target):
    return InlineKeyboardButton(T[lang]["btn_back"], callback_data=f"go:{target}")


def one_button(lang, label_key, target, back=None):
    rows = [[InlineKeyboardButton(T[lang][label_key], callback_data=f"go:{target}")]]
    if back:
        rows.append([back_button(lang, back)])
    return InlineKeyboardMarkup(rows)


_TASKS = set()


def ack(q):
    async def _go():
        try:
            await q.answer()
        except Exception:
            pass

    t = asyncio.get_running_loop().create_task(_go())
    _TASKS.add(t)
    t.add_done_callback(_TASKS.discard)


def track(context, *items):
    ids = context.user_data.setdefault("msgs", [])
    for item in items:
        if isinstance(item, (list, tuple)):
            ids.extend(m.message_id for m in item)
        elif item is not None:
            ids.append(item.message_id)


async def delete_many(context, chat_id, ids):
    await asyncio.gather(*(context.bot.delete_message(chat_id, mid) for mid in ids), return_exceptions=True)


FILE_IDS = {}


def _file_id(msg, kind):
    try:
        obj = getattr(msg, kind)
        return obj[-1].file_id if kind == "photo" else obj.file_id
    except Exception:
        return None


async def send_video_cached(bot, chat_id, path, **kw):
    key = str(path)
    kw.setdefault("supports_streaming", True)
    if key in FILE_IDS:
        return await bot.send_video(chat_id, FILE_IDS[key], **kw)
    with open(path, "rb") as f:
        msg = await bot.send_video(chat_id, f, read_timeout=120, write_timeout=120, **kw)
    if _file_id(msg, "video"):
        FILE_IDS[key] = _file_id(msg, "video")
    return msg


async def send_voice_cached(bot, chat_id, path, **kw):
    key = f"voice:{path}"
    if key in FILE_IDS:
        return await bot.send_voice(chat_id, FILE_IDS[key], **kw)
    with open(path, "rb") as f:
        msg = await bot.send_voice(chat_id, f, read_timeout=60, write_timeout=60, **kw)
    fid = _file_id(msg, "voice") or _file_id(msg, "audio")
    if fid:
        FILE_IDS[key] = fid
    return msg


# ---------------------------------------------------------------- screens
PKG_LABEL = {
    "books": "📕 መጽሐፍ ብቻ (Private Group)",
    "bundle": "👑 መጽሐፍ + ቪዲዮ (VIP Group)",
    "upgrade": "⬆️ ወደ VIP ግሩፕ ማሳደጊያ",
    "gift_books": "🎁 ስጦታ፦ መጽሐፍ ብቻ ግሩፕ",
    "gift_bundle": "🎁👑 ስጦታ፦ መጽሐፍ + ቪዲዮ ግሩፕ",
}


def photo_list():
    photos = []
    if config.TESTIMONIAL_DIR.exists():
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            photos += sorted(config.TESTIMONIAL_DIR.glob(ext))
    return photos[:10]


def b_lang(context, user, lang):
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang:am")],
            [InlineKeyboardButton("🌳 Afaan Oromoo", callback_data="lang:om")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")],
        ]
    )
    return CHOOSE_LANG, kb


def b_welcome(context, user, lang):
    return T[lang]["welcome"].format(name=user.first_name or "", brand=config.BOT_NAME), one_button(lang, "btn_begin", "q1", back="lang")


def b_q1(context, user, lang):
    return T[lang]["ask_height"], keyboard("height", HEIGHT_CODES, T[lang]["heights"], back="welcome", lang=lang)


def b_q2(context, user, lang):
    return T[lang]["ask_age"], keyboard("age", AGE_CODES, T[lang]["ages"], back="q1", lang=lang)


def b_q3(context, user, lang):
    return T[lang]["ask_gender"], keyboard("gender", GENDER_CODES, T[lang]["genders"], back="q2", lang=lang)


def answer_label(lang, key, codes, code):
    return T[lang][key][codes.index(code)] if code in codes else "—"


def b_offer(context, user, lang):
    rows = fetch("SELECT age, gender, height FROM users WHERE user_id=?", (user.id,))
    r = dict(rows[0]) if rows else {}
    age_code = r.get("age")
    analysis_key = "analysis_adult" if age_code == "a4" else "analysis_young"
    text = T[lang]["result"].format(
        height=answer_label(lang, "heights", HEIGHT_CODES, r.get("height")),
        age=answer_label(lang, "ages", AGE_CODES, age_code),
        gender=answer_label(lang, "genders", GENDER_CODES, r.get("gender")),
        custom_analysis=T[lang].get(analysis_key, T["am"][analysis_key]),
    )
    return text, one_button(lang, "btn_video", "video", back="q3")


def b_video(context, user, lang):
    if config.INTRO_VIDEO.exists():
        return None
    return T[lang]["video_intro"], one_button(lang, "btn_watched", "proof", back="offer")


def b_proof(context, user, lang):
    if photo_list():
        return None
    entries = config.TESTIMONIALS.get(lang) or []
    text = (T[lang]["proof_header"] + "\n\n" + "\n\n".join(entries)) if entries else T[lang]["proof_text"]
    return text, one_button(lang, "btn_decided", "pkg", back="video")


def get_ref_stats(user_id):
    rows = fetch("SELECT COALESCE(ref_paid_count, 0) AS c FROM users WHERE user_id=?", (user_id,))
    cnt = rows[0]["c"] if rows else 0
    return cnt, REFERRAL_TARGET, max(0, REFERRAL_TARGET - cnt)


def b_pkg(context, user, lang):
    p = config.PRICES
    cnt, target, _ = get_ref_stats(user.id)
    text = config.OFFER[lang].format(price=p["books"], price_bundle=p["bundle"], accounts="") + get_social_and_bonus_footer(user.id, lang)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(T[lang]["btn_books"].format(price=p["books"]), callback_data="pkg:books")],
            [InlineKeyboardButton(T[lang]["btn_bundle"].format(price=p["bundle"]), callback_data="pkg:bundle")],
            [
                InlineKeyboardButton(T[lang]["btn_buy_gift"], callback_data="go:gift"),
                InlineKeyboardButton(T[lang]["btn_redeem_gift"], callback_data="gift:redeem"),
            ],
            [InlineKeyboardButton(T[lang]["btn_refer"].format(count=cnt, target=target), callback_data="go:refer")],
            [back_button(lang, "proof")],
        ]
    )
    return text, kb


def b_gift(context, user, lang):
    p = config.PRICES
    back_target = "vip" if user_best_package(user.id) else "pkg"
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(T[lang]["btn_gift_books"].format(price=p["gift_books"]), callback_data="pkg:gift_books")],
            [InlineKeyboardButton(T[lang]["btn_gift_bundle"].format(price=p["gift_bundle"]), callback_data="pkg:gift_bundle")],
            [back_button(lang, back_target)],
        ]
    )
    return T[lang]["gift_menu_text"], kb


def format_height_progress(user_id, lang):
    rows = fetch("SELECT start_cm, current_cm FROM users WHERE user_id=?", (user_id,))
    if not rows or not rows[0]["start_cm"]:
        return T[lang]["height_none"]
    s, c = rows[0]["start_cm"], rows[0]["current_cm"] or rows[0]["start_cm"]
    diff = round(c - s, 1)
    return f"{s:g} CM ➔ {c:g} CM (+{diff:g} CM 🚀)" if diff > 0 else f"{c:g} CM"


def b_vip(context, user, lang):
    best = user_best_package(user.id) or "books"
    cnt, target, _ = get_ref_stats(user.id)
    h_prog = format_height_progress(user.id, lang)
    u_rows = fetch("SELECT COALESCE(streak_count, 0) AS sc FROM users WHERE user_id=?", (user.id,))
    streak = u_rows[0]["sc"] if u_rows else 0
    text = T[lang]["vip_welcome"].format(
        name=user.first_name or "", pkg_name=PKG_LABEL.get(best, best), streak=streak, height_progress=h_prog, ref_count=cnt, ref_target=target
    )
    rows = [
        [InlineKeyboardButton(T[lang]["btn_streak"].format(streak=streak), callback_data="vip:streak")],
        [InlineKeyboardButton(T[lang]["btn_log_height"], callback_data="vip:log_h")],
        [InlineKeyboardButton(T[lang]["btn_vip_files"], callback_data="vip:files")],
    ]
    if best == "books":
        rows.append([InlineKeyboardButton(T[lang]["btn_upgrade"].format(price=config.PRICES.get("upgrade", 200)), callback_data="pkg:upgrade")])
    rows.append([InlineKeyboardButton(T[lang]["btn_buy_gift"], callback_data="go:gift")])
    rows.append([InlineKeyboardButton(T[lang]["btn_refer"].format(count=cnt, target=target), callback_data="go:refer")])
    rows.append([InlineKeyboardButton(T[lang]["btn_vip_restart"], callback_data="go:lang")])
    return text, InlineKeyboardMarkup(rows)


def b_refer(context, user, lang):
    cnt, target, rem = get_ref_stats(user.id)
    link = referral_link_for(user.id)
    text = T[lang]["refer_text"].format(link=link, count=cnt, target=target, rem=rem)
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(link)}&text={urllib.parse.quote('🔥 በተፈጥሯዊ መንገድ ቁመት ለመጨመር የሚረዳ ምርጥ የቴሌግራም ቦት!')}"
    back_target = "vip" if user_best_package(user.id) else "pkg"
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(T[lang]["btn_share_tg"], url=share_url)],
            [InlineKeyboardButton("📋 ሊንኩን ቅዳ (Copy Link)", copy_text=CopyTextButton(text=link))],
            [back_button(lang, back_target)],
        ]
    )
    return text, kb


def account_copy_rows(lang="am", has_promo=False):
    rows = []
    for line in config.PAYMENT_ACCOUNTS.splitlines():
        nums = re.findall(r"\d{6,}", line)
        if nums:
            label = re.sub(r"\s*\(.*?\)", "", line).strip()[:55]
            rows.append([InlineKeyboardButton(f"📋 {label}", copy_text=CopyTextButton(text=nums[0]))])
    rows = rows[:6]
    ussd_row = []
    if getattr(config, "TELEBIRR_PHONE", ""):
        ussd_row.append(InlineKeyboardButton(T[lang]["ussd_telebirr_btn"], copy_text=CopyTextButton(text="*127#")))
    if getattr(config, "CBE_ACCOUNT", ""):
        ussd_row.append(InlineKeyboardButton(T[lang]["ussd_cbe_btn"], copy_text=CopyTextButton(text="*889#")))
    if ussd_row:
        rows.append(ussd_row)
    if not has_promo:
        rows.append([InlineKeyboardButton(T[lang]["btn_promo"], callback_data="promo:ask")])
    rows.append([InlineKeyboardButton(T[lang]["faq_time_btn"], callback_data="faq:time")])
    rows.append([InlineKeyboardButton(T[lang]["faq_other_btn"], callback_data="faq:other")])
    return rows


def b_pay(context, user, lang):
    s = st_get(user.id)
    pkg = s.get("pkg")
    if pkg not in config.PRICES:
        return b_pkg(context, user, lang)
    disc = int(s.get("discount") or 0)
    final_price = max(10, config.PRICES[pkg] - disc)
    disc_note = f"(🎟️ -{disc} ብር ቅናሽ!)" if disc > 0 else ""
    text = T[lang]["pay"].format(price=final_price, discount_note=disc_note, accounts=config.PAYMENT_ACCOUNTS, extra_footer=get_social_and_bonus_footer(user.id, lang))
    st_set(user.id, step="await_photo", pay_started=s.get("pay_started") or time.time())
    back_target = "gift" if pkg.startswith("gift_") else ("vip" if pkg == "upgrade" else "pkg")
    return text, InlineKeyboardMarkup(account_copy_rows(lang, has_promo=bool(disc)) + [[back_button(lang, back_target)]])


BUILD = {
    "lang": b_lang, "welcome": b_welcome, "q1": b_q1, "q2": b_q2, "q3": b_q3,
    "offer": b_offer, "video": b_video, "proof": b_proof, "pkg": b_pkg, "pay": b_pay,
    "vip": b_vip, "refer": b_refer, "gift": b_gift,
}


def make_text_screen(name):
    async def screen(context, chat_id, user, lang):
        text, kb = BUILD[name](context, user, lang)
        track(context, await context.bot.send_message(chat_id, text, reply_markup=kb))

    return screen


async def scr_video(context, chat_id, user, lang):
    kb = one_button(lang, "btn_watched", "proof", back="offer")
    msg = await (send_video_cached(context.bot, chat_id, config.INTRO_VIDEO, caption=T[lang]["video_intro"], reply_markup=kb) if config.INTRO_VIDEO.exists() else context.bot.send_message(chat_id, T[lang]["video_intro"], reply_markup=kb))
    track(context, msg)


async def scr_proof(context, chat_id, user, lang):
    photos = photo_list()
    key = ("photos",) + tuple(str(p) for p in photos)
    cached = FILE_IDS.get(key)
    if len(photos) == 1:
        msg = await context.bot.send_photo(chat_id, cached[0] if cached else photos[0].read_bytes())
        if not cached and _file_id(msg, "photo"):
            FILE_IDS[key] = [_file_id(msg, "photo")]
        track(context, msg)
    elif photos:
        media = [InputMediaPhoto(c if cached else p.read_bytes()) for c, p in zip(cached or photos, photos)]
        msgs = await context.bot.send_media_group(chat_id, media)
        if not cached:
            fids = [_file_id(m, "photo") for m in msgs]
            if all(fids):
                FILE_IDS[key] = fids
        track(context, msgs)
    entries = config.TESTIMONIALS.get(lang) or []
    text = (T[lang]["proof_header"] + "\n\n" + "\n\n".join(entries)) if entries else T[lang]["proof_text"]
    track(context, await context.bot.send_message(chat_id, text, reply_markup=one_button(lang, "btn_decided", "pkg", back="video")))


async def maybe_send_pay_voice(context, chat_id, lang):
    voice_map = getattr(config, "PAY_VOICE_NOTES", {}) or {}
    path = voice_map.get(lang) or voice_map.get("am")
    if path and Path(path).exists():
        try:
            track(context, await send_voice_cached(context.bot, chat_id, path, caption=T[lang].get("voice_caption", "")))
        except Exception:
            pass


SCREENS = {name: make_text_screen(name) for name in BUILD}
SCREENS["video"] = scr_video
SCREENS["proof"] = scr_proof

_LOCKS = {}


def _can_edit(q):
    return bool(getattr(q.message, "text", None))


async def play_loading(context, chat_id, lang, current, can_edit):
    frames = [T[lang]["loading_1"], T[lang]["loading_2"], T[lang]["loading_3"]]
    mid = None
    if current is not None and can_edit:
        try:
            await context.bot.edit_message_text(frames[0], chat_id=chat_id, message_id=current)
            mid = current
        except Exception:
            mid = None
    if mid is None:
        mid = (await context.bot.send_message(chat_id, frames[0])).message_id
    for frame in frames[1:]:
        await asyncio.sleep(0.5)
        try:
            await context.bot.edit_message_text(frame, chat_id=chat_id, message_id=mid)
        except Exception:
            pass
    return mid


async def show(name, context, chat_id, user, current=None, can_edit=False):
    lock = _LOCKS.setdefault(user.id, asyncio.Lock())
    async with lock:
        old = context.user_data.pop("msgs", [])
        if current is not None and current not in old:
            old.append(current)
        st_reset_step(user.id)
        mark_funnel(user.id, name)
        lang = get_lang(user.id)
        if name == "offer":
            current = await play_loading(context, chat_id, lang, current, can_edit)
            can_edit = True
        edited = False
        built = BUILD[name](context, user, lang)
        if built and current is not None and can_edit:
            try:
                await context.bot.edit_message_text(built[0], chat_id=chat_id, message_id=current, reply_markup=built[1])
                edited = True
            except Exception as e:
                edited = "not modified" in str(e).lower()
        if edited:
            context.user_data["msgs"] = [current]
            old = [m for m in old if m != current]
        else:
            if name == "offer" and current is not None:
                old.append(current)
            await SCREENS[name](context, chat_id, user, lang)
        if name == "pay":
            await maybe_send_pay_voice(context, chat_id, lang)
        await delete_many(context, chat_id, old)


# ---------------------------------------------------------------- Streak helper
async def process_user_streak(bot, user, lang):
    today_str = time.strftime("%Y-%m-%d")
    yest_str = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 86400))
    r = fetch("SELECT COALESCE(streak_count,0) AS sc, streak_last_date FROM users WHERE user_id=?", (user.id,))[0]
    if r["streak_last_date"] == today_str:
        return False, r["sc"], T[lang]["streak_already"].format(streak=r["sc"])
    new_sc = (r["sc"] + 1) if r["streak_last_date"] == yest_str else 1
    execute("UPDATE users SET streak_count=?, streak_last_date=? WHERE user_id=?", (new_sc, today_str, user.id))
    if new_sc == 7:
        try:
            await bot.send_message(user.id, T[lang]["streak_7_secret"])
        except Exception:
            pass
    if new_sc in (3, 7, 14, 21, 30):
        await announce_in_user_group(bot, user.id, f"🔥 **እንኳን ደስ አለህ {user.first_name}!**\nለ **{new_sc} ተከታታይ ቀናት (Streak)** የቁመት ልምምዱን ሳያቋርጥ ሰርቷል! 👏💪")
    return True, new_sc, T[lang]["streak_up"].format(streak=new_sc)


# ---------------------------------------------------------------- customer flow
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    u = update.effective_user
    referrer_id = ad_source = deep_action = None
    if context.args:
        arg = context.args[0]
        if arg in ("streak", "log_h"):
            deep_action = arg
        elif arg.startswith("ref_") and arg[4:].isdigit():
            referrer_id, ad_source = int(arg[4:]), "referral"
        elif arg.startswith("src_"):
            ad_source = arg[4:].lower()
        else:
            ad_source = arg.lower()

    ensure_user(u, referrer_id=referrer_id, ad_source=ad_source)
    st_clear(u.id)
    lang = get_lang(u.id)
    try:
        await update.message.delete()
    except Exception:
        pass

    # ከ Private ግሩፑ ላይ ባለው አዝራር ቀጥታ ወደ ቦቱ ሲገቡ (Deep-Link Actions)
    if user_best_package(u.id):
        if deep_action == "streak":
            _, _, msg_txt = await process_user_streak(context.bot, u, lang)
            await context.bot.send_message(u.id, msg_txt)
            await show("vip", context, update.effective_chat.id, u)
            return
        if deep_action == "log_h":
            await show("vip", context, update.effective_chat.id, u)
            st_set(u.id, step="await_height")
            await context.bot.send_message(u.id, T[lang]["ask_log_height"])
            return
        await show("vip", context, update.effective_chat.id, u)
        return

    execute("UPDATE users SET started_at=?, followup_stage=0, bot_blocked=0 WHERE user_id=?", (time.time(), u.id))
    await show("lang", context, update.effective_chat.id, u)


async def cmd_refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    await show("refer", context, update.effective_chat.id, update.effective_user)


async def on_vip_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = q.from_user
    lang = get_lang(u.id)
    action = q.data.split(":")[1]
    if action == "files":
        rows = fetch(
            "SELECT * FROM orders WHERE user_id=? AND status='approved' AND package IN ('books','bundle','upgrade') ORDER BY CASE WHEN package IN ('bundle','upgrade') THEN 0 ELSE 1 END, id DESC LIMIT 1",
            (u.id,),
        )
        if not rows:
            await q.answer("ምንም የተረጋገጠ ትዕዛዝ አልተገኘም", show_alert=True)
            return
        await q.answer("🔗 አዲስ የ Private ግሩፕ መግቢያ ሊንክ እየተላከ ነው...")
        await send_invite(context.bot, dict(rows[0]))
    elif action == "log_h":
        ack(q)
        st_set(u.id, step="await_height")
        await context.bot.send_message(u.id, T[lang]["ask_log_height"])
    elif action == "streak":
        changed, _, msg_txt = await process_user_streak(context.bot, u, lang)
        await q.answer(msg_txt[:200], show_alert=True)
        if changed:
            await show("vip", context, q.message.chat_id, u, current=q.message.message_id, can_edit=_can_edit(q))


async def on_gift_redeem_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    ack(q)
    uid = q.from_user.id
    st_set(uid, step="await_gift")
    await context.bot.send_message(uid, T[get_lang(uid)]["ask_gift_code"])


async def on_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    ack(q)
    name = q.data.split(":")[1]
    if name in SCREENS and name != "pay":
        await show(name, context, q.message.chat_id, q.from_user, current=q.message.message_id, can_edit=_can_edit(q))


async def on_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    ack(q)
    lang = q.data.split(":")[1]
    if lang in T:
        ensure_user(q.from_user)
        execute("UPDATE users SET lang=? WHERE user_id=?", (lang, q.from_user.id))
        await show("welcome", context, q.message.chat_id, q.from_user, current=q.message.message_id, can_edit=_can_edit(q))


NEXT_AFTER = {"height": "q2", "age": "q3", "gender": "offer"}


async def on_profile_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    ack(q)
    field, code = q.data.split(":")
    if field in NEXT_AFTER:
        execute(f"UPDATE users SET {field}=? WHERE user_id=?", (code, q.from_user.id))
        await show(NEXT_AFTER[field], context, q.message.chat_id, q.from_user, current=q.message.message_id, can_edit=_can_edit(q))


async def on_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    ack(q)
    pkg = q.data.split(":")[1]
    if pkg in config.PRICES:
        st_set(q.from_user.id, pkg=pkg, promo_code=None, discount=0)
        await show("pay", context, q.message.chat_id, q.from_user, current=q.message.message_id, can_edit=_can_edit(q))


async def on_promo_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    ack(q)
    st_set(q.from_user.id, step="await_promo")
    await context.bot.send_message(q.from_user.id, T[get_lang(q.from_user.id)]["ask_promo"])


async def on_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    key = "faq_time_ans" if q.data.split(":")[1] == "time" else "faq_other_ans"
    await q.answer(T[get_lang(q.from_user.id)][key][:200], show_alert=True)


async def on_send_testi_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    ack(q)
    st_set(q.from_user.id, step="await_testi")
    await context.bot.send_message(q.from_user.id, T[get_lang(q.from_user.id)]["ask_testi"])


def incoming_file(msg):
    if msg.photo:
        return msg.photo[-1].file_id, msg.photo[-1].file_unique_id
    if msg.document and (msg.document.mime_type or "").startswith("image/"):
        return "doc:" + msg.document.file_id, msg.document.file_unique_id
    return None, None


async def file_fingerprint(bot, fid):
    try:
        f = await bot.get_file(fid[4:] if fid.startswith("doc:") else fid)
        if f.file_size and f.file_size > 8_000_000:
            return None, None, True
        data = bytes(await f.download_as_bytearray())
        loop = asyncio.get_running_loop()
        quality_ok = await loop.run_in_executor(None, check_image_quality, data)
        digest = hashlib.sha256(data).hexdigest()
        small = await loop.run_in_executor(None, ocr.thumb, data)
        return digest, small, quality_ok
    except Exception:
        return None, None, True


def _similar_exists(small, limit):
    try:
        mine = ocr.to_array(small)
    except Exception:
        return False
    for r in fetch("SELECT photo_thumb FROM orders WHERE photo_thumb IS NOT NULL ORDER BY id DESC LIMIT 3000"):
        try:
            if ocr.differing_blocks(mine, ocr.to_array(bytes(r["photo_thumb"]))) <= limit:
                return True
        except Exception:
            continue
    return False


async def is_duplicate_receipt(uniq, digest, small=None):
    conds, args = [], []
    if uniq:
        conds.append("photo_uid=?")
        args.append(uniq)
    if digest:
        conds.append("photo_hash=?")
        args.append(digest)
    if conds and fetch(f"SELECT id FROM orders WHERE {' OR '.join(conds)}", args):
        return True
    limit = getattr(config, "DUP_MAX_BLOCKS", 6)
    if small and limit > 0:
        return await asyncio.get_running_loop().run_in_executor(None, _similar_exists, small, limit)
    return False


def ready_to_pay(s):
    return s.get("step") in ("await_photo", "await_promo") and s.get("pkg") in config.PRICES


async def update_live_user_status(bot, order, text_key):
    mid = order.get("user_status_msg")
    if mid:
        try:
            await bot.edit_message_text(T[get_lang(order["user_id"])][text_key], chat_id=order["user_id"], message_id=mid)
        except Exception:
            pass


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    lang = get_lang(uid)
    s = st_get(uid)
    if not ready_to_pay(s):
        await update.message.reply_text(T[lang]["hint"])
        return
    fid, uniq = incoming_file(update.message)
    if not fid:
        await update.message.reply_text(T[lang]["need_photo"])
        return
    digest, small, quality_ok = await file_fingerprint(context.bot, fid)
    if not quality_ok:
        await update.message.reply_text(T[lang]["bad_photo_quality"])
        return
    try:
        await update.message.set_reaction("❤️")
        await context.bot.send_chat_action(chat_id=uid, action=ChatAction.TYPING)
    except Exception:
        pass
    if await is_duplicate_receipt(uniq, digest, small):
        await update.message.reply_text(T[lang]["dup_receipt"])
        return
    if fetch("SELECT COUNT(*) AS n FROM orders WHERE user_id=? AND status='pending'", (uid,))[0]["n"] >= MAX_PENDING_PER_USER:
        await update.message.reply_text(T[lang]["help_busy"])
        return
    pkg, disc, promo = s["pkg"], int(s.get("discount") or 0), s.get("promo_code")
    final_price = max(10, config.PRICES[pkg] - disc)
    try:
        order_id = execute(
            "INSERT INTO orders(user_id, package, price, promo_code, photo_file_id, photo_uid, photo_hash, photo_thumb) VALUES(?,?,?,?,?,?,?,?)",
            (uid, pkg, final_price, promo, fid, uniq, digest, small),
        )
    except sqlite3.IntegrityError:
        await update.message.reply_text(T[lang]["dup_receipt"])
        return
    if promo:
        execute("UPDATE promos SET used_count = COALESCE(used_count, 0) + 1 WHERE code=?", (promo,))
    st_clear(uid)
    ensure_user(user)
    status_msg = await update.message.reply_text(T[lang]["received"])
    execute("UPDATE orders SET user_status_msg=? WHERE id=?", (status_msg.message_id, order_id))
    await send_order_to_admin(context.bot, order_id)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    txt = (update.message.text or "").strip()

    if uid == ADMIN_ID and not update.message.reply_to_message:
        if any(w in txt.lower() for w in ("etb", "birr", "telebirr", "cbe", "transferred", "credited", "received")):
            added = register_sms_text(txt)
            if added:
                await update.message.reply_text(f"✅ የክፍያ SMS ተመዝግቧል፦ {', '.join(added)}")
                await try_match_pending_with_sms(context.bot)
                return

    s = st_get(uid)
    lang = get_lang(uid)

    if s.get("step") == "await_gift":
        code = txt.upper().strip()
        rows = fetch("SELECT * FROM gifts WHERE code=? AND redeemed_by IS NULL", (code,))
        if not rows or not execute_rc("UPDATE gifts SET redeemed_by=? WHERE code=? AND redeemed_by IS NULL", (uid, code)):
            st_clear(uid)
            await update.message.reply_text(T[lang]["gift_invalid"])
            return
        st_clear(uid)
        order_id = execute("INSERT INTO orders(user_id, package, price, ref, status) VALUES(?,?,0,?,'approved')", (uid, rows[0]["package"], code))
        order = dict(fetch("SELECT * FROM orders WHERE id=?", (order_id,))[0])
        await update.message.reply_text(T[lang]["gift_redeemed_ok"])
        await deliver_approved_order(context.bot, order)
        return

    if s.get("step") == "await_height":
        nums = re.findall(r"\d+(?:\.\d+)?", txt)
        if not nums or not (100 <= float(nums[0]) <= 250):
            await update.message.reply_text(T[lang]["log_height_invalid"])
            return
        cm = round(float(nums[0]), 1)
        st_clear(uid)
        rows = fetch("SELECT start_cm FROM users WHERE user_id=?", (uid,))
        start_cm = rows[0]["start_cm"] if rows and rows[0]["start_cm"] else None
        if not start_cm:
            execute("UPDATE users SET start_cm=?, current_cm=? WHERE user_id=?", (cm, cm, uid))
            await update.message.reply_text(T[lang]["log_height_first"].format(cm=f"{cm:g}"))
        else:
            execute("UPDATE users SET current_cm=? WHERE user_id=?", (cm, uid))
            diff = round(cm - start_cm, 1)
            if diff > 0:
                await update.message.reply_text(T[lang]["log_height_gain"].format(diff=f"{diff:g}", start=f"{start_cm:g}", cm=f"{cm:g}"))
                await announce_in_user_group(context.bot, uid, f"🎉 **አስደናቂ ውጤት በግሩፓችን!**\nአባላችን **{user.first_name}** ልምምዱን በትክክል በመስራት **+{diff:g} CM** ቁመት ጨምሯል! ({start_cm:g} CM ➔ {cm:g} CM) 🚀👏")
                card_bytes = await asyncio.get_running_loop().run_in_executor(None, generate_progress_card, user.first_name, start_cm, cm)
                if card_bytes:
                    try:
                        await context.bot.send_photo(uid, card_bytes, caption=T[lang]["card_caption"])
                        await context.bot.send_photo(ADMIN_ID, card_bytes, caption=f"🎉 ደንበኛ {user.full_name} (ID: {uid}) +{diff:g} CM አድጓል!")
                    except Exception:
                        pass
            else:
                await update.message.reply_text(T[lang]["log_height_same"].format(cm=f"{cm:g}"))
        await show("vip", context, update.effective_chat.id, user)
        return

    if s.get("step") == "await_promo" and s.get("pkg") in config.PRICES:
        code = txt.upper()
        rows = fetch("SELECT * FROM promos WHERE code=? AND used_count < max_uses", (code,))
        if not rows:
            st_set(uid, step="await_photo")
            await update.message.reply_text(T[lang]["promo_invalid"])
            return
        disc = int(rows[0]["discount"])
        new_price = max(10, config.PRICES[s["pkg"]] - disc)
        st_set(uid, promo_code=code, discount=disc, step="await_photo")
        await update.message.reply_text(T[lang]["promo_ok"].format(disc=disc, new_price=new_price))
        await show("pay", context, update.effective_chat.id, user)
        return

    if s.get("step") == "await_testi":
        st_clear(uid)
        uname = f" @{user.username}" if user.username else ""
        m = await context.bot.send_message(ADMIN_ID, f"🌟 አዲስ ምስክርነት!\nደንበኛ፦ {user.full_name}{uname} (ID: {uid})\n\n💬 “{txt}”")
        execute("INSERT OR REPLACE INTO support(msg_id, user_id) VALUES(?, ?)", (m.message_id, uid))
        await update.message.reply_text(T[lang]["testi_thanks"])
        return

    await update.message.reply_text(T[lang]["need_photo" if ready_to_pay(s) else "hint"])


# ---------------------------------------------------------------- Admin Commands (/postgroup, /find, /addpromo, etc.)
async def cmd_postgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """አድሚኑ ወዲያውኑ ወደ Private ግሩፖቹ የማነቃቂያ ፖስትና የStreak/ቁመት አዝራሮችን ለመልቀቅ ሲፈልግ"""
    if update.effective_user.id != ADMIN_ID:
        return
    sent = await post_motivation_to_groups(context.bot)
    await update.message.reply_text(f"✅ የማነቃቂያ ጽሑፍ እና የ1-ንኪ አዝራሮች ወደ {sent} ግሩፕ(ዎች) ተለቋል!" if sent else "⚠️ ምንም ግሩፕ አልተገኘም (BOOKS_CHANNEL_ID / BUNDLE_CHANNEL_ID ያረጋግጡ)።")


async def cmd_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("🔎 አጠቃቀም፦ `/find <ስም፣ @username ወይም ID>`")
        return
    q_str = " ".join(context.args).strip().lstrip("@")
    rows = fetch("SELECT * FROM users WHERE user_id=? OR name LIKE ? LIMIT 5", (int(q_str), f"%{q_str}%")) if q_str.isdigit() else fetch("SELECT * FROM users WHERE name LIKE ? OR username LIKE ? LIMIT 5", (f"%{q_str}%", f"%{q_str}%"))
    if not rows:
        await update.message.reply_text("❌ ምንም ተጠቃሚ አልተገኘም።")
        return
    for u in rows:
        uid = u["user_id"]
        best = user_best_package(uid)
        uname = f" @{u['username']}" if u["username"] else ""
        info = (
            f"👤 **ደንበኛ፦** {u['name']}{uname} (`{uid}`)\n"
            f"🌐 **ምንጭ፦** {u['ad_source'] or 'ቀጥታ'} | 📊 {u['height']}/{u['age']}/{u['gender']}\n"
            f"📦 **ግሩፕ፦** {PKG_LABEL.get(best, 'አልገባም')}\n"
            f"📏 **ቁመት፦** {format_height_progress(uid, 'am')} | 🔥 Streak: {u['streak_count'] or 0}\n"
            f"🎁 **ሪፈራል፦** {u['ref_paid_count'] or 0}/{REFERRAL_TARGET}"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📕 መጽሐፍ ግሩፕ ስጥ", callback_data=f"admgrant:books:{uid}"), InlineKeyboardButton("👑 VIP ግሩፕ ስጥ", callback_data=f"admgrant:bundle:{uid}")]])
        m = await update.message.reply_text(info, reply_markup=kb)
        execute("INSERT OR REPLACE INTO support(msg_id, user_id) VALUES(?, ?)", (m.message_id, uid))


async def on_admin_grant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    _, pkg, uid_str = q.data.split(":")
    order_id = execute("INSERT INTO orders(user_id, package, price, status) VALUES(?,?,0,'approved')", (int(uid_str), pkg))
    order = dict(fetch("SELECT * FROM orders WHERE id=?", (order_id,))[0])
    ok, info = await deliver_approved_order(context.bot, order)
    await q.answer("✅ የግሩፕ መግቢያ ሊንኩ ለደንበኛው ተልኳል!" if ok else f"⚠️ {info}"[:190], show_alert=True)


async def cmd_addpromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2 or not context.args[1].isdigit():
        await update.message.reply_text("አጠቃቀም፦ `/addpromo <ኮድ> <ቅናሽ_ብር> [ብዛት]`")
        return
    code, disc = context.args[0].upper(), int(context.args[1])
    max_u = int(context.args[2]) if len(context.args) >= 3 and context.args[2].isdigit() else 100
    execute("INSERT OR REPLACE INTO promos(code, discount, max_uses, used_count) VALUES(?,?,?,0)", (code, disc, max_u))
    await update.message.reply_text(f"✅ የቅናሽ ኮድ ተፈጥሯል፦ `{code}` (-{disc} ብር፣ ለ {max_u} ሰው)")


async def cmd_delpromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        rows = fetch("SELECT * FROM promos")
        await update.message.reply_text("\n".join(["🎟️ ኮዶች፦"] + [f"• {r['code']} (-{r['discount']} ብር) — {r['used_count']}/{r['max_uses']}" for r in rows]) if rows else "ምንም የቅናሽ ኮድ የለም።")
        return
    execute("DELETE FROM promos WHERE code=?", (context.args[0].upper(),))
    await update.message.reply_text("🗑️ ተሰርዟል።")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("📢 መጀመሪያ መልዕክቱን ይላኩና እሱን **Reply** አድርገው `/broadcast` ይጻፉ።")
        return
    mid = update.message.reply_to_message.message_id
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎯 ላልከፈሉ ብቻ ላክ (Unpaid)", callback_data=f"bcast:unpaid:{mid}")],
            [InlineKeyboardButton("📕 መጽሐፍ ብቻ ለገዙ (ለ Upgrade)", callback_data=f"bcast:books:{mid}")],
            [InlineKeyboardButton("🌍 ለሁሉም ተጠቃሚዎች ላክ", callback_data=f"bcast:all:{mid}")],
        ]
    )
    await update.message.reply_text("📢 ይህ መልዕክት ለማን ይላክ?", reply_markup=kb)


async def on_broadcast_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    _, target, mid_str = q.data.split(":")
    mid = int(mid_str)
    if target == "unpaid":
        rows = fetch("SELECT user_id FROM users u WHERE COALESCE(bot_blocked,0)=0 AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id=u.user_id AND o.status='approved')")
    elif target == "books":
        rows = fetch("SELECT DISTINCT user_id FROM orders WHERE status='approved' AND package='books' AND user_id NOT IN (SELECT user_id FROM orders WHERE status='approved' AND package IN ('bundle','upgrade'))")
    else:
        rows = fetch("SELECT user_id FROM users WHERE COALESCE(bot_blocked,0)=0")
    await q.edit_message_text(f"⏳ ለ {len(rows)} ተጠቃሚዎች በመላክ ላይ...")
    sent = blocked = 0
    for r in rows:
        try:
            await context.bot.copy_message(chat_id=r["user_id"], from_chat_id=ADMIN_ID, message_id=mid)
            sent += 1
            await asyncio.sleep(0.05)
        except Forbidden:
            blocked += 1
            execute("UPDATE users SET bot_blocked=1 WHERE user_id=?", (r["user_id"],))
        except Exception:
            pass
    await context.bot.send_message(ADMIN_ID, f"✅ Broadcast ተጠናቀቀ! የደረሳቸው፦ {sent} | ብሎክ፦ {blocked}")


async def send_db_backup(bot):
    global LAST_BACKUP_TS
    LAST_BACKUP_TS = time.time()
    if DB_PATH.exists():
        try:
            with open(DB_PATH, "rb") as f:
                await bot.send_document(ADMIN_ID, f, filename=f"bot_backup_{int(LAST_BACKUP_TS)}.db", caption="💾 የዳታቤዝ ባክአፕ (bot.db)")
        except Exception:
            pass


async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await send_db_backup(context.bot)


# ---------------------------------------------------------------- Auto-Approve SMS & Referrals
def extract_tx_ids(text: str):
    candidates = re.findall(r"\b(?:FT[A-Z0-9]{8,14}|[A-Z0-9]{10,16})\b", text.upper())
    return [c for c in candidates if any(ch.isdigit() for ch in c) and any(ch.isalpha() for ch in c)]


def register_sms_text(text: str):
    txs = extract_tx_ids(text)
    nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]
    amt = next((n for n in nums if n in config.PRICES.values()), nums[0] if nums else 0.0)
    added = []
    for tx in txs:
        try:
            execute("INSERT OR IGNORE INTO sms_payments(tx_id, amount, raw_text, created) VALUES(?,?,?,?)", (tx, amt, text[:500], time.time()))
            added.append(f"{tx} ({amt} ብር)")
        except Exception:
            pass
    return added


async def cmd_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    raw = update.message.text.partition(" ")[2].strip()
    if not raw:
        await update.message.reply_text("አጠቃቀም፦ የባንክ SMS ወደ ቦቱ Forward ያድርጉ ወይም `/sms <ጽሑፍ>` ይጠቀሙ።")
        return
    added = register_sms_text(raw)
    await update.message.reply_text(f"✅ ተመዝግቧል፦ {', '.join(added)}" if added else "⚠️ የግብይት ቁጥር አልተገኘም።")
    if added:
        await try_match_pending_with_sms(context.bot)


async def try_match_pending_with_sms(bot, specific_order_id=None, ocr_text=""):
    unused_sms = fetch("SELECT * FROM sms_payments WHERE used_order_id IS NULL")
    if not unused_sms:
        return False
    orders = fetch("SELECT * FROM orders WHERE id=? AND status='pending'", (specific_order_id,)) if specific_order_id else fetch("SELECT * FROM orders WHERE status='pending'")
    for order in orders:
        check_space = (ocr_text + " " + (order["note"] or "") + " " + (order["ref"] or "")).upper()
        for sms in unused_sms:
            if sms["tx_id"] in check_space and (not sms["amount"] or abs(sms["amount"] - order["price"]) < 1.0):
                if execute_rc("UPDATE orders SET status='approved', ref=? WHERE id=? AND status='pending'", (sms["tx_id"], order["id"])):
                    execute("UPDATE sms_payments SET used_order_id=? WHERE id=?", (order["id"], sms["id"]))
                    await deliver_approved_order(bot, dict(order), auto_sms=sms["tx_id"])
                    return True
    return False


async def credit_referrer_on_purchase(bot, buyer_id, package):
    if package not in ("books", "bundle", "gift_books", "gift_bundle"):
        return
    rows = fetch("SELECT referred_by, COALESCE(ref_credited, 0) AS credited FROM users WHERE user_id=?", (buyer_id,))
    if not rows or not rows[0]["referred_by"] or rows[0]["credited"]:
        return
    referrer_id = rows[0]["referred_by"]
    if not execute_rc("UPDATE users SET ref_credited=1 WHERE user_id=? AND COALESCE(ref_credited,0)=0", (buyer_id,)):
        return
    execute("UPDATE users SET ref_paid_count = COALESCE(ref_paid_count, 0) + 1 WHERE user_id=?", (referrer_id,))
    ref_rows = fetch("SELECT name, username, lang, ref_paid_count, COALESCE(ref_rewarded, 0) AS rewarded FROM users WHERE user_id=?", (referrer_id,))
    if not ref_rows:
        return
    ref_u = ref_rows[0]
    cnt = ref_u["ref_paid_count"]
    lang = ref_u["lang"] if ref_u["lang"] in T else "am"
    if cnt >= REFERRAL_TARGET and not ref_u["rewarded"]:
        execute("UPDATE users SET ref_rewarded=1 WHERE user_id=?", (referrer_id,))
        try:
            await bot.send_message(referrer_id, T[lang]["refer_won"].format(target=REFERRAL_TARGET))
            m = await bot.send_message(ADMIN_ID, f"🏆 የሪፈራል አሸናፊ!\nደንበኛ፦ {ref_u['name']} (ID: {referrer_id}) — {cnt} ሰዎች አስገዝቷል!")
            execute("INSERT OR REPLACE INTO support(msg_id, user_id) VALUES(?, ?)", (m.message_id, referrer_id))
        except Exception:
            pass
    elif cnt < REFERRAL_TARGET:
        try:
            await bot.send_message(referrer_id, T[lang]["refer_progress"].format(count=cnt, target=REFERRAL_TARGET, rem=REFERRAL_TARGET - cnt))
        except Exception:
            pass


# ---------------------------------------------------------------- Admin Order Review & Private Group Invite
CAPTION_MAX = 1024


def fit_caption(text, suffix=""):
    room = CAPTION_MAX - len(suffix)
    return (text[: max(room - 1, 0)] + "…" if len(text) > room else text) + suffix


def order_caption(order, user, footer=True):
    uname = f" @{user['username']}" if user["username"] else ""
    promo_tag = f" (🎟️ {order['promo_code']})" if order.get("promo_code") else ""
    text = (
        f"🧾 ትዕዛዝ #{order['id']}\n"
        f"ደንበኛ፦ {user['name']} (id {order['user_id']}){uname}\n"
        f"ጥቅል፦ {PKG_LABEL.get(order['package'], order['package'])} | ዋጋ፦ {order['price']} ብር{promo_tag}\n"
        f"ቁመት/እድሜ/ፆታ፦ {user['height']}/{user['age']}/{user['gender']}"
    )
    if order["note"]:
        text += "\n\n" + order["note"]
    return fit_caption(text, "\n\n↩️ ከታች ባሉት ፈጣን አዝራሮች መልስ ይስጡ ወይም Reply ያድርጉ።" if footer else "")


def order_kb(order_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"approve:{order_id}"), InlineKeyboardButton("❌ ውድቅ", callback_data=f"reject:{order_id}")],
            [InlineKeyboardButton("⏳ ትንሽ ጠብቅ", callback_data=f"qrep:wait:{order_id}"), InlineKeyboardButton("🔍 ፎቶው አይታይም", callback_data=f"qrep:blur:{order_id}")],
            [InlineKeyboardButton("💰 ቀሪ ብር አለው", callback_data=f"qrep:less:{order_id}")],
        ]
    )


def load_order(order_id):
    rows = fetch("SELECT o.*, u.name AS uname_, u.username AS username, u.height, u.age, u.gender FROM orders o LEFT JOIN users u ON u.user_id=o.user_id WHERE o.id=?", (order_id,))
    if not rows:
        return None, None
    r = dict(rows[0])
    user = {k: r.get(k) for k in ("username", "height", "age", "gender")}
    user["name"] = r.get("uname_") or str(r["user_id"])
    return r, user


async def send_order_to_admin(bot, order_id):
    order, user = load_order(order_id)
    if not order:
        return
    if order["admin_msg"]:
        try:
            await bot.edit_message_reply_markup(ADMIN_ID, order["admin_msg"], reply_markup=None)
        except Exception:
            pass
    fid = order["photo_file_id"]
    cap, kb = order_caption(order, user), order_kb(order_id)
    msg = await (bot.send_document(ADMIN_ID, fid[4:], caption=cap, reply_markup=kb) if fid.startswith("doc:") else bot.send_photo(ADMIN_ID, fid, caption=cap, reply_markup=kb))
    execute("UPDATE orders SET admin_msg=? WHERE id=?", (msg.message_id, order_id))
    execute("INSERT OR REPLACE INTO support(msg_id, user_id) VALUES(?, ?)", (msg.message_id, order["user_id"]))
    if ocr.available() and not order["note"]:
        t = asyncio.get_running_loop().create_task(run_ocr(bot, order_id))
        _TASKS.add(t)
        t.add_done_callback(_TASKS.discard)


async def run_ocr(bot, order_id):
    text = ""
    try:
        order, _ = load_order(order_id)
        if not order:
            return
        fid = order["photo_file_id"]
        f = await bot.get_file(fid[4:] if fid.startswith("doc:") else fid)
        data = bytes(await f.download_as_bytearray())
        text = await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(None, ocr.read_text, data), 60)
        res = ocr.analyze(text, order["price"], "", config.RECEIVER_NAMES)
        amt = "✅" if res.get("amount_strong") else ("⚠️" if res["amount"] else "❌")
        txs = extract_tx_ids(text)
        note = f"🔍 OCR፦ መጠን {order['price']} {amt}" + (f" · ስም {'✅' if res['name'] else '❌'}" if config.RECEIVER_NAMES else "") + (f"\n🔢 TxID፦ {', '.join(txs[:2])}" if txs else "")
    except Exception:
        note = "🔍 OCR፦ ማንበብ አልተቻለም።"
    execute("UPDATE orders SET note=? WHERE id=?", (note, order_id))
    if text and await try_match_pending_with_sms(bot, specific_order_id=order_id, ocr_text=text):
        return
    order, user = load_order(order_id)
    if order and order["status"] == "pending" and order["admin_msg"]:
        try:
            await bot.edit_message_caption(chat_id=ADMIN_ID, message_id=order["admin_msg"], caption=order_caption(order, user), reply_markup=order_kb(order_id))
        except Exception:
            pass


async def on_admin_quick_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    _, kind, oid = q.data.split(":")
    rows = fetch("SELECT * FROM orders WHERE id=?", (int(oid),))
    if not rows:
        return
    order = dict(rows[0])
    uid = order["user_id"]
    msg_key = {"wait": "qreply_wait", "blur": "qreply_blur", "less": "qreply_less"}.get(kind)
    if kind == "wait":
        await update_live_user_status(context.bot, order, "status_checking")
    elif kind in ("blur", "less"):
        st_set(uid, pkg=order["package"], step="await_photo", pay_started=time.time(), reminded=0)
    try:
        await context.bot.send_message(uid, T[get_lang(uid)][msg_key])
        await q.answer("✅ መልዕክቱ ተልኳል!")
    except Exception as e:
        await q.answer(f"❌ {e}"[:190], show_alert=True)


async def on_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    rep = msg.reply_to_message
    rows = fetch("SELECT user_id FROM support WHERE msg_id=?", (rep.message_id,)) if rep else []
    if not rows:
        await msg.reply_text("⚠️ ይህ መልዕክት ከደንበኛ ጋር አልተያያዘም።")
        return
    uid = rows[0]["user_id"]
    try:
        await context.bot.send_message(uid, f"{T[get_lang(uid)]['reply_prefix']}\n{msg.text}")
        await msg.reply_text("✅ ተልኳል")
    except Exception as e:
        await msg.reply_text(f"❌ መላክ አልተቻለም፦ {e}")


def channel_for(package):
    chans = getattr(config, "CHANNELS", {}) or {}
    return int((chans.get("upgrade") or chans.get("bundle") or 0) if package == "upgrade" else (chans.get(package) or 0))


async def send_invite(bot, order):
    """ለደንበኛው ወደ Private Group/Channel የሚያስገባ የ1-ጊዜ ሊንክ ብቻ ይልካል"""
    uid = order["user_id"]
    lang = get_lang(uid)
    chan = channel_for(order["package"])
    if not chan:
        return False, "የ Private ግሩፕ ID አልተሞላም (BOOKS_CHANNEL_ID / BUNDLE_CHANNEL_ID)"
    hours = getattr(config, "INVITE_HOURS", 24)
    if order.get("invite_link"):
        try:
            await bot.revoke_chat_invite_link(chan, order["invite_link"])
        except Exception:
            pass
    exp = time.time() + hours * 3600
    try:
        link = await bot.create_chat_invite_link(chan, name=f"order {order['id']}", expire_date=int(exp), creates_join_request=True)
    except Exception as e:
        return False, f"የግሩፕ ሊንክ መፍጠር አልተቻለም ({type(e).__name__}) — ቦቱ የግሩፑ አድሚን መሆኑን ያረጋግጡ"
    execute("UPDATE orders SET invite_link=?, invite_exp=?, joined=0 WHERE id=?", (link.invite_link, exp, order["id"]))
    try:
        await bot.send_message(
            uid, T[lang]["approved_link"].format(hours=hours),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(T[lang]["btn_join"], url=link.invite_link)]]),
        )
    except Exception:
        return False, f"ለደንበኛው አልደረሰም። ሊንኩ፦ {link.invite_link}"
    return True, link.invite_link


async def deliver_approved_order(bot, order, auto_sms=None):
    uid = order["user_id"]
    pkg = order["package"]
    lang = get_lang(uid)
    await update_live_user_status(bot, order, "status_approved")
    await credit_referrer_on_purchase(bot, uid, pkg)

    if pkg in ("gift_books", "gift_bundle"):
        real_pkg = "books" if pkg == "gift_books" else "bundle"
        code = f"GIFT-{random.randint(1000, 9999)}-{order['id']}"
        execute("INSERT OR REPLACE INTO gifts(code, package, buyer_id, created) VALUES(?,?,?,?)", (code, real_pkg, uid, time.time()))
        try:
            await bot.send_message(uid, T[lang]["gift_code_created"].format(code=code, pkg_name=PKG_LABEL[real_pkg]))
        except Exception:
            pass
        full, user = load_order(order["id"])
        if full and full.get("admin_msg"):
            try:
                await bot.edit_message_caption(chat_id=ADMIN_ID, message_id=full["admin_msg"], caption=fit_caption(order_caption(full, user, footer=False), f"\n\n✅ የስጦታ ኮድ ({code}) ተልኳል"))
            except Exception:
                pass
        return True, code

    execute("UPDATE users SET bought_at=COALESCE(bought_at, ?), coach_stage=COALESCE(coach_stage, 0), max_funnel=6 WHERE user_id=?", (time.time(), uid))
    label = PKG_LABEL.get(pkg, pkg)
    ok, info = await send_invite(bot, order)
    auto_tag = f" (⚡ በSMS #{auto_sms})" if auto_sms else ""
    suffix = f"\n\n✅ ተረጋግጧል{auto_tag} — የ {label} ሊንክ ተልኳል" if ok else f"\n\n✅ ተረጋግጧል — ⚠️ ሊንክ አልተላከም ({info})"

    full, user = load_order(order["id"])
    if full and full.get("admin_msg"):
        try:
            await bot.edit_message_caption(chat_id=ADMIN_ID, message_id=full["admin_msg"], caption=fit_caption(order_caption(full, user, footer=False), suffix))
        except Exception:
            pass
    return ok, info


async def on_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    link = req.invite_link.invite_link if req.invite_link else None
    rows = fetch("SELECT * FROM orders WHERE invite_link=?", (link,)) if link else []
    if not rows:
        return
    order = rows[0]
    uid = req.from_user.id
    good = uid == order["user_id"] and order["status"] == "approved" and channel_for(order["package"]) == req.chat.id and not order["joined"]
    try:
        await (req.approve() if good else req.decline())
    except Exception:
        return
    if good:
        execute("UPDATE orders SET joined=1 WHERE id=?", (order["id"],))
        try:
            await context.bot.revoke_chat_invite_link(req.chat.id, link)
            await context.bot.send_message(uid, T[get_lang(uid)]["joined"], reply_markup=group_deeplink_kb())
            await context.bot.send_message(ADMIN_ID, f"✅ ትዕዛዝ #{order['id']} — ደንበኛው ወደ Private ግሩፑ ገብቷል።")
        except Exception:
            pass


async def cmd_resend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("አጠቃቀም፦ `/resend <ትዕዛዝ ቁጥር>`")
        return
    rows = fetch("SELECT * FROM orders WHERE id=?", (int(context.args[0]),))
    if not rows or rows[0]["status"] != "approved":
        await update.message.reply_text("ትዕዛዙ አልተገኘም ወይም አልተረጋገጠም።")
        return
    ok, info = await send_invite(context.bot, dict(rows[0]))
    await update.message.reply_text("✅ አዲስ የግሩፕ ሊንክ ተልኳል።" if ok else f"⚠️ {info}")


async def channel_warnings(bot):
    warns = []
    for pkg in ("books", "bundle"):
        chan = channel_for(pkg)
        if not chan:
            warns.append(f"⚠️ የ «{PKG_LABEL.get(pkg, pkg)}» ID አልተሞላም።")
            continue
        try:
            m = await bot.get_chat_member(chan, bot.id)
            if m.status not in ("administrator", "creator"):
                warns.append(f"⚠️ ቦቱ የ «{PKG_LABEL.get(pkg, pkg)}» አድሚን አይደለም።")
        except Exception:
            warns.append(f"⚠️ ቦቱ የ «{PKG_LABEL.get(pkg, pkg)}» ግሩፕን ({chan}) ማግኘት አልቻለም።")
    return warns


async def on_admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    action, oid = q.data.split(":")
    rows = fetch("SELECT * FROM orders WHERE id=?", (int(oid),))
    if not rows or rows[0]["status"] != "pending":
        await q.answer("ቀድሞ ተወስኗል", show_alert=True)
        return
    order = dict(rows[0])

    if action == "approve":
        if not execute_rc("UPDATE orders SET status='approved' WHERE id=? AND status='pending'", (order["id"],)):
            return
        ok, info = await deliver_approved_order(context.bot, order)
        await q.answer("ተረጋግጧል ✅ የግሩፕ ሊንክ ተልኳል" if ok else f"ሊንክ አልተላከም፦ {info}"[:190], show_alert=not ok)
    else:
        if not execute_rc("UPDATE orders SET status='rejected' WHERE id=? AND status='pending'", (order["id"],)):
            return
        await update_live_user_status(context.bot, order, "status_rejected")
        execute("UPDATE users SET started_at=?, followup_stage=0 WHERE user_id=?", (time.time(), order["user_id"]))
        try:
            await context.bot.send_message(order["user_id"], T[get_lang(order["user_id"])]["rejected"])
        except Exception:
            pass
        await q.answer("ውድቅ ተደርጓል")
        full, user = load_order(order["id"])
        try:
            await q.edit_message_caption(fit_caption(order_caption(full, user, footer=False), "\n\n❌ ውድቅ ተደርጓል"))
        except Exception:
            pass


# ---------------------------------------------------------------- Stats & Users
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = fetch("SELECT COUNT(*) AS n FROM users")[0]["n"]
    pending = fetch("SELECT COUNT(*) AS n FROM orders WHERE status='pending'")[0]["n"]
    ok = fetch("SELECT COUNT(*) AS n, COALESCE(SUM(price),0) AS s FROM orders WHERE status='approved'")[0]
    refs = fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(ref_credited, 0)=1")[0]["n"]
    f_q = fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(max_funnel,0) >= 1")[0]["n"]
    f_res = fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(max_funnel,0) >= 2")[0]["n"]
    f_vid = fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(max_funnel,0) >= 3")[0]["n"]
    f_pkg = fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(max_funnel,0) >= 4")[0]["n"]
    f_pay = fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(max_funnel,0) >= 5")[0]["n"]

    src_rows = fetch(
        """
        SELECT COALESCE(u.ad_source, 'ቀጥታ (Direct)') AS src, COUNT(DISTINCT u.user_id) AS u_cnt,
               COUNT(o.id) AS o_cnt, COALESCE(SUM(o.price), 0) AS rev
        FROM users u LEFT JOIN orders o ON o.user_id = u.user_id AND o.status = 'approved'
        GROUP BY COALESCE(u.ad_source, 'ቀጥታ (Direct)') ORDER BY rev DESC, u_cnt DESC LIMIT 6
        """
    )
    src_lines = [f"• {r['src']}: {r['u_cnt']} ሰው ({r['o_cnt']} ሽያጭ — {r['rev']} ብር)" for r in src_rows]
    text = (
        f"📊 **አጠቃላይ ስታቲስቲክስ**\n👥 ተጠቃሚዎች፦ {users} | ⏳ በመጠባበቅ ላይ፦ {pending}\n"
        f"✅ የተሸጠ፦ {ok['n']} ({ok['s']} ብር) | 🎁 በሪፈራል፦ {refs}\n\n"
        f"📈 **የደንበኞች ጉዞ (Funnel)**\n🏁 ጥያቄ፦ {f_q} ➔ 🧬 ውጤት፦ {f_res} ➔ 🎥 ቪዲዮ፦ {f_vid} ➔ 📦 ጥቅል፦ {f_pkg} ➔ 💳 ክፍያ፦ {f_pay}\n\n"
        f"📢 **የማስታወቂያ ምንጮች**\n" + "\n".join(src_lines)
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👥 የተጠቃሚዎች ዝርዝር", callback_data="uopen:0")]])
    await update.message.reply_text(text, reply_markup=kb)


def get_users_page(page=0):
    limit, offset = 15, page * 15
    total_users = fetch("SELECT COUNT(*) AS n FROM users")[0]["n"]
    total_pages = max(1, (total_users + limit - 1) // limit)
    rows = fetch(
        """
        SELECT u.user_id, u.name, u.username, date(u.created) as created_date, COALESCE(u.ref_paid_count, 0) as refs,
           (SELECT package FROM orders WHERE user_id = u.user_id AND status = 'approved' ORDER BY id DESC LIMIT 1) as ap_pkg,
           (SELECT status FROM orders WHERE user_id = u.user_id AND status = 'pending' ORDER BY id DESC LIMIT 1) as pd_status
        FROM users u ORDER BY u.user_id DESC LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    lines = [f"👥 የተጠቃሚዎች ዝርዝር (ገጽ {page+1}/{total_pages})", "━━━━━━━━━━━━━━━━━━━━"]
    for i, r in enumerate(rows):
        sym = "✅👑" if r["ap_pkg"] in ("bundle", "upgrade") else ("✅📕" if r["ap_pkg"] == "books" else ("⏳" if r["pd_status"] == "pending" else "—"))
        uname = f" @{r['username']}" if r["username"] else ""
        ref_tag = f" [🎁{r['refs']}]" if r["refs"] else ""
        lines.append(f"{offset + i + 1}. {sym} {r['name']}{uname}{ref_tag} (ID: {r['user_id']}) - {r['created_date']}")
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"upage:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"upage:{page+1}"))
    return "\n".join(lines), (InlineKeyboardMarkup([nav]) if nav else None)


async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        text, kb = get_users_page(0)
        await update.message.reply_text(text, reply_markup=kb)


async def on_users_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    action, page_str = q.data.split(":")
    text, kb = get_users_page(int(page_str))
    await q.answer()
    if action == "uopen":
        await context.bot.send_message(chat_id=q.message.chat_id, text=text, reply_markup=kb)
    else:
        try:
            await q.edit_message_text(text, reply_markup=kb)
        except Exception:
            pass


def get_followup_page(page=0):
    now, limit, offset = time.time(), 15, page * 15
    total_in_queue = fetch("SELECT COUNT(*) AS n FROM users u WHERE u.started_at IS NOT NULL AND COALESCE(u.bot_blocked,0)=0 AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id=u.user_id AND o.status IN ('pending','approved'))")[0]["n"]
    total_pages = max(1, (total_in_queue + limit - 1) // limit)
    rows = fetch("SELECT u.user_id, u.name, u.started_at, COALESCE(u.followup_stage,0) AS stage FROM users u WHERE u.started_at IS NOT NULL AND COALESCE(u.bot_blocked,0)=0 AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id=u.user_id AND o.status IN ('pending','approved')) ORDER BY u.user_id DESC LIMIT ? OFFSET ?", (limit, offset))
    lines = [f"🔍 የማስታወሻ ክትትል — ያልከፈሉ፦ {total_in_queue} (ገጽ {page+1}/{total_pages})", "━━━━━━━━━━━━━━━━━━━━"]
    for i, r in enumerate(rows):
        stage, elapsed_min = r["stage"], (now - r["started_at"]) / 60.0
        status = f"ደረጃ {stage+1}/3 (ከ {max(0.0, FOLLOWUP_HOURS[stage] * 60.0 - elapsed_min):.0f} ደቂቃ በኋላ)" if stage < len(FOLLOWUP_HOURS) else "3ቱም ተልኳል"
        lines.append(f"{offset + i + 1}. {r['name']} (ID:{r['user_id']}) — {status}")
    kb_rows = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"fpage:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"fpage:{page+1}"))
    if nav:
        kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton("🚀 1ኛውን መልዕክት ለእኔ ላክ (Test)", callback_data="fnow:1")])
    kb_rows.append([InlineKeyboardButton("🔄 ሁሉም ያልገዙ ሰዎች አሁን እንዲደርሳቸው አድርግ", callback_data="fnow:all")])
    return "\n".join(lines), InlineKeyboardMarkup(kb_rows)


async def cmd_test_followup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        text, kb = get_followup_page(0)
        await update.message.reply_text(text, reply_markup=kb)


async def on_followup_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id == ADMIN_ID:
        text, kb = get_followup_page(int(q.data.split(":")[1]))
        try:
            await q.edit_message_text(text, reply_markup=kb)
        except Exception:
            pass
        await q.answer()


async def on_followup_test_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    if q.data.split(":")[1] == "1":
        await context.bot.send_message(ADMIN_ID, T[get_lang(ADMIN_ID)]["followup_1"].format(name=q.from_user.first_name or "ጓደኛዬ"))
        await q.answer("1ኛው መልዕክት ተልኳል!")
    else:
        immediate_start = time.time() - (FOLLOWUP_HOURS[0] * 3600) - 10
        execute("UPDATE users SET started_at=?, followup_stage=0 WHERE COALESCE(bot_blocked,0)=0 AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id=users.user_id AND o.status IN ('pending','approved'))", (immediate_start,))
        await q.answer("አሁኑኑ ለሁሉም መላክ ይጀምራል።", show_alert=True)
        await check_followups(context.bot)


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    rows = fetch("SELECT id FROM orders WHERE status='pending' ORDER BY id")
    if not rows:
        await update.message.reply_text("✅ በመጠባበቅ ላይ ያለ ደረሰኝ የለም።")
        return
    for r in rows[:10]:
        await send_order_to_admin(context.bot, r["id"])


# ---------------------------------------------------------------- Background tasks
async def check_reminders(bot):
    cutoff = time.time() - getattr(config, "REMINDER_MINUTES", 10) * 60
    for r in fetch("SELECT user_id FROM sessions WHERE pkg IS NOT NULL AND pay_started IS NOT NULL AND COALESCE(reminded,0)=0 AND pay_started < ?", (cutoff,)):
        st_set(r["user_id"], reminded=1)
        try:
            await bot.send_message(r["user_id"], T[get_lang(r["user_id"])]["reminder"])
        except Exception:
            pass


async def check_followups(bot):
    now = time.time()
    rows = fetch("SELECT u.user_id, u.name, u.lang, u.started_at, COALESCE(u.followup_stage, 0) AS stage FROM users u WHERE u.started_at IS NOT NULL AND COALESCE(u.bot_blocked, 0) = 0 AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.user_id AND o.status IN ('pending', 'approved'))")
    sent_count = 0
    for r in rows:
        uid, stage, elapsed_hours = r["user_id"], r["stage"], (now - r["started_at"]) / 3600.0
        if stage >= len(FOLLOWUP_HOURS):
            if elapsed_hours >= FOLLOWUP_RESET_HOURS:
                execute("UPDATE users SET started_at=?, followup_stage=0 WHERE user_id=?", (now, uid))
            continue
        if elapsed_hours >= FOLLOWUP_HOURS[stage]:
            next_stage = stage + 1
            execute("UPDATE users SET followup_stage=? WHERE user_id=?", (next_stage, uid))
            lang = r["lang"] if r["lang"] in T else "am"
            try:
                await bot.send_message(uid, T[lang][f"followup_{next_stage}"].format(name=(r["name"] or "ጓደኛዬ").split()[0]))
                sent_count += 1
                await asyncio.sleep(0.1)
                if sent_count >= 25:
                    break
            except Forbidden:
                execute("UPDATE users SET bot_blocked=1, started_at=NULL WHERE user_id=?", (uid,))
            except Exception:
                pass


async def check_coach_messages(bot):
    now = time.time()
    rows = fetch("SELECT user_id, name, lang, bought_at, COALESCE(coach_stage, 0) AS stage FROM users WHERE bought_at IS NOT NULL AND COALESCE(bot_blocked, 0) = 0 AND COALESCE(coach_stage, 0) < ?", (len(COACH_DAYS),))
    for r in rows:
        stage = r["stage"]
        target_day = COACH_DAYS[stage]
        if (now - r["bought_at"]) / 86400.0 >= target_day:
            uid = r["user_id"]
            execute("UPDATE users SET coach_stage=? WHERE user_id=?", (stage + 1, uid))
            lang = r["lang"] if r["lang"] in T else "am"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(T[lang]["btn_send_testi"], callback_data="testi:send")]]) if target_day == 30 else group_deeplink_kb()
            try:
                await bot.send_message(uid, T[lang][f"coach_d{target_day}"].format(name=(r["name"] or "ጓደኛዬ").split()[0]), reply_markup=kb)
                await asyncio.sleep(0.1)
            except Forbidden:
                execute("UPDATE users SET bot_blocked=1 WHERE user_id=?", (uid,))
            except Exception:
                pass


async def nag_admin(bot):
    rows = fetch("SELECT id FROM orders WHERE status='pending' AND COALESCE(nudged,0)=0 AND created <= datetime('now', ?)", (f"-{config.NAG_MINUTES} minutes",))
    if rows:
        ids = [r["id"] for r in rows]
        try:
            await bot.send_message(ADMIN_ID, f"⏳ {len(ids)} ደረሰኝ ከ{config.NAG_MINUTES} ደቂቃ በላይ እየጠበቀ ነው። /pending ይጫኑ።")
            for oid in ids:
                execute("UPDATE orders SET nudged=1 WHERE id=?", (oid,))
        except Exception:
            pass


async def background_loop(bot):
    global LAST_BACKUP_TS, LAST_GROUP_POST_TS
    LAST_BACKUP_TS = LAST_GROUP_POST_TS = time.time()
    while True:
        try:
            await check_reminders(bot)
            await check_followups(bot)
            await check_coach_messages(bot)
            await nag_admin(bot)
            if GROUP_POST_HOURS > 0 and (time.time() - LAST_GROUP_POST_TS) >= GROUP_POST_HOURS * 3600:
                await post_motivation_to_groups(bot)
            if BACKUP_INTERVAL_HOURS > 0 and (time.time() - LAST_BACKUP_TS) >= BACKUP_INTERVAL_HOURS * 3600:
                await send_db_backup(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("background task error")
        await asyncio.sleep(getattr(config, "BACKGROUND_INTERVAL", 60))


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled error", exc_info=context.error)


async def post_init(app):
    global BOT_USERNAME
    try:
        BOT_USERNAME = (await app.bot.get_me()).username or ""
    except Exception:
        pass
    user_cmds = [BotCommand("start", "🚀 ከመጀመሪያ ጀምር / VIP ገጽ"), BotCommand("refer", "🎁 ጓደኛ ጋብዘው ሽልማት ያግኙ")]
    try:
        await app.bot.set_my_commands(user_cmds)
        await app.bot.set_my_commands(
            user_cmds + [
                BotCommand("pending", "⏳ ያልተረጋገጡ ደረሰኞች"),
                BotCommand("postgroup", "🔥 ወደ ግሩፑ ማነቃቂያ ፖስት ልቀቅ"),
                BotCommand("find", "🔎 ደንበኛ መፈለጊያ (በስም/ID)"),
                BotCommand("stats", "📊 ስታቲስቲክስ እና ማስታወቂያዎች"),
                BotCommand("users", "👥 የተጠቃሚዎች ዝርዝር"),
                BotCommand("broadcast", "📢 የጅምላ መልዕክት መላኪያ"),
                BotCommand("addpromo", "🎟️ የቅናሽ ኮድ ፍጠር"),
                BotCommand("delpromo", "🗑️ የቅናሽ ኮዶች እይ/አጥፋ"),
                BotCommand("backup", "💾 ዳታቤዝ ባክአፕ አውርድ"),
                BotCommand("sms", "⚡ የባንክ SMS መዝግብ"),
                BotCommand("resend", "🔗 የግሩፕ ሊንክ እንደገና ላክ"),
                BotCommand("test_followup", "🔍 የማስታወሻ መፈተሻ"),
            ],
            scope=BotCommandScopeChat(ADMIN_ID),
        )
    except Exception:
        pass
    warns = ([DB_WARN] if DB_WARN else []) + await channel_warnings(app.bot)
    if warns:
        try:
            await app.bot.send_message(ADMIN_ID, "\n\n".join(warns))
        except Exception:
            pass
    app.bot_data["bg"] = asyncio.create_task(background_loop(app.bot))


def main():
    if not TOKEN or not ADMIN_ID:
        raise SystemExit("BOT_TOKEN እና ADMIN_ID በ .env ፋይል ውስጥ ያስቀምጡ።")
    check_texts()
    prepare_db_path()
    init_db()
    app = Application.builder().token(TOKEN).concurrent_updates(True).post_init(post_init).build()
    app.add_error_handler(on_error)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("refer", cmd_refer))
    app.add_handler(CommandHandler("postgroup", cmd_postgroup))
    app.add_handler(CommandHandler("find", cmd_find))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("test_followup", cmd_test_followup))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("resend", cmd_resend))
    app.add_handler(CommandHandler("sms", cmd_sms))
    app.add_handler(CommandHandler("addpromo", cmd_addpromo))
    app.add_handler(CommandHandler("delpromo", cmd_delpromo))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(ChatJoinRequestHandler(on_join_request))
    app.add_handler(CallbackQueryHandler(on_go, pattern=r"^go:"))
    app.add_handler(CallbackQueryHandler(on_vip_action, pattern=r"^vip:"))
    app.add_handler(CallbackQueryHandler(on_gift_redeem_btn, pattern=r"^gift:redeem$"))
    app.add_handler(CallbackQueryHandler(on_lang, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(on_profile_answer, pattern=r"^(age|gender|height):"))
    app.add_handler(CallbackQueryHandler(on_package, pattern=r"^pkg:"))
    app.add_handler(CallbackQueryHandler(on_promo_btn, pattern=r"^promo:ask$"))
    app.add_handler(CallbackQueryHandler(on_faq, pattern=r"^faq:"))
    app.add_handler(CallbackQueryHandler(on_send_testi_btn, pattern=r"^testi:send$"))
    app.add_handler(CallbackQueryHandler(on_admin_decision, pattern=r"^(approve|reject):\d+$"))
    app.add_handler(CallbackQueryHandler(on_admin_quick_reply, pattern=r"^qrep:(wait|blur|less):\d+$"))
    app.add_handler(CallbackQueryHandler(on_admin_grant, pattern=r"^admgrant:(books|bundle):\d+$"))
    app.add_handler(CallbackQueryHandler(on_users_page, pattern=r"^(uopen|upage):\d+$"))
    app.add_handler(CallbackQueryHandler(on_followup_page, pattern=r"^fpage:\d+$"))
    app.add_handler(CallbackQueryHandler(on_followup_test_btn, pattern=r"^fnow:"))
    app.add_handler(CallbackQueryHandler(on_broadcast_btn, pattern=r"^bcast:"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY & filters.User(user_id=ADMIN_ID) & ~filters.COMMAND, on_admin_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("ቦቱ እየሰራ ነው…")
    app.run_polling(allowed_updates=["message", "callback_query", "chat_join_request"])


if __name__ == "__main__":
    main()
