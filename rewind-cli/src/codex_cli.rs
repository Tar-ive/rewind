use anyhow::{bail, Context, Result};
use tokio::io::AsyncReadExt;

use crate::llm_stream::StreamEvent;

/// Stream a completion by shelling out to the `codex` CLI.
///
/// We do this instead of scraping OAuth tokens from codex's credential store.
/// This keeps the integration portable and safe.
///
/// Because Codex CLI flags can vary across versions, we try a small set of common
/// invocations and provide a clear error if none work.
pub async fn stream_codex(
    codex_command: &str,
    codex_args: &[String],
    system: &str,
    turns: &[(String, String)],
    mut on_event: impl FnMut(StreamEvent) + Send,
) -> Result<()> {
    on_event(StreamEvent::Started);

    // Build a single prompt. (v0)
    let mut prompt = String::new();
    prompt.push_str(system);
    prompt.push_str("\n\n");
    for (role, content) in turns {
        prompt.push_str(role);
        prompt.push_str(": ");
        prompt.push_str(content);
        prompt.push_str("\n\n");
    }

    // Candidate commands to try (based on Codex CLI help):
    // - `codex exec <PROMPT>` is the documented non-interactive entrypoint.
    // - `codex <PROMPT>` also starts a session when no subcommand is provided.
    //
    // We pass `codex_args` (from ~/.rewind/config.toml) before the prompt so
    // users can control model/profile/sandbox, e.g.:
    //   codex_args = ["-m", "gpt-5-codex", "--full-auto"]
    let candidates: Vec<Vec<String>> = vec![
        {
            let mut v = Vec::new();
            v.push("exec".to_string());
            v.extend_from_slice(codex_args);
            v.push(prompt.clone());
            v
        },
        {
            let mut v = Vec::new();
            v.extend_from_slice(codex_args);
            v.push(prompt.clone());
            v
        },
    ];

    let mut last_err: Option<anyhow::Error> = None;

    for args in candidates {
        match try_run(codex_command, &args, &mut on_event).await {
            Ok(()) => {
                on_event(StreamEvent::Completed);
                return Ok(());
            }
            Err(e) => {
                last_err = Some(e);
                continue;
            }
        }
    }

    if let Some(e) = last_err {
        bail!(
            "Failed to run codex CLI for streaming.\n\
Tried: `{codex_command} exec <prompt>` and `{codex_command} <prompt>`.\n\
\nUnderlying error: {e}\n\
\nFix: run `codex --help` and set llm.codex_args in ~/.rewind/config.toml (provider=codex-cli)."
        );
    }

    bail!("Failed to run codex CLI for streaming (unknown error)");
}

async fn try_run(
    cmd: &str,
    args: &[String],
    on_event: &mut (impl FnMut(StreamEvent) + Send),
) -> Result<()> {
    let mut child = tokio::process::Command::new(cmd)
        .args(args)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .with_context(|| format!("spawning {cmd} {:?}", args))?;

    let mut stdout = child.stdout.take().context("missing stdout")?;
    let mut stderr = child.stderr.take().context("missing stderr")?;

    // Read stderr in background (best-effort)
    let (tx, rx) = tokio::sync::oneshot::channel::<String>();
    tokio::spawn(async move {
        let mut buf = String::new();
        let _ = stderr.read_to_string(&mut buf).await;
        let _ = tx.send(buf);
    });

    let mut buf = [0u8; 4096];
    loop {
        let n = stdout
            .read(&mut buf)
            .await
            .context("reading codex stdout")?;
        if n == 0 {
            break;
        }
        let s = String::from_utf8_lossy(&buf[..n]);
        on_event(StreamEvent::Delta(s.to_string()));
    }

    let status = child.wait().await.context("waiting for codex")?;
    if !status.success() {
        let stderr_txt = rx.await.unwrap_or_default();
        bail!("codex exited with {status}. stderr: {stderr_txt}");
    }

    Ok(())
}
