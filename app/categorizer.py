"""
categorizer.py - automatic categorization of expenses (processing engine, part 1).

Owner: Member D (Processing engine and Tests)

HOW IT WORKS (rule-based, no AI, fully explainable)
1. Every category has KEYWORDS, stored in the table `category_rules`.
   Example: "rewe" -> Food, "deutsche bahn" -> Transit, "netflix" -> Entertainment.
2. To categorize a description such as "REWE Markt GmbH Berlin", we
   NORMALIZE it ("rewe markt gmbh berlin") and look for a keyword that
   appears in it as a whole word.
3. Which rule wins if several match?
      a) the user's own (learned) rules beat the built-in rules,
      b) a longer keyword beats a shorter one ("deutsche bahn" beats "bahn").
4. No keyword matches -> the expense goes to "Other" and the web page
   marks it "needs review".
5. LEARNING: when the user corrects a suggested category during import,
   we take the merchant word from the description (merchant_key) and save
   it as a new rule for that user. Next time it is categorized correctly.
"""
import re
from dataclasses import dataclass

# Built-in keywords, inserted into category_rules once at startup (user_id = NULL).
# Written in normalized form: lowercase, umlauts as ae/oe/ue, no punctuation.
DEFAULT_RULES: dict[str, list[str]] = {
    "Food": [
        "rewe", "edeka", "aldi", "lidl", "netto", "penny", "kaufland", "norma", "tegut", "globus",
        "restaurant", "cafe", "coffee", "starbucks", "baeckerei", "bakery", "backwerk", "mcdonalds",
        "burger king", "subway", "kfc", "pizza", "lieferando", "wolt", "uber eats", "mensa",
        "canteen", "kantine", "grocery", "supermarket", "supermarkt", "doener", "sushi",
    ],
    "Transit": [
        "deutsche bahn", "db vertrieb", "db fernverkehr", "bahn", "bvg", "mvg", "mvv", "rmv", "hvv", "vrs",
        "kvb", "vvs", "flixbus", "flixtrain", "uber", "bolt", "freenow", "taxi", "deutschlandticket",
        "tankstelle", "aral", "shell", "esso", "parking", "parken", "lufthansa",
        "ryanair", "eurowings", "train", "bus",
    ],
    "Utilities": [
        "stadtwerke", "vattenfall", "eon", "enbw", "strom", "gas", "wasser", "electricity",
        "telekom", "vodafone", "o2", "telefonica", "congstar", "1 1", "internet", "rundfunk",
        "rundfunkbeitrag", "gez", "mobilfunk", "phone",
    ],
    "Rent": ["miete", "rent", "kaltmiete", "warmmiete", "vermieter", "landlord", "wohnung", "nebenkosten"],
    "Shopping": [
        "amazon", "zalando", "ebay", "otto", "ikea", "mediamarkt", "media markt", "saturn", "h m",
        "primark", "zara", "decathlon", "tk maxx", "douglas", "rossmann", "dm drogerie", "mueller",
        "apple", "shop", "store",
    ],
    "Health": [
        "apotheke", "pharmacy", "arzt", "doctor", "zahnarzt", "dentist", "klinik", "hospital",
        "krankenkasse", "techniker", "aok", "barmer", "fitness", "gym", "mcfit", "urban sports",
        "physio", "optiker",
    ],
    "Entertainment": [
        "netflix", "spotify", "disney", "prime video", "youtube", "dazn", "kino", "cinema", "cinemaxx",
        "steam", "playstation", "xbox", "nintendo", "theater", "eventim", "concert", "konzert",
        "museum",
    ],
}

# Words that appear in many bank descriptions but say nothing about the
# merchant. merchant_key() skips them.
STOPWORDS = {
    "sepa", "lastschrift", "kartenzahlung", "karte", "girocard", "debitk", "debit", "kreditkarte",
    "visa", "mastercard", "maestro", "ueberweisung", "dauerauftrag", "gutschrift", "einzug",
    "zahlung", "payment", "purchase", "pos", "card", "online", "gmbh", "ag", "kg", "co", "und",
    "the", "and", "der", "die", "das", "fuer", "von", "bei", "mit", "eur", "euro", "sagt",
    "danke", "ref", "end", "mandat", "nr", "www", "com", "de", "filiale", "folgenr", "verfalld",
    "basislastschrift", "abbuchung", "transaction", "transfer", "standing", "order",
    "vertrieb", "deutschland", "international", "dienstleistung", "center",
}

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def normalize(text: str) -> str:
    """'REWE Markt GmbH, Berlin' -> 'rewe markt gmbh berlin'"""
    text = text.lower().translate(_UMLAUTS)
    text = re.sub(r"[^a-z0-9]+", " ", text)  # every non-letter/digit becomes a space
    return " ".join(text.split())


def merchant_key(description: str) -> str | None:
    """The first meaningful word, used as the keyword for a learned rule.

    'SEPA-Lastschrift Stadtwerke Muenchen' -> 'stadtwerke'
    """
    for word in normalize(description).split():
        if len(word) >= 3 and word not in STOPWORDS and not any(ch.isdigit() for ch in word):
            return word
    return None


@dataclass
class Rule:
    keyword: str        # normalized
    category_id: int
    learned: bool       # True = the user's own rule, False = built-in


@dataclass
class Match:
    category_id: int
    keyword: str
    source: str         # "learned" or "built-in"


class Categorizer:
    def __init__(self, rules: list[Rule]):
        # Sort once: user rules first, then longer (more specific) keywords first.
        self.rules = sorted(rules, key=lambda r: (not r.learned, -len(r.keyword)))

    def categorize(self, description: str) -> Match | None:
        # Spaces around the text and the keyword = whole-word matching:
        # keyword "bar" matches "cocktail bar" but not "barmer".
        text = f" {normalize(description)} "
        for rule in self.rules:
            if f" {rule.keyword} " in text:
                return Match(rule.category_id, rule.keyword, "learned" if rule.learned else "built-in")
        return None
