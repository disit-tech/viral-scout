"""What an ad says: hook, offer types, CTA and format. Regex + keywords in English, Russian and Ukrainian.

Offer tags (an ad can have several):
  price       a price or a monthly amount ($49, 1 200 грн, /mo)
  free_trial  free trial / first lesson free / пробный урок / пробне заняття
  free_quote  free quote, estimate, consultation, assessment
  free        any other "free" claim (check it: FTC rules on "free"; solar: no "free solar")
  discount    % off, sale, promo code, скидка / знижка
  guarantee   money-back / satisfaction guarantee, гарантия / гарантія
  financing   $0 down, monthly payments, 0% APR, loan/lease/PPA, рассрочка / розстрочка
  incentive   tax credit, rebate, incentives (ITC, SREC, Illinois Shines)
  urgency     limited time, only N spots, ends soon, осталось / залишилось
  social_proof  ratings, "N students/customers", reviews
"""
import re

_I = re.I | re.U

OFFER_PATTERNS = {
    "price": [
        r"[$€£₴₽]\s?[1-9][\d\s,.]*(?:\s?(?:/|per\s)(?:mo|month|lesson|hour|hr|class|week)\w*)?",
        r"\b\d[\d\s,.]*\s?(?:usd|eur|грн|uah|руб|rub|zł|pln|долл\w*|доларів|долларов)\b",
        r"\b\d[\d,.]*\s?(?:/mo|/month|a month|per month|в месяц|на місяць|в місяць)\b",
    ],
    "free_trial": [
        r"\bfree\s+(?:trial|lesson|class|session|week|month|first lesson|intro\w*)\b",
        r"\btry\s+(?:it\s+)?(?:for\s+)?free\b", r"\bfirst\s+(?:lesson|class|session)\s+(?:is\s+)?free\b",
        r"\btrial\s+(?:lesson|class)\b",
        r"бесплатн\w*\s+(?:пробн\w*\s+)?(?:урок|заняти|заняті|заняття|заняттю|заняттям|недел)\w*",
        r"пробн\w*\s+(?:урок|заняти|заняття|занятт)\w*", r"безкоштовн\w*\s+(?:пробн\w*\s+)?(?:урок|занятт|заняття|тиждень)\w*",
    ],
    "free_quote": [
        r"\bfree\s+(?:quote|estimate|consult\w*|assessment|inspection|design|savings\s+report|home\s+evaluation)\b",
        r"\bno[- ]cost\s+(?:quote|estimate|consult\w*|assessment)\b",
        r"бесплатн\w*\s+(?:консультац|оценк|расчет|расчёт|замер)\w*",
        r"безкоштовн\w*\s+(?:консультац|оцінк|розрахун|замір)\w*",
    ],
    "free": [r"\bfree\b", r"\$0\b(?!\s*down)", r"бесплатн\w*", r"безкоштовн\w*", r"даром\b", r"задарма\b"],
    "discount": [
        r"\b\d{1,2}\s?%\s?(?:off|discount)\b", r"\b(?:discount|sale|promo\s?code|coupon|save\s+\$?\d+|special\s+offer|deal)\b",
        r"скидк\w*", r"знижк\w*", r"\bакци[яи]\b", r"\bакці[яї]\b", r"промокод\w*", r"-\s?\d{1,2}\s?%",
    ],
    "guarantee": [
        r"\b(?:money[- ]back|satisfaction|price[- ]match|results?)\s+guarantee\w*\b", r"\bguarantee\w*\b",
        r"\brisk[- ]free\b", r"гаранти\w*", r"гаранті\w*", r"верн[её]м\s+деньги", r"поверн\w*\s+гроші",
    ],
    "financing": [
        r"\$0\s+down\b", r"\bno\s+money\s+down\b", r"\bzero\s+down\b", r"\bfinanc\w*\b", r"\bmonthly\s+payments?\b",
        r"\b0\s?%\s?(?:apr|interest|financing)\b", r"\b(?:loan|lease|ppa|power\s+purchase\s+agreement)\b",
        r"\bpay\s+(?:over\s+time|monthly|later)\b", r"рассрочк\w*", r"розстрочк\w*", r"\bкредит\w*", r"частями\b",
    ],
    "incentive": [
        r"\btax\s+credit\w*\b", r"\brebate\w*\b", r"\bincentive\w*\b", r"\b(?:itc|srec\w*)\b", r"\billinois\s+shines\b",
        r"\bgrant\w*\b", r"налогов\w*\s+вычет\w*", r"податков\w*\s+(?:знижк|кредит)\w*",
    ],
    "urgency": [
        r"\blimited\s+(?:time|spots|seats|offer|availability)\b", r"\bonly\s+\d+\s+(?:spots|seats|places|left)\b",
        r"\b(?:ends|expires)\s+(?:soon|today|tonight|sunday|friday|this)\b", r"\btoday\s+only\b", r"\bdeadline\b",
        r"\blast\s+chance\b", r"осталось\s+\d*", r"залишилось\s+\d*", r"только\s+до\b", r"лише\s+до\b", r"успей\w*", r"встигн\w*",
    ],
    "social_proof": [
        r"\b\d[\d,.]*\+?\s?(?:k\s)?(?:students|customers|clients|homeowners|families|reviews|installs)\b",
        r"\b[45](?:\.\d)?\s?(?:★|stars?)\b", r"\brated\s+#?1\b", r"\b#1\b",
        r"\d[\d\s]*\+?\s?(?:студент\w*|учени\w*|клиент\w*|клієнт\w*|відгук\w*|отзыв\w*)",
    ],
}
_COMPILED = {k: [re.compile(p, _I) for p in v] for k, v in OFFER_PATTERNS.items()}

