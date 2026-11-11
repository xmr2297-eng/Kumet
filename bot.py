import asyncio
import hashlib
import io
import logging
import os
import random
import re
import sqlite3
import time
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
from texts import AGE_CODES, CHOOSE_LANG, GENDER_CODES, HEIGHT_CODES, T

try:
    from PIL import Image
except Exception:
    Image = None

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
FAST_BONUS_HOURS = getattr(config, "FAST_BONUS_HOURS", 24)

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("bookbot")
for _noisy in ("httpx", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

FALLBACK_TEXTS = {
    "analysis_young": "አስደናቂ ዜና! በዚህ የእድሜ ክልል የእድገት ፕሌቶችዎ እና የዕድገት ሆርሞን (HGH) ከፍተኛ ንቁ ደረጃ ላይ ይገኛሉ።\n📈 ከ 8 እስከ 12 CM የቁመት መጨመር ከፍተኛ እድል አለዎት!",
    "analysis_adult": "መልካም ዜና! በዚህ የእድሜ ክልል የአከርካሪ መለጠጥ (Spinal Decompression) እና የአቋም ማስተካከያ ልምምዶችን በመጠቀም\n📈 ከ 5 እስከ 8 CM ተጨማሪ ቁመት ማግኘት ይችላሉ!",
    "btn_upgrade": "⬆️ ወደ ቪዲዮ ግሩፕ አሳድግ ({price} ብር ብቻ)",
    "btn_buy_gift": "🎁 ለጓደኛ በስጦታ ግዛ",
    "btn_redeem_gift": "🔑 የስጦታ ኮድ አለኝ",
    "gift_menu_text": "🎁 **ለጓደኛ ወይም ለቤተሰብ ስጦታ ይግዙ!**\n\nክፍያው እንደተረጋገጠ ልዩ የስጦታ ኮድ (`GIFT-XXXX`) ይሰጥዎታል። ኮዱን ለጓደኛዎ ሲልኩለት ወዲያውኑ ወደ ልዩ ግሩፑ መግባት ይችላል! 👇",
    "btn_gift_books": "🎁 ስጦታ፦ መጽሐፍ ብቻ ({price} ብር)",
    "btn_gift_bundle": "🎁👑 ስጦታ፦ መጽሐፍ + ቪዲዮ ({price} ብር)",
    "gift_code_created": "🎉 **የስጦታ ግዢዎ ተረጋግጧል!**\n\n🔑 የስጦታ ኮድ፦ `{code}`\n📦 ጥቅል፦ {pkg_name}\n\nይህን ኮድ ለጓደኛዎ ይላኩለት፤ ቦቱ ውስጥ **«🔑 የስጦታ ኮድ አለኝ»** የሚለውን ሲነካ ወዲያውኑ የግሩፑ ሊንክ ይከፈትለታል!",
    "ask_gift_code": "🔑 እባክዎ የተሰጠዎትን የስጦታ ኮድ (ለምሳሌ፦ `GIFT-1234`) ይጻፉ 👇",
    "gift_redeemed_ok": "🎉 እንኳን ደስ አለዎት! የስጦታ ኮዱ ትክክል ነው፤ የግሩፑ መግቢያ ሊንክ ከታች ተልኮልዎታል! 👇",
    "gift_invalid": "❌ ይህ የስጦታ ኮድ ትክክል አይደለም ወይም ቀድሞ ጥቅም ላይ ውሏል።",
    "social_proof_line": "\n\n🔥 ዛሬ ብቻ {today_count} ወጣቶች ወደ ግሩፑ ተቀላቅለዋል! (የመጨረሻው ከ {mins_ago} ደቂቃ በፊት)",
    "fast_bonus_line": "\n⏳ በ {rem_hr} ውስጥ ከከፈሉ የ VIP ግሩፕ ልዩ ድጋፍ ያገኛሉ!",
    "fast_bonus_expired": "",
    "btn_promo": "🎟️ የቅናሽ ኮድ አለኝ (Promo Code)",
    "ask_promo": "🎟️ እባክዎ ያለዎትን የቅናሽ ኮድ ይጻፉ 👇",
    "promo_ok": "🎉 የ {disc} ብር ቅናሽ ተደርጎልዎታል! አዲሱ ዋጋ፦ {new_price} ብር።",
    "promo_invalid": "❌ ይህ የቅናሽ ኮድ ትክክል አይደለም።",
    "faq_time_btn": "❓ በስንት ደቂቃ ወደ ግሩፑ እገባለሁ?",
    "faq_time_ans": "⏱ የደረሰኝ ፎቶ እንደላኩ ከ 1 እስከ 3 ደቂቃ ውስጥ ተረጋግጦ ወዲያውኑ ወደ Private ግሩፑ የሚያስገባዎት ሊንክ እዚሁ ይደርስዎታል!",
    "faq_other_btn": "❓ በሌላ ሰው ስልክ/ባንክ መክፈል ይቻላል?",
    "faq_other_ans": "✅ አዎ ይቻላል! በማንኛውም ሰው ስልክ ወይም ባንክ ከፍለው የደረሰኙን ፎቶ እዚህ መላክ ይችላሉ።",
    "ussd_telebirr_btn": "📲 የቴሌብር USSD (*127#) ቅዳ",
    "ussd_cbe_btn": "🏦 የ CBE USSD (*889#) ቅዳ",
    "voice_caption": "🎧 እንዴት በቀላሉ እንደሚከፍሉና ወደ ግሩፑ ወዲያውኑ እንደሚገቡ ይህን ድምጽ ያዳምጡ።",
    "bad_photo_quality": "⚠️ የላኩት ፎቶ በጣም የጨለመ ወይም ጥራቱ አነስተኛ ስለሆነ አይነበብም። እባክዎ ግልጽ Screenshot ይላኩ። 👇",
    "status_checking": "🔵 ሁኔታ፦ አድሚኑ ደረሰኝዎን እያረጋገጠ ነው...\n⏳ እባክዎ ጥቂት ይጠብቁን። 🙏",
    "status_approved": "🟢 ሁኔታ፦ ክፍያዎ ተረጋግጧል! የግሩፕ መግቢያ ሊንክዎ ከታች ተልኳል 🎉",
    "status_rejected": "🔴 ሁኔታ፦ ደረሰኙ አልተረጋገጠም። እባክዎ ትክክለኛ ደረሰኝ ይላኩ።",
    "qreply_wait": "⏳ ሰላም! ደረሰኝዎ ደርሶናል፣ እያረጋገጥን ስለሆነ እባክዎ ጥቂት ደቂቃዎች ይጠብቁን። 🙏",
    "qreply_blur": "🔍 ሰላም! የላኩት የደረሰኝ ፎቶ በደንብ አይነበብም። እባክዎ ግልጽ ስክሪንሾት እንደገና ይላኩ። 👇",
    "qreply_less": "💰 ሰላም! የላኩት የገንዘብ መጠን ከመረጡት ጥቅል ዋጋ ያነሰ ነው። እባክዎ ቀሪውን አሟልተው ይላኩ። 👇",
    "member_welcome": "👑 እንኳን ደህና መጡ ክቡር አባላችን {name}!\n\n📦 የገቡበት ግሩፕ፦ {pkg_name}\n\nከታች ባሉት አዝራሮች የግሩፕ መግቢያ ሊንክዎን ማግኘት ወይም ጥቅልዎን ማሳደግ ይችላሉ 👇",
    "btn_vip_files": "🔗 የ Private ግሩፕ መግቢያ ሊንክ ላክልኝ",
    "btn_vip_restart": "🔄 ጥያቄዎቹን ከመጀመሪያ ለማየት",
}


def check_texts():
    config.PRICES.setdefault("upgrade", max(100, config.PRICES.get("bundle", 597) - config.PRICES.get("books", 397)))
    config.PRICES.setdefault("gift_books", config.PRICES.get("books", 397))
    config.PRICES.setdefault("gift_bundle", config.PRICES.get("bundle", 597))
    if "upgrade" not in getattr(config, "CHANNELS", {}):
        config.CHANNELS["upgrade"] = config.CHANNELS.get("bundle", 0)
    for lang, table in T.items():
        for k, v in FALLBACK_TEXTS.items():
            table.setdefault(k, v)
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
            "ALTER TABLE users ADD COLUMN bot_blocked INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN bought_at REAL",
            "ALTER TABLE users ADD COLUMN max_funnel INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN offer_seen_at REAL",
            "ALTER TABLE users ADD COLUMN ad_source TEXT",
            "ALTER TABLE sessions ADD COLUMN promo_code TEXT",
            "ALTER TABLE sessions ADD COLUMN discount INTEGER DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN promo_code TEXT",
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


def ensure_user(u, ad_source=None):
    execute("INSERT OR IGNORE INTO users(user_id, name, bot_blocked) VALUES(?, ?, 0)", (u.id, u.full_name))
    execute("UPDATE users SET name=?, username=?, bot_blocked=0 WHERE user_id=?", (u.full_name, getattr(u, "username", None), u.id))
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


def channel_for(package):
    chans = getattr(config, "CHANNELS", {}) or {}
    return int((chans.get("upgrade") or chans.get("bundle") or 0) if package == "upgrade" else (chans.get(package) or 0))


# ---------------------------------------------------------------- Smart Image Check
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
    custom_analysis = T[lang].get(analysis_key, FALLBACK_TEXTS[analysis_key])
    raw_res = T[lang]["result"]
    if "{custom_analysis}" in raw_res:
        text = raw_res.format(
            height=answer_label(lang, "heights", HEIGHT_CODES, r.get("height")),
            age=answer_label(lang, "ages", AGE_CODES, age_code),
            gender=answer_label(lang, "genders", GENDER_CODES, r.get("gender")),
            custom_analysis=custom_analysis,
        )
    else:
        text = raw_res.format(
            height=answer_label(lang, "heights", HEIGHT_CODES, r.get("height")),
            age=answer_label(lang, "ages", AGE_CODES, age_code),
            gender=answer_label(lang, "genders", GENDER_CODES, r.get("gender")),
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


def b_pkg(context, user, lang):
    p = config.PRICES
    text = config.OFFER[lang].format(price=p["books"], price_bundle=p["bundle"], accounts="") + get_social_and_bonus_footer(user.id, lang)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(T[lang]["btn_books"].format(price=p["books"]), callback_data="pkg:books")],
            [InlineKeyboardButton(T[lang]["btn_bundle"].format(price=p["bundle"]), callback_data="pkg:bundle")],
            [
                InlineKeyboardButton(T[lang]["btn_buy_gift"], callback_data="go:gift"),
                InlineKeyboardButton(T[lang]["btn_redeem_gift"], callback_data="gift:redeem"),
            ],
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


def b_vip(context, user, lang):
    best = user_best_package(user.id) or "books"
    text = T[lang]["member_welcome"].format(name=user.first_name or "", pkg_name=PKG_LABEL.get(best, best))
    rows = [
        [InlineKeyboardButton(T[lang]["btn_vip_files"], callback_data="vip:files")],
    ]
    if best == "books":
        rows.append([InlineKeyboardButton(T[lang]["btn_upgrade"].format(price=config.PRICES.get("upgrade", 200)), callback_data="pkg:upgrade")])
    rows.append([InlineKeyboardButton(T[lang]["btn_buy_gift"], callback_data="go:gift")])
    rows.append([InlineKeyboardButton(T[lang]["btn_vip_restart"], callback_data="go:lang")])
    return text, InlineKeyboardMarkup(rows)


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
    raw_pay = T[lang]["pay"]
    extra_footer = get_social_and_bonus_footer(user.id, lang)
    if "{discount_note}" in raw_pay:
        text = raw_pay.format(price=final_price, discount_note=disc_note, accounts=config.PAYMENT_ACCOUNTS, extra_footer=extra_footer)
    else:
        text = raw_pay.format(price=f"{final_price} {disc_note}".strip(), accounts=config.PAYMENT_ACCOUNTS) + extra_footer
    st_set(user.id, step="await_photo", pay_started=s.get("pay_started") or time.time())
    back_target = "gift" if pkg.startswith("gift_") else ("vip" if pkg == "upgrade" else "pkg")
    return text, InlineKeyboardMarkup(account_copy_rows(lang, has_promo=bool(disc)) + [[back_button(lang, back_target)]])


BUILD = {
    "lang": b_lang, "welcome": b_welcome, "q1": b_q1, "q2": b_q2, "q3": b_q3,
    "offer": b_offer, "video": b_video, "proof": b_proof, "pkg": b_pkg, "pay": b_pay,
    "vip": b_vip, "gift": b_gift,
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


# ---------------------------------------------------------------- customer flow
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    u = update.effective_user
    ad_source = None
    if context.args:
        arg = context.args[0]
        ad_source = arg[4:].lower() if arg.startswith("src_") else arg.lower()

    ensure_user(u, ad_source=ad_source)
    st_clear(u.id)
    try:
        await update.message.delete()
    except Exception:
        pass

    if user_best_package(u.id):
        await show("vip", context, update.effective_chat.id, u)
        return

    await show("lang", context, update.effective_chat.id, u)


async def on_vip_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = q.from_user
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

    if uid == ADMIN_ID and update.message.reply_to_message:
        rmid = update.message.reply_to_message.message_id
        sup = fetch("SELECT user_id FROM support WHERE msg_id=?", (rmid,))
        if sup:
            target_uid = sup[0]["user_id"]
            try:
                await context.bot.send_message(target_uid, f"💬 **ከአድሚን የተላከ መልዕክት፦**\n\n{txt}")
                await update.message.reply_text("✅ መልዕክቱ ለደንበኛው ተልኳል።")
            except Exception as e:
                await update.message.reply_text(f"⚠️ መላክ አልተቻለም፦ {e}")
            return

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

    await update.message.reply_text(T[lang]["need_photo" if ready_to_pay(s) else "hint"])


# ---------------------------------------------------------------- Admin Commands
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
            f"📦 **ግሩፕ፦** {PKG_LABEL.get(best, 'አልገባም')}"
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
    if DB_PATH.exists():
        try:
            with open(DB_PATH, "rb") as f:
                await bot.send_document(ADMIN_ID, f, filename=f"bot_backup_{int(time.time())}.db", caption="💾 የዳታቤዝ ባክአፕ (bot.db)")
        except Exception:
            pass


async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await send_db_backup(context.bot)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total_users = fetch("SELECT COUNT(*) AS n FROM users")[0]["n"]
    approved = fetch("SELECT COUNT(*) AS n, COALESCE(SUM(price),0) AS rev FROM orders WHERE status='approved'")[0]
    pending = fetch("SELECT COUNT(*) AS n FROM orders WHERE status='pending'")[0]["n"]
    today_app = fetch("SELECT COUNT(*) AS n, COALESCE(SUM(price),0) AS rev FROM orders WHERE status='approved' AND date(created)=date('now')")[0]
    msg = (
        f"📊 **የቦት አጠቃላይ ሪፖርት**\n\n"
        f"👥 ጠቅላላ ተጠቃሚዎች፦ `{total_users}`\n"
        f"✅ የተረጋገጡ ትዕዛዞች፦ `{approved['n']}` ({approved['rev']} ብር)\n"
        f"🔥 የዛሬ ሽያጭ፦ `{today_app['n']}` ({today_app['rev']} ብር)\n"
        f"⏳ በመጠባበቅ ላይ (Pending)፦ `{pending}`"
    )
    await update.message.reply_text(msg)


# ---------------------------------------------------------------- Auto-Approve SMS & Orders
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
    orders = (
        fetch("SELECT * FROM orders WHERE id=? AND status='pending'", (specific_order_id,))
        if specific_order_id
        else fetch("SELECT * FROM orders WHERE status='pending' ORDER BY id ASC")
    )
    for o in orders:
        oid = o["id"]
        blob = f"{ocr_text} {o['note'] or ''} {o['ref'] or ''}".upper()
        for sms in unused_sms:
            tx = sms["tx_id"].upper()
            if tx and tx in blob and (sms["amount"] <= 0 or abs(sms["amount"] - o["price"]) <= 5):
                if execute_rc("UPDATE orders SET status='approved', ref=? WHERE id=? AND status='pending'", (tx, oid)):
                    execute("UPDATE sms_payments SET used_order_id=? WHERE id=?", (oid, sms["id"]))
                    order_dict = dict(fetch("SELECT * FROM orders WHERE id=?", (oid,))[0])
                    await update_live_user_status(bot, order_dict, "status_approved")
                    await deliver_approved_order(bot, order_dict)
                    try:
                        await bot.send_message(ADMIN_ID, f"🤖 **Auto-Approved!** ትዕዛዝ #{oid} በ SMS (`{tx}`) በራሱ ተረጋግጧል!")
                    except Exception:
                        pass
                    return True
    return False


async def send_invite(bot, order):
    uid = order["user_id"]
    pkg = order["package"]
    lang = get_lang(uid)
    cid = channel_for(pkg)
    if not cid:
        return False, "Channel ID በ config.py ላይ አልተሞላም።"
    try:
        exp = int(time.time()) + 86400 * 3
        inv = await bot.create_chat_invite_link(
            chat_id=cid,
            creates_join_request=True,
            expire_date=exp,
            name=f"u{uid}_o{order['id']}",
        )
        link = inv.invite_link
    except Exception:
        try:
            inv = await bot.create_chat_invite_link(chat_id=cid, member_limit=1, name=f"u{uid}_o{order['id']}")
            link = inv.invite_link
        except Exception as e:
            return False, str(e)

    execute("UPDATE orders SET invite_link=?, invite_exp=? WHERE id=?", (link, time.time() + 86400 * 3, order["id"]))
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(T[lang].get("btn_join", "🚀 ወደ ግሩፑ ይግቡ"), url=link)]])
    msg_text = T[lang].get("approved", "🎉 ክፍያዎ ተረጋግጧል! ከታች ባለው ሊንክ ወደ ግሩፑ ይግቡ፦\n{link}").format(
        link=link, pkg_name=PKG_LABEL.get(pkg, pkg)
    )
    try:
        await bot.send_message(uid, msg_text, reply_markup=kb)
        return True, link
    except Exception as e:
        return False, str(e)


