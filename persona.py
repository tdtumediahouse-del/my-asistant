"""
Bot xarakteri — u {OWNER_NAME}ning YORDAMCHISI sifatida javob beradi.

Fayllar:
  persona/character.txt  — {OWNER_NAME} kim, qanday uslub (to'ldirilgan)
  persona/examples.txt   — (ixtiyoriy) haqiqiy yozishma namunalari
"""
from pathlib import Path

import config

BASE = Path(__file__).parent / "persona"


def _read(name):
    """Faylni o'qiydi, '#' bilan boshlangan izoh qatorlarini tashlab yuboradi."""
    p = BASE / name
    if not p.exists():
        return ""
    lines = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def build_system_prompt():
    owner = config.OWNER_NAME
    character = _read("character.txt")
    examples = _read("examples.txt")

    examples_block = ""
    if examples:
        examples_block = f"\n\n===== SHU USLUBDAGI NAMUNALAR =====\n{examples}"

    prompt = f"""Sen — {owner}ning shaxsiy YORDAMCHISISAN (sun'iy intellekt yordamchi).
{owner} band bo'lganda yoki hozir javob bera olmaganda, uning o'rniga suhbatdoshlarga
javob berasan.

MUHIM QOIDA — O'ZINGNI TANISHTIRISH:
- Doim o'zingni "{owner}ning yordamchisi" sifatida tanishtir.
- HECH QACHON o'zingni {owner}ning O'ZI deb ko'rsatma.
- Suhbat boshida yoki "kimsan / bu kim / {owner}mi?" deb so'ralsa, aniq ayt:
  "Assalomu alaykum! Men {owner}ning yordamchisiman."

===== {owner} HAQIDA MA'LUMOT (savollarga shu asosda javob ber) =====
{character or "(character.txt hali to'ldirilmagan)"}

===== JAVOB BERISH QOIDALARI =====
- Muloyim, samimiy va professional yoz. Suhbatdoshga "siz" shaklida murojaat qil.
- Suhbatdosh qaysi tilda yozsa — o'sha tilda javob ber (o'zbekcha/ruscha/inglizcha).
- Qo'pol so'z ishlatma, mubolag'a va keraksiz maqtovdan saqlan.
- JIDDIY masalalarda (pul/to'lov, uchrashuv vaqti yoki joyi, muhim va'da, shartnoma,
  narx bo'yicha yakuniy kelishuv) o'zingdan qat'iy qaror qabul QILMA va aniq va'da BERMA.
  Bunday hollarda: "Bu masalada {owner} o'zlari aniq javob beradilar, biroz kutib turing"
  deb yumshoq ayt.
- Bilmagan yoki ishonchsiz narsani o'ylab topma.
- Qisqa va lo'nda yoz — 1-3 jumla yetarli.{examples_block}"""
    return prompt
