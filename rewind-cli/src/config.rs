use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

use crate::state::ensure_rewind_home;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    pub llm: LlmSection,
    pub chat: ChatSection,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmSection {
    pub provider: String,
    pub model: String,
    pub base_url: String,
    pub temperature: f32,

    /// For provider = "codex-cli": command to execute (default: "codex")
    pub codex_command: Option<String>,
    /// For provider = "codex-cli": extra args to pass before the message (optional)
    pub codex_args: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatSection {
    pub stream: bool,
    pub max_turns_context: usize,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            llm: LlmSection {
                provider: "openai".to_string(),
                // Accept OpenClaw-style aliases too. We'll normalize when calling the API.
                model: "openai-codex/gpt-5.1".to_string(),
                base_url: "https://api.openai.com".to_string(),
                temperature: 0.4,
                codex_command: Some("codex".to_string()),
                codex_args: None,
            },
            chat: ChatSection {
                stream: true,
                max_turns_context: 12,
            },
        }
    }
}

pub fn config_path() -> Result<PathBuf> {
    Ok(ensure_rewind_home()?.join("config.toml"))
}

pub fn load_config() -> Result<Config> {
    let p = config_path()?;
    if !p.exists() {
        return Ok(Config::default());
    }
    let s = fs::read_to_string(&p).with_context(|| format!("read {}", p.display()))?;
    Ok(toml::from_str(&s).context("parse config.toml")?)
}

pub fn save_config(cfg: &Config) -> Result<()> {
    let p = config_path()?;
    let s = toml::to_string_pretty(cfg).context("serialize config")?;
    fs::write(&p, s).with_context(|| format!("write {}", p.display()))?;
    Ok(())
}

pub fn init_config() -> Result<()> {
    let p = config_path()?;
    if p.exists() {
        println!("Config already exists: {}", p.display());
        return Ok(());
    }
    let cfg = Config::default();
    save_config(&cfg)?;
    println!("Wrote {}", p.display());
    Ok(())
}

/// Normalize model names.
/// - Accept `openai-codex/gpt-5.1` and return `gpt-5.1` for OpenAI API.
pub fn normalize_openai_model(model: &str) -> String {
    model
        .strip_prefix("openai-codex/")
        .unwrap_or(model)
        .to_string()
}