async def deliver_approved_order(bot, order):
    uid = order["user_id"]
    pkg = order["package"]
    lang = get_lang(uid)
    execute("UPDATE users SET bought_at=COALESCE(bought_at, ?) WHERE user_id=?", (time.time(), uid))

    if pkg.startswith("gift_"):
        real_pkg = "bundle" if "bundle" in pkg else "books"
        code = f"GIFT-{random.randint(1000, 9999)}-{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}"
        execute("INSERT INTO gifts(code, package, buyer_id, created) VALUES(?,?,?,?)", (code, real_pkg, uid, time.time()))
        txt = T[lang]["gift_code_created"].format(code=code, pkg_name=PKG_LABEL.get(real_pkg, real_pkg))
        try:
            await bot.send_message(uid, txt, parse_mode="Markdown")
            return True, code
        except Exception as e:
            return False, str(e)

    return await send_invite(bot, order)


async def send_order_to_admin(bot, order_id):
    rows = fetch("SELECT * FROM orders WHERE id=?", (order_id,))
    if not rows:
        return
    o = dict(rows[0])
    uid = o["user_id"]
    u_rows = fetch("SELECT * FROM users WHERE user_id=?", (uid,))
    u = dict(u_rows[0]) if u_rows else {"name": str(uid), "username": None, "ad_source": None}
    await update_live_user_status(bot, o, "status_checking")

    ocr_info = ""
    fid = o["photo_file_id"] or ""
    if fid and hasattr(ocr, "read_receipt"):
        try:
            f = await bot.get_file(fid[4:] if fid.startswith("doc:") else fid)
            data = bytes(await f.download_as_bytearray())
            ocr_info = await asyncio.get_running_loop().run_in_executor(None, ocr.read_receipt, data) or ""
            if ocr_info:
                execute("UPDATE orders SET note=? WHERE id=?", (ocr_info[:300], order_id))
        except Exception:
            pass

    if await try_match_pending_with_sms(bot, specific_order_id=order_id, ocr_text=ocr_info):
        return

    uname = f" (@{u['username']})" if u.get("username") else ""
    promo_line = f"\n🎟️ ፕሮሞ፦ `{o['promo_code']}`" if o.get("promo_code") else ""
    ocr_line = f"\n🔍 OCR፦ `{ocr_info[:120]}`" if ocr_info else ""
    caption = (
        f"🆕 **አዲስ ትዕዛዝ #{order_id}**\n"
        f"👤 ደንበኛ፦ {u.get('name')}{uname} (`{uid}`)\n"
        f"📦 ጥቅል፦ {PKG_LABEL.get(o['package'], o['package'])}\n"
        f"💰 ዋጋ፦ **{o['price']} ብር**{promo_line}{ocr_line}"
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ አጽድቅ (Approve)", callback_data=f"ord:ok:{order_id}"),
                InlineKeyboardButton("❌ ውድቅ (Reject)", callback_data=f"ord:no:{order_id}"),
            ],
            [
                InlineKeyboardButton("⏳ ጠብቁ", callback_data=f"qrep:wait:{order_id}"),
                InlineKeyboardButton("🔍 አይነበብም", callback_data=f"qrep:blur:{order_id}"),
                InlineKeyboardButton("💰 ያነሰ ብር", callback_data=f"qrep:less:{order_id}"),
            ],
        ]
    )
    try:
        if fid.startswith("doc:"):
            m = await bot.send_document(ADMIN_ID, fid[4:], caption=caption, reply_markup=kb)
        else:
            m = await bot.send_photo(ADMIN_ID, fid, caption=caption, reply_markup=kb)
        execute("UPDATE orders SET admin_msg=? WHERE id=?", (m.message_id, order_id))
        execute("INSERT OR REPLACE INTO support(msg_id, user_id) VALUES(?, ?)", (m.message_id, uid))
    except Exception as e:
        log.error("send_order_to_admin error: %s", e)


