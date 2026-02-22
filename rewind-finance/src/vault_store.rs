use crate::robinhood_bridge::{BridgeHolding, BridgeOrder};
use anyhow::{Context, Result};
use chrono::Utc;
use serde_json::json;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;

fn vault_root() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    PathBuf::from(home)
        .join(".rewind")
        .join("vault")
        .join("finance")
        .join("robinhood")
}

fn ensure_dirs() -> Result<()> {
    fs::create_dir_all(vault_root().join("raw").join("orders"))?;
    fs::create_dir_all(vault_root().join("holdings"))?;
    Ok(())
}

pub fn write_raw_orders_snapshot(orders: &[BridgeOrder]) -> Result<PathBuf> {
    ensure_dirs()?;
    let ts = Utc::now().format("%Y-%m-%dT%H%M%SZ").to_string();
    let path = vault_root().join("raw").join("orders").join(format!("{ts}.json"));
    let payload = json!({
        "provider": "robinhood_unofficial_robin_stocks",
        "fetched_at": Utc::now().to_rfc3339(),
        "read_only": true,
        "orders": orders,
    });
    fs::write(&path, serde_json::to_vec_pretty(&payload)?)
        .with_context(|| format!("writing {}", path.display()))?;
    Ok(path)
}

pub fn append_normalized_orders(orders: &[BridgeOrder], raw_ref: &str) -> Result<usize> {
    ensure_dirs()?;
    let path = vault_root().join("orders.jsonl");
    let mut f = OpenOptions::new().create(true).append(true).open(&path)?;

    for o in orders {
        let row = json!({
            "provider": "robinhood_unofficial_robin_stocks",
            "account_id": "default",
            "order_id": o.order_id,
            "client_order_id": serde_json::Value::Null,
            "symbol": o.symbol,
            "asset_type": "unknown",
            "side": o.side,
            "order_type": o.order_type,
            "time_in_force": o.time_in_force,
            "status": o.status,
            "quantity": o.quantity,
            "filled_quantity": o.filled_quantity,
            "limit_price": o.limit_price,
            "avg_fill_price": o.avg_fill_price,
            "fees": 0.0,
            "submitted_at": o.submitted_at,
            "updated_at": o.updated_at,
            "source_fetched_at": Utc::now().to_rfc3339(),
            "source_hash": serde_json::Value::Null,
            "raw_ref": raw_ref,
            "read_only": true
        });
        writeln!(f, "{}", serde_json::to_string(&row)?)?;
    }

    Ok(orders.len())
}

pub fn write_holdings_snapshot(holdings: &[BridgeHolding]) -> Result<PathBuf> {
    ensure_dirs()?;
    let day = Utc::now().format("%Y-%m-%d").to_string();
    let path = vault_root().join("holdings").join(format!("{day}.json"));
    let payload = json!({
        "provider": "robinhood_unofficial_robin_stocks",
        "fetched_at": Utc::now().to_rfc3339(),
        "read_only": true,
        "holdings": holdings,
    });
    fs::write(&path, serde_json::to_vec_pretty(&payload)?)
        .with_context(|| format!("writing {}", path.display()))?;
    Ok(path)
}
