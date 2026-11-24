"""
importer.py - reads a bank or spreadsheet export (CSV) into clean rows
(processing engine, part 2).

Owner: Member D (Processing engine and Tests)

Banks export CSV files in many slightly different shapes. This module
handles the common differences so the user does not have to edit the file:

  difference                 examples we accept
  -------------------------  ---------------------------------------------
  separator                  ;  ,  tab  |
  text encoding              UTF-8, Windows-1252 (common for German banks)
  extra lines before header  bank name, account number, date range ...
  column names               "Date" / "Datum" / "Buchungstag" ...
  number format              12.50   12,50   1.234,56   1,234.56   -12,50
  date format                2026-10-05   05.10.2026   05.10.26   05/10/2026
  sign of expenses           negative (bank) or positive (own spreadsheet)

The result is a list of ParsedRow plus a list of errors with line numbers.
Categorizing is NOT done here; that is categorizer.py's job.
"""
import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime

from .categorizer import normalize

MAX_ROWS = 5000

# Possible names for each column (already normalized), most preferred first.
COLUMN_ALIASES = {
    "date": ["date", "datum", "buchungstag", "buchungsdatum", "booking date", "transaction date",
             "posting date", "wertstellung", "valutadatum", "value date"],
    "description": ["description", "verwendungszweck", "beschreibung", "details", "purpose", "memo",
                    "reference", "text", "buchungstext"],
    "payee": ["payee", "merchant", "name", "empfaenger", "zahlungsempfaenger", "zahlungsempfaenger in",
              "beguenstigter zahlungspflichtiger", "auftraggeber beguenstigter", "beguenstigter",
              "name zahlungsbeteiligter", "counterparty"],
    "amount": ["amount", "betrag", "betrag eur", "betrag euro", "amount eur", "umsatz", "umsatz in eur",
               "value"],
    "debit": ["debit", "soll", "ausgabe", "withdrawal", "paid out"],
    "category": ["category", "kategorie"],
}

DATE_FORMATS = ["%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y.%m.%d"]


@dataclass
class ParsedRow:
    line: int                    # line number in the file, for messages
    expense_date: date
    description: str
    amount: float                # always positive
    category_hint: str | None    # category name if the file had a category column


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)
    skipped_income: int = 0


class ImportFormatError(ValueError):
    """The file cannot be read at all (no header row found, empty file...)."""


# ---------------- small parsers ----------------

def decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")  # never fails


def parse_amount(text: str) -> float:
    """'1.234,56' -> 1234.56   '-12,50' -> -12.5   '12,50-' -> -12.5   '(9.99)' -> -9.99"""
    s = text.strip().replace(" ", "").replace(" ", "")
    for symbol in ("€", "EUR", "eur", "$", "£"):
        s = s.replace(symbol, "")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    if s.endswith("-"):
        negative, s = True, s[:-1]
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("-"):
        negative, s = not negative, s[1:]
    if not s:
        raise ValueError("empty amount")

    if "," in s and "." in s:
        # Whichever comes LAST is the decimal separator.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # 1.234,56
        else:
            s = s.replace(",", "")                     # 1,234.56
    elif "," in s:
        whole, _, decimals = s.rpartition(",")
        s = f"{whole.replace(',', '')}.{decimals}" if len(decimals) <= 2 else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")                         # 1.234.567
    value = float(s)
    return -value if negative else value


def parse_date(text: str) -> date:
    s = text.strip().split("T")[0].split(" ")[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unknown date format '{text.strip()}'")


# ---------------- header detection ----------------

def find_columns(header: list[str]) -> dict[str, int]:
    """Map our column names to positions in this header row."""
    names = [normalize(cell) for cell in header]
    found = {}
    for column, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in names:
                found[column] = names.index(alias)
                break
    return found


def is_header(columns: dict[str, int]) -> bool:
    return "date" in columns and ("amount" in columns or "debit" in columns) and (
        "description" in columns or "payee" in columns
    )


def locate_table(text: str) -> tuple[list[list[str]], int, dict[str, int]]:
    """Try each separator; return (all rows, header index, columns) for the first that works."""
    for delimiter in (";", ",", "\t", "|"):
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        for index, row in enumerate(rows[:30]):  # the header is within the first 30 lines
            columns = find_columns(row)
            if is_header(columns):
                return rows, index, columns
    raise ImportFormatError(
        "Could not find the header row. The file needs columns for a date, a description "
        "(or payee) and an amount, e.g. 'date,description,amount'."
    )


# ---------------- main function ----------------

def parse_transactions(raw: bytes) -> ParseResult:
    text = decode(raw)
    if not text.strip():
        raise ImportFormatError("The file is empty.")
    rows, header_index, col = locate_table(text)

    def cell(row: list[str], name: str) -> str:
        i = col.get(name)
        return row[i].strip() if i is not None and i < len(row) else ""

    candidates = []  # (line, date, description, signed amount, category hint)
    result = ParseResult()
    for offset, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        if not any(c.strip() for c in row):
            continue  # blank line
        if len(candidates) >= MAX_ROWS:
            result.errors.append((offset, f"Stopped after {MAX_ROWS} rows."))
            break
        try:
            day = parse_date(cell(row, "date"))
            if "amount" in col:
                amount = parse_amount(cell(row, "amount"))
            else:  # separate debit column: a value there is money going out
                debit = cell(row, "debit")
                if not debit:
                    result.skipped_income += 1
                    continue
                amount = -abs(parse_amount(debit))
        except ValueError as err:
            result.errors.append((offset, str(err)))
            continue

        payee, purpose = cell(row, "payee"), cell(row, "description")
        if payee and purpose and normalize(payee) not in normalize(purpose):
            description = f"{payee} - {purpose}"
        else:
            description = purpose or payee
        description = " ".join(description.split())[:200]
        if not description:
            result.errors.append((offset, "missing description"))
            continue
        candidates.append((offset, day, description, amount, cell(row, "category") or None))

    # Bank exports: expenses are negative, income positive -> keep only the negatives.
    # Own spreadsheets: usually all positive -> keep everything.
    has_negatives = any(c[3] < 0 for c in candidates)
    for line, day, description, amount, hint in candidates:
        if amount == 0 or (has_negatives and amount > 0):
            result.skipped_income += 1
            continue
        result.rows.append(ParsedRow(line, day, description, round(abs(amount), 2), hint))
    return result
