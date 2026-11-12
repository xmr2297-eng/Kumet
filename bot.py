import asyncio
import hashlib
import hmac
import io
import json
import logging
import os
import re
import sqlite3
import time
import urllib.parse
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiohttp import web
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

try:
    import texts as _texts_mod
    from texts import AGE_CODES, CHOOSE_LANG, GENDER_CODES, HEIGHT_CODES, T
except ImportError:
    import text as _texts_mod
    from text import AGE_CODES, CHOOSE_LANG, GENDER_CODES, HEIGHT_CODES, T

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

DASHBOARD_PASS = os.getenv("DASHBOARD_PASS", "").strip() or str(ADMIN_ID)
PORT = int(os.getenv("PORT", "8080") or 8080)
PUBLIC_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
if PUBLIC_URL and not PUBLIC_URL.startswith("http"):
    PUBLIC_URL = f"https://{PUBLIC_URL}"

DB_PATH_SET = bool(os.getenv("DB_PATH"))
DB_PATH = Path(os.getenv("DB_PATH") or (config.BASE / "bot.db"))
DB_WARN = None if DB_PATH_SET else "⚠️ DB_PATH አልተሞላም፤ Railway ላይ Volume (/data) እና DB_PATH=/data/bot.db ያስቀምጡ።"

MAX_PENDING_PER_USER = getattr(config, "MAX_PENDING_PER_USER", 3)
COACH_DAYS = getattr(config, "COACH_DAYS", (3, 7, 15, 30))
BACKUP_INTERVAL_HOURS = getattr(config, "BACKUP_INTERVAL_HOURS", 24)
FAST_BONUS_HOURS = getattr(config, "FAST_BONUS_HOURS", 24)
FOLLOWUP_HOURS = getattr(config, "FOLLOWUP_HOURS", (0.25, 6.0, 24.0))
FOLLOWUP_RESET_HOURS = getattr(config, "FOLLOWUP_RESET_HOURS", 48.0)

ETH_TZ = timezone(timedelta(hours=3))

BOT_USERNAME = ""
LAST_BACKUP_TS = 0.0

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("bookbot")
for _noisy in ("httpx", "httpcore", "aiohttp.access"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

FALLBACK_TEXTS = {
    "analysis_young": "አስደናቂ ዜና! በዚህ የእድሜ ክልል የእድገት ፕሌቶችዎ እና የዕድገት ሆርሞን (HGH) ከፍተኛ ንቁ ደረጃ ላይ ይገኛሉ።\n📈 ከ 8 እስከ 12 CM የቁመት መጨመር ከፍተኛ እድል አለዎት!",
    "analysis_adult": "መልካም ዜና! በዚህ የእድሜ ክልል የአከርካሪ መለጠጥ (Spinal Decompression) እና የአቋም ማስተካከያ ልምምዶችን በመጠቀም\n📈 ከ 5 እስከ 8 CM ተጨማሪ ቁመት ማግኘት ይችላሉ!",
    "btn_upgrade": "⬆️ ወደ ቪዲዮ ግሩፕ አሳድግ ({price} ብር ብቻ)",
    "social_proof_line": "\n\n🔥 ዛሬ ብቻ {today_count} ወጣቶች ወደ ግሩፑ ተቀላቅለዋል! (የመጨረሻው ከ {mins_ago} ደቂቃ በፊት)",
    "fast_bonus_line": "\n⏳ በ {rem_hr} ውስጥ ከከፈሉ የ VIP ግሩፕ ልዩ ድጋፍ ያገኛሉ!",
    "fast_bonus_expired": "",
    "faq_time_btn": "❓ በስንት ደቂቃ ወደ ግሩፑ እገባለሁ?",
    "faq_time_ans": "⏱ የደረሰኝ ፎቶ እንደላኩ ከ 1 እስከ 3 ደቂቃ ውስጥ ተረጋግጦ ወዲያውኑ ወደ Private ግሩፑ የሚያስገባዎት ሊንክ እዚሁ ይደርስዎታል!",
    "faq_other_btn": "❓ በሌላ ሰው ስልክ/ባንክ መክፈል ይቻላል?",
    "faq_other_ans": "✅ አዎ ይቻላል! በማንኛውም ሰው ስልክ ወይም ባንክ ከፍለው የደረሰኙን ፎቶ እዚህ መላክ ይችላሉ።",
    "voice_caption": "🎧 እንዴት በቀላሉ እንደሚከፍሉና ወደ ግሩፑ ወዲያውኑ እንደሚገቡ ይህን ድምጽ ያዳምጡ።",
    "bad_photo_quality": "⚠️ የላኩት ፎቶ በጣም የጨለመ ወይም ጥራቱ አነስተኛ ስለሆነ አይነበብም። እባክዎ ግልጽ Screenshot ይላኩ። 👇",
    "status_checking": "🔵 ሁኔታ፦ አድሚኑ ደረሰኝዎን እያረጋገጠ ነው...\n⏳ እባክዎ ጥቂት ይጠብቁን። 🙏",
    "status_approved": "🟢 ሁኔታ፦ ክፍያዎ ተረጋግጧል! የግሩፕ መግቢያ ሊንክዎ ከታች ተልኳል 🎉",
    "status_rejected": "🔴 ሁኔታ፦ ደረሰኙ አልተረጋገጠም። እባክዎ ትክክለኛ ደረሰኝ ይላኩ።",
    "qreply_wait": "⏳ ሰላም! ደረሰኝዎ ደርሶናል፣ እያረጋገጥን ስለሆነ እባክዎ ጥቂት ደቂቃዎች ይጠብቁን። 🙏",
    "qreply_blur": "🔍 ሰላም! የላኩት የደረሰኝ ፎቶ በደንብ አይነበብም። እባክዎ ግልጽ ስክሪንሾት እንደገና ይላኩ። 👇",
    "qreply_less": "💰 ሰላም! የላኩት የገንዘብ መጠን ከመረጡት ጥቅል ዋጋ ያነሰ ነው። እባክዎ ቀሪውን አሟልተው ይላኩ። 👇",
    "vip_welcome": "👑 እንኳን ደህና መጡ ክቡር አባላችን {name}!\n\n📦 የገቡበት ግሩፕ፦ {pkg_name}\n🔥 የልምምድ ተከታታይነት (Streak)፦ {streak} ቀን\n📏 የቁመት ክትትል፦ {height_progress}\n\nከታች ባሉት አዝራሮች የዕለቱን ልምምድና ቁመትዎን ይመዝግቡ 👇",
    "btn_streak": "✅ የዛሬውን ልምምድ ሰርቻለሁ (🔥 {streak} ቀን)",
    "streak_already": "⚡ የዛሬውን ልምምድ አስቀድመው መዝግበዋል! ነገ ተመልሰው ይመዝግቡ (🔥 {streak} ቀን)።",
    "streak_up": "🔥 ምርጥ ነው! ለ {streak} ተከታታይ ቀናት ልምምድዎን ሰርተዋል! በግሩፑም ላይ ቀጥሉበት!",
    "streak_7_secret": "🏆 እንኳን ደስ አለዎት! 7 ተከታታይ ቀናት ስላጠናቀቁ ልዩ ምስጢር ተከፍቶልዎታል፦\n💡 ማታ ከመተኛትዎ በፊት ለ 2 ደቂቃ በባር ላይ መንጠልጠል (Dead Hang) የአከርካሪ ዲስኮች በፍጥነት እንዲለጠጡ ያደርጋል! 🚀",
    "height_none": "ገና አልተመዘገበም",
    "btn_log_height": "📏 የዛሬ ቁመቴን መዝግብ (Height Log)",
    "ask_log_height": "📏 እባክዎ አሁን ያሉበትን ትክክለኛ ቁመት በሴንቲሜትር (በቁጥር ብቻ፣ ለምሳሌ፦ 170) ይጻፉ 👇",
    "log_height_first": "✅ የመጀመሪያ ቁመትዎ ({cm} CM) ተመዝግቧል! ከሳምንታት ልምምድ በኋላ ለውጥዎን እዚህ ይመዝግቡ። 💪",
    "log_height_gain": "🎉 እንኳን ደስ አለዎት! ከጀመሩ ጀምሮ +{diff} CM ጨምረዋል! ({start} CM ➔ {cm} CM) 🚀",
    "log_height_same": "✅ የዛሬ ቁመትዎ ({cm} CM) ተመዝግቧል። ልምምድዎን በግሩፑ መመሪያ መሰረት ይቀጥሉ! 💪",
    "log_height_invalid": "⚠️ እባክዎ ትክክለኛ ቁመት በቁጥር ብቻ ይጻፉ (ከ 100 እስከ 250 CM፣ ለምሳሌ፦ 168)።",
    "card_caption": "🏆 እንኳን ደስ አለዎት! ይህ የእርስዎ ኦፊሴላዊ የቁመት እድገት ሰርተፊኬት ነው! 🎉",
    "btn_vip_files": "🔗 የ Private ግሩፕ መግቢያ ሊንክ ላክልኝ",
    "btn_vip_restart": "🔄 ጥያቄዎቹን ከመጀመሪያ ለማየት",
    "coach_d3": "🏋️‍♂️ ሰላም {name}! ግሩፑን ከተቀላቀሉ 3 ቀን ሆነዎት። የዛሬውን ልምምድዎን ከታች ይመዝግቡ! 💪",
    "coach_d7": "🥗 ሰላም {name}! 1 ሳምንት ተቆጠረ! ልምምዱን ከ8 ሰዓት እንቅልፍ ጋር አቀናጅተው ይቀጥሉ! 😴🔥",
    "coach_d15": "🚀 ሰላም {name}! 15 ቀናት አለፉ! አንድም ቀን ሳያቋርጡ ይቀጥሉ! 🏆",
    "coach_d30": "🎉 እንኳን ደስ አለዎት {name}! 30 ቀን አጠናቀቁ! ከታች ባለው አዝራር ውጤትዎን ያጋሩን! 👇",
    "btn_send_testi": "✍️ ለውጤን / ምስክርነቴን ልላክ",
    "ask_testi": "✍️ እባክዎ ያገኙትን የቁመት ለውጥ (በ CM) እና አስተያየትዎን ይጻፉልን 👇",
    "testi_thanks": "🙏 ከልብ እናመሰግናለን! ምስክርነትዎ ለአድሚኑ ደርሷል።",
    "followup_1": "👋 ሰላም {name}፣ ቅድም የጀመሩትን የቁመት ማሳደጊያ ፕሮግራም ለመጨረስ አሁኑኑ ይጫኑ፦\n👉 /start",
    "followup_2": "🔥 ሰላም {name}፣ የሰውነትዎ የዕድገት እድል ሳይዘጋ አሁኑኑ ወደ ልዩ ግሩፓችን ይቀላቀሉ፦\n👉 /start",
    "followup_3": "⏳ የመጨረሻ ማሳሰቢያ ለ {name}! ለለውጥ ዝግጁ ከሆኑ አሁኑኑ ይጀምሩ፦\n👉 /start",
}


def check_texts():
    config.PRICES.setdefault("upgrade", max(100, config.PRICES.get("bundle", 597) - config.PRICES.get("books", 397)))
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


def ensure_user(u, ad_source=None):
    execute("INSERT OR IGNORE INTO users(user_id, name, started_at, followup_stage, bot_blocked) VALUES(?, ?, ?, 0, 0)", (u.id, u.full_name, time.time()))
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
    allowed = {"pkg", "step", "photo", "pay_started", "reminded"}
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


# ---------------------------------------------------------------- Deep-Link Helpers
def channel_for(package):
    chans = getattr(config, "CHANNELS", {}) or {}
    return int((chans.get("upgrade") or chans.get("bundle") or 0) if package == "upgrade" else (chans.get(package) or 0))


def group_deeplink_kb():
    uname = BOT_USERNAME or "bot"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔥 የዛሬ ልምምዴን ሰርቻለሁ (Streak)", url=f"https://t.me/{uname}?start=streak")],
            [InlineKeyboardButton("📏 የዛሬ ቁመቴን ልመዝግብ (Height Log)", url=f"https://t.me/{uname}?start=log_h")],
        ]
    )


