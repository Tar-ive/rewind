use anyhow::{bail, Context, Result};
use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION, CONTENT_TYPE};
use serde::{Deserialize, Serialize};

use crate::auth;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Provider {
    Anthropic,
    OpenAI,
}

#[derive(Debug, Clone)]
pub struct LlmConfig {
    pub provider: Provider,
    pub model: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ChatTurn {
    pub role: String,
    pub content: String,
}

pub fn default_config() -> Result<Option<LlmConfig>> {
    let a = auth::load_auth()?;
    if a.anthropic_token.is_some() {
        return Ok(Some(LlmConfig {
            provider: Provider::Anthropic,
            model: "claude-3-5-sonnet-latest".to_string(),
        }));
    }
    if a.openai_api_key.is_some() {
        return Ok(Some(LlmConfig {
            provider: Provider::OpenAI,
            model: "gpt-4o-mini".to_string(),
        }));
    }
    Ok(None)
}

pub fn chat_complete(config: &LlmConfig, system: &str, turns: &[ChatTurn]) -> Result<String> {
    // The CLI uses #[tokio::main], so we're often already inside a runtime.
    // Creating a nested runtime and calling block_on will panic.
    //
    // Strategy:
    // - If a runtime is already running: use block_in_place + Handle::block_on
    // - Otherwise: create a runtime and block_on
    if let Ok(handle) = tokio::runtime::Handle::try_current() {
        tokio::task::block_in_place(|| handle.block_on(async { chat_complete_async(config, system, turns).await }))
    } else {
        let rt = tokio::runtime::Runtime::new().context("create tokio runtime")?;
        rt.block_on(async { chat_complete_async(config, system, turns).await })
    }
}

async fn chat_complete_async(config: &LlmConfig, system: &str, turns: &[ChatTurn]) -> Result<String> {
    match config.provider {
        Provider::Anthropic => anthropic_complete(&config.model, system, turns).await,
        Provider::OpenAI => openai_complete(&config.model, system, turns).await,
    }
}

async fn anthropic_complete(model: &str, system: &str, turns: &[ChatTurn]) -> Result<String> {
    let a = auth::load_auth()?;
    let token = a
        .anthropic_token
        .ok_or_else(|| anyhow::anyhow!("missing anthropic_token; run: rewind auth paste-anthropic-token"))?;

    #[derive(Serialize)]
    struct Msg {
        role: String,
        content: String,
    }

    #[derive(Serialize)]
    struct Req {
        model: String,
        max_tokens: i32,
        system: String,
        messages: Vec<Msg>,
    }

    #[derive(Deserialize)]
    struct Resp {
        content: Vec<ContentBlock>,
    }

    #[derive(Deserialize)]
    struct ContentBlock {
        #[serde(rename = "type")]
        t: String,
        text: Option<String>,
    }

    let messages = turns
        .iter()
        .map(|t| Msg {
            role: t.role.clone(),
            content: t.content.clone(),
        })
        .collect();

    let body = Req {
        model: model.to_string(),
        max_tokens: 450,
        system: system.to_string(),
        messages,
    };

    let mut headers = HeaderMap::new();
    headers.insert(AUTHORIZATION, HeaderValue::from_str(&format!("Bearer {token}"))?);
    headers.insert("anthropic-version", HeaderValue::from_static("2023-06-01"));
    headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));

    let client = reqwest::Client::new();
    let resp = client
        .post("https://api.anthropic.com/v1/messages")
        .headers(headers)
        .json(&body)
        .send()
        .await
        .context("anthropic request")?;

    let status = resp.status();
    if !status.is_success() {
        let txt = resp.text().await.unwrap_or_default();
        bail!("anthropic error: {status} {txt}");
    }

    let out: Resp = resp.json().await.context("parse anthropic response")?;
    let mut s = String::new();
    for b in out.content {
        if b.t == "text" {
            if let Some(t) = b.text {
                s.push_str(&t);
            }
        }
    }
    Ok(s.trim().to_string())
}

async fn openai_complete(model: &str, system: &str, turns: &[ChatTurn]) -> Result<String> {
    let a = auth::load_auth()?;
    let key = a
        .openai_api_key
        .ok_or_else(|| anyhow::anyhow!("missing openai_api_key; run: rewind auth paste-openai-api-key"))?;

    #[derive(Serialize)]
    struct Msg {
        role: String,
        content: String,
    }

    #[derive(Serialize)]
    struct Req {
        model: String,
        messages: Vec<Msg>,
        temperature: f32,
    }

    #[derive(Deserialize)]
    struct Resp {
        choices: Vec<Choice>,
    }

    #[derive(Deserialize)]
    struct Choice {
        message: MsgOut,
    }

    #[derive(Deserialize)]
    struct MsgOut {
        content: Option<String>,
    }

    let mut msgs: Vec<Msg> = Vec::new();
    msgs.push(Msg {
        role: "system".to_string(),
        content: system.to_string(),
    });
    for t in turns {
        msgs.push(Msg {
            role: t.role.clone(),
            content: t.content.clone(),
        });
    }

    let body = Req {
        model: model.to_string(),
        messages: msgs,
        temperature: 0.4,
    };

    let client = reqwest::Client::new();
    let resp = client
        .post("https://api.openai.com/v1/chat/completions")
        .header(AUTHORIZATION, format!("Bearer {key}"))
        .json(&body)
        .send()
        .await
        .context("openai request")?;

    let status = resp.status();
    if !status.is_success() {
        let txt = resp.text().await.unwrap_or_default();
        bail!("openai error: {status} {txt}");
    }

    let out: Resp = resp.json().await.context("parse openai response")?;
    let content = out
        .choices
        .first()
        .and_then(|c| c.message.content.clone())
        .unwrap_or_default();

    Ok(content.trim().to_string())
}
