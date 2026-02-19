use anyhow::{Context, Result};
use crate::state::{goals_path, profile_path, write_profile, Profile};
use std::fs;
use std::io::{self, Write};

fn prompt(label: &str) -> Result<String> {
    print!("{}: ", label);
    io::stdout().flush().ok();
    let mut s = String::new();
    io::stdin().read_line(&mut s)?;
    Ok(s.trim().to_string())
}

fn prompt_timezone() -> Result<String> {
    use chrono_tz::Tz;

    // For Tarive/Saksham: default to CST (America/Chicago) if empty.
    // For OSS users: keep prompting until valid.
    // If REWIND_TZ is set, use it as an override.
    if let Ok(tz) = std::env::var("REWIND_TZ") {
        let _parsed: Tz = tz
            .parse()
            .map_err(|_| anyhow::anyhow!("Invalid REWIND_TZ: {tz}"))?;
        return Ok(tz);
    }

    loop {
        let tz = prompt("Your timezone (IANA, e.g. America/Chicago) [required]")?;
        let tz = tz.trim().to_string();
        if tz.is_empty() {
            // Default for you. OSS users can just type their timezone.
            return Ok("America/Chicago".to_string());
        }
        if tz.parse::<Tz>().is_ok() {
            return Ok(tz);
        }
        println!("Timezone not recognized. Example: America/Chicago, America/Los_Angeles, Europe/London");
    }
}

fn prompt_multiline(label: &str) -> Result<Vec<String>> {
    println!("{} (enter one per line; blank line to finish)", label);
    let mut out = Vec::new();
    loop {
        print!("> ");
        io::stdout().flush().ok();
        let mut s = String::new();
        io::stdin().read_line(&mut s)?;
        let s = s.trim().to_string();
        if s.is_empty() {
            break;
        }
        out.push(s);
    }
    Ok(out)
}

pub fn run_setup() -> Result<()> {
    println!("Rewind setup\n");
    let name = prompt("Your name (optional)")?;
    let timezone = prompt_timezone()?;

    let long = prompt_multiline("LONG-TERM goals")?;
    let medium = prompt_multiline("MEDIUM-TERM goals")?;
    let short = prompt_multiline("SHORT-TERM goals")?;

    let goals_md = render_goals_md(&name, &long, &medium, &short);

    let gp = goals_path()?;
    fs::write(&gp, goals_md).with_context(|| format!("write {}", gp.display()))?;

    let tz = if timezone.trim().is_empty() {
        "America/Chicago".to_string()
    } else {
        timezone.trim().to_string()
    };

    let profile = Profile {
        created_at_utc: Some(chrono::Utc::now().to_rfc3339()),
        goals_file: gp.display().to_string(),
        timezone: tz,
    };
    write_profile(&profile)?;

    println!("\nWrote:");
    println!("- {}", gp.display());
    println!("- {}", profile_path()?.display());

    println!("\nNext recommended steps:");
    println!("- rewind auth claude-setup-token   (optional, to enable Claude OAuth via claude CLI)");
    println!("- rewind auth paste-anthropic-token (if you want direct Anthropic API calls)");
    println!("- rewind finance sync --csv amex.csv");

    Ok(())
}

fn render_goals_md(name: &str, long: &[String], medium: &[String], short: &[String]) -> String {
    let mut s = String::new();
    s.push_str("# Rewind Goals\n\n");
    if !name.trim().is_empty() {
        s.push_str(&format!("User: {}\n\n", name.trim()));
    }

    s.push_str("## Long-term\n");
    for g in long {
        s.push_str(&format!("- {}\n", g));
    }
    s.push_str("\n## Medium-term\n");
    for g in medium {
        s.push_str(&format!("- {}\n", g));
    }
    s.push_str("\n## Short-term\n");
    for g in short {
        s.push_str(&format!("- {}\n", g));
    }
    s
}
