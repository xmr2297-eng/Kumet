import logging
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from texts import AGE_CODES, CHOOSE_LANG, GENDER_CODES, HEIGHT_CODES, T

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DB_PATH = Path(os.getenv("DB_PATH") or (config.BASE / "bot.db"))

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("bookbot")


# ---------------------------------------------------------------- database
def init_db():
    with closing(sqlite3.connect(DB_PATH)) as con:
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
            """
        )
        con.commit()


def execute(sql, args=()):
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid


def fetch(sql, args=()):
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.row_factory = sqlite3.Row
        return con.execute(sql, args).fetchall()


def get_lang(user_id):
    rows = fetch("SELECT lang FROM users WHERE user_id=?", (user_id,))
    return rows[0]["lang"] if rows and rows[0]["lang"] in T else "am"


# ---------------------------------------------------------------- screen helpers
def keyboard(prefix, codes, labels, cols=2, back=None, lang="am"):
    buttons = [
        InlineKeyboardButton(label, callback_data=f"{prefix}:{code}")
        for code, label in zip(codes, labels)
    ]
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


def track(context, *items):
    """የተላኩ መልዕክቶችን ያስታውሳል፣ ወደ ቀጣዩ ስክሪን ሲሄድ ይሰረዛሉ።"""
    ids = context.user_data.setdefault("msgs", [])
    for item in items:
        if isinstance(item, (list, tuple)):
            ids.extend(m.message_id for m in item)
        else:
            ids.append(item.message_id)


async def wipe(context, chat_id, current=None):
    ids = context.user_data.pop("msgs", [])
    if current is not None and current not in ids:
        ids.append(current)
    for mid in ids:
        try:
            await context.bot.delete_message(chat_id, mid)
        except Exception:
            pass  # ቀድሞ ተሰርዟል ወይም ከ48 ሰዓት በላይ ሆኖታል


# ---------------------------------------------------------------- screens
# እያንዳንዱ ስክሪን ቀዳሚውን ያጠፋል፣ ራሱን ይልካል፣ ከታች "ተመለስ" አዝራር አለው።
async def scr_lang(context, chat_id, user, lang):
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang:am"),
                InlineKeyboardButton("🌳 Afaan Oromoo", callback_data="lang:om"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
            ]
        ]
    )
    track(context, await context.bot.send_message(chat_id, CHOOSE_LANG, reply_markup=kb))


async def scr_welcome(context, chat_id, user, lang):
    text = T[lang]["welcome"].format(name=user.first_name or "", brand=config.BOT_NAME)
    kb = one_button(lang, "btn_begin", "q1", back="lang")
    track(context, await context.bot.send_message(chat_id, text, reply_markup=kb))


async def scr_q1(context, chat_id, user, lang):
    kb = keyboard("height", HEIGHT_CODES, T[lang]["heights"], cols=1, back="welcome", lang=lang)
    track(context, await context.bot.send_message(chat_id, T[lang]["ask_height"], reply_markup=kb))


async def scr_q2(context, chat_id, user, lang):
    kb = keyboard("age", AGE_CODES, T[lang]["ages"], cols=2, back="q1", lang=lang)
    track(context, await context.bot.send_message(chat_id, T[lang]["ask_age"], reply_markup=kb))


async def scr_q3(context, chat_id, user, lang):
    kb = keyboard("gender", GENDER_CODES, T[lang]["genders"], cols=2, back="q2", lang=lang)
    track(context, await context.bot.send_message(chat_id, T[lang]["ask_gender"], reply_markup=kb))


def answer_label(lang, key, codes, code):
    return T[lang][key][codes.index(code)] if code in codes else "—"


async def scr_offer(context, chat_id, user, lang):
    """የደንበኛውን መልሶች መዝግቦ ያሳያል (ምንም ያልተረጋገጠ ተስፋ ሳይሰጥ)።"""
    rows = fetch("SELECT age, gender, height FROM users WHERE user_id=?", (user.id,))
    r = dict(rows[0]) if rows else {}
    text = T[lang]["result"].format(
        height=answer_label(lang, "heights", HEIGHT_CODES, r.get("height")),
        age=answer_label(lang, "ages", AGE_CODES, r.get("age")),
        gender=answer_label(lang, "genders", GENDER_CODES, r.get("gender")),
    )
    kb = one_button(lang, "btn_video", "video", back="q3")
    track(context, await context.bot.send_message(chat_id, text, reply_markup=kb))


async def scr_video(context, chat_id, user, lang):
    kb = one_button(lang, "btn_watched", "proof", back="offer")
    if config.INTRO_VIDEO.exists():
        with open(config.INTRO_VIDEO, "rb") as f:
            msg = await context.bot.send_video(
                chat_id, f, caption=T[lang]["video_intro"], reply_markup=kb
            )
    else:
        msg = await context.bot.send_message(chat_id, T[lang]["video_intro"], reply_markup=kb)
    track(context, msg)


async def scr_proof(context, chat_id, user, lang):
    photos = []
    if config.TESTIMONIAL_DIR.exists():
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            photos += sorted(config.TESTIMONIAL_DIR.glob(ext))
    photos = photos[:10]
    if len(photos) == 1:
        track(context, await context.bot.send_photo(chat_id, photos[0].read_bytes()))
    elif photos:
        media = [InputMediaPhoto(p.read_bytes()) for p in photos]
        track(context, await context.bot.send_media_group(chat_id, media))
    entries = config.TESTIMONIALS.get(lang) or []
    if entries:
        text = T[lang]["proof_header"] + "\n\n" + "\n\n".join(entries)
    elif photos:
        text = T[lang]["proof_text"]
    else:
        text = T[lang]["decide_text"]
    kb = one_button(lang, "btn_decided", "pkg", back="video")
    track(context, await context.bot.send_message(chat_id, text, reply_markup=kb))


async def scr_pkg(context, chat_id, user, lang):
    p = config.PRICES
    text = config.OFFER[lang].format(
        price=p["books"], price_bundle=p["bundle"], accounts=config.PAYMENT_ACCOUNTS
    )
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(T[lang]["btn_books"].format(price=p["books"]), callback_data="pkg:books")],
            [InlineKeyboardButton(T[lang]["btn_bundle"].format(price=p["bundle"]), callback_data="pkg:bundle")],
            [back_button(lang, "proof")],
        ]
    )
    track(context, await context.bot.send_message(chat_id, text, reply_markup=kb))


async def scr_pay(context, chat_id, user, lang):
    pkg = context.user_data.get("pkg")
    if pkg not in config.PRICES:
        return await scr_pkg(context, chat_id, user, lang)
    text = T[lang]["pay"].format(price=config.PRICES[pkg], accounts=config.PAYMENT_ACCOUNTS)
    kb = InlineKeyboardMarkup([[back_button(lang, "pkg")]])
    track(context, await context.bot.send_message(chat_id, text, reply_markup=kb))
    context.user_data["step"] = "await_photo"


SCREENS = {
    "lang": scr_lang,
    "welcome": scr_welcome,
    "q1": scr_q1,
    "q2": scr_q2,
    "q3": scr_q3,
    "offer": scr_offer,
    "video": scr_video,
    "proof": scr_proof,
    "pkg": scr_pkg,
}


async def show(name, context, chat_id, user, current=None):
    await wipe(context, chat_id, current)
    context.user_data.pop("step", None)
    lang = get_lang(user.id)
    screen = scr_pay if name == "pay" else SCREENS[name]
    await screen(context, chat_id, user, lang)


# ---------------------------------------------------------------- customer flow
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    u = update.effective_user
    execute("INSERT OR IGNORE INTO users(user_id, name) VALUES(?, ?)", (u.id, u.full_name))
    try:
        await update.message.delete()
    except Exception:
        pass
    await show("lang", context, update.effective_chat.id, u)


async def on_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = q.data.split(":")[1]
    if name not in SCREENS:
        return
    await show(name, context, q.message.chat_id, q.from_user, current=q.message.message_id)


async def on_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = q.data.split(":")[1]
    if lang not in T:
        return
    u = q.from_user
    execute("INSERT OR IGNORE INTO users(user_id, name) VALUES(?, ?)", (u.id, u.full_name))
    execute("UPDATE users SET lang=? WHERE user_id=?", (lang, u.id))
    await show("welcome", context, q.message.chat_id, u, current=q.message.message_id)


NEXT_AFTER = {"height": "q2", "age": "q3", "gender": "offer"}


async def on_profile_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    field, code = q.data.split(":")
    if field not in NEXT_AFTER:
        return
    execute(f"UPDATE users SET {field}=? WHERE user_id=?", (code, q.from_user.id))
    await show(NEXT_AFTER[field], context, q.message.chat_id, q.from_user, current=q.message.message_id)


async def on_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    pkg = q.data.split(":")[1]
    if pkg not in config.PRICES:
        return
    context.user_data["pkg"] = pkg
    await show("pay", context, q.message.chat_id, q.from_user, current=q.message.message_id)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    if context.user_data.get("step") != "await_photo":
        await update.message.reply_text(T[lang]["hint"])
        return
    context.user_data["photo"] = update.message.photo[-1].file_id
    context.user_data["step"] = "await_ref"
    await update.message.reply_text(T[lang]["ask_ref"])


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_lang(user.id)
    step = context.user_data.get("step")

    if step == "await_photo":
        await update.message.reply_text(T[lang]["need_photo"])
        return
    if step != "await_ref":
        await update.message.reply_text(T[lang]["hint"])
        return

    ref = update.message.text.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{6,30}", ref):
        await update.message.reply_text(T[lang]["ref_bad"])
        return
    if fetch("SELECT id FROM orders WHERE ref=? AND status IN ('pending','approved')", (ref,)):
        await update.message.reply_text(T[lang]["ref_dup"])
        return

    pkg = context.user_data["pkg"]
    price = config.PRICES[pkg]
    photo = context.user_data["photo"]
    order_id = execute(
        "INSERT INTO orders(user_id, package, price, ref, photo_file_id) VALUES(?,?,?,?,?)",
        (user.id, pkg, price, ref, photo),
    )
    context.user_data.clear()
    await update.message.reply_text(T[lang]["received"])

    profile = fetch("SELECT age, gender, height FROM users WHERE user_id=?", (user.id,))[0]
    caption = (
        f"🧾 አዲስ ትዕዛዝ #{order_id}\n"
        f"ደንበኛ፦ {user.full_name} (id {user.id})"
        f"{' @' + user.username if user.username else ''}\n"
        f"ጥቅል፦ {pkg}  |  ዋጋ፦ {price} ብር\n"
        f"የግብይት ቁጥር፦ {ref}\n"
        f"ቁመት/እድሜ/ፆታ፦ {profile['height']}/{profile['age']}/{profile['gender']}"
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"approve:{order_id}"),
                InlineKeyboardButton("❌ ውድቅ", callback_data=f"reject:{order_id}"),
            ]
        ]
    )
    await context.bot.send_photo(ADMIN_ID, photo, caption=caption, reply_markup=kb)


# ---------------------------------------------------------------- admin
async def deliver(context: ContextTypes.DEFAULT_TYPE, order):
    user_id = order["user_id"]
    lang = get_lang(user_id)
    await context.bot.send_message(user_id, T[lang]["approved"])
    for path in config.BOOKS[lang]:
        with open(path, "rb") as f:
            await context.bot.send_document(user_id, f, filename=path.name)
    if order["package"] == "bundle":
        with open(config.BONUS_VIDEO, "rb") as f:
            await context.bot.send_video(user_id, f)


async def on_admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("አይፈቀድልዎትም", show_alert=True)
        return
    action, oid = q.data.split(":")
    rows = fetch("SELECT * FROM orders WHERE id=?", (int(oid),))
    if not rows:
        await q.answer("ትዕዛዙ አልተገኘም", show_alert=True)
        return
    order = rows[0]
    if order["status"] != "pending":
        await q.answer(f"ቀድሞ ተወስኗል ({order['status']})", show_alert=True)
        return

    if action == "approve":
        missing = [p.name for p in config.BOOKS[get_lang(order["user_id"])] if not p.exists()]
        if order["package"] == "bundle" and not config.BONUS_VIDEO.exists():
            missing.append(config.BONUS_VIDEO.name)
        if missing:
            await q.answer(f"ፋይል የለም፦ {', '.join(missing)}", show_alert=True)
            return
        try:
            await deliver(context, order)
        except Exception as e:  # ደንበኛው ቦቱን አግዶ ሊሆን ይችላል
            log.exception("delivery failed")
            await q.answer(f"መላክ አልተቻለም፦ {e}", show_alert=True)
            return
        execute("UPDATE orders SET status='approved' WHERE id=?", (order["id"],))
        await q.answer("ተልኳል ✅")
        await q.edit_message_caption(q.message.caption + "\n\n✅ ተረጋግጧል እና ተልኳል")
    else:
        execute("UPDATE orders SET status='rejected' WHERE id=?", (order["id"],))
        lang = get_lang(order["user_id"])
        try:
            await context.bot.send_message(order["user_id"], T[lang]["rejected"])
        except Exception:
            log.exception("could not notify user")
        await q.answer("ውድቅ ተደርጓል")
        await q.edit_message_caption(q.message.caption + "\n\n❌ ውድቅ ተደርጓል")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = fetch("SELECT COUNT(*) AS n FROM users")[0]["n"]
    pending = fetch("SELECT COUNT(*) AS n FROM orders WHERE status='pending'")[0]["n"]
    ok = fetch("SELECT COUNT(*) AS n, COALESCE(SUM(price),0) AS s FROM orders WHERE status='approved'")[0]
    await update.message.reply_text(
        f"👥 ተጠቃሚዎች፦ {users}\n⏳ በመጠባበቅ ላይ፦ {pending}\n✅ የተሸጠ፦ {ok['n']} ({ok['s']} ብር)"
    )


# ---------------------------------------------------------------- main
def main():
    if not TOKEN or not ADMIN_ID:
        raise SystemExit("BOT_TOKEN እና ADMIN_ID በ .env ፋይል ውስጥ ያስቀምጡ (README ይመልከቱ)።")
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(on_go, pattern=r"^go:"))
    app.add_handler(CallbackQueryHandler(on_lang, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(on_profile_answer, pattern=r"^(age|gender|height):"))
    app.add_handler(CallbackQueryHandler(on_package, pattern=r"^pkg:"))
    app.add_handler(CallbackQueryHandler(on_admin_decision, pattern=r"^(approve|reject):\d+$"))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("ቦቱ እየሰራ ነው…")
    app.run_polling()


if __name__ == "__main__":
    main()
