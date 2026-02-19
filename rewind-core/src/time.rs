//! Time utilities: accurate timezone-aware deadlines.

use anyhow::Result;
use chrono::{DateTime, NaiveDateTime, TimeZone, Utc};
use chrono_tz::Tz;

/// Parse a deadline like "2026-02-20 23:59" in an IANA tz like "America/Chicago",
/// returning UTC.
pub fn parse_local_deadline_to_utc(local: &str, tz: &str) -> Result<DateTime<Utc>> {
    let tz: Tz = tz
        .parse()
        .map_err(|_| anyhow::anyhow!("invalid timezone: {tz}"))?;

    let ndt = NaiveDateTime::parse_from_str(local, "%Y-%m-%d %H:%M")
        .map_err(|e| anyhow::anyhow!("invalid local datetime '{local}': {e}"))?;

    let local_dt = tz
        .from_local_datetime(&ndt)
        .single()
        .ok_or_else(|| anyhow::anyhow!("ambiguous or invalid local time (DST?): {local} {tz}"))?;

    Ok(local_dt.with_timezone(&Utc))
}

/// Helper: format a UTC time into RFC3339.
pub fn to_rfc3339_utc(dt: DateTime<Utc>) -> String {
    dt.to_rfc3339()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_chicago_deadline() {
        // Feb is CST (UTC-6)
        let utc = parse_local_deadline_to_utc("2026-02-20 23:59", "America/Chicago").unwrap();
        assert_eq!(utc.to_rfc3339(), "2026-02-21T05:59:00+00:00");
    }
}