async def on_order_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    _, decision, oid_str = q.data.split(":")
    oid = int(oid_str)
    rows = fetch("SELECT * FROM orders WHERE id=?", (oid,))
    if not rows:
        await q.answer("ትዕዛዙ አልተገኘም", show_alert=True)
        return
    order = dict(rows[0])
    if order["status"] != "pending":
        await q.answer(f"ቀድሞ {order['status']} ተደርጓል!", show_alert=True)
        return

    uid = order["user_id"]
    lang = get_lang(uid)

    if decision == "ok":
        execute("UPDATE orders SET status='approved' WHERE id=?", (oid,))
        await update_live_user_status(context.bot, order, "status_approved")
        ok, info = await deliver_approved_order(context.bot, order)
        status_line = "✅ ጸድቋል (ሊንክ ተልኳል)" if ok else f"⚠️ ጸድቋል ግን ሊንክ አልተላከም፦ {info}"
        await q.answer(status_line[:190], show_alert=not ok)
    else:
        execute("UPDATE orders SET status='rejected' WHERE id=?", (oid,))
        await update_live_user_status(context.bot, order, "status_rejected")
        try:
            await context.bot.send_message(uid, T[lang].get("rejected", "❌ የላኩት ደረሰኝ አልተረጋገጠም። እባክዎ ትክክለኛ ደረሰኝ ይላኩ።"))
        except Exception:
            pass
        status_line = "❌ ውድቅ ተደርጓል"
        await q.answer(status_line)

    try:
        old_cap = q.message.caption or ""
        await q.edit_message_caption(caption=f"{old_cap}\n\n{status_line}", reply_markup=None)
    except Exception:
        pass


