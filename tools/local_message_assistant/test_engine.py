import tempfile
import unittest

from engine import Assistant, Store, account_key, question


class FakeExtractor:
    def __init__(self, **facts):
        self.calls = 0
        self.facts = dict(city="", district="", budget="", people="", human_required=False, reason="")
        self.facts.update(facts)

    def extract(self, *_args):
        self.calls += 1
        return self.facts


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(self.directory.name)
        self.extractor = FakeExtractor(city="上海", district="浦东")
        self.assistant = Assistant(self.store, self.extractor, {})
        self.key = account_key("telegram", "KTV_AZ")
        self.event = dict(kind="private", outgoing=False, bot=False, service=False,
                          date=102, id="1", chat="42", text="我在上海浦东")

    def tearDown(self):
        self.store.db.close()
        self.directory.cleanup()

    def add(self, **updates):
        return self.store.ingest(self.key, {**self.event, **updates}, 100)

    def test_idle_does_not_call_model(self):
        self.assertIsNone(self.assistant.prepare(self.key, "42"))
        self.assertEqual(self.extractor.calls, 0)

    def test_groups_bots_outgoing_old_and_unknown_fail_closed(self):
        for updates in [dict(kind="group"), dict(kind="channel"), dict(bot=True),
                        dict(outgoing=True), dict(service=True), dict(date=99), dict(bot=None),
                        dict(outgoing=None), dict(text=""), dict(text=None)]:
            with self.subTest(updates=updates):
                self.assertFalse(self.add(**updates))
        self.assertEqual(self.extractor.calls, 0)

    def test_duplicate_message_and_restart(self):
        self.assertTrue(self.add())
        self.assertFalse(self.add())
        self.store.db.close()
        self.store = Store(self.directory.name)
        self.assertFalse(self.add())

    def test_account_isolation(self):
        self.assertTrue(self.add())
        other = account_key("telegram", "shanghai_xiaozhang")
        self.assertTrue(self.store.ingest(other, self.event, 100))
        self.assertEqual(len(self.store.pending(other, "42")), 1)

    def test_only_missing_fields_are_asked(self):
        self.add()
        item = self.assistant.prepare(self.key, "42")
        self.assertEqual(item["reply"], "你们一共几个人，人均预算大概多少呀？")
        self.assertEqual(self.extractor.calls, 1)

    def test_all_information_goes_to_human(self):
        self.extractor.facts.update(people="4", budget="人均500元")
        self.add()
        self.assertIsNone(self.assistant.prepare(self.key, "42"))
        self.assertEqual(self.store.conversation(self.key, "42")["status"], "human_required")

    def test_uncertain_send_never_retries(self):
        self.add()
        item = self.assistant.prepare(self.key, "42")
        self.assistant.begin_send(item)
        self.assistant.finish_send(item, False)
        self.assertIsNone(self.assistant.prepare(self.key, "42"))
        self.add(id="2", date=103)
        self.assertIsNone(self.assistant.prepare(self.key, "42"))
        self.assertEqual(self.extractor.calls, 1)

    def test_prepared_message_not_regenerated_after_restart(self):
        self.add()
        self.assistant.prepare(self.key, "42")
        self.store.db.close()
        self.store = Store(self.directory.name)
        self.assistant = Assistant(self.store, self.extractor, {})
        self.assertIsNone(self.assistant.prepare(self.key, "42"))
        self.assertEqual(self.extractor.calls, 1)

    def test_no_repeated_question(self):
        self.add()
        item = self.assistant.prepare(self.key, "42")
        self.assistant.begin_send(item)
        self.assistant.finish_send(item, True)
        self.add(id="2", date=103)
        self.assertIsNone(self.assistant.prepare(self.key, "42"))

    def test_requested_manual_handling_does_not_send(self):
        self.extractor.facts["human_required"] = True
        self.add()
        self.assertIsNone(self.assistant.prepare(self.key, "42"))

    def test_unknown_city_not_assumed_from_account_focus(self):
        self.assertEqual(question({}), "你好，你现在在哪个城市、哪个区呀？")
        self.assertEqual(question({"city": "北京"}), "你在北京哪个区呀？")


if __name__ == "__main__":
    unittest.main()
