//! Capital One US statement parser (scaffold)
//!
//! Port target: `capitalone_us.py` in repo root.
//!
//! Expected text rows after PDF-to-text:
//!   Trans Date     Post Date      Description                                         Amount
//!   Jul 20         Jul 22         H-E-B #455SAN MARCOSTX                                $5.82
//!   Jul 28         Jul 29         WALMART.COMWALMART.COMAR                            - $14.05

use anyhow::Result;
use chrono::NaiveDate;
use regex::Regex;

use crate::types::StatementTransaction;

fn parse_mmm_dd_with_year(s: &str, year: i32) -> Option<NaiveDate> {
    // Example: "Jul 20"
    let s = s.trim();
    let parts: Vec<_> = s.split_whitespace().collect();
    if parts.len() != 2 {
        return None;
    }
    let month_str = parts[0];
    let day: u32 = parts[1].parse().ok()?;

    let month = match month_str {
        "Jan" => 1,
        "Feb" => 2,
        "Mar" => 3,
        "Apr" => 4,
        "May" => 5,
        "Jun" => 6,
        "Jul" => 7,
        "Aug" => 8,
        "Sep" => 9,
        "Oct" => 10,
        "Nov" => 11,
        "Dec" => 12,
        _ => return None,
    };

    NaiveDate::from_ymd_opt(year, month, day)
}

/// Parse extracted statement text into transactions.
///
/// `statement_year` is required because transaction rows only include MMM DD.
pub fn parse_capital_one_us_text(text: &str, statement_year: i32) -> Result<Vec<StatementTransaction>> {
    let header_re = Regex::new(r"Trans\s+Date\s+Post\s+Date\s+Description\s+Amount")?;
    let txn_re = Regex::new(concat!(
        r"^\s*(?P<trans>[A-Za-z]{3}\s+\d{1,2})\s+",
        r"(?P<post>[A-Za-z]{3}\s+\d{1,2})\s+",
        r"(?P<desc>.+?)\s+",
        r"(?P<polarity>-)?\s*\$(?P<amt>\d{1,3}(?:,\d{3})*\.\d{2})\s*$"
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
            let trans = parse_mmm_dd_with_year(&caps["trans"], statement_year);
            let post = parse_mmm_dd_with_year(&caps["post"], statement_year);
            if trans.is_none() {
                continue;
            }

            let amt_raw = caps["amt"].replace(",", "");
            let mut amount: f64 = amt_raw.parse().unwrap_or(0.0);
            if caps.name("polarity").is_some() {
                amount = -amount;
            }

            out.push(StatementTransaction {
                trans_date: trans.unwrap(),
                post_date: post,
                description: caps["desc"].trim().to_string(),
                amount,
                balance: None,
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
    fn test_parses_basic_rows() {
        let text = r#"
Trans Date     Post Date      Description                                         Amount
Jul 20         Jul 22         H-E-B #455SAN MARCOSTX                                $5.82
Jul 28         Jul 29         WALMART.COMWALMART.COMAR                            - $14.05
"#;

        let txns = parse_capital_one_us_text(text, 2024).unwrap();
        assert_eq!(txns.len(), 2);
        assert_eq!(txns[0].amount, 5.82);
        assert_eq!(txns[1].amount, -14.05);
        assert!(txns[0].description.contains("H-E-B"));
    }
}
