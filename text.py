"""የቦቱ መልዕክቶች በሶስት ቋንቋ። ጽሑፉን እዚህ መቀየር ይቻላል።"""

CHOOSE_LANG = "🌐 ቋንቋ ይምረጡ / Afaan filadhu / Choose your language"

T = {
    "am": {
        "btn_back": "⬅️ Back",
        "welcome": "ሰላም {name} 👋 እንኳን ወደ {brand} ቦት በደህና መጡ!\n\n🧾 ለእርስዎ የሚስማማውን ፕሮግራም ለማቅረብ ጥቂት ጥያቄዎችን እንጠይቅዎታለን። 👇 ዝግጁ ሲሆኑ «ጥያቄውን ጀምር» ይጫኑ።",
        "btn_begin": "▶️ ጥያቄውን ጀምር",
        "loading_1": "⌛ መረጃዎን በማዘጋጀት ላይ...\n☕ እባክዎ ጥቂት ሰከንዶች ይጠብቁ...\n██▒▒▒▒▒▒▒▒ 10%",
        "loading_2": "⌛ መረጃዎን በማዘጋጀት ላይ...\n☕ እባክዎ ጥቂት ሰከንዶች ይጠብቁ...\n███████▒▒▒ 70%",
        "loading_3": "✅ መረጃዎ ተዘጋጅቷል!\n██████████ 100%",
        "result": """┏━━━━━━━━━━━━━━━━━━━┓
   📊 𝗥𝗘𝗦𝗨𝗟𝗧
┗━━━━━━━━━━━━━━━━━━━┛

• {height}
• {age}
• {gender}

🟢 ሁኔታ፦ እጅግ ጠቃሚ!

🧬 አስደናቂ ዜና!
የእርስዎ የዕድገት ሆርሞን (HGH) ሙሉ በሙሉ ንቁ በሆነ ደረጃ ላይ ይገኛል።

📈 የኛን ሳይንሳዊ ፕሮግራም ተጠቅመው ያለ ምንም ጥርጥር
እስከ 10 CM የሚደርስ የቁመት መጨመር ይችላሉ!

━━━━━━━━━━━━━━━━━━━━
👇 ለመቀጠል ከታች ይጫኑ።""",
        "proof_header": "🔥 REAL RESULTS\nየተጠቃሚዎች የእድገት ውጤት",
        "decide_text": "ሲወስኑ ከታች ይጫኑ 👇",
        "btn_video": "⚡️ ቁመትን መጨመር እፈልጋለሁ!",
        "video_intro": "🎥 ይህን ቪዲዮ እስኪጨርሱ ይመልከቱ 👆\n\n⚠️ ለውጥ የሚያመጡት ትዕግስት ያላቸው ሰዎች ናቸው።",
        "btn_watched": "🎥 ቪዲዮውን እስክጨርስ አይቼዋለሁ",
        "proof_text": """━━━━━━━━━━━━━━━━━━━━

🔥 𝗥𝗘𝗔𝗟 𝗥𝗘𝗦𝗨𝗟𝗧𝗦
የተጠቃሚዎች ምስክርነት፦

────────────────────
✦ Leul — በ3 ወር ውስጥ
   168CM ➜ 176CM (+8CM) 🚀
   ❝እስካሁን ድረስ ማመን ከብዶኛል፣በ3 ወር ውስጥ 8CM ጨምሬአለሁ!❞

✦ Amanuel — በ7 ወር ውስጥ
   ከ171CM ➜ 182CM (+11CM) 🚀
   ❝ ለእኔ ትልቅ ውለታ ነው የዋልክልኝ 😍!❞

✦ Abenezer— በ3 ወር ውስጥ
   5CM 🚀
   ❝ይህ Program በራስ መተማመኔን ጨምሮታል!❞

✦ Tsion — በ2 ወር ውስጥ
   148CM ➜ 154CM (+6CM) 🚀
   ❝በጣም ነው የማመሰግነው፣ ለውጡ ያስደንቃል!❞

━━━━━━━━━━━━━━━━━━━━
💡 እነዚህ ከብዙዎቹ ስኬታማ የጥቂቶቹ ምስክርነት ብቻ ናቸው!

ሲወስኑ ከታች ይጫኑ 👇""",
        "btn_decided": "💪 ወስኛለሁ",
        "ask_age": "🎂 ጥያቄ 2፦ የትኛው የእድሜ ክልል ውስጥ ነዎት?",
        "ages": ["🧒 ከ13 በታች", "🧑 13–17", "🧑‍🎓 18–24", "🧔 25 እና ከዚያ በላይ"],
        "ask_gender": "🚻 ጥያቄ 3፦ ፆታዎ ምንድነው?",
        "genders": ["👨 ወንድ", "👩 ሴት"],
        "ask_height": "📏 ጥያቄ 1፦ አሁን ያሉበት ቁመት ስንት ነው?",
        "heights": ["📏 ከ150 ሴ.ሜ በታች", "📏 150–159 ሴ.ሜ", "📏 160–169 ሴ.ሜ", "📏 170–179 ሴ.ሜ", "📏 180 ሴ.ሜ እና ከዚያ በላይ"],
        "testimonials": "የደንበኞች ምስክርነት",
        "btn_books": "📕 መፅሀፍ ብቻ ({price} ብር)",
        "btn_bundle": "👑 መፅሐፍ + ቪዲዮ ({price} ብር)",
        "pay": """💰 የመረጡት ጥቅል ዋጋ፦ {price} ብር

┏━━━━━━━━━━━━━━━━━━━┓
   🏦 የክፍያ አማራጮች
┗━━━━━━━━━━━━━━━━━━━┛

🔹 𝗖𝗕𝗘 (ንግድ ባንክ)፦ 1000658433605
🔹 𝗧𝗲𝗹𝗲𝗯𝗶𝗿𝗿፦ 0967507969
🔹 ABYSSINIA:- 149004718

👤 የተቀባይ ስም፦ FASIKA BEKELE

━━━━━━━━━━━━━━━━━━━━

📌 ቀጣይ እርምጃ፦
1. ከታች ያሉትን አዝራሮች በመንካት የባንክ ቁጥሩን ወይም የ USSD ኮዱን ኮፒ ያድርጉ።
2. ክፍያውን ከፈፀሙ በኋላ የክፍያ ማረጋገጫውን ፎቶ (Screenshot) እዚሁ ይላኩ። 👇

⏱ ከ 1-3 ደቂቃ ውስጥ ክፍያዎ ተረጋግጦ ሙሉ ፕሮግራሙ እዚሁ ይደርሶታል! 👇""",
        "faq_time_btn": "❓ በስንት ደቂቃ ይደርሰኛል?",
        "faq_time_ans": "⏱ የደረሰኝ ፎቶ እንደላኩ ከ 1 እስከ 3 ደቂቃ ውስጥ ክፍያዎ ተረጋግጦ ወዲያውኑ መጽሐፎቹ እና የቻናሉ ሊንክ እዚሁ ይደርስዎታል!",
        "faq_other_btn": "❓ በሌላ ሰው ስልክ/ባንክ መክፈል ይቻላል?",
        "faq_other_ans": "✅ አዎ ይቻላል! በማንኛውም ሰው ስልክ፣ ቴሌብር ወይም ባንክ ወኪል ከፍለው የደረሰኙን ፎቶ (ወይም የደረሰውን SMS ስክሪንሾት) እዚህ መላክ ይችላሉ።",
        "ussd_telebirr_btn": "📲 የቴሌብር USSD (*127#) ቅዳ",
        "ussd_cbe_btn": "🏦 የ CBE USSD (*889#) ቅዳ",
        "voice_caption": "🎧 እንዴት በቀላሉ እንደሚከፍሉና መጽሐፉን ወዲያውኑ እንደሚያገኙ ይህን አጭር ድምጽ ያዳምጡ።",
        "received": "✅ ደረሰኝዎ ደርሶናል። ከተረጋገጠ በኋላ ያዘዙትን ጥቅል በቅርቡ እንልክልዎታለን።",
        "approved": "✅ ክፍያዎ ተረጋግጧል! ያዘዙትን ጥቅል በቅርቡ እንልክልዎታለን።",
        "approved_link": "✅ ክፍያዎ ተረጋግጧል! 🎉\n\nያዘዙትን ጥቅል ለማግኘት ከታች ያለውን አዝራር ይንኩ፣ ከዚያ «Request to Join» ይጫኑ — ወዲያው ይቀበሉዎታል።\n\n⏰ ሊንኩ ለ{hours} ሰዓት ብቻ የሚሰራ እና ለእርስዎ ብቻ የተፈጠረ ነው፤ ለሌላ ሰው አያጋሩ።",
        "inbot_delivered": "📦 እንኳን ደስ አለዎት! ያዘዙት ጥቅል ፋይሎች ከላይ በቀጥታ ተልከውልዎታል 👆",
        "btn_join": "📚 ወደ ቻናሉ ግባ",
        "joined": "🎉 እንኳን ደህና መጡ! ጥቅልዎ በቻናሉ ውስጥ ይገኛል።",
        "rejected": "ይቅርታ፣ ክፍያዎን ማረጋገጥ አልቻልንም። ትክክለኛውን ደረሰኝ ለመላክ /start ይጫኑ።",
        "qreply_wait": "⏳ ሰላም! ደረሰኝዎ ደርሶናል፣ በአሁኑ ሰዓት እያረጋገጥን ስለሆነ እባክዎ ጥቂት ደቂቃዎች ይጠብቁን። 🙏",
        "qreply_blur": "🔍 ሰላም! የላኩት የደረሰኝ ፎቶ በደንብ አይነበብም (ደብዝዟል ወይም ተቆርጧል)። እባክዎ የክፍያው መጠን እና ቀን በግልጽ የሚታይበትን ሙሉ ስክሪንሾት እንደገና ይላኩ። 👇",
        "qreply_less": "💰 ሰላም! የላኩት የገንዘብ መጠን ከመረጡት ጥቅል ዋጋ ያነሰ ነው። እባክዎ ቀሪውን የገንዘብ መጠን አሟልተው የደረሰኙን ፎቶ እዚሁ ይላኩ። 👇",
        "need_photo": "እባክዎ የደረሰኙን ስክሪንሾት እንደ ፎቶ ይላኩ።",
        "hint": "ለመጀመር /start ይጫኑ።",
        "help_busy": "⏳ በአጭር ጊዜ ብዙ መልዕክት ልከዋል፤ እባክዎ ጥቂት ደቂቃ ይጠብቁ።",
        "reply_prefix": "💬 መልስ፦",
        "dup_receipt": "⚠️ ይህ ደረሰኝ ከዚህ በፊት ተልኳል። እባክዎ የራስዎን የክፍያ ደረሰኝ ስክሪንሾት ይላኩ።",
        "reminder": "👋 ክፍያዎን ገና አላጠናቀቁም። ክፍያ ፈጽመው የደረሰኙን ፎቶ እዚሁ ይላኩ።",
        "followup_1": """👋 ሰላም {name}፣ ቅድም የጀመሩትን የቁመት ማሳደጊያ ፕሮግራም አቋርጠው ወጥተዋል!

ዛሬም በነበሩበት ቁመት መቅረት ይፈልጋሉ? 🤔 ልብ ይበሉ፣ ዛሬ የሚወስኑት አንድ ትንሽ ውሳኔ በጥቂት ወራት ውስጥ እስከ 10 ሴ.ሜ ተጨማሪ ቁመትና አዲስ በራስ መተማመን ይሰጥዎታል። ነገ "ምነው በጀመርኩት" ከማለት ዛሬውኑ እርምጃ ይውሰዱ!

👇 ያቋረጡትን ለመጨረስ አሁኑኑ ይጫኑ፦
👉 /start""",
        "followup_2": """🔥 ሰላም {name}፣ አንድ እውነት ላስታውስዎት...

እርስዎ ማመንታት ውስጥ እያሉ፣ ትላንትና እንደ እርስዎ ወደ ቦቱ የገቡ በመቶዎች የሚቆጠሩ ወጣቶች ፕሮግራሙን ጀምረው የመጀመሪያ እርምጃቸውን እየወሰዱ ነው! ጊዜ እየሄደ ነው፤ የሰውነትዎ የዕድገት እድል ሳይዘጋ አሁኑኑ ይጠቀሙበት።

👇 የጀመሩትን ጥያቄ ጨርሰው ዛሬውኑ ይቀላቀሉን፦
👉 /start""",
        "followup_3": """⏳ የመጨረሻ ማሳሰቢያ ለ {name}!

"ነገ እጀምራለሁ" የሚለው ቃል የብዙ ሰዎችን ህልም አስቀርቷል። ከ3 ወር በኋላ መስታወት ፊት ቆመው ቁመትዎ ጨምሮ ማየት ይፈልጋሉ ወይስ አሁን ባሉበት መቀጠል? ምርጫው በእጅዎ ነው! ይህ የመጨረሻው የማስታወሻ መልዕክት ነው።

👇 ለለውጥ ዝግጁ ከሆኑ አሁኑኑ ይጀምሩ፦
👉 /start""",
    },
    "om": {
        "btn_back": "⬅️ Duubatti",
        "welcome": "Akkam {name} 👋 Baga gara bootii {brand} nagaan dhuftan!\n\n🧾 Sagantaa isin mijaa'u isiniif dhiyeessuuf gaaffilee muraasa isin gaafanna. 👇 Yeroo qophaa'an «Gaaffii jalqabi» tuqaa.",
        "btn_begin": "▶️ Gaaffii jalqabi",
        "loading_1": "⌛ Odeeffannoo keessan qopheessaa jirra...\n☕ Maaloo xiqqoo obsaa...\n██▒▒▒▒▒▒▒▒ 10%",
        "loading_2": "⌛ Odeeffannoo keessan qopheessaa jirra...\n☕ Maaloo xiqqoo obsaa...\n███████▒▒▒ 70%",
        "loading_3": "✅ Odeeffannoon keessan qophaa'eera!\n██████████ 100%",
        "result": """┏━━━━━━━━━━━━━━━━━━━┓
   📊 𝗥𝗘𝗦𝗨𝗟𝗧
┗━━━━━━━━━━━━━━━━━━━┛

• {height}
• {age}
• {gender}

🟢 Haala: Baay'ee fayyadaa!

🧬 Oduu gammachiisaa!
Hormooniin guddina keessanii (HGH) sadarkaa guutummatti hojjetu irra jira.

📈 Porogiraamii keenya saayinsawaa fayyadamuun qulqullinaan
hanga 10 CM dheerina dabaluu dandeessu!

━━━━━━━━━━━━━━━━━━━━
👇 Itti fufuuf armaan gadii tuqaa.""",
        "proof_header": "🔥 REAL RESULTS\nRagaa fayyadamtootaa:",
        "decide_text": "Yeroo murteessan armaan gadii tuqaa 👇",
        "btn_video": "⚡ Dheerina koo dabaluu barbaada",
        "video_intro": "🎥 Viidiyoon kun hanga xumuramutti ilaalaa 👆\n\n⚠️ Jijjiirama fidan namoota obsa qabaniidha.",
        "btn_watched": "🎥 Hanga xumuruttin ilaaleera",
        "proof_text": """━━━━━━━━━━━━━━━━━━━━

🔥 𝗥𝗘𝗔𝗟 𝗥𝗘𝗦𝗨𝗟𝗧 𝗦
Ragaa fayyadamtootaa:

────────────────────
✦ Leul — Ji'a 3 keessatti
   168CM ➜ 176CM (+8CM) 🚀
   ❝Hanga ammaatti amanuun natti ulfaata, ji'a 3 keessatti 8CMn dabale!❞

✦ Amanuel — Ji'a 7 keessatti
   171CM ➜ 182CM (+11CM) 🚀
   ❝Goota guddaa naaf taatan 😍!❞

✦ Abenezer — Ji'a 3 keessatti
   5CM 🚀
   ❝Porogiraamiin kun ofitti amanamummaa koo naaf dabaleera!❞

✦ Tsion — Ji'a 2 keessatti
   148CM ➜ 154CM (+6CM) 🚀
   ❝Baay'een galateeffadha, jijjiiramni isaa dinqisiisaadha!❞

━━━━━━━━━━━━━━━━━━━━
💡 Kunneen ragaa milkaa'ina maamiltoota dhiyeenyaa muraasa qofa!

Yeroo murteessan armaan gadii tuqaa 👇""",
        "btn_decided": "💪 Murteesseera",
        "ask_age": "🎂 Gaaffii 2: Umuriin kee kutaa kam keessa jira?",
        "ages": ["🧒 Waggaa 13 gadi", "🧑 13–17", "🧑‍🎓 18–24", "🧔 25 fi isaa ol"],
        "ask_gender": "🚻 Gaaffii 3: Saalli kee maali?",
        "genders": ["👨 Dhiira", "👩 Dubartii"],
        "ask_height": "📏 Gaaffii 1: Dheerinni kee amma meeqa?",
        "heights": ["📏 150 cm gadi", "📏 150–159 cm", "📏 160–169 cm", "📏 170–179 cm", "📏 180 cm fi isaa ol"],
        "testimonials": "Ragaa maamiltootaa",
        "btn_books": "📕 Kitaaba qofa — {price} Birr",
        "btn_bundle": "👑 Kitaaba + viidiyoo — {price} Birr",
        "pay": """💰 Gatiin paakeejii filattan: Birr {price}

┏━━━━━━━━━━━━━━━━━━━┓
   🏦 Filannoo Kaffaltii
┗━━━━━━━━━━━━━━━━━━━┛

🔹 CBE: 1000658433605
🔹 Telebirr: 0967507969
🔹 Abyssinia: 149004718

👤 Maqaa Simataa: FASIKA BEKELE

━━━━━━━━━━━━━━━━━━━━

📌 Tarkaanfii Itti Aanu:
1. Qabduuwwan armaan gadii tuquun lakkoofsa baankii ykn koodii USSD garagalchadhaa (Copy).
2. Kaffaltii erga raawwattanii booda suuraa (screenshot) ragaa kaffaltii amma as ergaa. 👇

⏱ Daqiiqaa 1-3 keessatti kaffaltiin keessan mirkanaa'ee sagantaan guutuun asuma siif ergama! 👇""",
        "faq_time_btn": "❓ Daqiiqaa meeqa keessatti na ga'a?",
        "faq_time_ans": "⏱ Suuraa ragaa kaffaltii akkuma ergitaniin daqiiqaa 1 hanga 3 keessatti mirkanaa'ee kitaabonni fi liinkiin chaanaalii battalumatti asuma isiniif ergama!",
        "faq_other_btn": "❓ Bilbila/Baankii nama biraatiin kaffaluun ni danda'amaa?",
        "faq_other_ans": "✅ Eeyyee ni danda'ama! Bilbila, Telebirr ykn baankii nama kamiyyuu fayyadamuun kaffaltanii suuraa ragaa kaffaltii (screenshot) asitti erguu dandeessu.",
        "ussd_telebirr_btn": "📲 USSD Telebirr (*127#) Copy",
        "ussd_cbe_btn": "🏦 USSD CBE (*889#) Copy",
        "voice_caption": "🎧 Akkaataa salphaatti itti kaffaltanii fi kitaabicha battalumatti argattan sagalee gabaabaa kana dhaggeeffadhaa.",
        "received": "✅ Ragaan kee nu ga'e. Erga mirkanaa'ee booda paakeejii ajajattan dhiyeenyatti si ergina.",
        "approved": "✅ Kaffaltiin kee mirkanaa'eera! Paakeejii ajajattan dhiyeenyatti si ergina.",
        "approved_link": "✅ Kaffaltiin kee mirkanaa'eera! 🎉\n\nPaakeejii ajajattan argachuuf qabduu armaan gadii tuqaa, ergasii «Request to Join» tuqaa — battalumatti ni simatamta.\n\n⏰ Linkiin kun sa'aatii {hours} qofaaf hojjeta; kan siif qofa qophaa'e waan ta'eef nama biraatti hin qooduun.",
        "inbot_delivered": "📦 Baga gammaddan! Faayiloonni paakeejii ajajattan kallattiin armaan olitti isiniif ergamaniiru 👆",
        "btn_join": "📚 Channel seeni",
        "joined": "🎉 Baga nagaan dhufte! Paakeejiin kee channel keessatti argama.",
        "rejected": "Dhiifama, kaffaltii kee mirkaneessuu hin dandeenye. Ragaa sirrii ergachuuf /start tuqi.",
        "qreply_wait": "⏳ Akkam! Ragaan kaffaltii keessan nu ga'eera, amma mirkaneessaa waan jirruuf maaloo daqiiqaa muraasa nu eegaa. 🙏",
        "qreply_blur": "🔍 Akkam! Suuraan ragaa kaffaltii ergitan sirriitti hin dubbifamu. Maaloo suuraa (screenshot) gatiin kaffaltii fi guyyaan irratti sirriitti mul'atu irra deebi'aa ergaa. 👇",
        "qreply_less": "💰 Akkam! Hangi maallaqaa ergitan gatii paakeejii filattanii gadi. Maaloo maallaqa hafe guuttanii suuraa ragaa kaffaltii asuma ergaa. 👇",
        "need_photo": "Maaloo suuraa (screenshot) ragaa kaffaltii akka suuraatti ergi.",
        "hint": "Jalqabuuf /start tuqi.",
        "help_busy": "⏳ Yeroo gabaabaa keessatti ergaa baayyee ergitaniirtu; maaloo daqiiqaa muraasa obsaa.",
        "reply_prefix": "💬 Deebii:",
        "dup_receipt": "⚠️ Ragaan kaffaltii kun duraan ergameera. Maaloo suuraa (screenshot) ragaa kaffaltii keessanii dhugaa ta'e ergaa.",
        "reminder": "👋 Kaffaltii keessan hin xumuranne. Kaffaltii raawwatanii suuraa ragaa kaffaltii asuma ergaa.",
        "followup_1": """👋 Akkam {name}, sagantaa guddina dheerinaa jalqabdan addaan kuttanii baatan!

Har'as gabaabaa ta'anii hafuu barbaadduu? 🤔 Murtoon xiqqoon har'a murteessitan ji'oota muraasa keessatti dheerina dabalataa hanga 10 CM fi ofitti amanamummaa haaraa isiniif kenna. Boru gaabbuurra har'uma tarkaanfii fudhadhaa!

👇 Kan jalqabdan xumuruuf amma tuqaa:
👉 /start""",
        "followup_2": """🔥 Akkam {name}, dhugaa tokko isin yaadachiisu...

Utuu isin mamii keessa jirtanii, dargaggoonni dhibbaan lakkaa'aman kaleessa akka keessan gara bootii seenan saganticha jalqabanii tarkaanfii jalqabaa fudhachaa jiru! Yeroon darbaa jira; carraa guddina qaama keessanii utuu hin cufamin amma itti fayyadamaa.

👇 Gaaffii jalqabdan xumuraatii har'uma nutti makamaa:
👉 /start""",
        "followup_3": """⏳ Yaadachiisa dhumaa {name}f!

Jechi "Borun jalqaba" jedhu abjuu namoota hedduu hambiseera. Ji'a 3 booda daawwitii dura dhaabbattanii dheerinni keessan dabalee arguu barbaaddu moo akkuma amma jirtanitti itti fufuu? Filannoon harka keessan jira! Kun ergaa yaadachiisaa isa dhumaati.

👇 Jijjiiramaaf qophaa'oo yoo taatan amma jalqabaa:
👉 /start""",
    },
    "en": {
        "btn_back": "⬅️ Back",
        "welcome": "Hello {name} 👋 Welcome to the {brand} bot!\n\n🧾 We will ask you a few short questions so we can offer the program that suits you. 👇 Press “Start questions” when you are ready.",
        "btn_begin": "▶️ Start questions",
        "loading_1": "⌛ Preparing your details...\n☕ Please wait a few seconds...\n██▒▒▒▒▒▒▒▒ 10%",
        "loading_2": "⌛ Preparing your details...\n☕ Please wait a few seconds...\n███████▒▒▒ 70%",
        "loading_3": "✅ Your details are ready!\n██████████ 100%",
        "result": """┏━━━━━━━━━━━━━━━━━━━┓
   📊 𝗥𝗘𝗦𝗨𝗟𝗧
┗━━━━━━━━━━━━━━━━━━━┛

• {height}
• {age}
• {gender}

🟢 Status: Highly Favorable!

🧬 Amazing News!
Your Human Growth Hormone (HGH) is fully active.

📈 By following our scientific program, you can undoubtedly
increase your height by up to 10 CM!

━━━━━━━━━━━━━━━━━━━━
👇 Press below to continue.""",
        "proof_header": "🔥 REAL RESULTS\nUser testimonials:",
        "decide_text": "Press below when you have decided 👇",
        "btn_video": "⚡ I want to increase my height",
        "video_intro": "🎥 Watch this video until the end 👆\n\n⚠️ Those who make a change are the patient ones.",
        "btn_watched": "🎥 I watched it to the end",
        "proof_text": """━━━━━━━━━━━━━━━━━━━━

🔥 𝗥𝗘𝗔𝗟 𝗥𝗘𝗦𝗨𝗟𝗧 𝗦
User Testimonials:

────────────────────
✦ Leul — In 3 months
   168CM ➜ 176CM (+8CM) 🚀
   ❝I still can't believe it, I gained 8CM in 3 months!❞

✦ Amanuel — In 7 months
   171CM ➜ 182CM (+11CM) 🚀
   ❝You did a huge favor for me 😍!❞

✦ Abenezer — In 3 months
   5CM 🚀
   ❝This program boosted my confidence!❞

✦ Tsion — In 2 months
   148CM ➜ 154CM (+6CM) 🚀
   ❝Thank you so much, the result is amazing!❞

━━━━━━━━━━━━━━━━━━━━
💡 These are just a few testimonials among many success stories!

Press below when you have decided 👇""",
        "btn_decided": "💪 I have decided",
        "ask_age": "🎂 Question 2: Which age range are you in?",
        "ages": ["🧒 Under 13", "🧑 13–17", "🧑‍🎓 18–24", "🧔 25 and above"],
        "ask_gender": "🚻 Question 3: What is your gender?",
        "genders": ["👨 Male", "👩 Female"],
        "ask_height": "📏 Question 1: What is your current height?",
        "heights": ["📏 Under 150 cm", "📏 150–159 cm", "📏 160–169 cm", "📏 170–179 cm", "📏 180 cm and above"],
        "testimonials": "Customer testimonials",
        "btn_books": "📕 Book only — {price} ETB",
        "btn_bundle": "👑 Book + video — {price} ETB",
        "pay": """💰 Price of your package: {price} ETB

┏━━━━━━━━━━━━━━━━━━━┓
   🏦 Payment Options
┗━━━━━━━━━━━━━━━━━━━┛

🔹 CBE: 1000658433605
🔹 Telebirr: 0967507969
🔹 Abyssinia: 149004718

👤 Account Name: FASIKA BEKELE

━━━━━━━━━━━━━━━━━━━━

📌 Next Step:
1. Tap the buttons below to copy the account number or USSD code.
2. After making the payment, send the screenshot or photo of the receipt right here. 👇

⏱ Your payment will be verified within 1-3 minutes and the full program will be delivered right here! 👇""",
        "faq_time_btn": "❓ How fast will I receive it?",
        "faq_time_ans": "⏱ Once you send the receipt photo, your payment is verified within 1-3 minutes and the books + channel link are delivered right here!",
        "faq_other_btn": "❓ Can I pay using someone else's phone/bank?",
        "faq_other_ans": "✅ Yes! You can pay from anyone's phone, Telebirr, or bank account and simply send the screenshot or photo of the receipt right here.",
        "ussd_telebirr_btn": "📲 Copy Telebirr USSD (*127#)",
        "ussd_cbe_btn": "🏦 Copy CBE USSD (*889#)",
        "voice_caption": "🎧 Listen to this short audio guide on how to easily complete your payment and receive your package immediately.",
        "received": "✅ We received your receipt. Once it is verified we will send your package shortly.",
        "approved": "✅ Your payment is confirmed! We will send your package shortly.",
        "approved_link": "✅ Your payment is confirmed! 🎉\n\nTap the button below, then press “Request to Join” — you will be accepted instantly.\n\n⏰ This link works for {hours} hours and was created for you only; please don't share it.",
        "inbot_delivered": "📦 Congratulations! Your package files have been delivered directly above 👆",
        "btn_join": "📚 Join the channel",
        "joined": "🎉 Welcome! Your package is in the channel.",
        "rejected": "Sorry, we could not verify your payment. Press /start to send a valid receipt.",
        "qreply_wait": "⏳ Hello! We have received your receipt and are verifying it right now. Please wait a few minutes. 🙏",
        "qreply_blur": "🔍 Hello! The receipt photo you sent is not clear. Please send a full, clear screenshot showing the amount and date. 👇",
        "qreply_less": "💰 Hello! The amount on the receipt is less than the package price. Please complete the remaining balance and send the receipt photo here. 👇",
        "need_photo": "Please send the receipt screenshot as a photo.",
        "hint": "Press /start to begin.",
        "help_busy": "⏳ You sent many messages in a short time; please wait a few minutes.",
        "reply_prefix": "💬 Reply:",
        "dup_receipt": "⚠️ This receipt was already submitted. Please send the screenshot of your own payment receipt.",
        "reminder": "👋 You have not finished your payment yet. Once you have paid, send the receipt photo right here.",
        "followup_1": """👋 Hello {name}, you left the height growth program before finishing!

Do you still want to stay at your current height? 🤔 Remember, one small decision today can give you up to 10 CM of extra height and new confidence within a few months. Take action today instead of regretting it tomorrow!

👇 Tap below to finish what you started:
👉 /start""",
        "followup_2": """🔥 Hello {name}, let me remind you of one truth...

While you are hesitating, hundreds of young people who entered this bot yesterday just like you have already started the program and are taking their first steps! Time is ticking; use your body's growth potential before it closes.

👇 Finish the questions you started and join us today:
👉 /start""",
        "followup_3": """⏳ Final reminder for {name}!

The phrase "I'll start tomorrow" has killed the dreams of many people. Three months from now, do you want to stand in front of the mirror and see yourself taller, or stay just as you are now? The choice is in your hands! This is the final reminder.

👇 If you are ready for a change, start right now:
👉 /start""",
    },
}

AGE_CODES = ["a1", "a2", "a3", "a4"]
GENDER_CODES = ["m", "f"]
HEIGHT_CODES = ["h1", "h2", "h3", "h4", "h5"]
