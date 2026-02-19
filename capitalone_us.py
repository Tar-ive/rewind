"""
Capital One US Credit Card Statement Parser for Monopoly

This module provides a custom bank parser for Capital One US credit card statements,
which have a different format than the Canadian statements supported by the base library.

US Statement Format:
    Trans Date     Post Date      Description                                         Amount
    Jul 20         Jul 22         H-E-B #455SAN MARCOSTX                                $5.82
    Jul 28         Jul 29         WALMART.COMWALMART.COMAR                            - $14.05
"""
import re

from monopoly.banks import BankBase
from monopoly.config import StatementConfig, DateOrder
from monopoly.constants import EntryType
from monopoly.identifiers import MetadataIdentifier, TextIdentifier


class CapitalOneUS(BankBase):
    """Parser for Capital One US credit card statements."""
    
    name = "CAPITAL_ONE_US"
    
    # Transaction pattern breakdown:
    # - transaction_date: "Jul 20" (MMM D or MMM DD)
    # - posting_date: "Jul 22" (MMM D or MMM DD)  
    # - description: "H-E-B #455SAN MARCOSTX" (any text until amount)
    # - polarity: "-" for credits/payments (optional)
    # - amount: "$5.82" or "$1,234.56"
    TRANSACTION_PATTERN = re.compile(
        r"^\s*"
        r"(?P<transaction_date>[A-Za-z]{3}\s+\d{1,2})\s+"
        r"(?P<posting_date>[A-Za-z]{3}\s+\d{1,2})\s+"
        r"(?P<description>.+?)\s+"
        r"(?P<polarity>-)?\s*\$"
        r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s*$"
    )
    
    # Header pattern to identify transaction sections
    HEADER_PATTERN = re.compile(
        r"Trans\s+Date\s+Post\s+Date\s+Description\s+Amount"
    )
    
    # Statement date pattern: "Jul 19, 2024 - Aug 18, 2024" (extract first date)
    STATEMENT_DATE_PATTERN = re.compile(
        r"(?P<statement_date>[A-Za-z]{3}\s+\d{1,2},\s+\d{4})\s+-\s+[A-Za-z]{3}\s+\d{1,2},\s+\d{4}"
    )
    
    credit = StatementConfig(
        statement_type=EntryType.CREDIT,
        header_pattern=HEADER_PATTERN,
        statement_date_pattern=STATEMENT_DATE_PATTERN,
        transaction_pattern=TRANSACTION_PATTERN,
        transaction_date_order=DateOrder("MDY"),  # US uses Month-Day-Year
    )
    
    # Identifiers to match Capital One US statements
    # PDFs can have different metadata depending on how they were generated
    identifiers = [
        # Match newer PDFium-generated statements (2024+)
        [
            MetadataIdentifier(creator="PDFium"),
            TextIdentifier(text="capitalone.com"),
        ],
        # Match older OpenText statements without "Canada" in title
        [
            MetadataIdentifier(author="Registered to: CAPITAL1", creator="OpenText Exstream"),
            TextIdentifier(text="capitalone.com"),
        ],
    ]
    
    statement_configs = [credit]
