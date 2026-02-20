use anyhow::{bail, Context, Result};
use google_calendar3::api::{Event, Events};
use google_calendar3::CalendarHub;
use hyper::client::HttpConnector;
use hyper_rustls::HttpsConnector;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

use crate::calendar::CalendarEvent;
use crate::state::ensure_rewind_home;

// IMPORTANT: use the oauth2 version re-exported by google-calendar3 to avoid version mismatches.
use google_calendar3::oauth2;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GoogleOAuthClient {
    pub client_id: String,
    pub client_secret: String,
    /// Defaults to https://accounts.google.com/o/oauth2/auth
    pub auth_uri: Option<String>,
    /// Defaults to https://oauth2.googleapis.com/token
    pub token_uri: Option<String>,
    /// Defaults to ["http://localhost"]
    pub redirect_uris: Option<Vec<String>>,
}

#[derive(Debug, Clone, Deserialize)]
struct GoogleClientSecretsFile {
    installed: Option<oauth2::ApplicationSecret>,
    web: Option<oauth2::ApplicationSecret>,
}

fn oauth_client_path() -> Result<PathBuf> {
    Ok(ensure_rewind_home()?.join("google_oauth.json"))
}

fn token_cache_path() -> Result<PathBuf> {
    Ok(ensure_rewind_home()?.join("google_token_cache.json"))
}

pub fn save_oauth_client(client: &GoogleOAuthClient) -> Result<()> {
    let p = oauth_client_path()?;
    fs::write(&p, serde_json::to_string_pretty(client)?)
        .with_context(|| format!("write {}", p.display()))?;
    Ok(())
}

pub fn load_oauth_client() -> Result<GoogleOAuthClient> {
    let p = oauth_client_path()?;
    if !p.exists() {
        bail!(
            "Missing Google OAuth client config at {}. Run: rewind calendar connect",
            p.display()
        );
    }
    let s = fs::read_to_string(&p).with_context(|| format!("read {}", p.display()))?;
    Ok(serde_json::from_str(&s)?)
}

pub fn calendar_status() -> Result<()> {
    let oauth_p = oauth_client_path()?;
    let token_p = token_cache_path()?;
    println!("Google Calendar status\n");
    println!("OAuth config:  {}", if oauth_p.exists() { "OK" } else { "MISSING" });
    println!("Token cache:  {}", if token_p.exists() { "OK" } else { "MISSING" });
    println!("\nPaths:\n- {}\n- {}", oauth_p.display(), token_p.display());
    if !oauth_p.exists() {
        println!("\nNext: rewind calendar connect --client-json <path/to/client_secret.json>");
    } else if !token_p.exists() {
        println!("\nNext: rewind calendar connect (to complete OAuth in browser)");
    }
    Ok(())
}

/// Interactive connect:
/// - preferred: `--client-json client_secret_*.json` from Google Cloud Console
/// - fallback: user pastes client_id/client_secret
/// - we run OAuth installed-app flow
/// - tokens cached under ~/.rewind/google_token_cache.json
pub async fn connect_interactive(client_json: Option<PathBuf>) -> Result<()> {
    if let Some(p) = client_json {
        return connect_from_google_json(&p).await;
    }

    println!("Google Calendar connect\n");
    println!("Fast path: rewind calendar connect --client-json <client_secret.json>\n");
    println!("Fallback (manual): paste client_id + client_secret from Google Cloud Console (Desktop app).\n");

    let client_id = prompt("Paste client_id")?;
    let client_secret = prompt("Paste client_secret")?;

    if !client_id.contains('.') || client_secret.len() < 10 {
        bail!("client_id/client_secret didn't look valid");
    }

    let client = GoogleOAuthClient {
        client_id,
        client_secret,
        auth_uri: Some("https://accounts.google.com/o/oauth2/auth".to_string()),
        token_uri: Some("https://oauth2.googleapis.com/token".to_string()),
        redirect_uris: Some(vec!["http://localhost".to_string()]),
    };

    save_oauth_client(&client)?;

    // Run OAuth flow (installed app) and cache token.
    let _hub = hub_from_client(&client).await?;

    println!("\nConnected. Tokens cached at: {}", token_cache_path()?.display());
    Ok(())
}

