import unittest

from db.search_utils import build_channel_search_terms, extract_telegram_name


class ChannelSearchUtilsTest(unittest.TestCase):
    def test_extracts_public_channel_from_telegram_url(self):
        self.assertEqual(extract_telegram_name("https://t.me/beijingktv5"), "beijingktv5")
        self.assertEqual(extract_telegram_name("https://t.me/beijingktv5/123?single"), "beijingktv5")
        self.assertEqual(extract_telegram_name("t.me/s/beijingktv5"), "beijingktv5")

    def test_builds_equivalent_search_terms_for_telegram_url(self):
        terms = set(build_channel_search_terms("https://t.me/beijingktv5"))

        self.assertIn("https://t.me/beijingktv5", terms)
        self.assertIn("t.me/beijingktv5", terms)
        self.assertIn("@beijingktv5", terms)
        self.assertIn("beijingktv5", terms)

    def test_builds_equivalent_search_terms_for_username(self):
        terms = set(build_channel_search_terms("@beijingktv5"))

        self.assertIn("@beijingktv5", terms)
        self.assertIn("beijingktv5", terms)
        self.assertIn("https://t.me/beijingktv5", terms)


if __name__ == "__main__":
    unittest.main()
