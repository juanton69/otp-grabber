import unittest

from otp_grabber.extract import domains_from_email, extract_otp, host_matches, issuer_from_email
from otp_grabber.store import CodeItem, CodeStore


class ExtractTests(unittest.TestCase):
    def test_google_g_code(self):
        got = extract_otp("G-847291 is your Google verification code.", source="sms")
        self.assertIsNotNone(got)
        self.assertEqual(got.code, "847291")
        self.assertEqual(got.issuer, "Google")

    def test_keyword_six_digit(self):
        got = extract_otp("Your verification code is 392185. It expires in 10 minutes.")
        self.assertIsNotNone(got)
        self.assertEqual(got.code, "392185")

    def test_grouped_digits(self):
        got = extract_otp("Microsoft account security code: 123 456")
        self.assertIsNotNone(got)
        self.assertEqual(got.code, "123456")

    def test_ignores_year_and_newsletter(self):
        text = (
            "Summer newsletter 2026! Order number 55102391 invoice 990012 "
            "tracking 88001122 copyright 1998 view in browser unsubscribe"
        )
        self.assertIsNone(extract_otp(text, source="email"))

    def test_short_sms_lone_code(self):
        got = extract_otp("847291", source="sms")
        self.assertIsNotNone(got)
        self.assertEqual(got.code, "847291")

    def test_email_without_keyword_ignored(self):
        self.assertIsNone(extract_otp("See you on 12/11 at 1400 hours.", source="email"))

    def test_domains_from_google_noreply(self):
        domains = domains_from_email("noreply@accounts.google.com")
        self.assertIn("google.com", domains)
        self.assertIn("accounts.google.com", domains)

    def test_issuer_from_friendly_name(self):
        self.assertEqual(issuer_from_email("a@x.com", "GitHub"), "GitHub")

    def test_host_match_accounts_google(self):
        self.assertTrue(host_matches("accounts.google.com", ["google.com"]))
        self.assertFalse(host_matches("github.com", ["google.com"]))


class StoreTests(unittest.TestCase):
    def test_prefers_matching_domain(self):
        store = CodeStore(ttl=60)
        store.ingest(CodeItem(code="111111", source="sms", issuer="SMS", domains=[]))
        store.ingest(
            CodeItem(code="222222", source="email", issuer="GitHub", domains=["github.com"])
        )
        self.assertEqual(store.peek("github.com").code, "222222")
        self.assertEqual(store.peek("accounts.google.com").code, "111111")

    def test_consume_removes(self):
        store = CodeStore(ttl=60)
        store.ingest(CodeItem(code="333333", source="sms", domains=[]))
        self.assertEqual(store.consume("example.com").code, "333333")
        self.assertIsNone(store.peek("example.com"))


if __name__ == "__main__":
    unittest.main()
