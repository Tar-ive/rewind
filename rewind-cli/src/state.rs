use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

pub fn rewind_home() -> Result<PathBuf> {
    let home = std::env::var("HOME").context("HOME is not set")?;
    Ok(PathBuf::from(home).join(".rewind"))
}

pub fn ensure_rewind_home() -> Result<PathBuf> {
    let dir = rewind_home()?;
    fs::create_dir_all(&dir).with_context(|| format!("create {}", dir.display()))?;
    Ok(dir)
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Profile {
    pub created_at_utc: Option<String>,
    pub goals_file: String,
    #[serde(default = "default_timezone")]
    pub timezone: String,
}

fn default_timezone() -> String {
    "America/Chicago".to_string()
}

pub fn goals_path() -> Result<PathBuf> {
    Ok(ensure_rewind_home()?.join("goals.md"))
}

pub fn profile_path() -> Result<PathBuf> {
    Ok(ensure_rewind_home()?.join("profile.json"))
}

pub fn write_profile(profile: &Profile) -> Result<()> {
    let p = profile_path()?;
    let json = serde_json::to_string_pretty(profile)?;
    fs::write(&p, json).with_context(|| format!("write {}", p.display()))?;
    Ok(())
}

pub fn read_profile() -> Result<Profile> {
    let p = profile_path()?;
    if !p.exists() {
        return Ok(Profile {
            created_at_utc: None,
            goals_file: goals_path()?.display().to_string(),
            timezone: "America/Chicago".to_string(),
        });
    }
    let s = fs::read_to_string(&p).with_context(|| format!("read {}", p.display()))?;
    Ok(serde_json::from_str(&s)?)
}

pub fn read_goals_md(path: &Path) -> Result<String> {
    Ok(fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?)
}
