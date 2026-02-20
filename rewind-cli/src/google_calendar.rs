use anyhow::{bail, Context, Result};
use google_calendar3::api::Event;
use google_calendar3::CalendarHub;
use hyper::client::HttpConnector;
use hyper_rustls::HttpsConnector;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

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

/// Interactive connect:
/// - user pastes client_id/client_secret from Google Cloud Console (Desktop app)
/// - we run OAuth installed-app flow
/// - tokens cached under ~/.rewind/google_token_cache.json
pub async fn connect_interactive() -> Result<()> {
    println!("Google Calendar connect\n");
    println!("This uses the official Google Calendar API (no gcalcli / no Composio).\n");
    println!("You need to create OAuth credentials once:\n");
    println!("1) Go to: https://console.cloud.google.com/apis/credentials");
    println!("2) Create credentials → OAuth client ID");
    println!("3) Application type: Desktop app");
    println!("4) Copy client_id + client_secret\n");

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

async fn hub_from_client(client: &GoogleOAuthClient) -> Result<CalendarHub<HttpsConnector<HttpConnector>>> {
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

pub async fn push_events(
    calendar_id: &str,
    events: &[CalendarEvent],
) -> Result<()> {
    let client = load_oauth_client()?;
    let hub = hub_from_client(&client).await?;

    for e in events {
        let mut ev = Event::default();
        ev.summary = Some(e.summary.clone());
        ev.description = Some(e.description.clone());

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

        hub.events()
            .insert(ev, calendar_id)
            .doit()
            .await
            .with_context(|| format!("inserting event '{}'", e.summary))?;
    }

    Ok(())
}