CTA_PATTERNS = [
    ("Book a free lesson", r"\b(?:book|claim|get|grab)\s+(?:your\s+)?(?:free\s+)?(?:trial\s+)?(?:lesson|class)\b|записат\w*\s+на\s+(?:пробн|бесплатн)\w*|запиш\w*\s+на\s+(?:пробн|безкоштовн)\w*"),
    ("Get a quote", r"\b(?:get|request|claim)\s+(?:your\s+|a\s+)?(?:free\s+)?(?:quote|estimate|proposal|savings\s+report)\b"),
    ("Sign up", r"\bsign\s+up\b|\bregister\b|\benroll\b|\bjoin\s+(?:now|today|us)\b|зарегистр\w*|зареєстр\w*"),
    ("Book / schedule", r"\b(?:book|schedule)\s+(?:a\s+|your\s+)?(?:call|consult\w*|appointment|visit|now|today|online)\b|записат\w*|запиш\w*"),
    ("Call", r"\bcall\s+(?:us|now|today)\b|\(\d{3}\)\s?\d{3}-\d{4}|звон\w*|телефонуй\w*|дзвон\w*"),
    ("Learn more", r"\blearn\s+more\b|\bfind\s+out\b|\bsee\s+(?:how|if)\b|узнат\w*|дізнат\w*"),
    ("Shop", r"\bshop\s+now\b|\bbuy\s+now\b|\border\s+now\b"),
    ("Message us", r"\b(?:message|dm|text)\s+us\b|\bsend\s+message\b|напиш\w*"),
    ("Check eligibility", r"\b(?:check|see)\s+(?:if\s+you\s+)?(?:qualify|eligib\w*)\b|\bqualif\w*\b"),
    ("Download", r"\bdownload\b|\binstall\s+(?:the\s+)?app\b|скача\w*|завантаж\w*"),
]
_CTA = [(name, re.compile(p, _I)) for name, p in CTA_PATTERNS]

_EMOJI_LEAD = re.compile(r"^[\W_]+", re.U)


def hook(title, body, max_words=18):
    """The first line of the primary text (what people read before 'See more'), else the headline."""
    text = (body or "").strip()
    first = ""
    for line in re.split(r"[\r\n]+", text):
        line = line.strip()
        if len(re.findall(r"\w+", line)) >= 2:
            first = line
            break
    if first:
        m = re.match(r"(.+?[.!?…])(\s|$)", first)
        if m and len(m.group(1).split()) >= 3:
            first = m.group(1)
    else:
        first = (title or "").strip()
    first = first.replace("{{product.name}}", "").strip()
    words = first.split()
    return " ".join(words[:max_words]) + ("…" if len(words) > max_words else "")


def offers(text):
    """(tags, snippets): which offer types the copy uses, and the matched words (max 6)."""
    found = {}
    t = text or ""
    for tag, pats in _COMPILED.items():
        for p in pats:
            m = p.search(t)
            if m:
                found[tag] = m.group(0).strip()
                break
    # A specific free offer makes the generic "free" tag redundant.
    if "free" in found and ("free_trial" in found or "free_quote" in found):
        del found["free"]
    snippets = []
    for s in found.values():
        if s and s.lower() not in (x.lower() for x in snippets):
            snippets.append(s)
    return list(found), snippets[:6]


def cta(button, text):
    """The call to action: the button text when the source gives it, else the first CTA phrase in the copy."""
    if button:
        b = re.sub(r"[_]+", " ", str(button)).strip()
        return b[:1].upper() + b[1:].lower() if b.isupper() else b
    for name, p in _CTA:
        if p.search(text or ""):
            return name
    return ""


def norm_format(v, has_video=False, has_images=0, cards=0):
    s = str(v or "").lower()
    if cards and cards > 1 or "carousel" in s:
        return "carousel"
    if "dco" in s or "dynamic" in s:
        return "dco"
    if "video" in s or has_video:
        return "video"
    if "image" in s or "photo" in s or has_images:
        return "image"
    if "text" in s:
        return "text"
    return s or "unknown"


def normalize_copy(text):
    """Copy fingerprint for grouping variants: lowercase words, no numbers/emoji/URLs, first ~25 words."""
    t = re.sub(r"https?://\S+", " ", (text or "").lower())
    t = re.sub(r"\{\{[^}]+\}\}", " ", t)
    words = re.findall(r"[^\W\d_]+", t, re.U)
    return " ".join(words[:25])
