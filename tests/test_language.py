"""Language filter: posts are read from their own text, since platforms mislabel them.

  python -m unittest tests.test_language -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from viral_scout.language import detect, outside  # noqa: E402


class LanguageTest(unittest.TestCase):
    def test_scripts(self):
        self.assertEqual(detect("PART 4 షాక్ అవుతారు TV ప్రైస్ ఎంతో తెలిస్తే Sony Bravia"), {"te"})
        self.assertIn("hi", detect("काली चाँदी कैसे चमकाएं? How to Clean & Shine Silver"))
        self.assertIn("ru", detect("Как почистить водосток за 5 минут"))
        self.assertIn("ar", detect("واو! كم هي جميلة! تعلّم كيف تقولها بالإنجليزية"))

    def test_latin_languages(self):
        # A real Short that declares itself English (defaultLanguage: en) but is Hindi in Latin letters.
        self.assertEqual(detect("Ganda Hostel Room Banaya Clean Aur Beautiful #emotionalstory #BathroomCleaning"), {"hi"})
        self.assertEqual(detect("Jak wyczyścić rynny, to jest bardzo proste i nie trzeba drabiny"), {"pl"})
        self.assertEqual(detect("Cómo limpiar las canaletas de la casa para que no se tapen"), {"es"})
        self.assertEqual(detect("Ternyata panel surya yang ini harus dibersihkan dengan air"), {"id"})
        self.assertEqual(detect("The old ball blocking the downspout once again! Book your gutter cleaning"), {"en"})

    def test_unsure_is_never_dropped(self):
        for t in ["Christmas lights 🎄", "Chimney Cleaning in Action 🔥 #build", "", "#guttercleaning #fyp"]:
            self.assertIsNone(outside(t, ["en"]), t)

    def test_outside(self):
        keep = ["en", "pl", "uk", "ru"]
        self.assertEqual(outside("Ganda Hostel Room Banaya Clean Aur Beautiful", keep), {"hi"})
        self.assertIsNone(outside("Как почистить водосток за 5 минут", keep))          # Cyrillic, ru/uk kept
        self.assertIsNone(outside("Jak wyczyścić rynny, to jest bardzo proste", keep))   # Polish kept
        self.assertIsNone(outside("Ganda Hostel Room Banaya Clean Aur Beautiful", []))   # no list: keep everything


if __name__ == "__main__":
    unittest.main()
