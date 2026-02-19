//! Chase Debit (Checking) statement parser (text)
//!
//! Port target: `chase_debit.py` in repo root.
//!
//! Expected extracted-text section:
//!   TRANSACTION DETAIL
//!          DATE        DESCRIPTION                                     AMOUNT     BALANCE
//!          04/22       Discover     E-Payment 8148   Web ID: ...       -15.00      53.70

use anyhow::Result;
use chrono::NaiveDate;
use regex::Regex;

use crate::types::StatementTransaction;

fn parse_mm_dd_with_year(s: &str, year: i32) -> Option<NaiveDate> {
    let s = s.trim();
    let mut it = s.split('/');
    let m: u32 = it.next()?.parse().ok()?;
    let d: u32 = it.next()?.parse().ok()?;
    NaiveDate::from_ymd_opt(year, m, d)
}

/// Parse extracted statement text into Chase debit transactions.
///
/// `statement_year` is required because rows are MM/DD.
pub fn parse_chase_debit_text(text: &str, statement_year: i32) -> Result<Vec<StatementTransaction>> {
    let header_re = Regex::new(r"TRANSACTION\s+DETAIL")?;

    // DATE DESCRIPTION AMOUNT BALANCE
    let txn_re = Regex::new(concat!(
        r"^\s*(?P<date>\d{2}/\d{2})\s+",
        r"(?P<desc>.+?)\s+",
        r"(?P<amount>-?[\d,]+\.\d{2})\s+",
        r"(?P<balance>[\d,]+\.\d{2})\s*$"
    ))?;

    let mut in_section = false;
    let mut out = Vec::new();

    for line in text.lines() {
        if !in_section {
            if header_re.is_match(line) {
                in_section = true;
            }
            continue;
        }

        if let Some(caps) = txn_re.captures(line) {
            let date = match parse_mm_dd_with_year(&caps["date"], statement_year) {
                Some(d) => d,
                None => continue,
            };

            let amount: f64 = caps["amount"].replace(",", "").parse().unwrap_or(0.0);
            let balance: f64 = caps["balance"].replace(",", "").parse().unwrap_or(0.0);

            out.push(StatementTransaction {
                trans_date: date,
                post_date: None,
                description: caps["desc"].trim().to_string(),
                amount,
                balance: Some(balance),
                currency: "USD".to_string(),
                raw_category: None,
            });
        }
    }

    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_chase_debit_basic() {
        let text = r#"
TRANSACTION DETAIL
       DATE        DESCRIPTION                                     AMOUNT     BALANCE
       04/22       Discover     E-Payment 8148   Web ID: 123       -15.00      53.70
       04/23       PAYROLL ACME INC                                100.00     153.70
"#;

        let txns = parse_chase_debit_text(text, 2026).unwrap();
        assert_eq!(txns.len(), 2);
        assert_eq!(txns[0].amount, -15.00);
        assert_eq!(txns[0].balance, Some(53.70));
        assert_eq!(txns[1].amount, 100.00);
        assert_eq!(txns[1].balance, Some(153.70));
    }
}
