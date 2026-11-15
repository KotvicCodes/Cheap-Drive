from copy import deepcopy
import io
import unittest
from dispatch import Journal
from models.delta import make_delta, parse_delta_note
from models.gamma_notes import visit_window
from models.notes import parse_note
from tests.test_gamma import GammaWorld, request

DAY=1440


class SaturdayNoteTests(unittest.TestCase):
    def test_observed_bare_phrases_retain_hours_and_revealed_saturday(self):
        # The audit's corpus exposes Saturday hours on77 pickup/104 delivery
        # orders whose bare weekday phrase previously hid that opportunity.
        place=dict(window={'from':0,'to':10*DAY},privateAddress=False,
                   hours=dict(opens=480,closes=1200,weekdays=[0,1,2,3,4],
                              saturday=dict(opens=600,closes=900)))
        for text,kind,hours in [('Nouto arkisin 10-15.30','pickup',(600,930)),
                                ('Destination open weekdays 9:00-20:00','delivery',(540,1200))]:
            normal=parse_note(text,540);facts=parse_note(text,540,weekday_saturday=True)
            self.assertEqual((getattr(facts,kind+'_opens'),getattr(facts,kind+'_closes')),hours)
            self.assertIsNone(visit_window(place,kind,normal,5*DAY,6*DAY-1))
            self.assertEqual(visit_window(place,kind,facts,5*DAY,6*DAY-1),(5*DAY+600,5*DAY+900))
            self.assertIsNone(visit_window(place,kind,facts,6*DAY,7*DAY-1))

    def test_explicit_ranges_and_scoped_negatives_remain_closed(self):
        for text in ('Pickup Mon-Fri 9-18','Nouto ma-pe 9-18','Hämtning måndag-fredag 9-18',
                     'Pickup weekdays 9-18; no Saturday pickups',
                     'Nouto arkisin 9-18; ei noutoja lauantaisin',
                     'Hämtning weekdays 9-18; stängt på lördagar'):
            facts=parse_note(text,540,weekday_saturday=True)
            with self.subTest(text=text):self.assertNotIn(5,facts.pickup_weekdays)
        facts=parse_note('Pickup weekdays 9-18; Delivery weekdays 9-18; no deliveries on Saturday',540,weekday_saturday=True)
        self.assertIn(5,facts.pickup_weekdays);self.assertNotIn(5,facts.delivery_weekdays)
        for closure in ('No Saturday deliveries', 'Ei lauantaisin toimituksia',
                        'Inga leveranser på lördagar', 'Ingen leverans på lördag'):
            scoped=parse_note('Pickup weekdays 9-18; Delivery weekdays 9-18; '+closure,
                              540,weekday_saturday=True)
            with self.subTest(closure=closure):
                self.assertIn(5,scoped.pickup_weekdays)
                self.assertNotIn(5,scoped.delivery_weekdays)
        facts=parse_note('No Saturday pickups; Pickup weekdays 9-18',540,weekday_saturday=True)
        self.assertNotIn(5,facts.pickup_weekdays)
        facts=parse_note('Ready for pickup not before Saturday 12:00',540,weekday_saturday=True)
        self.assertIsNone(facts.pickup_weekdays)
        self.assertEqual(facts.ready_at,5*DAY+720)

    def test_all_delta_parser_branches_and_default_off(self):
        text='Destination open weekdays 9:00-20:00'
        self.assertEqual(parse_delta_note(text,540),parse_note(text,540))
        for fixes in (0,1):
            for extra in ({},{'delta_english_pickup_close':1},{'delta_finnish_close_fixes':1}):
                desk=make_delta(GammaWorld(),8,500,Journal(io.StringIO()),delta_note_fixes=fixes,
                                delta_note_weekday_saturday=1,**extra)
                req=request();req['note']={'text':text}
                self.assertEqual(desk.note_facts(req).delivery_weekdays,tuple(range(6)))

    def test_private_slots_absolute_dates_and_other_fields_unchanged(self):
        text='Pickup weekdays 9-18; ready Saturday 12:00; Manual, plates'
        normal=parse_note(text,540);facts=parse_note(text,540,weekday_saturday=True)
        for field in ('ready_at','plates','manual','pickup_opens','pickup_closes'):
            self.assertEqual(getattr(normal,field),getattr(facts,field))
        private=dict(window={'from':5*DAY+780,'to':5*DAY+840},privateAddress=True,hours=None)
        self.assertEqual(visit_window(private,'pickup',facts,5*DAY,6*DAY-1),(5*DAY+780,5*DAY+840))
        self.assertIsNone(visit_window(private,'pickup',facts,6*DAY,7*DAY-1))

    def test_validation(self):
        for value in (True,False,-1,None,2,'1'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                make_delta(GammaWorld(),8,500,Journal(io.StringIO()),delta_note_weekday_saturday=value)
