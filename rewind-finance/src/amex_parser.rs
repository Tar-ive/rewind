//! Parse AMEX CSV statement exports into typed transactions.
//!
//! AMEX CSVs have 6 blank rows, then:
//! Date,Description,Amount,Extended Details,Appears On Your Statement As,
//! Address,City/State,Zip Code,Country,Reference,Category

use anyhow::{Context, Result};
use chrono::NaiveDate;
use serde::{Deserialize, Serialize};
use std::path::Path;

/// A raw AMEX transaction parsed from CSV
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AmexTransaction {
    pub date: NaiveDate,
    pub description: String,
    pub amount: f64,
    pub address: String,
    pub city_state: String,
    pub zip_code: String,
    pub country: String,
    pub reference: String,
    pub amex_category: String,
}

impl AmexTransaction {
    /// Top-level AMEX category (before the hyphen)
    pub fn category_group(&self) -> &str {
        self.amex_category
            .split('-')
            .next()
            .unwrap_or(&self.amex_category)
            .trim()
    }

    /// Sub-category (after the hyphen)
    pub fn category_sub(&self) -> &str {
        self.amex_category
            .split_once('-')
            .map(|(_, sub)| sub.trim())
            .unwrap_or("")
    }
}

/// Parse an AMEX CSV file, returning all valid transactions.
/// Skips the leading blank rows and header automatically.
pub fn parse_amex_csv(path: impl AsRef<Path>) -> Result<Vec<AmexTransaction>> {
    let mut rdr = csv::ReaderBuilder::new()
        .flexible(true)
        .has_headers(false)
        .from_path(path.as_ref())
        .with_context(|| format!("opening {}", path.as_ref().display()))?;

    let mut txns = Vec::new();
    let mut header_found = false;

    for result in rdr.records() {
        let record = result?;
        // Skip until we find the header row
        if !header_found {
            if record.get(0).map(|s| s.trim()) == Some("Date") {
                header_found = true;
            }
            continue;
        }

        // Parse data rows
        let date_str = record.get(0).unwrap_or("").trim();
        if date_str.is_empty() {
            continue;
        }

        let date = match NaiveDate::parse_from_str(date_str, "%m/%d/%Y") {
            Ok(d) => d,
            Err(_) => continue, // skip unparseable rows
        };

        let amount: f64 = record
            .get(2)
            .unwrap_or("0")
            .trim()
            .parse()
            .unwrap_or(0.0);

        txns.push(AmexTransaction {
            date,
            description: record.get(1).unwrap_or("").trim().to_string(),
            amount,
            address: record.get(5).unwrap_or("").trim().to_string(),
            city_state: record.get(6).unwrap_or("").trim().to_string(),
            zip_code: record.get(7).unwrap_or("").trim().to_string(),
            country: record.get(8).unwrap_or("").trim().to_string(),
            reference: record.get(9).unwrap_or("").trim().to_string(),
            amex_category: record.get(10).unwrap_or("").trim().to_string(),
        });
    }

    Ok(txns)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn amex_path() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .join("amex.csv")
    }

    #[test]
    fn test_parse_real_amex() {
        let txns = parse_amex_csv(amex_path()).expect("should parse amex.csv");
        assert!(txns.len() >= 400, "expected 400+ txns, got {}", txns.len());

        // First transaction should be 02/16/2026
        let first = &txns[0];
        assert_eq!(first.date, NaiveDate::from_ymd_opt(2026, 2, 16).unwrap());
        assert!(first.description.contains("CLIPPER"));
        assert_eq!(first.amount, 10.0);
        assert_eq!(first.amex_category, "Other-Government Services");
    }

    #[test]
    fn test_category_group_and_sub() {
        let txns = parse_amex_csv(amex_path()).unwrap();
        let restaurant = txns.iter().find(|t| t.amex_category.contains("Restaurant-Restaurant")).unwrap();
        assert_eq!(restaurant.category_group(), "Restaurant");
        assert_eq!(restaurant.category_sub(), "Restaurant");

        let grocery = txns.iter().find(|t| t.amex_category.contains("Groceries")).unwrap();
        assert_eq!(grocery.category_group(), "Merchandise & Supplies");
        assert_eq!(grocery.category_sub(), "Groceries");
    }

    #[test]
    fn test_date_range() {
        use chrono::Datelike;
        let txns = parse_amex_csv(amex_path()).unwrap();
        let min = txns.iter().map(|t| t.date).min().unwrap();
        let max = txns.iter().map(|t| t.date).max().unwrap();
        // Should span May 2025 to Feb 2026
        assert_eq!(min.year(), 2025);
        assert_eq!(max.year(), 2026);
    }

    #[test]
    fn test_known_transactions() {
        let txns = parse_amex_csv(amex_path()).unwrap();

        // ElevenLabs subscription
        let eleven = txns.iter().find(|t| t.description.contains("ELEVENLABS")).unwrap();
        assert_eq!(eleven.amount, 5.33);
        assert_eq!(eleven.amex_category, "Merchandise & Supplies-Computer Supplies");

        // Wakaba restaurant
        let wakaba = txns.iter().find(|t| t.description.contains("WAKABA")).unwrap();
        assert_eq!(wakaba.amount, 37.30);
        assert!(wakaba.amex_category.contains("Restaurant"));
    }
}
