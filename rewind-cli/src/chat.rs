use anyhow::Result;
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Alignment, Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span, Text},
    widgets::{Block, Borders, Paragraph, Wrap},
    Terminal,
};
use std::io::{self, Stdout};
use std::path::PathBuf;

use crate::chat_worker;
use crate::llm;

#[derive(Clone, Debug)]
struct Msg {
    role: Role,
    content: String,
}

#[derive(Clone, Debug)]
enum Role {
    User,
    Assistant,
}

struct ChatLog {
    path: PathBuf,
}

impl ChatLog {
    fn open_today() -> Result<Self> {
        let home = crate::state::ensure_rewind_home()?;
        let dir = home.join("chat");
        std::fs::create_dir_all(&dir)?;
        let today = chrono::Utc::now().format("%Y-%m-%d").to_string();
        let path = dir.join(format!("{today}.md"));
        Ok(Self { path })
    }

    fn append(&mut self, role: &str, msg: &str) -> Result<()> {
        use std::io::Write;
        let mut f = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        writeln!(
            f,
            "- {} [{}] {}",
            chrono::Utc::now().to_rfc3339(),
            role,
            msg.replace('\n', " ")
        )?;
        Ok(())
    }
}

pub fn run_chat() -> Result<()> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;

    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let res = chat_loop(&mut terminal);

    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen, DisableMouseCapture)?;
    terminal.show_cursor()?;

    res
}

fn chat_loop(terminal: &mut Terminal<CrosstermBackend<Stdout>>) -> Result<()> {
    let mut messages: Vec<Msg> = vec![Msg {
        role: Role::Assistant,
        content: "Hi — I’m Rewind. What would you like to improve today?".to_string(),
    }];

    let mut input = String::new();
    let mut show_help = true;

    let mut log = ChatLog::open_today()?;
    log.append("system", "session_start")?;

    // UI -> worker (async)
    let (tx_req, rx_req) = tokio::sync::mpsc::unbounded_channel::<chat_worker::ChatRequest>();
    // worker -> UI (sync)
    let (tx_evt, rx_evt) = std::sync::mpsc::channel::<chat_worker::ChatEvent>();

    tokio::spawn(chat_worker::run_worker(rx_req, tx_evt));

    let mut next_request_id: u64 = 1;
    let mut streaming_request_id: Option<u64> = None;

    loop {
        // Drain worker events to update UI state.
        while let Ok(ev) = rx_evt.try_recv() {
            match ev {
                chat_worker::ChatEvent::Started { request_id } => {
                    streaming_request_id = Some(request_id);
                }
                chat_worker::ChatEvent::Delta { request_id, text } => {
                    if streaming_request_id == Some(request_id) {
                        // Append deltas to last assistant message.
                        if let Some(last) = messages.last_mut() {
                            if matches!(last.role, Role::Assistant) {
                                last.content.push_str(&text);
                            }
                        }
                    }
                }
                chat_worker::ChatEvent::Completed { request_id } => {
                    if streaming_request_id == Some(request_id) {
                        streaming_request_id = None;
                        if let Some(last) = messages.last() {
                            if matches!(last.role, Role::Assistant) {
                                let _ = log.append("assistant", &last.content);
                            }
                        }
                    }
                }
                chat_worker::ChatEvent::Error { request_id, message } => {
                    if streaming_request_id == Some(request_id) {
                        streaming_request_id = None;
                    }
                    messages.push(Msg {
                        role: Role::Assistant,
                        content: format!("(note) {message}"),
                    });
                    let _ = log.append("assistant", &format!("(error) {message}"));
                }
            }
        }

        terminal.draw(|f| {
            let size = f.area();
            let chunks = Layout::default()
                .direction(Direction::Vertical)
                .constraints([
                    Constraint::Length(5),
                    Constraint::Min(5),
                    Constraint::Length(3),
                ])
                .split(size);

            let splash = Paragraph::new(Text::from(vec![
                Line::from(Span::styled(
                    "Rewind",
                    Style::default()
                        .fg(Color::Yellow)
                        .add_modifier(Modifier::BOLD),
                )),
                Line::from(Span::raw("")),
                Line::from(Span::styled(">_ rewind chat", Style::default().fg(Color::Cyan))),
                Line::from(Span::styled(
                    "type /help or ? for shortcuts",
                    Style::default().fg(Color::Gray),
                )),
            ]))
            .alignment(Alignment::Center)
            .block(Block::default().borders(Borders::ALL));
            f.render_widget(splash, chunks[0]);

            let header = Block::default().borders(Borders::ALL).title("conversation");

            let mut lines: Vec<Line> = Vec::new();
            if show_help {
                lines.push(Line::from(Span::styled(
                    "Shortcuts: Enter=send, q=quit, ?=toggle help",
                    Style::default().fg(Color::Gray),
                )));
                lines.push(Line::raw(
                    "Commands: /help /status /calendar /goals /statements /reminders",
                ));
                lines.push(Line::raw(""));
            }

            for m in &messages {
                let (tag, color) = match m.role {
                    Role::User => ("you", Color::Cyan),
                    Role::Assistant => ("rewind", Color::Magenta),
                };
                lines.push(Line::from(vec![
                    Span::styled(format!("{}: ", tag), Style::default().fg(color)),
                    Span::raw(m.content.clone()),
                ]));
                lines.push(Line::raw(""));
            }

            // Typing indicator
            if streaming_request_id.is_some() {
                lines.push(Line::from(Span::styled(
                    "rewind is writing…",
                    Style::default().fg(Color::Gray),
                )));
            }

            let history = Paragraph::new(Text::from(lines))
                .block(header)
                .wrap(Wrap { trim: false });
            f.render_widget(history, chunks[1]);

            let input_block = Block::default().borders(Borders::ALL).title("message");
            let input_widget = Paragraph::new(input.as_str())
                .block(input_block)
                .style(Style::default().fg(Color::White));
            f.render_widget(input_widget, chunks[2]);
        })?;

        if event::poll(std::time::Duration::from_millis(33))? {
            if let Event::Key(key) = event::read()? {
                if key.kind != KeyEventKind::Press {
                    continue;
                }
                match key.code {
                    KeyCode::Char('q') => break,
                    KeyCode::Char('?') => {
                        show_help = !show_help;
                    }
                    KeyCode::Enter => {
                        let trimmed = input.trim().to_string();
                        if trimmed.is_empty() {
                            input.clear();
                            continue;
                        }

                        // Log and append user message
                        log.append("user", &trimmed)?;

                        if let Some(reply) = handle_slash(&trimmed) {
                            messages.push(Msg {
                                role: Role::Assistant,
                                content: reply.clone(),
                            });
                            log.append("assistant", &reply)?;
                        } else {
                            messages.push(Msg {
                                role: Role::User,
                                content: trimmed.clone(),
                            });

                            // Reserve a message for streaming output.
                            messages.push(Msg {
                                role: Role::Assistant,
                                content: String::new(),
                            });

                            let req_id = next_request_id;
                            next_request_id += 1;
                            streaming_request_id = Some(req_id);

                            let req = chat_worker::ChatRequest {
                                request_id: req_id,
                                system: wellwisher_system_prompt(),
                                turns: to_llm_turns(&messages, ""),
                            };

                            let _ = tx_req.send(req);
                        }

                        input.clear();
                    }
                    KeyCode::Backspace => {
                        input.pop();
                    }
                    KeyCode::Char(c) => {
                        input.push(c);
                    }
                    _ => {}
                }
            }
        }
    }

    Ok(())
}

