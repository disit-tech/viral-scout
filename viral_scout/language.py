"""Which language a post is in, from its own text (title, caption, hook), to drop posts outside a business's languages.

Platform metadata can't be trusted for this: a Hindi YouTube Short can declare itself English (defaultLanguage: en)
and report no audio language. So this reads the text:
  * scripts: Devanagari, Telugu, Tamil, Cyrillic, Arabic, CJK… are unambiguous;
  * Latin-script text: counts very common words per language (English, Spanish, Portuguese, French, German, Italian,
    Polish, Turkish, Indonesian) and romanized Hindi/Urdu ("aur", "hai", "kaise"), which YouTube titles use a lot.
It only answers when it is fairly sure; short or mixed text returns None, and None is never dropped.
"""
import re

# script ranges → the languages that script stands for (a post in that script is dropped unless one of them is kept)
SCRIPTS = [
    ("Ѐ-ӿ", {"ru", "uk", "be", "bg", "sr", "mk", "kk"}),          # Cyrillic
    ("ऀ-ॿ", {"hi", "mr", "ne"}),                                 # Devanagari
    ("ঀ-৿", {"bn", "as"}), ("਀-੿", {"pa"}), ("઀-૿", {"gu"}),
    ("଀-୿", {"or"}), ("஀-௿", {"ta"}), ("ఀ-౿", {"te"}), ("ಀ-೿", {"kn"}),
    ("ഀ-ൿ", {"ml"}), ("඀-෿", {"si"}), ("฀-๿", {"th"}),
    ("؀-ۿݐ-ݿ", {"ar", "ur", "fa"}), ("֐-׿", {"he"}), ("Ͱ-Ͽ", {"el"}),
    ("一-鿿", {"zh", "ja"}), ("぀-ヿ", {"ja"}), ("가-힯ᄀ-ᇿ", {"ko"}),
    ("Ⴀ-ჿ", {"ka"}), ("԰-֏", {"hy"}),
]
_SCRIPT_RE = [(re.compile(f"[{r}]"), langs) for r, langs in SCRIPTS]
_LATIN = re.compile(r"[A-Za-zÀ-ɏ]")

# Very common words that are rare in the other languages listed (Latin script). Romanized Hindi/Urdu is "hi".
WORDS = {
    "en": "the and you this that with for are was what how your have not but just from they will can get when out all".split(),
    "es": "el la los las que de del por para con una como pero muy más esto está son cuando también sin hay".split(),
    "pt": "não você uma com para que mais isso está são muito também então pra seu sua".split(),
    "fr": "le les des une est pas que pour avec dans sur vous nous mais très tout cette comme".split(),
    "de": "der die das und ist nicht ein eine mit auf für sich auch noch wie wenn oder sehr".split(),
    "it": "il che non una per con sono della anche come più questo molto quando".split(),
    "pl": "jest nie się jak to na że ale co już tak tylko jeszcze bardzo przez dla czy".split(),
    "tr": "bir ve bu da de için çok ama gibi ne var olan daha".split(),
    "id": "yang dan ini itu dengan untuk tidak ada dari akan juga bisa sudah".split(),
    "hi": "aur hai hain kaise kya nahi nahin bhai wala wali banaya karo karna mein yeh kuch bahut apna apne raha rahi "
          "accha achha dekho bilkul sirf abhi ganda kaam ghar bana diya liya tha thi".split(),
}
_WORD_SETS = {k: set(v) for k, v in WORDS.items()}
_TOKEN = re.compile(r"[a-zà-ɏ']+")


def detect(text):
    """A set of language codes the text is in (e.g. {"hi"}, {"ru", "uk", …} for Cyrillic), or None when unsure."""
    text = re.sub(r"#\S+|@\S+|https?://\S+", " ", text or "")          # hashtags and handles say little
    letters = sum(1 for _ in _LATIN.finditer(text))
    best, best_n = None, 0
    for rx, langs in _SCRIPT_RE:
        n = len(rx.findall(text))
        if n > best_n:
            best, best_n = langs, n
    if best and best_n >= 4 and best_n >= 0.25 * (best_n + letters):
        return set(best)
    words = _TOKEN.findall(text.lower())
    if len(words) < 3:
        return None
    hits = {lang: len({w for w in words if w in s}) for lang, s in _WORD_SETS.items()}
    lang = max(hits, key=hits.get)
    if lang == "en" or hits[lang] < 2 or hits[lang] <= hits["en"]:
        return None if hits["en"] < 2 else {"en"}
    return {lang}


def outside(item_text, keep):
    """The detected language(s) when the text is in none of the kept languages, else None (kept, or unsure)."""
    if not keep:
        return None
    found = detect(item_text)
    if not found or found & set(keep):
        return None
    return found