async def on_quick_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    _, kind, oid_str = q.data.split(":")
    rows = fetch("SELECT user_id FROM orders WHERE id=?", (int(oid_str),))
    if not rows:
        return
    uid = rows[0]["user_id"]
    lang = get_lang(uid)
    key_map = {"wait": "qreply_wait", "blur": "qreply_blur", "less": "qreply_less"}
    msg = T[lang].get(key_map.get(kind, "qreply_wait"), FALLBACK_TEXTS["qreply_wait"])
    try:
        await context.bot.send_message(uid, msg)
        await q.answer("✅ መልዕክቱ ለደንበኛው ተልኳል!")
    except Exception as e:
        await q.answer(f"⚠️ አልተላከም፦ {e}"[:190], show_alert=True)


async def on_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    uid = req.from_user.id
    cid = req.chat.id
    rows = fetch("SELECT id, package FROM orders WHERE user_id=? AND status='approved'", (uid,))
    allowed_cids = {channel_for(r["package"]) for r in rows}
    if cid in allowed_cids:
        try:
            await req.approve()
            execute("UPDATE orders SET joined=1 WHERE user_id=? AND status='approved'", (uid,))
        except Exception as e:
            log.warning("Join approve failed for %s: %s", uid, e)
    else:
        try:
            await req.decline()
        except Exception:
            pass


