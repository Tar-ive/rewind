"""
Chase Debit (Checking) Statement Parser for Monopoly

Parses Chase checking account statements with format:
    TRANSACTION DETAIL
           DATE        DESCRIPTION                                     AMOUNT     BALANCE
           04/22       Discover     E-Payment 8148   Web ID: ...       -15.00      53.70
"""
import re

from monopoly.banks import BankBase
from monopoly.config import StatementConfig, DateOrder
from monopoly.constants import EntryType
from monopoly.identifiers import MetadataIdentifier, TextIdentifier


class ChaseDebit(BankBase):
    """Parser for Chase Checking/Debit statements."""
    
    name = "CHASE_DEBIT"
    
    # regex for transaction line:
    # 04/22                                     Discover     E-Payment 8148         Web ID: 2510020270                                 -15.00                   53.70
    TRANSACTION_PATTERN = re.compile(
        r"^\s*"
        r"(?P<transaction_date>\d{2}/\d{2})\s+"
        r"(?P<description>.+?)\s+"
        r"(?P<amount>-?[\d,]+\.\d{2})\s+"
        r"(?P<balance>[\d,]+\.\d{2})\s*$"
    )
    
    # Header: TRANSACTION DETAIL
    # Note: Use simple regex as possible
    HEADER_PATTERN = re.compile(r"TRANSACTION\s+DETAIL")
    
    # Statement Date: April 16, 2024 through May 15, 2024
    STATEMENT_DATE_PATTERN = re.compile(
        r"(?P<statement_date>[A-Za-z]+\s+\d{1,2},\s+\d{4})\s+through\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}"
    )

    debit = StatementConfig(
        statement_type=EntryType.DEBIT,
        header_pattern=HEADER_PATTERN,
        statement_date_pattern=STATEMENT_DATE_PATTERN,
        transaction_pattern=TRANSACTION_PATTERN,
        transaction_date_order=DateOrder("MDY"),
        transaction_auto_polarity=False, # Amounts are already signed (- for debit, + for credit)
        safety_check=False, # Summary parsing is unreliable for this format
    )
    
    identifiers = [
        # Match standard Chase checking statements
        [
            MetadataIdentifier(producer="OpenText Output Transformation Engine"),
            TextIdentifier(text="CHECKING SUMMARY"),
        ],
        # Falback for other variations
        [
            TextIdentifier(text="CHASE COLLEGE CHECKING"),
        ]
    ]
    
    statement_configs = [debit]
