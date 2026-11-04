"""
እዚህ ፋይል ውስጥ ያሉትን እሴቶች ብቻ ይቀይሩ (ዋጋ፣ የባንክ አካውንት፣ የማስታወቂያ ጽሑፍ፣ የመጽሐፍ ፋይሎች)።
ሌላ ፋይል መንካት አያስፈልግም።
"""
from pathlib import Path

BASE = Path(__file__).parent

# የቦቱ ስም (በእንኳን ደህና መጡ መልዕክት ላይ ይታያል)
BOT_NAME = "Ethio Length"

# ዋጋ (በብር)
PRICES = {
    "books": 397,    # ሁለቱም መጽሐፎች (PDF) ብቻ
    "bundle": 597,   # ሁለቱም መጽሐፎች (PDF) + ቪዲዮ
}

# ደንበኛው ክፍያ የሚልክባቸው አካውንቶች
PAYMENT_ACCOUNTS = """\
🏦 CBE: 1000658433605 (Fasika Bekele)
📱 Telebirr: 0967507969 (Fasika Bekele)
🏦 Abyssinia: 149004718 (Fasika Bekele)"""

# ደንበኛው ከ"ወስኛለሁ" በኋላ የሚያየው የማስታወቂያ ጽሑፍ። {price} እና {accounts} በራስ-ሰር ይሞላሉ።
OFFER = {
    "am": """\
ሰላም! 👋 ስለ መጽሐፎቻችን ፍላጎት ስላሳዩ ከልብ እናመሰግናለን! 🙏

ቁመትዎን በተፈጥሯዊ መንገዶች መጨመር ይፈልጋሉ? እነዚህ መጽሐፍት ለእርስዎ የተዘጋጁ ናቸው!

በውስጣቸው ምን ይዘዋል?
🏋️‍♂️ 1. ልምምድ (Exercise): ትክክለኛ ጫና በመፍጠር አጥንትን የማሳደግ ጥበብ።
🥗 2. አመጋገብ (Diet): ኪስ በማይጎዳ መልኩ ለሰውነት ግንባታ የሚረዱ ምግቦች።
😴 3. እረፍት (Rest): እንቅልፍ ለቁመት እድገት የሚጫወተው ቁልፍ ሚና።

የመጽሐፍቱ ዝርዝር፦
📕 "6 foot 6" - 37 ገጾች፣ በ2 ዋና ዋና ምዕራፎች የተከፈለ።
📗 "5 inches" - 69 ገጾች፣ በ14 ምዕራፎች በሰፊው የቀረበ።

📢 መልካም ዜና! መጽሐፎቹ በ English፣ በአማርኛ (Amharic) እና በኦሮምኛ (Afaan Oromoo) ተዘጋጅተው ቀርበዋል! በመረጡት ቋንቋ ያገኛሉ።

💳 ክፍያ እና አረካከብ፦

📘 መጽሐፎች (PDF) ብቻ፦ {price} ብር
📘🎬 መጽሐፎች (PDF) + ቪዲዮ፦ {price_bundle} ብር
(መጽሐፎቹ ዲጂታል /Soft Copy/ ስለሆኑ ክፍያ እንደፈጸሙ በዚሁ በቴሌግራም ይደርስዎታል።)

በሚከተሉት አማራጮች ክፍያውን መፈጸም ይችላሉ፦
{accounts}

📌 ማሳሰቢያ፦ ክፍያውን እንደፈጸሙ የደረሰኙን ፎቶ (Screenshot) እዚሁ ይላኩልን፤ መጽሐፎቹን እንልክልዎታለን! 🚀""",
    "en": """\
Hello! 👋 Thank you for your interest in our books! 🙏

Do you want to increase your height through natural methods? These books are made for you!

What is inside?
🏋️‍♂️ 1. Exercise: the craft of building up bone by applying the right stress.
🥗 2. Diet: affordable foods that support building the body.
😴 3. Rest: the key role sleep plays in height growth.

The books:
📕 "6 foot 6" - 37 pages, divided into 2 main chapters.
📗 "5 inches" - 69 pages, covered in detail across 14 chapters.

📢 Good news! The books are available in English, Amharic and Afaan Oromoo. You get them in the language you chose.

💳 Payment and delivery:

📘 Books (PDF) only: {price} Birr
📘🎬 Books (PDF) + video: {price_bundle} Birr
(The books are digital /soft copy/, so they are delivered right here on Telegram once you have paid.)

You can pay through:
{accounts}

📌 Note: after paying, send the receipt photo (screenshot) right here and we will send you the books! 🚀""",
    "om": """\
Akkam! 👋 Kitaaba keenya irratti hawwii agarsiiftanii baayyee galatoomaa! 🙏

Dheerinni keessan karaa uumamaa ta'een dabaluu barbaaddanii? Kitaabonni kun isiniif qophaa'aniiru!

Keessa isaanii maal qabu?
🏋️‍♂️ 1. Shaakala (Exercise): dhiibbaa sirrii uumuudhaan lafee ijaaruu.
🥗 2. Nyaata (Diet): nyaata baasii hin ulfaanne qaama ijaaruuf gargaaru.
😴 3. Boqonnaa (Rest): hirribni guddina dheerinaaf qabu ga'ee ijoo.

Tarreeffama kitaabotaa:
📕 "6 foot 6" - fuula 37, boqonnaa ijoo 2 tti qoodame.
📗 "5 inches" - fuula 69, boqonnaa 14 keessatti bal'inaan dhiyaate.

📢 Oduu gammachuu! Kitaabonni Afaan Ingiliffaa, Afaan Amaaraa fi Afaan Oromootiin qophaa'aniiru! Afaan filattan keessaan argattu.

💳 Kaffaltii fi dhaqqabiinsa:

📘 Kitaabota (PDF) qofa: Birr {price}
📘🎬 Kitaabota (PDF) + viidiyoo: Birr {price_bundle}
(Kitaabonni dijitaalaa /Soft Copy/ waan ta'aniif erga kaffaltanii Telegram kanaan isiniif ergamu.)

Karaa armaan gadiitiin kaffaluu dandeessu:
{accounts}

📌 Yaadachiisa: Erga kaffaltanii booda suuraa ragaa kaffaltii (Screenshot) as ergaa; kitaabota isiniif ergina! 🚀""",
}

