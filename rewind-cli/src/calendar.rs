use anyhow::{bail, Context, Result};
use chrono::{DateTime, Duration, Timelike, Utc};
use chrono_tz::Tz;
use rewind_core::{ShortTermScheduler, Task};
use std::io::Write;

/// Round up to the next 15-minute boundary.
fn ceil_to_quarter_hour(dt: DateTime<Tz>) -> DateTime<Tz> {
    let minute = dt.minute();
    let add = match minute % 15 {
        0 => 0,
        r => 15 - r,
    };
    let mut out = dt + Duration::minutes(add.into());
    out = out.with_second(0).unwrap().with_nanosecond(0).unwrap();
    out
}

pub struct CalendarEvent {
    pub start_utc: DateTime<Utc>,
    pub end_utc: DateTime<Utc>,
    pub summary: String,
    pub description: String,
}

/// Convert an ordered schedule of tasks into time-blocked events.
///
/// We keep this deterministic: no LLM, no fancy optimization yet.
pub fn tasks_to_timeblocks(
    ordered: &[Task],
    tz: Tz,
    now_utc: DateTime<Utc>,
    prefix: &str,
) -> Vec<CalendarEvent> {
    let mut events = Vec::new();

    let start_local = ceil_to_quarter_hour(now_utc.with_timezone(&tz));
    let mut cursor_local = start_local;

    for t in ordered {
        let minutes = t.estimated_duration.max(10) as i64;
        let end_local = cursor_local + Duration::minutes(minutes);

        events.push(CalendarEvent {
            start_utc: cursor_local.with_timezone(&Utc),
            end_utc: end_local.with_timezone(&Utc),
            summary: format!("{}{}", prefix, t.title),
            description: format!(
                "TaskId: {}\nPriority: {:?}\nEnergy: {}\nCognitive: {}\nUrgency: {}\n",
                t.id, t.priority, t.energy_cost, t.cognitive_load, t.deadline_urgency
            ),
        });

        cursor_local = end_local;
    }

    events
}

/// Emit a minimal ICS calendar containing VEVENT blocks.
///
/// Notes:
/// - DTSTART/DTEND are UTC.
/// - We avoid UID stability for now (v0); we can add stable UIDs later.
pub fn events_to_ics(events: &[CalendarEvent]) -> String {
    let mut s = String::new();
    s.push_str("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Rewind//EN\n");

    for (i, e) in events.iter().enumerate() {
        let dtstart = e.start_utc.format("%Y%m%dT%H%M%SZ");
        let dtend = e.end_utc.format("%Y%m%dT%H%M%SZ");

        s.push_str("BEGIN:VEVENT\n");
        s.push_str(&format!("UID:rewind-{}@rewind\n", i));
        s.push_str(&format!("DTSTART:{}\n", dtstart));
        s.push_str(&format!("DTEND:{}\n", dtend));
        s.push_str(&format!("SUMMARY:{}\n", escape_ics(&e.summary)));
        s.push_str(&format!("DESCRIPTION:{}\n", escape_ics(&e.description)));
        s.push_str("END:VEVENT\n");
    }

    s.push_str("END:VCALENDAR\n");
    s
}

fn escape_ics(s: &str) -> String {
    s.replace('\\', "\\\\")
        .replace('\n', "\\n")
        .replace(',', "\\,")
        .replace(';', "\\;")
}

/// Push ICS to Google Calendar using gcalcli import.
///
/// This requires `gcalcli` installed and authenticated on the machine.
pub fn push_ics_via_gcalcli(ics: &str, calendar: Option<&str>) -> Result<()> {
    // Verify binary exists
    let gcalcli = which::which("gcalcli").ok();
    if gcalcli.is_none() {
        bail!(
            "gcalcli is not installed. Install it, authenticate, then retry.\n\nmacOS (brew):  brew install gcalcli\nUbuntu (pipx): pipx install gcalcli\n\nOr use: rewind calendar export-ics > schedule.ics"
        );
    }

    let mut cmd = std::process::Command::new("gcalcli");
    cmd.arg("import");
    if let Some(cal) = calendar {
        cmd.args(["--calendar", cal]);
    }

    let mut child = cmd
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::inherit())
        .stderr(std::process::Stdio::inherit())
        .spawn()
        .context("spawning gcalcli import")?;

    {
        let stdin = child.stdin.as_mut().context("no stdin")?;
        stdin
            .write_all(ics.as_bytes())
            .context("writing ICS to gcalcli")?;
    }

    let status = child.wait().context("waiting on gcalcli")?;
    if !status.success() {
        bail!("gcalcli import failed: {status}");
    }

    Ok(())
}

/// Helper: order tasks using STS, producing a concrete execution schedule.
pub fn order_tasks_via_sts(mut sts: ShortTermScheduler, energy_level: i32) -> Vec<Task> {
    let mut ordered = Vec::new();
    while let Some(t) = sts.dequeue(energy_level) {
        ordered.push(t);
    }
    ordered
}
