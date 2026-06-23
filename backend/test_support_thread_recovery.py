import unittest

from bot.support_bot import is_message_thread_not_found_error


class SupportThreadRecoveryTest(unittest.TestCase):
    def test_detects_message_thread_not_found_error(self):
        error = "{'ok': False, 'error_code': 400, 'description': 'Bad Request: message thread not found'}"

        self.assertTrue(is_message_thread_not_found_error(Exception(error)))

    def test_does_not_match_other_bad_request_errors(self):
        error = "{'ok': False, 'error_code': 400, 'description': 'Bad Request: chat not found'}"

        self.assertFalse(is_message_thread_not_found_error(Exception(error)))


if __name__ == "__main__":
    unittest.main()