# የመጽሐፍ ፋይሎች በየቋንቋው (ከ book-bot ፎልደር አንጻር)። ደንበኛው በመረጠው ቋንቋ ይላካሉ።
CONTENT = BASE / "content"
BOOKS = {
    "am": [CONTENT / "6foot6_am.pdf", CONTENT / "5inches_am.pdf"],
    "om": [CONTENT / "6foot6_om.pdf", CONTENT / "5inches_om.pdf"],
    "en": [CONTENT / "6foot6_en.pdf", CONTENT / "5inches_en.pdf"],
}

BONUS_VIDEO = CONTENT / "bonus_video.mp4"                 # በ"PDF + ቪዲዮ" ጥቅል የሚላክ ቪዲዮ

INTRO_VIDEO = BASE / "media" / "intro.mp4"                # ደንበኛው የሚያየው አጭር ቪዲዮ (አማራጭ)
TESTIMONIAL_DIR = BASE / "media" / "testimonials"         # የደንበኞች ምስክርነት ፎቶዎች (jpg/png) (አማራጭ)

# የደንበኞች ምስክርነት (ጽሑፍ)። እዚህ የሚያስገቡት ከእውነተኛ ደንበኞችዎ በፈቃዳቸው ያገኙትን ብቻ ይሁን።
# እያንዳንዱ ንጥል አንድ ምስክርነት ነው። ባዶ ከሆነ ምንም አይታይም (ፎቶዎች ብቻ ይላካሉ)።
# ምሳሌ ቅርጽ፦
#   "✦ ስም — በ3 ወር ውስጥ\n  168CM ➜ 176CM (+8CM)\n  “የደንበኛው አስተያየት”"
TESTIMONIALS = {
    "am": [],
    "om": [],
    "en": [],
}