# ---------------------------------------------------------------- Background Jobs
async def job_remind_unpaid(context: ContextTypes.DEFAULT_TYPE):
    cutoff = time.time() - 900  # 15 ደቂቃ
    rows = fetch("SELECT user_id, pkg FROM sessions WHERE step='await_photo' AND reminded=0 AND pay_started IS NOT NULL AND pay_started < ?", (cutoff,))
    for r in rows:
        uid = r["user_id"]
        execute("UPDATE sessions SET reminded=1 WHERE user_id=?", (uid,))
        if user_best_package(uid):
            continue
        lang = get_lang(uid)
        rem_txt = T[lang].get("remind_pay", "⏳ ሰላም! የመረጡትን ጥቅል ክፍያ ገና አላጠናቀቁም። ማንኛውም ጥያቄ ካለዎት ወይም የደረሰኝ ፎቶ ለመላክ እዚሁ ይላኩልን! 👇")
        try:
            await context.bot.send_message(uid, rem_txt)
        except Forbidden:
            execute("UPDATE users SET bot_blocked=1 WHERE user_id=?", (uid,))
        except Exception:
            pass


async def post_init(app: Application):
    if ADMIN_ID:
        admin_cmds = [
            BotCommand("start", "ቦቱን እንደገና አስጀምር"),
            BotCommand("stats", "የሽያጭ እና ተጠቃሚ ሪፖርት"),
            BotCommand("find", "ደንበኛ ፈልግ (/find ስም)"),
            BotCommand("addpromo", "የቅናሽ ኮድ ፍጠር"),
            BotCommand("delpromo", "የቅናሽ ኮድ ሰርዝ"),
            BotCommand("broadcast", "መልዕክት ለሁሉም ላክ"),
            BotCommand("backup", "ዳታቤዝ ባክአፕ ላክ"),
        ]
        try:
            await app.bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(ADMIN_ID))
        except Exception:
            pass
        if DB_WARN:
            try:
                await app.bot.send_message(ADMIN_ID, DB_WARN)
            except Exception:
                pass


