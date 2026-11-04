# የመጽሐፍ መሸጫ ቴሌግራም ቦት — Ethio Length

## ቦቱ እንዴት ይሰራል
1. ደንበኛው ቋንቋ ይመርጣል (አማርኛ / Afaan Oromoo / English)
2. እንኳን ደህና መጡ → «ጥያቄውን ጀምር»
3. ጥያቄ 1 ቁመት፣ 2 እድሜ፣ 3 ፆታ (በአዝራሮች)
4. RESULT (የመለሰው መረጃ ተዘርዝሮ ይታያል) → «ቁመትን መጨመር እፈልጋለሁ»
5. ቪዲዮ → «ቪዲዮውን እስክጨርስ አይቼዋለሁ»
6. የደንበኞች ምስክርነት (እውነተኛ ሲኖር) → «ወስኛለሁ»
7. ጥቅሎች (397 / 597 ብር) ከማብራሪያ ጋር (የባንክ አካውንት እዚህ አይታይም)
8. ጥቅል ሲመርጥ ክፍያ ማያ ይመጣል፤ የባንክ አካውንቶች እዚህ ይታያሉ፣ እያንዳንዱ በ «📋» አዝራር ሲነካ ቁጥሩ ይቀዳል → የደረሰኝ ፎቶ ብቻ ይልካል (የግብይት ቁጥር አይጠየቅም) → ወዲያው ለአድሚኑ ይደርሳል። ፎቶ ሳይልክ ከ10 ደቂቃ በኋላ አንድ ጊዜ ይታወሳል
9. ደረሰኙ ወደ እርስዎ ይደርሳል (የተመረጠው ጥቅል በመግለጫው ላይ ይታያል) → **✅ አረጋግጥ** ሲጫኑ ቦቱ በገዛው ጥቅል መሰረት (መጽሐፍ ብቻ ወይም መጽሐፍ + ቪዲዮ) ከሁለቱ private ቻናሎች ለዚያ ደንበኛ ብቻ የሚሰራ የመቀላቀል ሊንክ ይልክለታል። ደንበኛው ሊንኩን ነክቶ «Request to Join» ሲል ቦቱ የከፈለው ሰው መሆኑን አይቶ ወዲያው ያጸድቃል (ሌላ ሰው ሊንኩን ቢጠቀም ውድቅ ይሆናል፤ ለእርስዎም ይነገርዎታል)። ሊንኩ ከ`INVITE_HOURS` (24) ሰዓት በኋላ ያልፋል፣ ከተቀላቀለም በኋላ ይሰረዛል። ሊንክ ባይፈጠር ለእርስዎ ማሳወቂያ ይመጣል፤ ጥቅሉን በእጅዎ ይላኩ ወይም `/resend <ትዕዛዝ ቁጥር>` ይጠቀሙ
10. ተመሳሳይ የደረሰኝ ስክሪንሾት ድጋሚ ከተላከ (ውድቅ የተደረገውንም ጨምሮ፤ የተጨመቀ፣ የተቀነሰ ወይም ሰዓቱ ብቻ የተለየ ቅጂም) በራስ ውድቅ ይሆናል። ትክክለኛ ደንበኛ ከታገደ ደረሰኙን በ Reply አይተው ያነጋግሩት

በሁሉም ማያ ላይ «Back» አለ። ጽሑፍ ብቻ ያላቸው ማያዎች ያው መልዕክት በቦታው ይቀየራል (ፈጣን)።

## Railway ላይ የሚሞሉ Variables
| Variable | እሴት |
|---|---|
| `BOT_TOKEN` | ከ @BotFather ያገኙት token |
| `ADMIN_ID` | የእርስዎ ቴሌግራም ID (ከ @userinfobot) |
| `DB_PATH` | `/data/bot.db` (Railway ላይ Volume ጨምረው Mount path `/data` ያድርጉ) |
| `BOOKS_CHANNEL_ID` | «መጽሐፍ ብቻ» private ቻናል ID (`-100…`) |
| `BUNDLE_CHANNEL_ID` | «መጽሐፍ + ቪዲዮ» private ቻናል ID (`-100…`) |
| `INVITE_HOURS` | (አማራጭ) የሊንኩ ቆይታ በሰዓት፤ ነባሪ 24 |

