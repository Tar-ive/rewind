use anyhow::Result;
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Color, Style},
    text::{Line, Span, Text},
    widgets::{Block, Borders, Paragraph, Wrap},
    Terminal,
};
use std::io::{self, Stdout};

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
        content: "I'm Rewind. Tell me what you want help with today (money, deadlines, or just stress).".to_string(),
    }];
    let mut input = String::new();

    loop {
        terminal.draw(|f| {
            let size = f.area();
            let chunks = Layout::default()
                .direction(Direction::Vertical)
                .constraints([Constraint::Min(5), Constraint::Length(3)].as_ref())
                .split(size);

            let header = Block::default()
                .borders(Borders::ALL)
                .title("rewind chat  (q to quit, enter to send)");

            let mut lines: Vec<Line> = Vec::new();
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

            let history = Paragraph::new(Text::from(lines))
                .block(header)
                .wrap(Wrap { trim: false });
            f.render_widget(history, chunks[0]);

            let input_block = Block::default().borders(Borders::ALL).title("message");
            let input_widget = Paragraph::new(input.as_str())
                .block(input_block)
                .style(Style::default().fg(Color::White));
            f.render_widget(input_widget, chunks[1]);
        })?;

        if event::poll(std::time::Duration::from_millis(50))? {
            if let Event::Key(key) = event::read()? {
                if key.kind != KeyEventKind::Press {
                    continue;
                }
                match key.code {
                    KeyCode::Char('q') => break,
                    KeyCode::Enter => {
                        let trimmed = input.trim().to_string();
                        if !trimmed.is_empty() {
                            messages.push(Msg {
                                role: Role::User,
                                content: trimmed.clone(),
                            });

                            // v0 assistant: deterministic, non-LLM. We'll swap in providers next.
                            let reply = deterministic_reply(&trimmed);
                            messages.push(Msg {
                                role: Role::Assistant,
                                content: reply,
                            });
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

fn deterministic_reply(user: &str) -> String {
    let u = user.to_lowercase();

    if u.contains("overwhelm") || u.contains("stressed") || u.contains("anx") {
        return "Okay. Let's make this smaller.\n\nPick one: (1) Pay something (2 min) (2) Check what's due (5 min) (3) Review spending (10 min).\nReply with 1/2/3.".to_string();
    }

    if u.trim() == "1" {
        return "Pay: do the minimum payment for your highest-interest card. After you do it, add ' - done' to today’s Pay nudge in calendar.".to_string();
    }
    if u.trim() == "2" {
        return "Check: open your bank/CC app and confirm the next due date + minimum. If you find one due within 72h, tell me the due date/timezone.".to_string();
    }
    if u.trim() == "3" {
        return "Review: look at last 7 days. Name 1 subscription + 1 impulse spend. We’ll decide one rule to reduce it (cancel, cap, or swap).".to_string();
    }

    "Tell me: what’s the one money thing you’re avoiding right now?".to_string()
}
