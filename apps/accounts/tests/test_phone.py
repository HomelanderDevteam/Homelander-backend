from django.test import SimpleTestCase

from common.phone import normalize_phone


class NormalizePhoneTests(SimpleTestCase):
    def test_all_common_nigerian_formats_become_the_same_number(self):
        for raw in ["08012345678", "+2348012345678", "2348012345678", "8012345678",
                    "0801 234 5678", "0801-234-5678", "+234 (801) 234 5678", "002348012345678"]:
            self.assertEqual(normalize_phone(raw), "+2348012345678", raw)

    def test_other_countries_need_a_plus_sign(self):
        self.assertEqual(normalize_phone("+14155552671"), "+14155552671")

    def test_invalid_numbers_are_rejected(self):
        for raw in ["", "abc", "123", "+234801234", "080123456789", "+23480123456789", "phone"]:
            with self.assertRaises(ValueError, msg=raw):
                normalize_phone(raw)