fn handle_slash(input: &str) -> Option<String> {
    let s = input.trim();
    if !s.starts_with('/') {
        return None;
    }
    match s {
        "/help" => Some(
            "Commands:\n\
- /help\n\
- /status\n\
- /calendar (shows nudge commands)\n\
- /goals (how to add goals)\n\
- /statements (how to add statements)\n\
- /reminders (coming soon)\n\
\nShortcuts: Enter=send, q=quit, ?=toggle help"
                .to_string(),
        ),
        "/status" => Some("Status: chat logs are saved daily under ~/.rewind/chat/YYYY-MM-DD.md".to_string()),
        "/calendar" => Some(
            "Calendar:\n\
- push nudges: rewind calendar push-google --mode nudge --csv amex.csv --calendar-id primary\n\
- visualize schedule: rewind calendar push-google --mode visualize-sts --csv amex.csv --limit 10 --energy 5"
                .to_string(),
        ),
        "/goals" => Some(
            "Goals: (schema v1 soon)\n\
For now, add/edit ~/.rewind/goals.md and rerun rewind plan-day / calendar push."
                .to_string(),
        ),
        "/statements" => Some(
            "Statements:\n\
- AMEX: rewind finance sync --csv amex.csv\n\
(Adding more banks + PDF ingestion is coming.)"
                .to_string(),
        ),
        "/reminders" => Some(
            "Reminders: coming soon (WhatsApp/iMessage + cron). For now, use the 3 daily calendar nudges.".to_string(),
        ),
        _ => Some("Unknown command. Try /help".to_string()),
    }
}

fn to_llm_turns(messages: &[Msg], _pending_user: &str) -> Vec<llm::ChatTurn> {
    let mut turns = Vec::new();

    // Include only recent conversation to keep it fast.
    let start = messages.len().saturating_sub(12);
    for m in &messages[start..] {
        match m.role {
            Role::User => turns.push(llm::ChatTurn {
                role: "user".to_string(),
                content: m.content.clone(),
            }),
            Role::Assistant => {
                // Skip empty streaming placeholder
                if m.content.trim().is_empty() {
                    continue;
                }
                turns.push(llm::ChatTurn {
                    role: "assistant".to_string(),
                    content: m.content.clone(),
                })
            }
        }
    }

    turns
}

fn wellwisher_system_prompt() -> String {
    "You are Rewind, a calm, kind wellwisher and planning companion focused on financial goals.\n\
The user is capable and chooses to chat with you; treat them with respect.\n\
Be concise and practical. Offer small, optional next steps, not lectures.\n\
Never use pathologizing language.\n\
When appropriate, suggest one of: Pay (2–5 min), Check (5 min), Review/Plan (10 min).\n\
If the user asks about calendar/goals/statements, provide exact commands."
        .to_string()
}
