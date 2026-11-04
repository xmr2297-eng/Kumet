import os
from pathlib import Path

BASE = Path(__file__).parent
BOT_NAME = "Ethio Length"

PRICES = {
    "books": 397,        # መጽሐፍ ብቻ ግሩፕ/ቻናል
    "bundle": 597,       # መጽሐፍ + ቪዲዮ ግሩፕ/ቻናል
    "upgrade": 200,      # ወደ ቪዲዮ ግሩፕ ማሳደጊያ
    "gift_books": 397,   # ስጦታ (መጽሐፍ ብቻ)
    "gift_bundle": 597,  # ስጦታ (መጽሐፍ + ቪዲዮ)
}

REFERRAL_TARGET = 5
BACKUP_INTERVAL_HOURS = 24
FAST_BONUS_HOURS = 24
GROUP_POST_HOURS = 8

PAYMENT_ACCOUNTS = os.getenv("PAYMENT_ACCOUNTS", "").replace("\\n", "\n") or """\
🏦 CBE: 1000658433605 (Fasika Bekele)
📱 Telebirr: 0967507969 (Fasika Bekele)
🏦 Abyssinia: 149004718 (Fasika Bekele)"""

TELEBIRR_PHONE = os.getenv("TELEBIRR_PHONE", "0967507969")
CBE_ACCOUNT = os.getenv("CBE_ACCOUNT", "1000658433605")

OFFER = {
    "am": """\
ሰላም! 👋 ቁመትዎን በተፈጥሯዊ መንገዶች መጨመር ይፈልጋሉ? እነዚህ መጽሐፍት እና የልምምድ ግሩፖች ለእርስዎ የተዘጋጁ ናቸው!

በውስጣቸው ምን ይዘዋል?
🏋️‍♂️ 1. ልምምድ (Exercise): አጥንትንና አከርካሪን የማሳደግ ጥበብ።
🥗 2. አመጋገብ (Diet): ለሰውነት ግንባታ የሚረዱ ምግቦች።
😴 3. እረፍት (Rest): እንቅልፍ ለቁመት እድገት የሚጫወተው ሚና።
🔥 4. ልዩ የልምምድ ግሩፕ: በየቀኑ ክትትል እና ማበረታቻ የሚያገኙበት!

📕 "6 foot 6" (37 ገጾች) + 📗 "5 inches" (69 ገጾች)
📢 በ English፣ በአማርኛ እና በ Afaan Oromoo ተዘጋጅተዋል!

💳 ክፍያ እና አረካከብ፦
📘 መጽሐፎች ብቻ (Private Group)፦ {price} ብር
📘🎬 መጽሐፎች + ቪዲዮ (VIP Group)፦ {price_bundle} ብር

👇 ከታች ጥቅል ይምረጡ፤ ክፍያ እንደፈጸሙ ወደ ትክክለኛው Private ግሩፕ የሚገቡበት ሊንክ ይደርስዎታል።""",
    "en": """\
Hello! 👋 Do you want to increase your height naturally?

What you get inside our Private Groups:
🏋️‍♂️ 1. Exercise & Stretching guides
🥗 2. Affordable Diet plans
😴 3. HGH Sleep optimization
🔥 4. Daily Motivation & Height Tracker!

📕 "6 foot 6" (37 pages) + 📗 "5 inches" (69 pages)
📢 Available in English, Amharic and Afaan Oromoo!

💳 Packages:
📘 Books Group: {price} Birr
📘🎬 Books + Video VIP Group: {price_bundle} Birr

👇 Choose a package below to get your instant group invite link.""",
    "om": """\
Akkam! 👋 Dheerina keessan karaa uumamaan dabaluu barbaadduu?

Keessa Garee Dhuunfaa (Private Group) keenyaa maal qaba?
🏋️‍♂️ 1. Shaakala (Exercise) lafee fi dugugguruu diriirsu
🥗 2. Nyaata (Diet) fi 😴 Boqonnaa (Rest)
🔥 3. Hordoffii guyyaa guyyaa fi jajjabina garee keessatti!

📕 "6 foot 6" (fuula 37) + 📗 "5 inches" (fuula 69)
📢 Afaan Ingiliffaa, Amaaraa fi Afaan Oromootiin qophaa'aniiru!

💳 Kaffaltii:
📘 Kitaabota qofa (Private Group): Birr {price}
📘🎬 Kitaabota + Viidiyoo (VIP Group): Birr {price_bundle}

👇 Paakeejii armaan gadii filadhaa."""
}

CHANNELS = {
    "books": int(os.getenv("BOOKS_CHANNEL_ID", "0") or 0),
    "bundle": int(os.getenv("BUNDLE_CHANNEL_ID", "0") or 0),
    "upgrade": int(os.getenv("BUNDLE_CHANNEL_ID", "0") or 0),
}
INVITE_HOURS = int(os.getenv("INVITE_HOURS", "24") or 24)

INTRO_VIDEO = BASE / "media" / "intro.mp4"
if not INTRO_VIDEO.exists() and (BASE / "intro.mp4").exists():
    INTRO_VIDEO = BASE / "intro.mp4"

INTRO_VIDEO_DURATION = 179
INTRO_VIDEO_WIDTH = 568
INTRO_VIDEO_HEIGHT = 320
TESTIMONIAL_DIR = BASE / "media" / "testimonials"

PAY_VOICE_NOTES = {
    "am": BASE / "media" / "pay_voice_am.ogg",
    "om": BASE / "media" / "pay_voice_om.ogg",
    "en": BASE / "media" / "pay_voice_en.ogg",
}

COACH_DAYS = (3, 7, 15, 30)
TESTIMONIALS = {"am": [], "om": [], "en": []}
RECEIVER_NAMES = ["Fasika"]
REMINDER_MINUTES = 10
NAG_MINUTES = 15
BACKGROUND_INTERVAL = 60
MAX_PENDING_PER_USER = 3
DUP_MAX_BLOCKS = 6
