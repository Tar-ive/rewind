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

    let long = prompt_multiline("LONG-TERM goals")?;
    let medium = prompt_multiline("MEDIUM-TERM goals")?;
    let short = prompt_multiline("SHORT-TERM goals")?;

    let goals_md = render_goals_md(&name, &long, &medium, &short);

    let gp = goals_path()?;
    fs::write(&gp, goals_md).with_context(|| format!("write {}", gp.display()))?;

    let profile = Profile {
        created_at_utc: Some(chrono::Utc::now().to_rfc3339()),
        goals_file: gp.display().to_string(),
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
