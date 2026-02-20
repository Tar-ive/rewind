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
    System,
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

    fn append_system(&mut self, msg: &str) -> Result<()> {
        self.append("system", msg)
    }

    fn append_user(&mut self, msg: &str) -> Result<()> {
        self.append("user", msg)
    }

    fn append_assistant(&mut self, msg: &str) -> Result<()> {
        self.append("assistant", msg)
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

    // daily log file
    let mut log = ChatLog::open_today()?;
    log.append_system("session_start")?;

    loop {
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

            // Splash/header (Codex-style)
            let splash = Paragraph::new(Text::from(vec![
                Line::from(Span::styled(
                    "Rewind",
                    Style::default()
                        .fg(Color::Yellow)
                        .add_modifier(Modifier::BOLD),
                )),
                Line::from(Span::raw("")),
                Line::from(Span::styled(
                    ">_ rewind chat",
                    Style::default().fg(Color::Cyan),
                )),
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
                    "Shortcuts: Enter=send, q=quit, ?=help",
                    Style::default().fg(Color::Gray),
                )));
                lines.push(Line::raw("Commands: /help /status /calendar /goals /statements /reminders"));
                lines.push(Line::raw(""));
            }

            for m in &messages {
                let (tag, color) = match m.role {
                    Role::User => ("you", Color::Cyan),
                    Role::Assistant => ("rewind", Color::Magenta),
                    Role::System => ("system", Color::Gray),
                };
                lines.push(Line::from(vec![
                    Span::styled(format!("{}: ", tag), Style::default().fg(color)),
                    Span::raw(m.content.clone()),
                ]));
                lines.push(Line::raw(""));
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

        if event::poll(std::time::Duration::from_millis(50))? {
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
                        if !trimmed.is_empty() {
                            log.append_user(&trimmed)?;

                            // Slash commands
                            if let Some(reply) = handle_slash(&trimmed) {
                                messages.push(Msg {
                                    role: Role::Assistant,
                                    content: reply.clone(),
                                });
                                log.append_assistant(&reply)?;
                            } else {
                                messages.push(Msg {
                                    role: Role::User,
                                    content: trimmed.clone(),
                                });

                                // If an LLM is configured, use it; otherwise fall back to deterministic.
                                let reply = if let Some(cfg) = llm::default_config()? {
                                    let system = wellwisher_system_prompt();
                                    let turns = to_llm_turns(&messages, &trimmed);
                                    match llm::chat_complete(&cfg, &system, &turns) {
                                        Ok(s) if !s.trim().is_empty() => s,
                                        _ => wellwisher_reply(&trimmed),
                                    }
                                } else {
                                    wellwisher_reply(&trimmed)
                                };

                                messages.push(Msg {
                                    role: Role::Assistant,
                                    content: reply.clone(),
                                });
                                log.append_assistant(&reply)?;
                            }
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

fn to_llm_turns(messages: &[Msg], pending_user: &str) -> Vec<llm::ChatTurn> {
    let mut turns = Vec::new();

    // Include only recent conversation to keep it fast.
    let start = messages.len().saturating_sub(12);
    for m in &messages[start..] {
        match m.role {
            Role::User => turns.push(llm::ChatTurn {
                role: "user".to_string(),
                content: m.content.clone(),
            }),
            Role::Assistant => turns.push(llm::ChatTurn {
                role: "assistant".to_string(),
                content: m.content.clone(),
            }),
            Role::System => {}
        }
    }

    turns.push(llm::ChatTurn {
        role: "user".to_string(),
        content: pending_user.to_string(),
    });

    turns
}

fn wellwisher_system_prompt() -> String {
    // Tone rules from Tarive:
    // - soft, smooth, respectful
    // - user is capable; they choose Rewind as a companion
    // - avoid pathologizing language (e.g., do not use "overwhelm")
    // - keep it practical: pay/check/review, goals, gentle accountability
    "You are Rewind, a calm, kind wellwisher and planning companion.\n\
The user is capable and chooses to chat with you; treat them with respect.\n\
Be concise and action-oriented. Offer small, optional next steps, not lectures.\n\
Never use pathologizing language; avoid words like 'overwhelm'.\n\
When appropriate, suggest one of: Pay (2–5 min), Check (5 min), Review/Plan (10 min).\n\
If the user asks about calendar/goals/statements, provide exact commands."
        .to_string()
}

fn wellwisher_reply(user: &str) -> String {
    let u = user.to_lowercase();

    // Respectful, non-pathologizing prompts.
    if u.contains("busy") || u.contains("later") {
        return "No problem. If you want, tell me: (1) Pay, (2) Check, or (3) Review — and I’ll keep it to one small step.".to_string();
    }

    if u.trim() == "1" {
        return "Pay: do the minimum payment for your highest-interest card. When you finish, add ' - done' to today’s Pay nudge in Calendar.".to_string();
    }
    if u.trim() == "2" {
        return "Check: open your bank/CC app and confirm next due date + minimum. If anything is due within 72 hours, tell me the due date + your timezone.".to_string();
    }
    if u.trim() == "3" {
        return "Review: look at the last 7 days and pick one category you’d like to improve (food, subscriptions, transport). We’ll choose one small rule.".to_string();
    }

    "What’s one money win you’d like this week — lower stress, fewer surprises, or more savings?".to_string()
}
