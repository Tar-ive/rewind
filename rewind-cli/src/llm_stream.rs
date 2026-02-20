use anyhow::{bail, Context, Result};
use futures_util::StreamExt;
use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION, CONTENT_TYPE};
use serde::Serialize;
use serde_json::Value;

use crate::auth;
use crate::llm::{ChatTurn, LlmConfig, Provider};

#[derive(Debug, Clone)]
pub enum StreamEvent {
    Started,
    Delta(String),
    Completed,
    Error(String),
}

pub async fn stream_chat(
    cfg: &LlmConfig,
    system: &str,
    turns: &[ChatTurn],
    mut on_event: impl FnMut(StreamEvent) + Send,
) -> Result<()> {
    on_event(StreamEvent::Started);

    match cfg.provider {
        Provider::OpenAI => stream_openai_compatible(cfg, system, turns, &cfg.base_url, &mut on_event).await,
        Provider::CodexCli => {
            let c = crate::config::load_config()?;
            let cmd = c.llm.codex_command.unwrap_or_else(|| "codex".to_string());
            let args = c.llm.codex_args.unwrap_or_default();
            let turns2: Vec<(String, String)> = turns
                .iter()
                .map(|t| (t.role.clone(), t.content.clone()))
                .collect();
            crate::codex_cli::stream_codex(&cmd, &args, system, &turns2, &mut on_event).await
        }
        Provider::Anthropic => {
            bail!("streaming for anthropic not implemented yet (next).")
        }
    }
}

#[derive(Serialize)]
struct OaiMsg {
    role: String,
    content: String,
}

#[derive(Serialize)]
struct OaiReq {
    model: String,
    messages: Vec<OaiMsg>,
    temperature: f32,
    stream: bool,
}

async fn stream_openai_compatible(
    cfg: &LlmConfig,
    system: &str,
    turns: &[ChatTurn],
    base_url: &str,
    on_event: &mut (impl FnMut(StreamEvent) + Send),
) -> Result<()> {
    let a = auth::load_auth()?;
    let key = a
        .openai_api_key
        .ok_or_else(|| anyhow::anyhow!("missing openai_api_key; run: rewind auth paste-openai-api-key"))?;

    let mut messages: Vec<OaiMsg> = Vec::new();
    messages.push(OaiMsg {
        role: "system".to_string(),
        content: system.to_string(),
    });
    for t in turns {
        messages.push(OaiMsg {
            role: t.role.clone(),
            content: t.content.clone(),
        });
    }

    let body = OaiReq {
        model: crate::config::normalize_openai_model(&cfg.model),
        messages,
        temperature: cfg.temperature,
        stream: true,
    };

    let mut headers = HeaderMap::new();
    headers.insert(AUTHORIZATION, HeaderValue::from_str(&format!("Bearer {key}"))?);
    headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));

    let client = reqwest::Client::new();
    let resp = client
        .post(format!("{}/v1/chat/completions", base_url))
        .headers(headers)
        .json(&body)
        .send()
        .await
        .context("openai-compatible streaming request")?;

    let status = resp.status();
    if !status.is_success() {
        let txt = resp.text().await.unwrap_or_default();
        bail!("openai-compatible streaming error: {status} {txt}");
    }

    let mut stream = resp.bytes_stream();
    let mut buf = String::new();

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.context("stream chunk")?;
        let s = String::from_utf8_lossy(chunk.as_ref());
        buf.push_str(&s);

        while let Some(pos) = buf.find('\n') {
            let mut line = buf[..pos].to_string();
            buf = buf[(pos + 1)..].to_string();

            line = line.trim().to_string();
            if line.is_empty() {
                continue;
            }
            if !line.starts_with("data:") {
                continue;
            }
            let data = line.trim_start_matches("data:").trim();
            if data == "[DONE]" {
                on_event(StreamEvent::Completed);
                return Ok(());
            }

            let v: Value = serde_json::from_str(data).context("parse SSE json")?;
            // choices[0].delta.content
            if let Some(content) = v
                .get("choices")
                .and_then(|c| c.get(0))
                .and_then(|c0| c0.get("delta"))
                .and_then(|d| d.get("content"))
                .and_then(|c| c.as_str())
            {
                if !content.is_empty() {
                    on_event(StreamEvent::Delta(content.to_string()));
                }
            }

            // Some providers send tool calls / role deltas; ignore for now.
        }
    }

    on_event(StreamEvent::Completed);
    Ok(())
}
