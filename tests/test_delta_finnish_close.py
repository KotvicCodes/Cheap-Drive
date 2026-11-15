"""Finnish closed-after notes are closing bounds, not readiness."""
import io
import unittest

from dispatch import Journal
from models.delta import make_delta, parse_delta_note
from models.notes import NoteFacts
from tests.test_gamma_pairs import PairWorld, pair_order


class FinnishCloseTests(unittest.TestCase):
    def test_destination_closed_after_is_not_destination_opening(self):
        facts = parse_delta_note('Perillä liike kiinni klo 16.30 jälkeen', 540,
                                 finnish_close_fixes=True)
        self.assertEqual(facts, NoteFacts(delivery_closes=990))

    def test_pickup_closed_after_is_not_ready_after(self):
        facts = parse_delta_note('Noutopaikka kiinni klo 16.30 jälkeen', 540,
                                 finnish_close_fixes=True)
        self.assertEqual(facts, NoteFacts(pickup_closes=990))

    def test_fix_is_independent_and_keeps_separate_readiness(self):
        text = 'Valmis huomenna klo 10:00; perillä liike kiinni klo 16.30 jälkeen'
        for note_fixes in (0, 1):
            desk = make_delta(PairWorld(), 8, 540, Journal(io.StringIO()),
                              delta_note_fixes=note_fixes, delta_finnish_close_fixes=1)
            pair_order(desk, 'one')
            desk.requests['one']['note'] = {'text': text}
            facts = desk.note_facts(desk.requests['one'])
            self.assertEqual((facts.ready_at, facts.delivery_closes), (2040, 990))
            self.assertIsNone(facts.delivery_opens)

    def test_neutral_and_unrelated_or_invalid_text_retain_old_parse(self):
        for text in ('Valmis klo 16.30 jälkeen', 'Perillä kiinni klo 25:00 jälkeen',
                     'Ready after 16:30; collect before 18:00'):
            self.assertEqual(parse_delta_note(text, 540, finnish_close_fixes=True),
                             parse_delta_note(text, 540))
        text = 'Perillä liike kiinni klo 16.30 jälkeen'
        self.assertEqual(parse_delta_note(text, 540),
                         parse_delta_note(text, 540, finnish_close_fixes=False))

    def test_switch_requires_integer_zero_or_one(self):
        for value in (True, False, -1, 2, '1', None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'delta_finnish_close_fixes'):
                make_delta(PairWorld(), 8, 540, Journal(io.StringIO()), delta_finnish_close_fixes=value)