async def announce_in_user_group(bot, user_id, msg_text):
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
            [back_button(lang, "proof")],
        ]
    )
    return text, kb


def format_height_progress(user_id, lang):
    rows = fetch("SELECT start_cm, current_cm FROM users WHERE user_id=?", (user_id,))
    if not rows or not rows[0]["start_cm"]:
        return T[lang]["height_none"]
    s, c = rows[0]["start_cm"], rows[0]["current_cm"] or rows[0]["start_cm"]
    diff = round(c - s, 1)
    return f"{s:g} CM ➔ {c:g} CM (+{diff:g} CM 🚀)" if diff > 0 else f"{c:g} CM"


def b_vip(context, user, lang):
    best = user_best_package(user.id) or "books"
    h_prog = format_height_progress(user.id, lang)
    u_rows = fetch("SELECT COALESCE(streak_count, 0) AS sc FROM users WHERE user_id=?", (user.id,))
    streak = u_rows[0]["sc"] if u_rows else 0
    raw_vip = T[lang]["vip_welcome"]
    text = raw_vip.format(
        name=user.first_name or "", pkg_name=PKG_LABEL.get(best, best), streak=streak, height_progress=h_prog, ref_count=0, ref_target=0
    )
    text = "\n".join(line for line in text.splitlines() if "በእርስዎ ሊንክ" not in line and "ጓደኞች፦" not in line)
    rows = [
        [InlineKeyboardButton(T[lang]["btn_streak"].format(streak=streak), callback_data="vip:streak")],
        [InlineKeyboardButton(T[lang]["btn_log_height"], callback_data="vip:log_h")],
        [InlineKeyboardButton(T[lang]["btn_vip_files"], callback_data="vip:files")],
    ]
    if best == "books":
        rows.append([InlineKeyboardButton(T[lang]["btn_upgrade"].format(price=config.PRICES.get("upgrade", 200)), callback_data="pkg:upgrade")])
    rows.append([InlineKeyboardButton(T[lang]["btn_vip_restart"], callback_data="go:lang")])
    return text, InlineKeyboardMarkup(rows)


def account_copy_rows(lang="am"):
    rows = []
    for line in config.PAYMENT_ACCOUNTS.splitlines():
        nums = re.findall(r"\d{6,}", line)
        if nums:
            label = re.sub(r"\s*\(.*?\)", "", line).strip()[:55]
            rows.append([InlineKeyboardButton(f"📋 {label}", copy_text=CopyTextButton(text=nums[0]))])
    rows = rows[:6]
    rows.append([InlineKeyboardButton(T[lang]["faq_time_btn"], callback_data="faq:time")])
    rows.append([InlineKeyboardButton(T[lang]["faq_other_btn"], callback_data="faq:other")])
    return rows


def b_pay(context, user, lang):
    s = st_get(user.id)
    pkg = s.get("pkg")
    if pkg not in config.PRICES:
        return b_pkg(context, user, lang)
    final_price = config.PRICES[pkg]
    raw_pay = T[lang]["pay"]
    extra_footer = get_social_and_bonus_footer(user.id, lang)
    if "{discount_note}" in raw_pay:
        text = raw_pay.format(price=final_price, discount_note="", accounts=config.PAYMENT_ACCOUNTS, extra_footer=extra_footer)
    else:
        text = raw_pay.format(price=final_price, accounts=config.PAYMENT_ACCOUNTS) + extra_footer
    st_set(user.id, step="await_photo", pay_started=s.get("pay_started") or time.time())
    back_target = "vip" if pkg == "upgrade" else "pkg"
    return text, InlineKeyboardMarkup(account_copy_rows(lang) + [[back_button(lang, back_target)]])


