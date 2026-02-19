use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{self, Write};

use crate::state::ensure_rewind_home;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AuthState {
    pub anthropic_token: Option<String>,
    pub openai_api_key: Option<String>,
}

fn auth_path() -> Result<std::path::PathBuf> {
    Ok(ensure_rewind_home()?.join("auth.json"))
}

pub fn load_auth() -> Result<AuthState> {
    let p = auth_path()?;
    if !p.exists() {
        return Ok(AuthState::default());
    }
    let s = fs::read_to_string(&p).with_context(|| format!("read {}", p.display()))?;
    Ok(serde_json::from_str(&s)?)
}

pub fn save_auth(auth: &AuthState) -> Result<()> {
    let p = auth_path()?;
    let s = serde_json::to_string_pretty(auth)?;
    fs::write(&p, s).with_context(|| format!("write {}", p.display()))?;
    Ok(())
}

fn prompt_secret(label: &str) -> Result<String> {
    // Minimal portable secret prompt: just stdin.
    // (We can switch to rpassword later.)
    print!("{}: ", label);
    io::stdout().flush().ok();
    let mut s = String::new();
    io::stdin().read_line(&mut s)?;
    Ok(s.trim().to_string())
}

pub fn anthropic_paste_token() -> Result<()> {
    let mut auth = load_auth()?;
    let token = prompt_secret("Paste Anthropic token (starts with sk-ant-)")?;
    if !token.starts_with("sk-ant-") {
        bail!("token didn't look like an Anthropic token (expected prefix sk-ant-)");
    }
    auth.anthropic_token = Some(token);
    save_auth(&auth)?;
    println!("Saved Anthropic token to ~/.rewind/auth.json");
    Ok(())
}

pub fn openai_paste_api_key() -> Result<()> {
    let mut auth = load_auth()?;
    let key = prompt_secret("Paste OpenAI API key (starts with sk-)")?;
    if !key.starts_with("sk-") {
        bail!("key didn't look like an OpenAI API key (expected prefix sk-)");
    }
    auth.openai_api_key = Some(key);
    save_auth(&auth)?;
    println!("Saved OpenAI API key to ~/.rewind/auth.json");
    Ok(())
}

pub fn claude_setup_token() -> Result<()> {
    // We intentionally do NOT depend on OpenClaw.
    // This uses the Claude Code CLI when installed.
    let status = std::process::Command::new("claude")
        .args(["setup-token"])
        .stdin(std::process::Stdio::inherit())
        .stdout(std::process::Stdio::inherit())
        .stderr(std::process::Stdio::inherit())
        .status();

    match status {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            bail!(
                "Claude CLI not found. Install it, then retry.\n\nInstall (recommended):\n  npm i -g @anthropic-ai/claude-code\n\nOr skip setup-token and run:\n  rewind auth paste-anthropic-token"
            );
        }
        Err(e) => return Err(e).context("running claude setup-token"),
        Ok(s) if !s.success() => bail!("claude setup-token failed: {s}"),
        Ok(_) => {}
    }

    println!("\nClaude setup-token completed.");
    println!("If you want Rewind to call Anthropic directly, store the token:");
    println!("  rewind auth paste-anthropic-token");
    Ok(())
}
