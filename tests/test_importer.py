"""Unit tests for the CSV reader and the categorizer (no database needed). Owner: Member D."""
from datetime import date
from pathlib import Path

import pytest

from app.categorizer import Categorizer, Rule, merchant_key, normalize
from app.importer import ImportFormatError, parse_amount, parse_date, parse_transactions

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"


# ---------- small parsers ----------

@pytest.mark.parametrize("text, expected", [
    ("12.50", 12.5), ("12,50", 12.5), ("-12,50", -12.5), ("12,50-", -12.5),
    ("1.234,56", 1234.56), ("1,234.56", 1234.56), ("€ 9,99", 9.99), ("(9.99)", -9.99), ("+3", 3.0),
])
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["2026-10-05", "05.10.2026", "05.10.26", "05/10/2026", "2026-10-05T14:22:00"])
def test_parse_date(text):
    assert parse_date(text) == date(2026, 10, 5)


def test_bad_values_raise():
    with pytest.raises(ValueError):
        parse_amount("abc")
    with pytest.raises(ValueError):
        parse_date("yesterday")


# ---------- whole files ----------

def test_german_bank_export():
    result = parse_transactions((SAMPLES / "bank_export_de.csv").read_bytes())
    assert result.errors == []
    assert len(result.rows) == 25
    assert result.skipped_income == 2  # salary and a refund from a friend are not expenses
    first = result.rows[0]
    assert first.expense_date == date(2026, 10, 1)
    assert first.amount == 520.0
    assert first.description.startswith("Hausverwaltung Schmidt - Miete")


def test_simple_spreadsheet_all_positive():
    result = parse_transactions((SAMPLES / "transactions_simple.csv").read_bytes())
    assert len(result.rows) == 10 and result.skipped_income == 0


def test_windows_1252_encoding_and_semicolons():
    raw = "Datum;Beschreibung;Betrag\n03.11.2026;Bäckerei Müller;-3,20\n".encode("cp1252")
    row = parse_transactions(raw).rows[0]
    assert row.description == "Bäckerei Müller" and row.amount == 3.2


def test_bad_rows_are_reported_with_line_numbers():
    raw = b"date,description,amount\n2026-11-01,Coffee,3.20\nnot-a-date,Tea,2.00\n2026-11-02,Cake,\n"
    result = parse_transactions(raw)
    assert len(result.rows) == 1
    assert [line for line, _ in result.errors] == [3, 4]


def test_file_without_header_is_rejected():
    with pytest.raises(ImportFormatError):
        parse_transactions(b"hello;world\n1;2\n")


# ---------- categorizer ----------

def test_normalize_and_merchant_key():
    assert normalize("REWE Markt GmbH, Berlin") == "rewe markt gmbh berlin"
    assert normalize("Bäckerei Müller") == "baeckerei mueller"
    assert merchant_key("SEPA-Lastschrift Stadtwerke München") == "stadtwerke"
    assert merchant_key("12345 EUR") is None


def test_whole_words_longest_and_learned_rules_win():
    food, transit, health, books = 1, 2, 3, 4
    cat = Categorizer([
        Rule("bahn", transit, False), Rule("deutsche bahn", transit, False),
        Rule("bar", food, False), Rule("rewe", food, False), Rule("rewe", books, True),
    ])
    assert cat.categorize("BARMER Krankenkasse") is None            # "bar" is not a whole word here
    assert cat.categorize("Deutsche Bahn AG").keyword == "deutsche bahn"
    match = cat.categorize("REWE Markt")
    assert match.category_id == books and match.source == "learned"
