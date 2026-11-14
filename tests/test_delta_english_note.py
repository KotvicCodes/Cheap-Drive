"""A negative pickup cutoff must not become a ready-after time."""
import io
import unittest

from dispatch import Journal
from models.delta import make_delta, parse_delta_note
from models.notes import NoteFacts
from tests.test_gamma_pairs import PairWorld, pair_order


class EnglishPickupCloseTests(unittest.TestCase):
    def test_negative_clause_is_a_pickup_close_and_preserves_other_facts(self):
        for text in ('No pickups after 17:00', 'NO COLLECTIONS AFTER 17:00'):
            facts = parse_delta_note(text, 540, english_pickup_close=True)
            self.assertEqual(facts.pickup_closes, 1020)
            self.assertIsNone(facts.ready_at)
        facts = parse_delta_note('Ready tomorrow at 10:00; No pickups after 17:00',
                                 540, english_pickup_close=True)
        self.assertEqual((facts.ready_at, facts.pickup_closes), (2040, 1020))

    def test_explicit_off_preserves_the_existing_parse_and_switch_is_independent(self):
        text = 'No pickups after 17:00'
        self.assertEqual(parse_delta_note(text, 540),
                         parse_delta_note(text, 540, english_pickup_close=False))
        for note_fixes in (0, 1):
            desk = make_delta(PairWorld(), 8, 540, Journal(io.StringIO()),
                              delta_note_fixes=note_fixes, delta_english_pickup_close=1)
            pair_order(desk, 'one')
            desk.requests['one']['note'] = {'text': text}
            self.assertEqual(desk.note_facts(desk.requests['one']), NoteFacts(pickup_closes=1020))

    def test_bounded_clause_does_not_rewrite_unrelated_or_invalid_text(self):
        for text in ('Reference no pickups after 17:00', 'No pickups after 25:00',
                     'No pickups after tomorrow', 'No deliveries after 17:00'):
            self.assertEqual(parse_delta_note(text, 540, english_pickup_close=True),
                             parse_delta_note(text, 540))

    def test_strict_integer_switch(self):
        for value in (True, False, -1, 2, '1', None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'delta_english_pickup_close'):
                make_delta(PairWorld(), 8, 540, Journal(io.StringIO()),
                           delta_english_pickup_close=value)