async fn connect_from_google_json(path: &Path) -> Result<()> {
    let s = fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
    let secrets: GoogleClientSecretsFile = serde_json::from_str(&s)
        .with_context(|| format!("parse google client secrets JSON: {}", path.display()))?;

    let secret = secrets
        .installed
        .or(secrets.web)
        .ok_or_else(|| anyhow::anyhow!("client secrets JSON missing 'installed' or 'web' section"))?;

    let client = GoogleOAuthClient {
        client_id: secret.client_id,
        client_secret: secret.client_secret,
        auth_uri: Some(secret.auth_uri),
        token_uri: Some(secret.token_uri),
        redirect_uris: Some(secret.redirect_uris),
    };

    save_oauth_client(&client)?;

    println!("Saved OAuth client config to {}", oauth_client_path()?.display());

    // Run OAuth flow (installed app) and cache token.
    let _hub = hub_from_client(&client).await?;

    println!("Connected. Tokens cached at: {}", token_cache_path()?.display());
    Ok(())
}

async fn hub_from_client(
    client: &GoogleOAuthClient,
) -> Result<CalendarHub<HttpsConnector<HttpConnector>>> {
    // yup-oauth2 expects the same structure as Google "installed" client secrets.
    let installed = oauth2::ApplicationSecret {
        client_id: client.client_id.clone(),
        client_secret: client.client_secret.clone(),
        auth_uri: client
            .auth_uri
            .clone()
            .unwrap_or_else(|| "https://accounts.google.com/o/oauth2/auth".to_string()),
        token_uri: client
            .token_uri
            .clone()
            .unwrap_or_else(|| "https://oauth2.googleapis.com/token".to_string()),
        redirect_uris: client
            .redirect_uris
            .clone()
            .unwrap_or_else(|| vec!["http://localhost".to_string()]),
        ..Default::default()
    };

    let token_path = token_cache_path()?;
    let auth = oauth2::InstalledFlowAuthenticator::builder(
        installed,
        oauth2::InstalledFlowReturnMethod::HTTPRedirect,
    )
    .persist_tokens_to_disk(token_path)
    .build()
    .await
    .context("building oauth authenticator")?;

    let connector = hyper_rustls::HttpsConnectorBuilder::new()
        .with_native_roots()
        .https_or_http()
        .enable_http1()
        .build();

    let hub = CalendarHub::new(hyper::Client::builder().build(connector), auth);
    Ok(hub)
}

fn prompt(label: &str) -> Result<String> {
    use std::io::{self, Write};
    print!("{}: ", label);
    io::stdout().flush().ok();
    let mut s = String::new();
    io::stdin().read_line(&mut s)?;
    Ok(s.trim().to_string())
}

fn rewind_ical_uid(task_id: &str) -> String {
    format!("rewind-{}@rewind", task_id)
}

pub struct PushSummary {
    pub created: usize,
    pub updated: usize,
}

pub async fn push_events(calendar_id: &str, events: &[CalendarEvent]) -> Result<PushSummary> {
    let client = load_oauth_client()?;
    let hub = hub_from_client(&client).await?;

    let mut created = 0usize;
    let mut updated = 0usize;

    for e in events {
        let uid = rewind_ical_uid(&e.task_id);

        // Search by iCalUID; if found, update; else insert.
        let (_resp, existing): (_, Events) = hub
            .events()
            .list(calendar_id)
            .i_cal_uid(&uid)
            .max_results(1)
            .doit()
            .await
            .with_context(|| format!("query existing event by iCalUID {uid}"))?;

        let existing_id = existing
            .items
            .as_ref()
            .and_then(|items| items.first())
            .and_then(|ev| ev.id.clone());

        let mut ev = Event::default();
        ev.summary = Some(e.summary.clone());
        ev.description = Some(e.description.clone());
        ev.i_cal_uid = Some(uid.clone());

        let start = google_calendar3::api::EventDateTime {
            date_time: Some(e.start_utc),
            time_zone: Some("UTC".to_string()),
            ..Default::default()
        };
        let end = google_calendar3::api::EventDateTime {
            date_time: Some(e.end_utc),
            time_zone: Some("UTC".to_string()),
            ..Default::default()
        };
        ev.start = Some(start);
        ev.end = Some(end);

        if let Some(event_id) = existing_id {
            hub.events()
                .update(ev, calendar_id, &event_id)
                .doit()
                .await
                .with_context(|| format!("updating event {event_id} ({uid})"))?;
            updated += 1;
        } else {
            hub.events()
                .insert(ev, calendar_id)
                .doit()
                .await
                .with_context(|| format!("inserting event '{uid}'"))?;
            created += 1;
        }
    }

    Ok(PushSummary { created, updated })
}
