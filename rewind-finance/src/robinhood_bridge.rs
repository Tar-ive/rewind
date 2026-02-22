use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeStatus {
    pub ok: bool,
    pub read_only: bool,
    pub python: String,
    pub robin_stocks_installed: bool,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeOrder {
    pub order_id: String,
    pub symbol: String,
    pub side: String,
    pub order_type: String,
    pub time_in_force: String,
    pub status: String,
    pub quantity: f64,
    pub filled_quantity: f64,
    pub limit_price: Option<f64>,
    pub avg_fill_price: Option<f64>,
    pub submitted_at: Option<String>,
    pub updated_at: Option<String>,
    pub raw: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeHolding {
    pub symbol: String,
    pub quantity: f64,
    pub average_buy_price: Option<f64>,
    pub raw: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeData {
    pub read_only: bool,
    pub holdings: Vec<BridgeHolding>,
    pub orders: Vec<BridgeOrder>,
}

fn script_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("scripts")
        .join("robinhood_bridge.py")
}

fn resolve_python() -> String {
    if let Ok(py) = std::env::var("RH_PYTHON") {
        if !py.trim().is_empty() {
            return py;
        }
    }

    let preferred = "/home/sadhikari/.openclaw/workspace/.venv-rh/bin/python";
    if std::path::Path::new(preferred).exists() {
        return preferred.to_string();
    }

    "python3".to_string()
}

fn run_bridge(args: &[&str]) -> Result<String> {
    let script = script_path();
    if !script.exists() {
        bail!("bridge script missing: {}", script.display());
    }

    let python = resolve_python();

    let output = Command::new(python)
        .arg(script)
        .args(args)
        .output()
        .context("failed to execute python bridge")?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if !stdout.is_empty() {
            bail!("python bridge failed: {stdout}");
        }
        bail!("python bridge failed: {stderr}");
    }

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

pub fn status() -> Result<BridgeStatus> {
    let raw = run_bridge(&["status"])?;
    serde_json::from_str(&raw).context("invalid status json from bridge")
}

pub fn fetch_holdings() -> Result<Vec<BridgeHolding>> {
    let raw = run_bridge(&["holdings"])?;
    let data: BridgeData = serde_json::from_str(&raw).context("invalid holdings json from bridge")?;
    if !data.read_only {
        bail!("bridge read-only invariant violated");
    }
    Ok(data.holdings)
}

pub fn fetch_orders(since: Option<&str>) -> Result<Vec<BridgeOrder>> {
    let mut args = vec!["orders"];
    if let Some(s) = since {
        args.push("--since");
        args.push(s);
    }
    let raw = run_bridge(&args)?;
    let data: BridgeData = serde_json::from_str(&raw).context("invalid orders json from bridge")?;
    if !data.read_only {
        bail!("bridge read-only invariant violated");
    }
    Ok(data.orders)
}

pub fn fetch_all(since: Option<&str>) -> Result<BridgeData> {
    let mut args = vec!["sync"];
    if let Some(s) = since {
        args.push("--since");
        args.push(s);
    }
    let raw = run_bridge(&args)?;
    let data: BridgeData = serde_json::from_str(&raw).context("invalid sync json from bridge")?;
    if !data.read_only {
        bail!("bridge read-only invariant violated");
    }
    Ok(data)
}