BUILD = {
    "lang": b_lang, "welcome": b_welcome, "q1": b_q1, "q2": b_q2, "q3": b_q3,
    "offer": b_offer, "video": b_video, "proof": b_proof, "pkg": b_pkg, "pay": b_pay,
    "vip": b_vip,
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
    now_eth = datetime.now(ETH_TZ)
    today_str = now_eth.strftime("%Y-%m-%d")
    yest_str = (now_eth - timedelta(days=1)).strftime("%Y-%m-%d")
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
    ad_source = deep_action = None
    if context.args:
        arg = context.args[0]
        if arg in ("streak", "log_h"):
            deep_action = arg
        elif arg.startswith("src_"):
            ad_source = arg[4:].lower()
        elif not arg.startswith("ref_"):
            ad_source = arg.lower()

    ensure_user(u, ad_source=ad_source)
    st_clear(u.id)
    lang = get_lang(u.id)
    try:
        await update.message.delete()
    except Exception:
        pass

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
    if pkg in ("books", "bundle", "upgrade") and pkg in config.PRICES:
        st_set(q.from_user.id, pkg=pkg)
        await show("pay", context, q.message.chat_id, q.from_user, current=q.message.message_id, can_edit=_can_edit(q))


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
    return s.get("step") == "await_photo" and s.get("pkg") in config.PRICES


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
    pkg = s["pkg"]
    final_price = config.PRICES[pkg]
    try:
        order_id = execute(
            "INSERT INTO orders(user_id, package, price, photo_file_id, photo_uid, photo_hash, photo_thumb) VALUES(?,?,?,?,?,?,?)",
            (uid, pkg, final_price, fid, uniq, digest, small),
        )
    except sqlite3.IntegrityError:
        await update.message.reply_text(T[lang]["dup_receipt"])
        return
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

    if s.get("step") == "await_testi":
        st_clear(uid)
        uname = f" @{user.username}" if user.username else ""
        m = await context.bot.send_message(ADMIN_ID, f"🌟 አዲስ ምስክርነት!\nደንበኛ፦ {user.full_name}{uname} (ID: {uid})\n\n💬 “{txt}”")
        execute("INSERT OR REPLACE INTO support(msg_id, user_id) VALUES(?, ?)", (m.message_id, uid))
        await update.message.reply_text(T[lang]["testi_thanks"])
        return

    await update.message.reply_text(T[lang]["need_photo" if ready_to_pay(s) else "hint"])


# ---------------------------------------------------------------- Telegram Admin Commands
def build_admin_dashboard():
    total_u = fetch("SELECT COUNT(*) AS n FROM users")[0]["n"]
    today_u = fetch("SELECT COUNT(*) AS n FROM users WHERE date(created)=date('now')")[0]["n"]
    pending_o = fetch("SELECT COUNT(*) AS n FROM orders WHERE status='pending'")[0]["n"]
    approved_o = fetch("SELECT COUNT(*) AS n, COALESCE(SUM(price),0) AS rev FROM orders WHERE status='approved'")[0]
    today_o = fetch("SELECT COUNT(*) AS n, COALESCE(SUM(price),0) AS rev FROM orders WHERE status='approved' AND date(created)=date('now')")[0]

    url_note = f"\n🌐 **ዌብ ዳሽቦርድ፦** {PUBLIC_URL}\n" if PUBLIC_URL else "\n💡 *Railway Settings ➔ Networking ➔ Generate Domain በመጫን ዌብ ዳሽቦርዱን በብራውዘር ይክፈቱ!*\n"

    text = (
        f"🎛 **የአድሚን ዳሽቦርድ — {config.BOT_NAME}**\n"
        f"━━━━━━━━━━━━━━━━━━━━"
        f"{url_note}\n"
        f"👥 **ጠቅላላ ተጠቃሚዎች፦** {total_u} (ዛሬ፦ +{today_u})\n"
        f"💰 **ጠቅላላ ሽያጭ፦** {approved_o['n']} ጥቅል ({approved_o['rev']} ብር)\n"
        f"🔥 **የዛሬ ሽያጭ፦** {today_o['n']} ጥቅል ({today_o['rev']} ብር)\n"
        f"⏳ **በመጠባበቅ ላይ፦** {pending_o} ደረሰኝ"
    )
    rows = []
    if PUBLIC_URL:
        rows.append([InlineKeyboardButton("🌐 ዘመናዊ Web Dashboard በብራውዘር ክፈት", url=PUBLIC_URL)])
    rows.extend(
        [
            [
                InlineKeyboardButton(f"⏳ ያልተረጋገጡ ደረሰኞች ({pending_o})", callback_data="adm:pending"),
                InlineKeyboardButton("👥 ተጠቃሚዎች", callback_data="uopen:0"),
            ],
            [
                InlineKeyboardButton("💾 ዳታቤዝ ባክአፕ", callback_data="adm:backup"),
                InlineKeyboardButton("🔄 አድስ (Refresh)", callback_data="adm:refresh"),
            ],
        ]
    )
    return text, InlineKeyboardMarkup(rows)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text, kb = build_admin_dashboard()
    await update.message.reply_text(text, reply_markup=kb)


async def on_admin_dash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    action = q.data.split(":")[1]
    if action == "refresh":
        text, kb = build_admin_dashboard()
        try:
            await q.edit_message_text(text, reply_markup=kb)
        except Exception:
            pass
        await q.answer("✅ ታድሷል!")
    elif action == "pending":
        await q.answer()
        rows = fetch("SELECT id FROM orders WHERE status='pending' ORDER BY id")
        if not rows:
            await context.bot.send_message(ADMIN_ID, "✅ በመጠባበቅ ላይ ያለ ደረሰኝ የለም።")
            return
        for r in rows[:10]:
            await send_order_to_admin(context.bot, r["id"])
    elif action == "backup":
        await q.answer("💾 ባክአፕ በመላክ ላይ...")
        await send_db_backup(context.bot)


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
            f"📏 **ቁመት፦** {format_height_progress(uid, 'am')} | 🔥 Streak: {u['streak_count'] or 0}"
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


# ---------------------------------------------------------------- Auto-Approve SMS
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


# ---------------------------------------------------------------- Admin Order Review & Private Group Invite
CAPTION_MAX = 1024


def fit_caption(text, suffix=""):
    room = CAPTION_MAX - len(suffix)
    return (text[: max(room - 1, 0)] + "…" if len(text) > room else text) + suffix


def order_caption(order, user, footer=True):
    uname = f" @{user['username']}" if user["username"] else ""
    text = (
        f"🧾 ትዕዛዝ #{order['id']}\n"
        f"ደንበኛ፦ {user['name']} (id {order['user_id']}){uname}\n"
        f"ጥቅል፦ {PKG_LABEL.get(order['package'], order['package'])} | ዋጋ፦ {order['price']} ብር\n"
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


async def do_quick_reply(bot, oid: int, kind: str):
    rows = fetch("SELECT * FROM orders WHERE id=?", (oid,))
    if not rows:
        return False, "ትዕዛዙ አልተገኘም"
    order = dict(rows[0])
    uid = order["user_id"]
    msg_key = {"wait": "qreply_wait", "blur": "qreply_blur", "less": "qreply_less"}.get(kind)
    if kind == "wait":
        await update_live_user_status(bot, order, "status_checking")
    elif kind in ("blur", "less"):
        st_set(uid, pkg=order["package"], step="await_photo", pay_started=time.time(), reminded=0)
    try:
        await bot.send_message(uid, T[get_lang(uid)][msg_key])
        return True, "መልዕክቱ ለደንበኛው ተልኳል!"
    except Exception as e:
        return False, str(e)


async def on_admin_quick_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    _, kind, oid = q.data.split(":")
    ok, msg = await do_quick_reply(context.bot, int(oid), kind)
    await q.answer(f"✅ {msg}" if ok else f"❌ {msg}"[:190], show_alert=not ok)


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


async def send_invite(bot, order):
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
    await update_live_user_status(bot, order, "status_approved")

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


async def decide_order(bot, oid: int, action: str):
    rows = fetch("SELECT * FROM orders WHERE id=?", (oid,))
    if not rows or rows[0]["status"] != "pending":
        return False, "ይህ ትዕዛዝ ቀድሞ ተወስኗል"
    order = dict(rows[0])
    if action == "approve":
        if not execute_rc("UPDATE orders SET status='approved' WHERE id=? AND status='pending'", (oid,)):
            return False, "ቀድሞ ተወስኗል"
        ok, info = await deliver_approved_order(bot, order)
        return ok, ("ተረጋግጧል! የግሩፕ ሊንክ ለደንበኛው ተልኳል ✅" if ok else f"ተረጋግጧል ግን ሊንክ አልተላከም፦ {info}")
    else:
        if not execute_rc("UPDATE orders SET status='rejected' WHERE id=? AND status='pending'", (oid,)):
            return False, "ቀድሞ ተወስኗል"
        await update_live_user_status(bot, order, "status_rejected")
        execute("UPDATE users SET started_at=?, followup_stage=0 WHERE user_id=?", (time.time(), order["user_id"]))
        try:
            await bot.send_message(order["user_id"], T[get_lang(order["user_id"])]["rejected"])
        except Exception:
            pass
        full, user = load_order(oid)
        if full and full.get("admin_msg"):
            try:
                await bot.edit_message_caption(chat_id=ADMIN_ID, message_id=full["admin_msg"], caption=fit_caption(order_caption(full, user, footer=False), "\n\n❌ ውድቅ ተደርጓል"))
            except Exception:
                pass
        return True, "ትዕዛዙ ውድቅ ተደርጓል ❌"


async def on_admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    action, oid = q.data.split(":")
    ok, msg = await decide_order(context.bot, int(oid), action)
    await q.answer(msg[:190], show_alert=not ok)


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


# ---------------------------------------------------------------- Stats & Users (Telegram)
def get_users_page(page=0):
    limit, offset = 15, page * 15
    total_users = fetch("SELECT COUNT(*) AS n FROM users")[0]["n"]
    total_pages = max(1, (total_users + limit - 1) // limit)
    rows = fetch(
        """
        SELECT u.user_id, u.name, u.username, date(u.created) as created_date,
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
        lines.append(f"{offset + i + 1}. {sym} {r['name']}{uname} (ID: {r['user_id']}) - {r['created_date']}")
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


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    rows = fetch("SELECT id FROM orders WHERE status='pending' ORDER BY id")
    if not rows:
        await update.message.reply_text("✅ በመጠባበቅ ላይ ያለ ደረሰኝ የለም።")
        return
    for r in rows[:10]:
        await send_order_to_admin(context.bot, r["id"])


# ================================================================
# 🌐 MODERN WEB ADMIN DASHBOARD (AIOHTTP)
# ================================================================
def _dash_token():
    return hashlib.sha256(f"{TOKEN}:{DASHBOARD_PASS}:ethio_dash".encode()).hexdigest()


def _is_authed(request: web.Request) -> bool:
    cookie = request.cookies.get("adm_session", "")
    hdr = request.headers.get("X-Admin-Token", "")
    expected = _dash_token()
    return (cookie and hmac.compare_digest(cookie, expected)) or (hdr and hmac.compare_digest(hdr, expected))


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="am" class="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ethio Length — Admin Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  body { font-family: 'Plus Jakarta Sans', sans-serif; background: #090d16; color: #f1f5f9; }
  .glass { background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(16px); border: 1px solid rgba(255,255,255,0.08); }
  .card-hover { transition: all 0.2s ease; }
  .card-hover:hover { transform: translateY(-2px); border-color: rgba(56, 189, 248, 0.35); }
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: #090d16; }
  ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
</style>
</head>
<body class="min-h-screen flex flex-col">

<!-- LOGIN MODAL -->
<div id="loginScreen" class="fixed inset-0 z-50 flex items-center justify-center bg-[#090d16] p-4 hidden">
  <div class="glass max-w-md w-full rounded-3xl p-8 shadow-2xl text-center border border-sky-500/20">
    <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center mx-auto mb-5 shadow-lg shadow-sky-500/25 text-3xl">👑</div>
    <h1 class="text-2xl font-extrabold tracking-tight mb-1">Ethio Length Admin</h1>
    <p class="text-slate-400 text-sm mb-6">ወደ ዘመናዊው የአድሚን ዳሽቦርድ ለመግባት ፓስዎርድ ያስገቡ</p>
    <form onsubmit="doLogin(event)" class="space-y-4">
      <input id="passInput" type="password" placeholder="Password (ወይም ADMIN_ID)" required
        class="w-full px-4 py-3.5 rounded-xl bg-slate-900/90 border border-slate-700 text-white focus:outline-none focus:border-sky-500 text-center text-lg tracking-widest">
      <button type="submit" class="w-full py-3.5 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 font-bold text-white shadow-lg shadow-sky-500/25 transition">
        ግባ (Sign In) 🚀
      </button>
      <p id="loginErr" class="text-rose-400 text-sm hidden"></p>
    </form>
  </div>
</div>

<!-- TOP NAVBAR -->
<header class="glass sticky top-0 z-30 border-b border-slate-800/80">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center font-bold text-xl shadow-md shadow-sky-500/20">📏</div>
      <div>
        <div class="flex items-center gap-2">
          <span id="botName" class="font-extrabold text-lg tracking-tight text-white">Ethio Length</span>
          <span class="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">● LIVE</span>
        </div>
        <p id="botUser" class="text-xs text-slate-400">@bot</p>
      </div>
    </div>
    <div class="flex items-center gap-2 sm:gap-3">
      <button onclick="loadAll(true)" class="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs sm:text-sm font-medium flex items-center gap-1.5 transition">
        <span>🔄</span> <span class="hidden sm:inline">አድስ</span>
      </button>
      <a href="/api/backup" class="px-3.5 py-2 rounded-xl bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 border border-indigo-500/30 text-xs sm:text-sm font-medium flex items-center gap-1.5 transition">
        <span>💾</span> <span class="hidden sm:inline">Backup (.db)</span>
      </a>
      <button onclick="doLogout()" class="px-3 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-xs sm:text-sm font-medium transition">ውጣ</button>
    </div>
  </div>
  <!-- NAVIGATION TABS -->
  <div class="max-w-7xl mx-auto px-4 sm:px-6 flex gap-1 overflow-x-auto pb-2 pt-1">
    <button onclick="switchTab('overview')" id="tab-overview" class="tab-btn px-4 py-2 rounded-xl text-sm font-semibold whitespace-nowrap bg-sky-500 text-white">📊 አጠቃላይ (Overview)</button>
    <button onclick="switchTab('orders')" id="tab-orders" class="tab-btn px-4 py-2 rounded-xl text-sm font-semibold whitespace-nowrap text-slate-400 hover:text-white flex items-center gap-2">
      <span>🧾 ደረሰኞች (Orders)</span>
      <span id="navPendingBadge" class="px-2 py-0.5 text-xs rounded-full bg-amber-500 text-slate-950 font-extrabold hidden">0</span>
    </button>
    <button onclick="switchTab('users')" id="tab-users" class="tab-btn px-4 py-2 rounded-xl text-sm font-semibold whitespace-nowrap text-slate-400 hover:text-white">👥 ደንበኞች (Users)</button>
    <button onclick="switchTab('tools')" id="tab-tools" class="tab-btn px-4 py-2 rounded-xl text-sm font-semibold whitespace-nowrap text-slate-400 hover:text-white">🛠️ መሳሪያዎች & Broadcast</button>
  </div>
</header>

<!-- MAIN CONTENT -->
<main class="max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 flex-1 space-y-6">

  <!-- TAB 1: OVERVIEW -->
  <section id="sec-overview" class="space-y-6">
    <!-- KPI CARDS -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="glass rounded-2xl p-5 card-hover">
        <div class="flex justify-between items-start">
          <span class="text-slate-400 text-xs font-semibold uppercase tracking-wider">ጠቅላላ ገቢ</span>
          <span class="text-xl">💰</span>
        </div>
        <div id="kpiRev" class="text-2xl sm:text-3xl font-extrabold text-emerald-400 mt-2">0 ብር</div>
        <div id="kpiTodayRev" class="text-xs text-slate-400 mt-1">ዛሬ፦ 0 ብር (0 ሽያጭ)</div>
      </div>

      <div onclick="switchTab('orders')" class="glass rounded-2xl p-5 card-hover cursor-pointer border-amber-500/20">
        <div class="flex justify-between items-start">
          <span class="text-amber-300/90 text-xs font-semibold uppercase tracking-wider">ያልተረጋገጡ ደረሰኞች</span>
          <span class="text-xl">⏳</span>
        </div>
        <div id="kpiPending" class="text-2xl sm:text-3xl font-extrabold text-amber-400 mt-2">0</div>
        <div class="text-xs text-amber-300/70 mt-1">ለማረጋገጥ እዚህ ይጫኑ ➔</div>
      </div>

      <div class="glass rounded-2xl p-5 card-hover">
        <div class="flex justify-between items-start">
          <span class="text-slate-400 text-xs font-semibold uppercase tracking-wider">ጠቅላላ ተጠቃሚዎች</span>
          <span class="text-xl">👥</span>
        </div>
        <div id="kpiUsers" class="text-2xl sm:text-3xl font-extrabold text-sky-400 mt-2">0</div>
        <div id="kpiTodayUsers" class="text-xs text-slate-400 mt-1">ዛሬ የገቡ፦ +0</div>
      </div>

      <div class="glass rounded-2xl p-5 card-hover">
        <div class="flex justify-between items-start">
          <span class="text-slate-400 text-xs font-semibold uppercase tracking-wider">የተሸጡ ጥቅሎች</span>
          <span class="text-xl">👑</span>
        </div>
        <div id="kpiSales" class="text-2xl sm:text-3xl font-extrabold text-indigo-400 mt-2">0</div>
        <div id="kpiPkgSplit" class="text-xs text-slate-400 mt-1">📕 መጽሐፍ: 0 | 👑 VIP: 0</div>
      </div>
    </div>

    <!-- FUNNEL & SOURCES -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="glass rounded-2xl p-6">
        <h2 class="font-bold text-base mb-4 flex items-center gap-2"><span>📈</span> የደንበኞች ጉዞ (Conversion Funnel)</h2>
        <div id="funnelBox" class="space-y-3.5"></div>
      </div>
      <div class="glass rounded-2xl p-6">
        <h2 class="font-bold text-base mb-4 flex items-center gap-2"><span>📢</span> የማስታወቂያ ምንጮች (Top Ad Sources)</h2>
        <div id="sourcesBox" class="space-y-3"></div>
      </div>
    </div>
  </section>

  <!-- TAB 2: ORDERS -->
  <section id="sec-orders" class="space-y-4 hidden">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex gap-2">
        <button onclick="setOrderFilter('pending')" id="of-pending" class="px-4 py-2 rounded-xl text-xs sm:text-sm font-bold bg-amber-500 text-slate-950">⏳ በመጠባበቅ ላይ</button>
        <button onclick="setOrderFilter('approved')" id="of-approved" class="px-4 py-2 rounded-xl text-xs sm:text-sm font-bold bg-slate-800 text-slate-300">✅ የተረጋገጡ</button>
        <button onclick="setOrderFilter('rejected')" id="of-rejected" class="px-4 py-2 rounded-xl text-xs sm:text-sm font-bold bg-slate-800 text-slate-300">❌ ውድቅ የተደረጉ</button>
      </div>
      <span id="ordersCountText" class="text-xs text-slate-400"></span>
    </div>
    <div id="ordersGrid" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5"></div>
  </section>

  <!-- TAB 3: USERS -->
  <section id="sec-users" class="space-y-4 hidden">
    <div class="flex flex-col sm:flex-row gap-3 justify-between">
      <input id="userSearch" oninput="debounceUsers()" type="text" placeholder="🔎 በስም፣ @username ወይም ID ይፈልጉ..."
        class="w-full sm:max-w-md px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm focus:outline-none focus:border-sky-500">
      <div class="flex items-center gap-2">
        <button onclick="changeUserPage(-1)" class="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold">⬅️ ቀዳሚ</button>
        <span id="userPageInfo" class="text-xs text-slate-400 px-2">ገጽ 1</span>
        <button onclick="changeUserPage(1)" class="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold">ቀጣይ ➡️</button>
      </div>
    </div>
    <div class="glass rounded-2xl overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="border-b border-slate-800 text-slate-400 text-xs uppercase bg-slate-900/50">
              <th class="py-3.5 px-4">ደንበኛ</th>
              <th class="py-3.5 px-4">ሁኔታ / ጥቅል</th>
              <th class="py-3.5 px-4">ፕሮፋይል & ቁመት</th>
              <th class="py-3.5 px-4">ምንጭ / ቀን</th>
              <th class="py-3.5 px-4 text-right">እርምጃ (Actions)</th>
            </tr>
          </thead>
          <tbody id="usersTableBody" class="divide-y divide-slate-800/60"></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- TAB 4: TOOLS & BROADCAST -->
  <section id="sec-tools" class="grid grid-cols-1 lg:grid-cols-2 gap-6 hidden">
    <!-- Broadcast -->
    <div class="glass rounded-2xl p-6 space-y-4">
      <h2 class="font-bold text-base flex items-center gap-2"><span>📢</span> የጅምላ መልዕክት መላኪያ (Broadcast)</h2>
      <p class="text-xs text-slate-400">ከዚህ በታች የሚጽፉት መልዕክት ለመረጡት የደንበኞች ክፍል ወዲያውኑ በቴሌግራም ይላካል።</p>
      <select id="bcastTarget" class="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm">
        <option value="unpaid">🎯 ላልከፈሉ ብቻ (Unpaid Users)</option>
        <option value="books">📕 መጽሐፍ ብቻ ለገዙ (ለ VIP Upgrade)</option>
        <option value="all">🌍 ለሁሉም ተጠቃሚዎች (All Users)</option>
      </select>
      <textarea id="bcastText" rows="4" placeholder="መልዕክትዎን እዚህ ይጻፉ..." class="w-full p-4 rounded-xl bg-slate-900 border border-slate-700 text-sm focus:outline-none focus:border-sky-500"></textarea>
      <button onclick="sendBroadcast()" id="bcastBtn" class="w-full py-3 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:opacity-95 font-bold text-sm shadow-lg shadow-sky-500/20">
        📢 መልዕክቱን ለሁሉም ላክ
      </button>
    </div>

    <!-- Quick Tools -->
    <div class="space-y-6">
      <!-- Auto SMS Matcher -->
      <div class="glass rounded-2xl p-6 space-y-3">
        <h2 class="font-bold text-base flex items-center gap-2"><span>⚡</span> የባንክ SMS ማስገቢያ (Auto-Verify)</h2>
        <p class="text-xs text-slate-400">ከ CBE ወይም Telebirr የደረሰዎትን የክፍያ SMS እዚህ Paste ያድርጉ፤ ተመሳሳይ ደረሰኝ ካለ ወዲያውኑ በራሱ ያጸድቃል።</p>
        <textarea id="smsInput" rows="2" placeholder="Dear Fasika, your account has been credited with ETB 597.00..." class="w-full p-3 rounded-xl bg-slate-900 border border-slate-700 text-xs focus:outline-none focus:border-emerald-500"></textarea>
        <button onclick="submitSms()" class="w-full py-2.5 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 font-bold text-xs">
          ✅ SMS መዝግብ እና ደረሰኝ አዛምድ
        </button>
      </div>

      <!-- Followup Trigger -->
      <div class="glass rounded-2xl p-6 space-y-3">
        <h2 class="font-bold text-base flex items-center gap-2"><span>🚀</span> የደንበኞች ክትትል (Follow-up)</h2>
        <div class="pt-1">
          <button onclick="triggerFollowupNow()" class="w-full p-3.5 rounded-xl bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/30 text-sky-300 text-xs font-bold flex items-center justify-center gap-2">
            🚀 ላልከፈሉ Follow-up አሁን ላክ
          </button>
        </div>
      </div>
    </div>
  </section>

</main>

<!-- IMAGE LIGHTBOX MODAL -->
<div id="imgModal" onclick="this.classList.add('hidden')" class="fixed inset-0 z-50 bg-black/90 hidden flex items-center justify-center p-4 cursor-zoom-out">
  <img id="modalImg" src="" class="max-h-[92vh] max-w-[95vw] rounded-2xl shadow-2xl border border-slate-700">
</div>

<!-- TOAST NOTIFICATION -->
<div id="toast" class="fixed bottom-5 right-5 z-50 px-5 py-3.5 rounded-2xl glass border border-sky-500/40 text-sm font-semibold shadow-2xl hidden"></div>

<script>
let currentTab = 'overview';
let orderFilter = 'pending';
let userPage = 0;
let userTimer = null;

function showToast(msg, isErr=false) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `fixed bottom-5 right-5 z-50 px-5 py-3.5 rounded-2xl glass text-sm font-semibold shadow-2xl ${isErr ? 'border-rose-500/60 text-rose-300' : 'border-emerald-500/60 text-emerald-300'}`;
  t.classList.remove('hidden');
  setTimeout(() => t.classList.add('hidden'), 3500);
}

async function api(path, opts={}) {
  const res = await fetch(path, opts);
  if (res.status === 401) {
    document.getElementById('loginScreen').classList.remove('hidden');
    throw new Error('Unauthorized');
  }
  return res.json();
}

async function doLogin(e) {
  e.preventDefault();
  const password = document.getElementById('passInput').value;
  const res = await fetch('/api/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({password})
  });
  if (res.ok) {
    document.getElementById('loginScreen').classList.add('hidden');
    document.getElementById('loginErr').classList.add('hidden');
    loadAll();
  } else {
    const el = document.getElementById('loginErr');
    el.textContent = '❌ ፓስዎርድ ትክክል አይደለም!';
    el.classList.remove('hidden');
  }
}

async function doLogout() {
  await fetch('/api/logout', {method: 'POST'});
  location.reload();
}

function switchTab(tab) {
  currentTab = tab;
  ['overview', 'orders', 'users', 'tools'].forEach(t => {
    document.getElementById(`sec-${t}`).classList.toggle('hidden', t !== tab);
    const btn = document.getElementById(`tab-${t}`);
    if (t === tab) {
      btn.className = 'tab-btn px-4 py-2 rounded-xl text-sm font-semibold whitespace-nowrap bg-sky-500 text-white flex items-center gap-2';
    } else {
      btn.className = 'tab-btn px-4 py-2 rounded-xl text-sm font-semibold whitespace-nowrap text-slate-400 hover:text-white flex items-center gap-2';
    }
  });
  if (tab === 'orders') loadOrders();
  if (tab === 'users') loadUsers();
}

async function loadStats() {
  const d = await api('/api/stats');
  document.getElementById('botName').textContent = d.bot_name;
  document.getElementById('botUser').textContent = d.bot_username ? '@' + d.bot_username : 'Telegram Bot';
  document.getElementById('kpiRev').textContent = d.total_rev.toLocaleString() + ' ብር';
  document.getElementById('kpiTodayRev').textContent = `ዛሬ፦ ${d.today_rev.toLocaleString()} ብር (${d.today_sales} ሽያጭ)`;
  document.getElementById('kpiPending').textContent = d.pending_orders;
  document.getElementById('kpiUsers').textContent = d.total_users.toLocaleString();
  document.getElementById('kpiTodayUsers').textContent = `ዛሬ የገቡ፦ +${d.today_users} | ብሎክ፦ ${d.blocked_users}`;
  document.getElementById('kpiSales').textContent = d.total_sales.toLocaleString();
  document.getElementById('kpiPkgSplit').textContent = `📕 መጽሐፍ: ${d.books_sales} | 👑 VIP: ${d.bundle_sales}`;

  const badge = document.getElementById('navPendingBadge');
  badge.textContent = d.pending_orders;
  badge.classList.toggle('hidden', d.pending_orders === 0);

  // Funnel
  const maxF = Math.max(1, d.total_users);
  const fItems = [
    ['🏁 ጥያቄ የጀመሩ', d.funnel.q, 'bg-sky-500'],
    ['🧬 ውጤት ያዩ (Result)', d.funnel.res, 'bg-indigo-500'],
    ['🎥 ቪዲዮ/ምስክርነት ያዩ', d.funnel.vid, 'bg-purple-500'],
    ['📦 ጥቅል መምረጫ የደረሱ', d.funnel.pkg, 'bg-amber-500'],
    ['💳 ክፍያ ገጽ የደረሱ', d.funnel.pay, 'bg-emerald-500'],
  ];
  document.getElementById('funnelBox').innerHTML = fItems.map(([label, val, col]) => {
    const pct = Math.min(100, Math.round((val / maxF) * 100));
    return `<div>
      <div class="flex justify-between text-xs mb-1"><span class="text-slate-300 font-medium">${label}</span><span class="font-bold text-slate-200">${val} (${pct}%)</span></div>
      <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden"><div class="h-full ${col}" style="width:${pct}%"></div></div>
    </div>`;
  }).join('');

  // Sources
  document.getElementById('sourcesBox').innerHTML = d.sources.map(s => `
    <div class="flex items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-slate-800">
      <div>
        <div class="font-semibold text-sm text-white">${s.src}</div>
        <div class="text-xs text-slate-400">${s.users} ተጠቃሚዎች</div>
      </div>
      <div class="text-right">
        <div class="font-bold text-sm text-emerald-400">${s.rev.toLocaleString()} ብር</div>
        <div class="text-xs text-slate-400">${s.sales} ሽያጭ</div>
      </div>
    </div>
  `).join('') || '<p class="text-xs text-slate-500">ምንም መረጃ የለም</p>';
}

function setOrderFilter(f) {
  orderFilter = f;
  ['pending', 'approved', 'rejected'].forEach(k => {
    const b = document.getElementById(`of-${k}`);
    if (k === f) {
      b.className = 'px-4 py-2 rounded-xl text-xs sm:text-sm font-bold bg-sky-500 text-white';
    } else {
      b.className = 'px-4 py-2 rounded-xl text-xs sm:text-sm font-bold bg-slate-800 text-slate-300';
    }
  });
  loadOrders();
}

function openImg(url) {
  document.getElementById('modalImg').src = url;
  document.getElementById('imgModal').classList.remove('hidden');
}

async function loadOrders() {
  const d = await api(`/api/orders?status=${orderFilter}`);
  document.getElementById('ordersCountText').textContent = `${d.orders.length} ትዕዛዞች`;
  const grid = document.getElementById('ordersGrid');
  if (!d.orders.length) {
    grid.innerHTML = `<div class="col-span-full glass rounded-2xl p-12 text-center text-slate-400">✨ በዚህ ክፍል ምንም ደረሰኝ የለም።</div>`;
    return;
  }
  grid.innerHTML = d.orders.map(o => `
    <div class="glass rounded-2xl overflow-hidden flex flex-col justify-between border border-slate-800">
      <div>
        <div class="relative bg-slate-950 h-60 flex items-center justify-center overflow-hidden group cursor-zoom-in" onclick="openImg('/api/order_photo/${o.id}')">
          <img src="/api/order_photo/${o.id}" loading="lazy" class="object-contain h-full w-full group-hover:scale-105 transition">
          <span class="absolute top-3 left-3 px-2.5 py-1 rounded-lg bg-black/70 text-xs font-bold text-white">#${o.id}</span>
          <span class="absolute top-3 right-3 px-2.5 py-1 rounded-lg bg-sky-500/90 text-xs font-extrabold text-white">${o.price} ብር</span>
        </div>
        <div class="p-4 space-y-2">
          <div class="flex items-center justify-between">
            <div class="font-bold text-base text-white truncate">${o.user_name}</div>
            <span class="text-xs text-slate-400">ID: ${o.user_id}</span>
          </div>
          <div class="text-xs font-semibold text-sky-400">${o.pkg_label}</div>
          ${o.note ? `<div class="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 text-xs text-slate-300 whitespace-pre-line">${o.note}</div>` : ''}
          <div class="text-[11px] text-slate-500">🕒 ${o.created} ${o.username ? '· @'+o.username : ''}</div>
        </div>
      </div>
      ${o.status === 'pending' ? `
      <div class="p-4 pt-0 space-y-2">
        <div class="grid grid-cols-2 gap-2">
          <button onclick="orderAction(${o.id}, 'approve')" class="py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold text-xs transition">✅ አረጋግጥ (Approve)</button>
          <button onclick="orderAction(${o.id}, 'reject')" class="py-2.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30 font-bold text-xs transition">❌ ውድቅ (Reject)</button>
        </div>
        <div class="grid grid-cols-3 gap-1.5">
          <button onclick="orderAction(${o.id}, 'wait')" class="py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300">⏳ ጠብቅ</button>
          <button onclick="orderAction(${o.id}, 'blur')" class="py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300">🔍 አይታይም</button>
          <button onclick="orderAction(${o.id}, 'less')" class="py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300">💰 ቀሪ ብር</button>
        </div>
      </div>` : `
      <div class="p-4 pt-0">
        <button onclick="orderAction(${o.id}, 'resend')" class="w-full py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-sky-300">🔗 አዲስ የግሩፕ ሊንክ ላክ</button>
      </div>`}
    </div>
  `).join('');
}

async function orderAction(id, action) {
  const r = await api(`/api/orders/${id}/action`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action})
  });
  showToast(r.message, !r.ok);
  loadStats();
  loadOrders();
}

function debounceUsers() {
  clearTimeout(userTimer);
  userTimer = setTimeout(() => { userPage = 0; loadUsers(); }, 300);
}

function changeUserPage(dir) {
  userPage = Math.max(0, userPage + dir);
  loadUsers();
}

async function loadUsers() {
  const q = encodeURIComponent(document.getElementById('userSearch').value.trim());
  const d = await api(`/api/users?q=${q}&page=${userPage}`);
  document.getElementById('userPageInfo').textContent = `ገጽ ${d.page + 1} / ${d.total_pages} (${d.total} ሰዎች)`;
  const tbody = document.getElementById('usersTableBody');
  tbody.innerHTML = d.users.map(u => {
    const badge = u.pkg === 'bundle'
      ? '<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">👑 VIP Group</span>'
      : (u.pkg === 'books'
        ? '<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">📕 Books Group</span>'
        : '<span class="px-2.5 py-1 rounded-full text-xs bg-slate-800 text-slate-400">አልገዛም</span>');
    return `<tr class="hover:bg-slate-900/40">
      <td class="py-3.5 px-4">
        <div class="font-bold text-white">${u.name || '—'}</div>
        <div class="text-xs text-slate-400">ID: ${u.user_id} ${u.username ? '· @'+u.username : ''}</div>
      </td>
      <td class="py-3.5 px-4">${badge}</td>
      <td class="py-3.5 px-4 text-xs text-slate-300">
        <div>📏 ${u.height_prog}</div>
        <div class="text-slate-400">🔥 Streak: ${u.streak} ቀን</div>
      </td>
      <td class="py-3.5 px-4 text-xs text-slate-400">
        <div class="text-slate-300">${u.ad_source || 'ቀጥታ'}</div>
        <div>${u.created}</div>
      </td>
      <td class="py-3.5 px-4 text-right space-x-1 whitespace-nowrap">
        <button onclick="grantUser(${u.user_id}, 'books')" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-emerald-300" title="መጽሐፍ ግሩፕ ስጥ">+📕</button>
        <button onclick="grantUser(${u.user_id}, 'bundle')" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-amber-300" title="VIP ግሩፕ ስጥ">+👑</button>
        <button onclick="msgUser(${u.user_id}, '${(u.name||'').replace(/'/g, '')}')" class="px-2.5 py-1.5 rounded-lg bg-sky-500/20 hover:bg-sky-500/30 text-xs font-semibold text-sky-300">💬 መልዕክት</button>
      </td>
    </tr>`;
  }).join('');
}

async function grantUser(uid, pkg) {
  if (!confirm(`ለዚህ ደንበኛ (${uid}) የ ${pkg.toUpperCase()} ግሩፕ መግቢያ ሊንክ በነፃ ይላክለት?`)) return;
  const r = await api('/api/users/grant', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({user_id: uid, package: pkg})
  });
  showToast(r.message, !r.ok);
  loadUsers();
  loadStats();
}

async function msgUser(uid, name) {
  const text = prompt(`ለ ${name} (ID: ${uid}) የሚላክ መልዕክት ይጻፉ፦`);
  if (!text || !text.trim()) return;
  const r = await api('/api/users/message', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({user_id: uid, text})
  });
  showToast(r.message, !r.ok);
}

async function sendBroadcast() {
  const target = document.getElementById('bcastTarget').value;
  const text = document.getElementById('bcastText').value.trim();
  if (!text) return showToast('እባክዎ መልዕክት ይጻፉ!', true);
  if (!confirm('ይህ መልዕክት ለተመረጡት ደንበኞች በሙሉ ይላክ?')) return;
  const r = await api('/api/broadcast', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({target, text})
  });
  showToast(r.message, !r.ok);
  if (r.ok) document.getElementById('bcastText').value = '';
}

async function submitSms() {
  const text = document.getElementById('smsInput').value.trim();
  if (!text) return showToast('እባክዎ የSMS ጽሑፉን ያስገቡ!', true);
  const r = await api('/api/sms', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text})
  });
  showToast(r.message, !r.ok);
  if (r.ok) {
    document.getElementById('smsInput').value = '';
    loadStats();
  }
}

async function triggerFollowupNow() {
  const r = await api('/api/followup_now', {method: 'POST'});
  showToast(r.message, !r.ok);
}

async function loadAll(toast=false) {
  try {
    await loadStats();
    if (currentTab === 'orders') await loadOrders();
    if (currentTab === 'users') await loadUsers();
    if (toast) showToast('✅ ዳሽቦርዱ ታድሷል!');
  } catch (e) {}
}

loadAll();
setInterval(() => loadAll(false), 20000);
</script>
</body>
</html>
"""


async def web_index(request: web.Request):
    return web.Response(text=DASHBOARD_HTML, content_type="text/html")


async def web_login(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    pw = str(data.get("password", "")).strip()
    if hmac.compare_digest(pw, DASHBOARD_PASS):
        resp = web.json_response({"ok": True})
        resp.set_cookie("adm_session", _dash_token(), max_age=86400 * 30, httponly=True, samesite="Lax")
        return resp
    return web.json_response({"ok": False, "error": "Invalid password"}, status=401)


async def web_logout(request: web.Request):
    resp = web.json_response({"ok": True})
    resp.del_cookie("adm_session")
    return resp


async def web_stats(request: web.Request):
    if not _is_authed(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    total_u = fetch("SELECT COUNT(*) AS n FROM users")[0]["n"]
    today_u = fetch("SELECT COUNT(*) AS n FROM users WHERE date(created)=date('now')")[0]["n"]
    blocked_u = fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(bot_blocked,0)=1")[0]["n"]
    pending_o = fetch("SELECT COUNT(*) AS n FROM orders WHERE status='pending'")[0]["n"]
    approved_o = fetch("SELECT COUNT(*) AS n, COALESCE(SUM(price),0) AS rev FROM orders WHERE status='approved'")[0]
    today_o = fetch("SELECT COUNT(*) AS n, COALESCE(SUM(price),0) AS rev FROM orders WHERE status='approved' AND date(created)=date('now')")[0]
    books_cnt = fetch("SELECT COUNT(*) AS n FROM orders WHERE status='approved' AND package='books'")[0]["n"]
    bundle_cnt = fetch("SELECT COUNT(*) AS n FROM orders WHERE status='approved' AND package IN ('bundle','upgrade')")[0]["n"]

    funnel = {
        "q": fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(max_funnel,0) >= 1")[0]["n"],
        "res": fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(max_funnel,0) >= 2")[0]["n"],
        "vid": fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(max_funnel,0) >= 3")[0]["n"],
        "pkg": fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(max_funnel,0) >= 4")[0]["n"],
        "pay": fetch("SELECT COUNT(*) AS n FROM users WHERE COALESCE(max_funnel,0) >= 5")[0]["n"],
    }
    src_rows = fetch(
        """
        SELECT COALESCE(u.ad_source, 'ቀጥታ (Direct)') AS src, COUNT(DISTINCT u.user_id) AS u_cnt,
               COUNT(o.id) AS o_cnt, COALESCE(SUM(o.price), 0) AS rev
        FROM users u LEFT JOIN orders o ON o.user_id = u.user_id AND o.status = 'approved'
        GROUP BY COALESCE(u.ad_source, 'ቀጥታ (Direct)') ORDER BY rev DESC, u_cnt DESC LIMIT 6
        """
    )
    return web.json_response(
        {
            "bot_name": config.BOT_NAME,
            "bot_username": BOT_USERNAME,
            "total_users": total_u,
            "today_users": today_u,
            "blocked_users": blocked_u,
            "pending_orders": pending_o,
            "total_sales": approved_o["n"],
            "total_rev": approved_o["rev"],
            "today_sales": today_o["n"],
            "today_rev": today_o["rev"],
            "books_sales": books_cnt,
            "bundle_sales": bundle_cnt,
            "funnel": funnel,
            "sources": [{"src": r["src"], "users": r["u_cnt"], "sales": r["o_cnt"], "rev": r["rev"]} for r in src_rows],
        }
    )


async def web_orders(request: web.Request):
    if not _is_authed(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    status = request.query.get("status", "pending")
    rows = fetch(
        """
        SELECT o.id, o.user_id, o.package, o.price, o.status, o.note, o.created,
               u.name AS user_name, u.username
        FROM orders o LEFT JOIN users u ON u.user_id = o.user_id
        WHERE o.status = ? ORDER BY o.id DESC LIMIT 60
        """,
        (status,),
    )
    return web.json_response(
        {
            "orders": [
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "user_name": r["user_name"] or str(r["user_id"]),
                    "username": r["username"] or "",
                    "package": r["package"],
                    "pkg_label": PKG_LABEL.get(r["package"], r["package"]),
                    "price": r["price"],
                    "status": r["status"],
                    "note": r["note"] or "",
                    "created": r["created"],
                }
                for r in rows
            ]
        }
    )


async def web_order_photo(request: web.Request):
    if not _is_authed(request):
        return web.Response(status=401)
    oid = int(request.match_info["id"])
    rows = fetch("SELECT photo_file_id, photo_thumb FROM orders WHERE id=?", (oid,))
    if not rows:
        return web.Response(status=404)
    fid = rows[0]["photo_file_id"] or ""
    bot = request.app["bot"]
    if fid:
        try:
            f = await bot.get_file(fid[4:] if fid.startswith("doc:") else fid)
            data = bytes(await f.download_as_bytearray())
            return web.Response(body=data, content_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
        except Exception:
            pass
    return web.Response(status=404)


async def web_order_action(request: web.Request):
    if not _is_authed(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    oid = int(request.match_info["id"])
    data = await request.json()
    action = data.get("action")
    bot = request.app["bot"]

    if action in ("approve", "reject"):
        ok, msg = await decide_order(bot, oid, action)
        return web.json_response({"ok": ok, "message": msg})
    if action in ("wait", "blur", "less"):
        ok, msg = await do_quick_reply(bot, oid, action)
        return web.json_response({"ok": ok, "message": msg})
    if action == "resend":
        rows = fetch("SELECT * FROM orders WHERE id=?", (oid,))
        if not rows:
            return web.json_response({"ok": False, "message": "ትዕዛዙ አልተገኘም"})
        ok, info = await send_invite(bot, dict(rows[0]))
        return web.json_response({"ok": ok, "message": "✅ አዲስ ሊንክ ተልኳል!" if ok else f"⚠️ {info}"})
    return web.json_response({"ok": False, "message": "Unknown action"})


async def web_users(request: web.Request):
    if not _is_authed(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    q = request.query.get("q", "").strip().lstrip("@")
    page = max(0, int(request.query.get("page", "0") or 0))
    limit, offset = 20, page * 20

    if q:
        like = f"%{q}%"
        total = fetch("SELECT COUNT(*) AS n FROM users WHERE name LIKE ? OR username LIKE ? OR CAST(user_id AS TEXT) LIKE ?", (like, like, like))[0]["n"]
        rows = fetch(
            "SELECT * FROM users WHERE name LIKE ? OR username LIKE ? OR CAST(user_id AS TEXT) LIKE ? ORDER BY user_id DESC LIMIT ? OFFSET ?",
            (like, like, like, limit, offset),
        )
    else:
        total = fetch("SELECT COUNT(*) AS n FROM users")[0]["n"]
        rows = fetch("SELECT * FROM users ORDER BY user_id DESC LIMIT ? OFFSET ?", (limit, offset))

    users_list = []
    for u in rows:
        uid = u["user_id"]
        users_list.append(
            {
                "user_id": uid,
                "name": u["name"],
                "username": u["username"] or "",
                "pkg": user_best_package(uid),
                "height_prog": format_height_progress(uid, "am"),
                "streak": u["streak_count"] or 0,
                "ad_source": u["ad_source"] or "ቀጥታ",
                "created": (u["created"] or "")[:10],
            }
        )
    return web.json_response({"users": users_list, "total": total, "page": page, "total_pages": max(1, (total + limit - 1) // limit)})


async def web_user_grant(request: web.Request):
    if not _is_authed(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    data = await request.json()
    uid = int(data["user_id"])
    pkg = data["package"]
    if pkg not in ("books", "bundle"):
        return web.json_response({"ok": False, "message": "Invalid package"})
    order_id = execute("INSERT INTO orders(user_id, package, price, status) VALUES(?,?,0,'approved')", (uid, pkg))
    order = dict(fetch("SELECT * FROM orders WHERE id=?", (order_id,))[0])
    ok, info = await deliver_approved_order(request.app["bot"], order)
    return web.json_response({"ok": ok, "message": "✅ የግሩፕ መግቢያ ሊንኩ ለደንበኛው ተልኳል!" if ok else f"⚠️ {info}"})


async def web_user_message(request: web.Request):
    if not _is_authed(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    data = await request.json()
    uid = int(data["user_id"])
    text = (data.get("text") or "").strip()
    if not text:
        return web.json_response({"ok": False, "message": "ባዶ መልዕክት"})
    try:
        await request.app["bot"].send_message(uid, f"{T[get_lang(uid)]['reply_prefix']}\n{text}")
        return web.json_response({"ok": True, "message": "✅ መልዕክቱ ለደንበኛው ተልኳል!"})
    except Exception as e:
        return web.json_response({"ok": False, "message": f"❌ መላክ አልተቻለም፦ {e}"})


async def web_broadcast(request: web.Request):
    if not _is_authed(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    data = await request.json()
    target = data.get("target", "unpaid")
    text = (data.get("text") or "").strip()
    if not text:
        return web.json_response({"ok": False, "message": "ባዶ መልዕክት"})
    if target == "unpaid":
        rows = fetch("SELECT user_id FROM users u WHERE COALESCE(bot_blocked,0)=0 AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id=u.user_id AND o.status='approved')")
    elif target == "books":
        rows = fetch("SELECT DISTINCT user_id FROM orders WHERE status='approved' AND package='books' AND user_id NOT IN (SELECT user_id FROM orders WHERE status='approved' AND package IN ('bundle','upgrade'))")
    else:
        rows = fetch("SELECT user_id FROM users WHERE COALESCE(bot_blocked,0)=0")

    bot = request.app["bot"]

    async def _run_bcast():
        sent = blocked = 0
        for r in rows:
            try:
                await bot.send_message(r["user_id"], text)
                sent += 1
                await asyncio.sleep(0.05)
            except Forbidden:
                blocked += 1
                execute("UPDATE users SET bot_blocked=1 WHERE user_id=?", (r["user_id"],))
            except Exception:
                pass
        try:
            await bot.send_message(ADMIN_ID, f"✅ Web Broadcast ተጠናቀቀ! የደረሳቸው፦ {sent} | ብሎክ፦ {blocked}")
        except Exception:
            pass

    t = asyncio.create_task(_run_bcast())
    _TASKS.add(t)
    t.add_done_callback(_TASKS.discard)
    return web.json_response({"ok": True, "message": f"🚀 ለ {len(rows)} ደንበኞች በጀርባ መላክ ተጀምሯል!"})


async def web_sms(request: web.Request):
    if not _is_authed(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    data = await request.json()
    raw = (data.get("text") or "").strip()
    added = register_sms_text(raw)
    if added:
        await try_match_pending_with_sms(request.app["bot"])
        return web.json_response({"ok": True, "message": f"✅ ተመዝግቧል፦ {', '.join(added)}"})
    return web.json_response({"ok": False, "message": "⚠️ የግብይት ቁጥር (TxID) አልተገኘም።"})


async def web_followup_now(request: web.Request):
    if not _is_authed(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    immediate_start = time.time() - (FOLLOWUP_HOURS[0] * 3600) - 10
    execute("UPDATE users SET started_at=?, followup_stage=0 WHERE COALESCE(bot_blocked,0)=0 AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id=users.user_id AND o.status IN ('pending','approved'))", (immediate_start,))
    t = asyncio.create_task(check_followups(request.app["bot"]))
    _TASKS.add(t)
    t.add_done_callback(_TASKS.discard)
    return web.json_response({"ok": True, "message": "🚀 ላልከፈሉ ደንበኞች የማስታወሻ መልዕክት መላክ ተጀመረ!"})


async def web_backup(request: web.Request):
    if not _is_authed(request):
        return web.Response(status=401, text="Unauthorized")
    if not DB_PATH.exists():
        return web.Response(status=404, text="Database file not found")
    return web.FileResponse(
        DB_PATH,
        headers={"Content-Disposition": f'attachment; filename="bot_backup_{int(time.time())}.db"'},
    )


async def start_web_server(bot):
    wapp = web.Application()
    wapp["bot"] = bot
    wapp.router.add_get("/", web_index)
    wapp.router.add_post("/api/login", web_login)
    wapp.router.add_post("/api/logout", web_logout)
    wapp.router.add_get("/api/stats", web_stats)
    wapp.router.add_get("/api/orders", web_orders)
    wapp.router.add_get("/api/order_photo/{id:\\d+}", web_order_photo)
    wapp.router.add_post("/api/orders/{id:\\d+}/action", web_order_action)
    wapp.router.add_get("/api/users", web_users)
    wapp.router.add_post("/api/users/grant", web_user_grant)
    wapp.router.add_post("/api/users/message", web_user_message)
    wapp.router.add_post("/api/broadcast", web_broadcast)
    wapp.router.add_post("/api/sms", web_sms)
    wapp.router.add_post("/api/followup_now", web_followup_now)
    wapp.router.add_get("/api/backup", web_backup)

    runner = web.AppRunner(wapp)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info("🌐 Web Admin Dashboard started on port %s", PORT)
    return runner


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
    global LAST_BACKUP_TS
    LAST_BACKUP_TS = time.time()
    while True:
        try:
            await check_reminders(bot)
            await check_followups(bot)
            await check_coach_messages(bot)
            await nag_admin(bot)
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
    user_cmds = [BotCommand("start", "🚀 ከመጀመሪያ ጀምር / VIP ገጽ")]
    try:
        await app.bot.set_my_commands(user_cmds)
        await app.bot.set_my_commands(
            user_cmds + [
                BotCommand("admin", "🎛 የአድሚን ዳሽቦርድ (Web & Bot)"),
                BotCommand("pending", "⏳ ያልተረጋገጡ ደረሰኞች"),
                BotCommand("find", "🔎 ደንበኛ መፈለጊያ"),
                BotCommand("users", "👥 ተጠቃሚዎች"),
                BotCommand("broadcast", "📢 ጅምላ መልዕክት"),
                BotCommand("backup", "💾 ባክአፕ"),
                BotCommand("sms", "⚡ የባንክ SMS መዝግብ"),
                BotCommand("resend", "🔗 የግሩፕ ሊንክ"),
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
    app.bot_data["web_runner"] = await start_web_server(app.bot)
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
    app.add_handler(CommandHandler(["admin", "panel", "stats"], cmd_admin))
    app.add_handler(CommandHandler("find", cmd_find))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("resend", cmd_resend))
    app.add_handler(CommandHandler("sms", cmd_sms))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(ChatJoinRequestHandler(on_join_request))
    app.add_handler(CallbackQueryHandler(on_go, pattern=r"^go:"))
    app.add_handler(CallbackQueryHandler(on_vip_action, pattern=r"^vip:"))
    app.add_handler(CallbackQueryHandler(on_lang, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(on_profile_answer, pattern=r"^(age|gender|height):"))
    app.add_handler(CallbackQueryHandler(on_package, pattern=r"^pkg:"))
    app.add_handler(CallbackQueryHandler(on_faq, pattern=r"^faq:"))
    app.add_handler(CallbackQueryHandler(on_send_testi_btn, pattern=r"^testi:send$"))
    app.add_handler(CallbackQueryHandler(on_admin_dash, pattern=r"^adm:"))
    app.add_handler(CallbackQueryHandler(on_admin_decision, pattern=r"^(approve|reject):\d+$"))
    app.add_handler(CallbackQueryHandler(on_admin_quick_reply, pattern=r"^qrep:(wait|blur|less):\d+$"))
    app.add_handler(CallbackQueryHandler(on_admin_grant, pattern=r"^admgrant:(books|bundle):\d+$"))
    app.add_handler(CallbackQueryHandler(on_users_page, pattern=r"^(uopen|upage):\d+$"))
    app.add_handler(CallbackQueryHandler(on_broadcast_btn, pattern=r"^bcast:"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY & filters.User(user_id=ADMIN_ID) & ~filters.COMMAND, on_admin_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("ቦቱ እየሰራ ነው…")
    app.run_polling(allowed_updates=["message", "callback_query", "chat_join_request"])


if __name__ == "__main__":
    main()
