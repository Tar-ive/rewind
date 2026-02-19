# Statements: supported formats + schemas

Rewind works by ingesting statements → normalizing transactions → extracting signals.

## AMEX (CSV export)

### How to get it
- American Express web app: download/export transactions as CSV.

### Expected columns
Your `amex.csv` in this repo matches AMEX’s export format:

Header row:
- `Date` (MM/DD/YYYY)
- `Description`
- `Amount` (positive charges)
- `Extended Details` (multiline)
- `Appears On Your Statement As`
- `Address`
- `City/State`
- `Zip Code`
- `Country`
- `Reference`
- `Category` (e.g. `Restaurant-Restaurant`)

Notes:
- The file often contains leading blank rows before the header.
- Fields may contain embedded newlines (CSV quoting). Use a real CSV parser.

## Capital One US (PDF)

### Current status
- Parser scaffold exists in Rust: `rewind-ingest/src/parsers/capital_one_us.rs`
- It currently expects **PDF-to-text output** (not raw PDF bytes).

### Extracted-text expected shape
The parser looks for a header line like:

`Trans Date     Post Date      Description                                         Amount`

and then rows like:
- `Jul 20         Jul 22         H-E-B #455SAN MARCOSTX                                $5.82`
- `Jul 28         Jul 29         WALMART.COMWALMART.COMAR                            - $14.05`

### Next step
Implement a robust PDF→text extractor pipeline (may require multiple fallbacks).

## General advice
- Prefer deterministic parsing and only use LLM intent classification on ambiguous transactions.
- Keep per-bank parsers isolated and versioned.
