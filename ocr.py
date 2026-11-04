"""የደረሰኝ ፎቶ ንባብ (OCR) — አማራጭ እና ምክር ብቻ።

tesseract ከሌለ ወይም ከተሳሳተ ቦቱ ያለ እሱ ይሰራል። ውጤቱ ለእርስዎ (አድሚን) እንደ ጠቋሚ ይታያል፤
ክፍያን በራሱ አያረጋግጥም — ሁልጊዜ ደረሰኙን እርስዎ ያያሉ።
"""
import io
import logging
import re
import shutil
import threading
import zlib

log = logging.getLogger("bookbot.ocr")

try:
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = 40_000_000  # ከዚህ በላይ ያለ ምስል (decompression bomb) ውድቅ ይሆናል
except Exception:  # Pillow ካልተጫነ
    Image = ImageOps = None
    log.warning("Pillow አልተጫነም")

try:
    import numpy as np
except Exception:  # numpy ካልተጫነ ትክክለኛ ቅጂ ብቻ ይታገዳል
    np = None
    log.warning("numpy አልተጫነም")

try:
    import pytesseract
except Exception:  # ላይብረሪው ካልተጫነ
    pytesseract = None
    log.warning("pytesseract አልተጫነም")

OCR_TIMEOUT = 45  # ሰከንድ፤ tesseract ሂደቱ ራሱ ይቋረጣል (ከዚህ በፊት thread ብቻ ይቀር ነበር)
MAX_SIDE = 3000  # ከዚህ የሚበልጥ ምስል ይቀነሳል
_SLOTS = threading.Semaphore(2)  # በአንድ ጊዜ ቢበዛ 2 OCR፤ ሰርቨሩ እንዳይደክም

_AMOUNT_WORDS = ("etb", "birr", "amount", "total", "paid", "debit", "transfer", "sent")


def available() -> bool:
    return pytesseract is not None and Image is not None and shutil.which("tesseract") is not None


def read_text(data: bytes) -> str:
    with _SLOTS:
        img = Image.open(io.BytesIO(data)).convert("L")
        w, h = img.size
        if max(w, h) > MAX_SIDE:
            img.thumbnail((MAX_SIDE, MAX_SIDE))
        elif w < 1400:  # ትንሽ ምስል ከሆነ ማሳደግ ንባብን ያሻሽላል
            img = img.resize((w * 2, h * 2))
        img = ImageOps.autocontrast(img)
        return pytesseract.image_to_string(img, lang="eng", config="--psm 6", timeout=OCR_TIMEOUT)


THUMB_W, THUMB_H, BLOCK = 128, 192, 4   # ግራጫ ቅጂ መጠን እና የ4x4 ብሎኮች
BLOCK_DIFF = 12                         # አንድ ብሎክ "ተለየ" የሚባለው አማካይ ልዩነቱ ከዚህ ሲበልጥ


def thumb(data: bytes):
    """የምስሉን ትንሽ ግራጫ ቅጂ (zlib የተጨመቀ bytes) ይመልሳል። ድጋሚ የተላከ፣ የተጨመቀ ወይም መጠኑ የተቀየረ
    ተመሳሳይ ስክሪንሾት ከዋናው ጋር በጣም ይመሳሰላል። ማንበብ ካልተቻለ None።"""
    if Image is None or np is None:
        return None
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        return zlib.compress(img.convert("L").resize((THUMB_W, THUMB_H), Image.BOX).tobytes(), 6)
    except Exception:
        log.exception("thumb failed")
        return None


def to_array(blob: bytes):
    return np.frombuffer(zlib.decompress(blob), dtype=np.uint8).reshape(THUMB_H, THUMB_W).astype(np.int16)


def differing_blocks(a, b) -> int:
    """ሁለት ቅጂዎች (to_array ውጤት) በስንት ብሎክ እንደሚለያዩ። ትንሽ ቁጥር = ተመሳሳይ ምስል።
    በአንድ ደረሰኝ ላይ ሰዓት ብቻ ቢለያይ ጥቂት ብሎኮች ይለያሉ፤ የሌላ ደንበኛ ደረሰኝ ብዙ ብሎኮች ይለያሉ።"""
    d = np.abs(a - b)
    blocks = d.reshape(THUMB_H // BLOCK, BLOCK, THUMB_W // BLOCK, BLOCK).mean(axis=(1, 3))
    return int((blocks > BLOCK_DIFF).sum())


def _norm_alnum(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]", "", s).upper()
    return s.replace("O", "0").replace("I", "1").replace("L", "1")


def _numbers(line: str):
    for tok in re.findall(r"\d[\d,]*(?:\.\d+)?", line):
        try:
            yield float(tok.replace(",", ""))
        except ValueError:
            continue


def _ref_found(ref: str, text: str) -> bool:
    """የግብይት ቁጥሩ እንደ ሙሉ ቃል (ወይም ረጅም ከሆነ በአንድ መስመር ውስጥ) መታየት አለበት።
    አጭር ቁጥር በሌላ ጽሑፍ ውስጥ በአጋጣሚ ተደብቆ እንዳያልፍ።"""
    target = _norm_alnum(ref)
    if not target:
        return False
    for line in text.splitlines():
        if any(_norm_alnum(tok) == target for tok in re.findall(r"[A-Za-z0-9]+", line)):
            return True
        if len(target) >= 8 and target in _norm_alnum(line):  # በ OCR የተቆራረጠ ቁጥር
            return True
    return False


def analyze(text: str, price: int, ref: str, names) -> dict:
    """ጽሑፉ ውስጥ መጠን፣ የተቀባይ ስም እና የግብይት ቁጥር መኖራቸውን ይፈትሻል።

    amount_strong፦ መጠኑ «ETB/Birr/Amount…» ባለበት መስመር ላይ ተገኝቷል (አስተማማኝ)።
    amount፦ መጠኑ የትኛውም ቦታ ተገኝቷል (ደካማ ሊሆን ይችላል)።"""
    strong = weak = False
    for line in text.splitlines():
        low = line.lower()
        keyed = any(w in low for w in _AMOUNT_WORDS) or re.search(r"\bbr\b", low) is not None
        if any(abs(n - price) < 0.01 for n in _numbers(line)):
            weak = True
            strong = strong or keyed
    low = text.lower()
    return {
        "amount": strong or weak,
        "amount_strong": strong,
        "name": any(n.lower() in low for n in names if n),
        "ref": _ref_found(ref, text),
    }
