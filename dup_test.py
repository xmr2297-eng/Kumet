"""የተመሳሳይነት ፍተሻን በእውነተኛ ደረሰኞችዎ ለመሞከር፦
    python dup_test.py ፎልደር_ስም
ፎልደሩ ውስጥ ያሉ ምስሎችን (jpg/png) ሁሉ ጥንድ በጥንድ ያወዳድራል። የተለያዩ ሰዎች ደረሰኞች ከ DUP_MAX_BLOCKS
በላይ ቁጥር ማሳየት አለባቸው፤ የአንድ ደረሰኝ ሁለት ቅጂዎች ደግሞ ከእሱ በታች።"""
import itertools
import sys
from pathlib import Path

import config
import ocr

folder = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
files = sorted(p for ext in ("*.jpg", "*.jpeg", "*.png") for p in folder.glob(ext))
arrs = {}
for f in files:
    t = ocr.thumb(f.read_bytes())
    if t:
        arrs[f.name] = ocr.to_array(t)
limit = getattr(config, "DUP_MAX_BLOCKS", 6)
print(f"ገደብ DUP_MAX_BLOCKS = {limit}; {len(arrs)} ምስሎች\n")
rows = sorted((ocr.differing_blocks(arrs[a], arrs[b]), a, b) for a, b in itertools.combinations(arrs, 2))
for n, a, b in rows[:25]:
    print(f"{'🚫 ይታገዳል' if n <= limit else '✅ ያልፋል  '}  {n:5d}   {a}  ↔  {b}")
print("\n(ከላይ ያሉት በጣም የሚመሳሰሉ ጥንዶች ናቸው፤ የተለያዩ ደንበኞች ደረሰኞች '🚫' ካሳዩ ገደቡን ይቀንሱ።)")