`.env` ፋይልን ወደ GitHub አይጫኑ።

## Private ቻናሎችን ማዘጋጀት (አንድ ጊዜ)
1. ሁለት **private** ቻናሎች ይፍጠሩ፦ አንዱ ለ«መጽሐፍ ብቻ»፣ ሌላው ለ«መጽሐፍ + ቪዲዮ»። መጽሐፎቹን (እና ቪዲዮውን በ `ffmpeg -movflags +faststart` አዘጋጅተው) እዚያ ይጫኑ።
2. በእያንዳንዱ ቻናል Settings → Administrators → ቦቱን አድሚን ያድርጉ፤ **«Invite Users via Link»** መብት ይኑረው።
3. በእያንዳንዱ ቻናል Settings → **Restrict Saving Content** ያብሩ (ማስተላለፍና ማስቀመጥ ይከላከላል፤ ስክሪን መቅዳትን ግን አይከለክልም)።
4. የቻናሉን ID ለማግኘት ከቻናሉ አንድ መልዕክት ወደ @userinfobot ያስተላልፉ (`-100…` የሚል ቁጥር ነው) እና ከላይ ባለው Variables ሰንጠረዥ ይሙሉ።
5. ቦቱ ሲነሳ ቻናሎቹ ከተሞሉ እና ቦቱ አድሚን ካልሆነ ለእርስዎ ማስጠንቀቂያ ይልካል።

## በ GitHub ውስጥ መኖር ያለባቸው ፋይሎች
- `bot.py`፣ `ocr.py`፣ `texts.py`፣ `config.py`፣ `Procfile`፣ `requirements.txt`፣ `.python-version`፣ `.gitignore`
- `railpack.json` (Railway አዲሱ ገንቢ) እና `nixpacks.toml` (አሮጌ ገንቢ ከተመረጠ)፤ Railway ከሁለቱ አንዱን ብቻ ይጠቀማል
- አማራጭ፦ `media/intro.mp4` (መጀመሪያ የሚታይ ቪዲዮ)፣ `media/testimonials/` (የእውነተኛ ደንበኞች ምስክርነት ፎቶዎች)
- የሚሸጡ መጽሐፎችና ቪዲዮ በ GitHub ላይ አያስፈልጉም፤ በ private ቻናሎቹ ውስጥ ብቻ ናቸው። (የድሮውን `content/` ፎልደር ከ GitHub ማጥፋት ይችላሉ።)

## ማስተካከያ (config.py ብቻ)
- ዋጋ፦ `PRICES`
- የባንክ አካውንት፦ `PAYMENT_ACCOUNTS`
- ቻናሎች እና የሊንክ ቆይታ፦ `CHANNELS`፣ `INVITE_HOURS` (በ Variables በኩል)
- የማስታወቂያ ጽሑፍ፦ `OFFER`
- የጽሑፍ ምስክርነት፦ `TESTIMONIALS` — ከእውነተኛ ደንበኞችዎ በፈቃዳቸው ያገኙትን ብቻ ያስገቡ። ባዶ ከሆነ ምንም አይታይም።

## ትዕዛዞች
- `/start` — ደንበኛው ይጀምራል
- `/stats` (ለእርስዎ ብቻ) — ተጠቃሚዎች፣ በመጠባበቅ ላይ ያሉ እና የተሸጡ ብዛት፤ ከስሩ «👥 የተጠቃሚዎች ዝርዝር» አዝራር አለው
- `/users` (ለእርስዎ ብቻ) — የተጠቃሚዎች ዝርዝር (ስም፣ @username፣ ID፣ የገዙት ጥቅል፣ ቀን)፤ በ ⬅️ ➡️ ገጽ ይገለበጣል
- `/pending` (ለእርስዎ ብቻ) — ያልተረጋገጡ ደረሰኞችን እንደገና ይልካል
- `/resend <ትዕዛዝ ቁጥር>` (ለእርስዎ ብቻ) — ለተረጋገጠ ትዕዛዝ አዲስ የቻናል ሊንክ ይልካል (ሊንኩ ካለፈ ወይም ደንበኛው ከቻናሉ ከወጣ)

