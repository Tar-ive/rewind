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
    use chrono::{Duration, TimeZone};
    use chrono_tz::Tz;

    let client = load_oauth_client()?;
    let hub = hub_from_client(&client).await?;

    // Force an auth token with write scope up front, so users don't see multiple
    // browser prompts (readonly first, then write later).
    const SCOPE_EVENTS: &str = "https://www.googleapis.com/auth/calendar.events";
    let _ = hub
        .auth
        .get_token(&[SCOPE_EVENTS])
        .await
        .map_err(|e| anyhow::anyhow!("Google OAuth (calendar.events) failed: {e}"))?;

    // We manage a deterministic window: "today" in the user's timezone.
    // Anything previously created by Rewind in that window but not in the new schedule
    // gets moved to an end-of-day "graveyard" and marked CANCELLED.
    let profile = crate::state::read_profile()?;
    let tz: Tz = profile
        .timezone
        .parse()
        .map_err(|_| anyhow::anyhow!("invalid timezone in profile.json: {}", profile.timezone))?;

    let now_utc = chrono::Utc::now();
    let now_local = now_utc.with_timezone(&tz);
    let day = now_local.date_naive();

    let day_start_local = tz
        .from_local_datetime(&day.and_hms_opt(0, 0, 0).unwrap())
        .single()
        .unwrap();
    let day_end_local = tz
        .from_local_datetime(&day.and_hms_opt(23, 59, 59).unwrap())
        .single()
        .unwrap();

    let time_min = day_start_local.with_timezone(&chrono::Utc);
    let time_max = day_end_local.with_timezone(&chrono::Utc);

    let (_resp, existing): (_, Events) = hub
        .events()
        .list(calendar_id)
        .time_min(time_min)
        .time_max(time_max)
        .single_events(true)
        .max_results(2500)
        .doit()
        .await
        .with_context(|| format!("listing existing events for window {time_min}..{time_max}"))?;

    // Map iCalUID -> (event_id, existing_summary)
    let mut existing_map: std::collections::HashMap<String, (String, Option<String>)> =
        std::collections::HashMap::new();
    if let Some(items) = existing.items {
        for ev in items {
            if let (Some(uid), Some(id)) = (ev.i_cal_uid.clone(), ev.id.clone()) {
                if uid.starts_with("rewind-") {
                    existing_map.insert(uid, (id, ev.summary.clone()));
                }
            }
        }
    }

    let mut created = 0usize;
    let mut updated = 0usize;

    let mut desired_uids: std::collections::HashSet<String> = std::collections::HashSet::new();

    for e in events {
        let uid = rewind_ical_uid(&e.task_id);
        desired_uids.insert(uid.clone());

        let mut ev = Event::default();

        // Preserve manual completion tag if user edited it in Google Calendar.
        let done_suffix = " - done";
        let summary = match existing_map.get(&uid).and_then(|(_, s)| s.clone()) {
            Some(s) if s.trim_end().ends_with(done_suffix) => {
                format!("{}{}", e.summary, done_suffix)
            }
            _ => e.summary.clone(),
        };

        ev.summary = Some(summary);
        ev.description = Some(e.description.clone());
        ev.i_cal_uid = Some(uid.clone());
        ev.color_id = Some(color_id_for_horizon(e.horizon).to_string());

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

        if let Some((event_id, _)) = existing_map.get(&uid) {
            hub.events()
                .update(ev, calendar_id, event_id)
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

    // Cancel/move orphaned events into the graveyard.
    // Graveyard starts at 23:00 local, stacked in 5-minute blocks.
    let mut graveyard_cursor = tz
        .from_local_datetime(&day.and_hms_opt(23, 0, 0).unwrap())
        .single()
        .unwrap();

    for (uid, (event_id, existing_summary)) in existing_map.iter() {
        if desired_uids.contains(uid) {
            continue;
        }

        let mut ev = Event::default();
        let base = existing_summary.clone().unwrap_or_else(|| uid.clone());
        let new_summary = if base.starts_with("CANCELLED: ") {
            base
        } else {
            format!("CANCELLED: {}", base)
        };

        ev.summary = Some(new_summary);
        ev.status = Some("cancelled".to_string());
        ev.i_cal_uid = Some(uid.clone());
        ev.color_id = Some("8".to_string()); // a neutral/gray-ish color

        let start_utc = graveyard_cursor.with_timezone(&chrono::Utc);
        let end_utc = (graveyard_cursor + Duration::minutes(5)).with_timezone(&chrono::Utc);

        ev.start = Some(google_calendar3::api::EventDateTime {
            date_time: Some(start_utc),
            time_zone: Some("UTC".to_string()),
            ..Default::default()
        });
        ev.end = Some(google_calendar3::api::EventDateTime {
            date_time: Some(end_utc),
            time_zone: Some("UTC".to_string()),
            ..Default::default()
        });

        hub.events()
            .update(ev, calendar_id, event_id)
            .doit()
            .await
            .with_context(|| format!("moving orphaned event {event_id} to graveyard"))?;

        graveyard_cursor = graveyard_cursor + Duration::minutes(5);
    }

    Ok(PushSummary { created, updated })
}

fn color_id_for_horizon(h: rewind_core::GoalTag) -> &'static str {
    // Google Calendar colorId values are provider-defined. These are common defaults:
    // 11 ~ red, 5 ~ yellow, 10 ~ green.
    match h {
        rewind_core::GoalTag::Short => "11",  // maroon/red
        rewind_core::GoalTag::Medium => "5", // yellow
        rewind_core::GoalTag::Long => "10",  // green
    }
}
