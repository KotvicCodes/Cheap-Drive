"""Small, deterministic FI/SV/EN dispatch-note reader, authored for this repo.

Absolute days are relative to request arrival, never to an option or repost.
Unrecognized prose is ignored; this is a bounded vocabulary, not a translator.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

DAY = 1440


@dataclass(frozen=True)
class NoteFacts:
    ready_at: int | None = None
    released_at: int | None = None
    pickup_opens: int | None = None
    pickup_closes: int | None = None
    delivery_opens: int | None = None
    delivery_closes: int | None = None
    delivery_ready_at: int | None = None
    deadline: int | None = None
    plates: bool = False
    manual: bool = False
    pickup_deadline: int | None = None
    pickup_weekdays: tuple[int, ...] | None = None
    delivery_weekdays: tuple[int, ...] | None = None
    deadline_explicit_day: bool = False


def _plain(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower())
                   if not unicodedata.combining(c)).replace('–', '-').replace('—', '-')


_WEEKDAYS = (
    r'ma|maanantai(?:na)?|monday|mon|mandag',
    r'ti|tiistai(?:na)?|tuesday|tue|tisdag',
    r'ke|keskiviikko(?:na)?|wednesday|wed|onsdag',
    r'to(?=\s+(?:klo|kello|\d))|torstai(?:na)?|thursday|thu|torsdag',
    r'pe|perjantai(?:na)?|friday|fri|fredag',
    r'la|lauantai(?:na)?|saturday|sat|lordag',
    r'su|sunnuntai(?:na)?|sunday|sun|sondag',
)
_TOMORROW = r'huomenna|tomorrow|tmrw|i\s*morgon|imorgon'
_AFTER_TOMORROW = r'ylihuomenna|day after tomorrow|i\s*overmorgon|overmorgon'
_PICKUP = re.compile(r'nout|noud|hakea|haett|pickup|pick\s*up|collect|hamt|luovut|lamnas ut')
_DELIVERY = re.compile(r'toimit|perilla|perille|vastaanot|kohde|deliver|arriv|destination|receiv|recipient|leverans|leverer|framme|mottag')
_READY = re.compile(r'valmi|vamis|huolto|workshop|woorkshop|ready|available|klar|aik+a?isintaan|earliest|tidigast|alkaen|framat|\bfrom\b|\bafter\b|jalkeen|efter|not before|ei ennen|inte fore')
_RELEASE = re.compile(r'maksu|makset|payment|betal|released|luovut|lamnas ut')
_CLOSE = re.compile(r'close|sulke|kiinni|stang|nobody|no one|ei ketaan|ingen|ennen|before|viim|mennessa|latest|\bby\b|fore|senast|until|\btill\b|asti|saakka')
_OPEN = re.compile(r'auki|avoin|open|oppet')
_SITE_CLOSE = re.compile(r'close|sulke|kiinni|stang|nobody|no one|ei ketaan|ingen')
_CLOCK = re.compile(r'(?<![\w:])(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)?(?![\w:])')
_WORDS = {
    1: 'one yksi yhdelta ett en', 2: 'two kaksi kahdelta tva',
    3: 'three kolme kolmelta tre', 4: 'four nelja neljalta fyra',
    5: 'five viisi viidelta fem', 6: 'six kuusi kuudelta sex',
    7: 'seven seitseman seitsemalta sju', 8: 'eight kahdeksan kahdeksalta atta',
    9: 'nine yhdeksan yhdeksalta nio', 10: 'ten kymmenen kymmenelta tio',
    11: 'eleven yksitoista yhdeltatoista elva', 12: 'twelve kaksitoista kahdeltatoista tolv noon keskipaiva',
    13: 'thirteen kolmetoista treton tretton', 14: 'fourteen neljatoista fjorton',
    15: 'fifteen viisitoista femton', 16: 'sixteen kuusitoista sexton',
    17: 'seventeen seitsemantoista sjutton', 18: 'eighteen kahdeksantoista arton',
    19: 'nineteen yhdeksantoista nitton', 20: 'twenty kaksikymmenta tjugo',
    21: 'twenty-one tjugoett', 22: 'twenty-two tjugotva',
    23: 'twenty-three tjugotre', 24: 'midnight keskiyo midnatt',
}
_WORD_VALUES = {word: hour for hour, words in _WORDS.items() for word in words.split()}
_WORD_CLOCK = re.compile(r'\b(' + '|'.join(sorted(_WORD_VALUES, key=len, reverse=True)) + r')\b')
_TIME_CUE = re.compile(r'klo|kello|\bkl\b|klockan|\bat\b|before|after|\bby\b|\bfrom\b|ready|valmi|earliest|tidigast|alkaen|jalkeen|ennen|efter|fore|tomorrow|huomenna|morgon|open|close|auki|avoin|stang|oppet')


def _day(text, arrived_at):
    # A corrective aside such as "Wednesday (not tomorrow)" must not win.
    text = re.sub(r'\b(?:ei|not|inte)\s+(?:' + _TOMORROW + r')\b', '', text)
    day = arrived_at // DAY
    if re.search(r'\b(?:' + _AFTER_TOMORROW + r')\b', text):
        return day + 2, True
    if re.search(r'\b(?:' + _TOMORROW + r')\b', text):
        return day + 1, True
    if re.search(r'\b(?:tanaan|today|i\s*dag|idag)\b', text):
        return day, True
    for weekday, names in enumerate(_WEEKDAYS):
        if re.search(r'\b(?:' + names + r')\b', text):
            return day + (weekday - day % 7) % 7, True
    return day, False


def _word_hours(text):
    def replace(match):
        prefix = text[max(0, match.start() - 35):match.start()]
        if not _TIME_CUE.search(prefix) and not re.search(r'half past|quarter past|puoli|halv', prefix):
            return match[0]
        hour = _WORD_VALUES[match[1]]
        # In these business-hours notes, bare "kahdelta"/"at two"/"kl
        # tva" mean afternoon. Explicit AM/PM always takes precedence.
        suffix = text[match.end():]
        if 1 <= hour <= 7 and not re.match(r'\s*(?:am|pm)\b', suffix):
            hour += 12
        return str(hour) + ':00'
    text = _WORD_CLOCK.sub(replace, text)
    text = re.sub(r'(?:half past)\s+(\d{1,2}):00', lambda m: m[1] + ':30', text)
    text = re.sub(r'(?:quarter past)\s+(\d{1,2}):00', lambda m: m[1] + ':15', text)
    text = re.sub(r'(?:puoli|halv)\s+(\d{1,2}):00', lambda m: str((int(m[1]) - 1) % 24) + ':30', text)
    return text


def _clock(match):
    hour, minute = int(match[1]), int(match[2] or 0)
    if minute > 59 or hour > 24 or hour == 24 and minute:
        return None
    if match[3]:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if match[3] == 'pm' else 0)
    return hour * 60 + minute


_SATURDAY_CLOSED = re.compile(
    r'\b(?:no\s+(?:(?:pickups?|collections?|deliveries)\s+(?:on\s+)?)?saturdays?'
    r'|closed\s+(?:on\s+)?saturdays?|saturdays?\s+(?:closed|no\s+(?:pickups?|deliveries))'
    r'|ei\s+(?:(?:nout\w*|luovut\w*|toimit\w*)\s+)?lauantai(?:sin|na)?'
    r'|lauantai(?:sin|na)?\s+(?:kiinni|suljettu)'
    r'|(?:stangt|stangd)\s+(?:pa\s+)?lordag(?:ar)?'
    r'|lordag(?:ar)?\s+(?:stangt|stangd)'
    r'|inga?\s+(?:(?:hamt\w*|leveran\w*)\s+(?:pa\s+)?)?lordag(?:ar)?)\b')


def parse_note(note, arrived_at, *, weekday_saturday=False):
    """Extract supported constraints without retaining note text or access codes."""
    if isinstance(note, dict):
        note = note.get('text', '')
    text = _plain(note or '')
    text = re.sub(r'\b(?:a\.m\.|p\.m\.)', lambda m: m[0].replace('.', ''), text)
    text = re.sub(r'\b(viim|klo|kl|ma|ti|ke|to|pe|la|su|mon|tue|wed|thu|fri|sat|sun)\.(?=\s|$)', r'\1', text)
    values = {
        'plates': bool(re.search(r'kilvet|kilpi|rekkar|plates|skylt', text)),
        'manual': bool(re.search(r'manuaal|kasivaiht|manual|\bmaual\b|manuell|stick shift', text)),
    }

    def maximum(key, value):
        values[key] = max(values.get(key, value), value)

    def minimum(key, value):
        values[key] = min(values.get(key, value), value)

    # Independent clauses prevent a destination cue from swallowing pickup
    # instructions elsewhere in the note. Split again at an explicit new role.
    clauses = re.split(r'[,;\n!?]|\.(?!\d)', text)
    release_context = False
    saturday_closed = set()
    for clause in clauses:
        clause = _word_hours(clause)
        negative_prefix = r'(?<!\bno)(?<!\bei)(?<!\binte)' if weekday_saturday else ''
        pieces = re.split(negative_prefix + r'\s+(?=(?:ready for pickup|pick(?:up|\s+up)|collect(?:ion)?|nouto|toimit\w*|destination|deliver\w*|arriv\w*|recipient|oltava perilla|perilla|leverans\w*|framme)\b)', clause)
        for part in pieces:
            if not part.strip():
                continue
            delivery = bool(_DELIVERY.search(part)) and not _PICKUP.search(part)
            kind = 'delivery' if delivery else 'pickup'
            if _RELEASE.search(part):
                release_context = True
            elif delivery or re.search(r'valmi|vamis|\bready\b|workshop|woorkshop|\bklar\b', part):
                release_context = False
            explicit_weekdays = re.search(r'ma\s*-\s*pe|mon\s*-\s*fri|mandag\s*-\s*fredag', part)
            bare_weekdays = re.search(r'arkisin|weekdays', part)
            if explicit_weekdays or bare_weekdays:
                values[kind + '_weekdays'] = ((0, 1, 2, 3, 4, 5) if weekday_saturday
                                                and bare_weekdays and not explicit_weekdays
                                                else (0, 1, 2, 3, 4))
            if weekday_saturday and _SATURDAY_CLOSED.search(part):
                saturday_closed.add(kind)
            clocks = [(match, _clock(match)) for match in _CLOCK.finditer(part)]
            clocks = [(match, minute) for match, minute in clocks if minute is not None]
            # A pair of clocks joined by a dash is a recurring daily range.
            ranged = set()
            for i in range(len(clocks) - 1):
                left, right = clocks[i], clocks[i + 1]
                if re.fullmatch(r'\s*(?:-|to|till|asti)\s*', part[left[0].end():right[0].start()]):
                    if left[1] < right[1]:
                        maximum(kind + '_opens', left[1])
                        minimum(kind + '_closes', right[1])
                    ranged.update((i, i + 1))
            for i, (match, minute) in enumerate(clocks):
                if i in ranged:
                    continue
                # Bare integers need a time cue; don't read tyre counts or IDs.
                if not match[2] and not match[3] and not _TIME_CUE.search(part[:match.start()]):
                    continue
                day, explicit = _day(part, arrived_at)
                absolute = day * DAY + minute
                negative_presence = bool(re.search(r'nobody|no one|ei ketaan|ingen', part))
                after = bool(_READY.search(part)) and not negative_presence
                before = bool(_CLOSE.search(part)) or negative_presence
                if delivery and before and not after:
                    if _SITE_CLOSE.search(part) or _OPEN.search(part):
                        minimum('delivery_closes', minute)
                    else:
                        minimum('deadline', absolute)
                        values['deadline_explicit_day'] = values.get('deadline_explicit_day', False) or explicit
                elif delivery and after:
                    if _OPEN.search(part) or not explicit:
                        maximum('delivery_opens', minute)
                    else:
                        maximum('delivery_ready_at', absolute)
                elif after:
                    maximum('released_at' if release_context else 'ready_at', absolute)
                elif before:
                    if explicit:
                        minimum('pickup_deadline', absolute)
                    else:
                        minimum(kind + '_closes', minute)
                elif _OPEN.search(part):
                    maximum(kind + '_opens', minute)
                elif _PICKUP.search(part):
                    maximum('ready_at', absolute)
    for kind in saturday_closed:
        key = kind + '_weekdays'
        values[key] = tuple(day for day in values.get(key, range(7)) if day != 5)
    return NoteFacts(**values)