## ማስታወሻ
- አንድ ቦት በአንድ ጊዜ በአንድ ቦታ ብቻ መስራት አለበት (Railway ላይ replicas = 1)፤ ካልሆነ «Conflict» ስህተት ይመጣል።
- የ Afaan Oromoo ጽሑፎችን አፍ-መፍቻ ተናጋሪ ቢያይልዎ ይሻላል።

---

## አዲስ ባህሪያት

- **የደንበኛ ሂደት በዳታቤዝ ውስጥ ይቀመጣል** — ቦቱ ዳግም ቢጀምር (restart) ደንበኛው ያቆመበት ይቀጥላል። (Railway ላይ Volume `/data` እና `DB_PATH=/data/bot.db` መኖር አለበት።)
- **/pending** (ለእርስዎ ብቻ) — ያልተረጋገጡ ደረሰኞችን ዝርዝር ይልካል። ከ`NAG_MINUTES` በላይ የቆየ ደረሰኝ ካለ አንድ ጊዜ ያሳስብዎታል።
- **OCR መጠን ማረጋገጫ** — በደረሰኝ ፎቶ ላይ መጠኑን እና የተቀባይ ስም ይፈልጋል፤ ውጤቱን በደረሰኙ መግለጫ ላይ ያሳያል (✅/❌)። ይህ ምክር ብቻ ነው — ✅/❌ ን የሚጫኑት እርስዎ ነዎት።
  - tesseract ለመጫን `railpack.json` እና `nixpacks.toml` ተካትተዋል። Railway Logs ላይ «OCR፦ አለ» ካለ ይሰራል። ባይሰራ እንኳ ቦቱ ያለ OCR ይሰራል።
  - አማራጭ፦ Railway Variables ላይ `RAILPACK_DEPLOY_APT_PACKAGES=tesseract-ocr` እና `RAILPACK_BUILD_APT_PACKAGES=tesseract-ocr` ይጨምሩ።
- **አንድ ጊዜ ማስታወሻ** — ክፍያ ማያ ደርሶ ፎቶ ሳይልክ ከ`REMINDER_MINUTES` (10 ደቂቃ) በኋላ ለደንበኛው አንድ ጊዜ ብቻ ይላካል።

### በ config.py ውስጥ የሚቀየሩ
`RECEIVER_NAMES`, `REMINDER_MINUTES`, `NAG_MINUTES`, `BACKGROUND_INTERVAL`, `MAX_PENDING_PER_USER`, `DUP_MAX_BLOCKS`

**ተመሳሳይ ደረሰኝ ፍተሻ (`DUP_MAX_BLOCKS`)**፦ `python dup_test.py ፎልደር` በእውነተኛ ደረሰኞችዎ ይሞክሩ። የተለያዩ ደንበኞች ደረሰኞች '🚫 ይታገዳል' ካሳዩ ቁጥሩን ይቀንሱ። `numpy` በ `requirements.txt` ውስጥ ተጨምሯል።

የባንክ አካውንቱን ከኮድ ውጭ ለማድረግ Railway Variable `PAYMENT_ACCOUNTS` ይሙሉ (አዲስ መስመር በ `\n`)።

### GitHub ላይ ማዘመን
`bot.py, ocr.py, texts.py, config.py, dup_test.py, requirements.txt, railpack.json, nixpacks.toml, Procfile, README.md` ን ይተኩ/ይጨምሩ። `.env` ን አይጫኑ።