def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN በ .env ውስጥ አልተሞላም።")
    check_texts()
    prepare_db_path()
    init_db()

    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", cmd_find))
    app.add_handler(CommandHandler("addpromo", cmd_addpromo))
    app.add_handler(CommandHandler("delpromo", cmd_delpromo))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("sms", cmd_sms))

    app.add_handler(CallbackQueryHandler(on_go, pattern=r"^go:"))
    app.add_handler(CallbackQueryHandler(on_lang, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(on_profile_answer, pattern=r"^(height|age|gender):"))
    app.add_handler(CallbackQueryHandler(on_package, pattern=r"^pkg:"))
    app.add_handler(CallbackQueryHandler(on_vip_action, pattern=r"^vip:"))
    app.add_handler(CallbackQueryHandler(on_gift_redeem_btn, pattern=r"^gift:redeem$"))
    app.add_handler(CallbackQueryHandler(on_promo_btn, pattern=r"^promo:ask$"))
    app.add_handler(CallbackQueryHandler(on_faq, pattern=r"^faq:"))
    app.add_handler(CallbackQueryHandler(on_admin_grant, pattern=r"^admgrant:"))
    app.add_handler(CallbackQueryHandler(on_broadcast_btn, pattern=r"^bcast:"))
    app.add_handler(CallbackQueryHandler(on_order_decision, pattern=r"^ord:"))
    app.add_handler(CallbackQueryHandler(on_quick_reply, pattern=r"^qrep:"))

    app.add_handler(ChatJoinRequestHandler(on_join_request))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    if app.job_queue:
        app.job_queue.run_repeating(job_remind_unpaid, interval=300, first=60)

    log.info("Bot started successfully!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
