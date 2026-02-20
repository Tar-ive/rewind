use tokio::sync::mpsc;

use crate::llm;
use crate::llm_stream::{self, StreamEvent};

#[derive(Debug, Clone)]
pub struct ChatRequest {
    pub request_id: u64,
    pub system: String,
    pub turns: Vec<llm::ChatTurn>,
}

#[derive(Debug, Clone)]
pub enum ChatEvent {
    Started { request_id: u64 },
    Delta { request_id: u64, text: String },
    Completed { request_id: u64 },
    Error { request_id: u64, message: String },
}

pub async fn run_worker(
    mut rx: mpsc::UnboundedReceiver<ChatRequest>,
    tx: std::sync::mpsc::Sender<ChatEvent>,
) {
    let mut current: Option<tokio::task::JoinHandle<()>> = None;

    while let Some(req) = rx.recv().await {
        // cancel in-flight
        if let Some(h) = current.take() {
            h.abort();
        }

        let tx2 = tx.clone();
        current = Some(tokio::spawn(async move {
            let _ = tx2.send(ChatEvent::Started {
                request_id: req.request_id,
            });

            let cfg = match llm::default_config() {
                Ok(Some(c)) => c,
                Ok(None) => {
                    let _ = tx2.send(ChatEvent::Error {
                        request_id: req.request_id,
                        message: "No model configured. Add a key via: rewind auth paste-openai-api-key (or anthropic).".to_string(),
                    });
                    return;
                }
                Err(e) => {
                    let _ = tx2.send(ChatEvent::Error {
                        request_id: req.request_id,
                        message: format!("Auth/config error: {e}"),
                    });
                    return;
                }
            };

            let mut out_ok = true;
            let res = llm_stream::stream_chat(&cfg, &req.system, &req.turns, |ev| match ev {
                StreamEvent::Started => {}
                StreamEvent::Delta(t) => {
                    let _ = tx2.send(ChatEvent::Delta {
                        request_id: req.request_id,
                        text: t,
                    });
                }
                StreamEvent::Completed => {
                    let _ = tx2.send(ChatEvent::Completed {
                        request_id: req.request_id,
                    });
                }
                StreamEvent::Error(msg) => {
                    let _ = tx2.send(ChatEvent::Error {
                        request_id: req.request_id,
                        message: msg,
                    });
                    out_ok = false;
                }
            })
            .await;

            if let Err(e) = res {
                let _ = tx2.send(ChatEvent::Error {
                    request_id: req.request_id,
                    message: format!("LLM error: {e}"),
                });
                out_ok = false;
            }

            if out_ok {
                let _ = tx2.send(ChatEvent::Completed {
                    request_id: req.request_id,
                });
            }
        }));
    }
}
