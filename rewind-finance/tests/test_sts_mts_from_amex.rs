use chrono::{Duration, TimeZone, Utc};
use rewind_finance::amex_parser::parse_amex_csv;
use rewind_finance::task_emitter::TaskEmitter;
use rewind_core::{Priority, Task, TaskStatus, ShortTermScheduler, handle_swap_in, handle_swap_out};
use std::path::PathBuf;

fn amex_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("amex.csv")
}

fn finance_task_to_core_task(i: usize, ft: &rewind_finance::task_emitter::FinanceTask) -> Task {
    // Duration heuristic: larger totals and more txns imply more work.
    // Keep it bounded for scheduling.
    let mut minutes = 15 + (ft.transaction_count as i32 / 10) * 5;
    if ft.total_amount.abs() > 1000.0 {
        minutes += 15;
    }
    minutes = minutes.clamp(10, 90);

    // Energy heuristic by category
    let (energy, cognitive) = match ft.category {
        rewind_core::Category::CreditCard | rewind_core::Category::Tuition => (4, 4),
        rewind_core::Category::Savings => (3, 3),
        _ => (2, 2),
    };

    // Deadline urgency proxy: scale urgency(0..1) to 0..10
    let urgency = (ft.urgency * 10.0).round() as i32;

    let mut title = format!("{}", ft.goal_name);
    if !ft.sample_descriptions.is_empty() {
        title.push_str(" | ");
        title.push_str(&ft.sample_descriptions.join(" ; "));
    }

    Task {
        id: format!("amex-task-{i}"),
        title,
        status: TaskStatus::Backlog,
        priority: Priority::P2Normal,
        estimated_duration: minutes,
        energy_cost: energy,
        cognitive_load: cognitive,
        deadline: None,
        deadline_urgency: urgency,
    }
}

/// Real-data regression: build tasks from AMEX CSV and ensure STS prioritizes the most urgent.
#[test]
fn test_sts_from_real_amex_tasks() {
    let txns = parse_amex_csv(amex_path()).unwrap();
    let tasks = TaskEmitter::emit(&txns);
    assert!(tasks.len() >= 10);

    let now = Utc.with_ymd_and_hms(2026, 2, 19, 12, 0, 0).unwrap();

    let mut sts = ShortTermScheduler::new();
    for (i, ft) in tasks.iter().take(12).enumerate() {
        let t = finance_task_to_core_task(i, ft);
        sts.enqueue(t, now);
    }

    // With high energy, we should dequeue something.
    let next = sts.dequeue(5).unwrap();

    // Should be among top urgent tasks (deadline_urgency near 10).
    assert!(next.deadline_urgency >= 8, "expected urgent task, got {}", next.deadline_urgency);
}

/// Real-data regression: swap-in uses freed time to pull urgent backlog tasks.
#[test]
fn test_mts_swap_in_from_real_amex_tasks() {
    let txns = parse_amex_csv(amex_path()).unwrap();
    let tasks = TaskEmitter::emit(&txns);

    let now = Utc.with_ymd_and_hms(2026, 2, 19, 12, 0, 0).unwrap();

    // Backlog: convert top 15 finance tasks into core tasks
    let mut backlog: Vec<Task> = tasks
        .iter()
        .take(15)
        .enumerate()
        .map(|(i, ft)| finance_task_to_core_task(i, ft))
        .collect();

    let mut sts = ShortTermScheduler::new();

    // Free 60 minutes; energy high.
    let res = handle_swap_in(60, 5, &mut backlog, &mut sts, now);

    assert!(!res.swapped_in.is_empty());
    // Should have consumed some time and reduced backlog size.
    assert!(backlog.len() < 15);
    assert!(sts.total_count() == res.swapped_in.len());
}

/// Real-data regression: swap-out removes background/low priority tasks first.
#[test]
fn test_mts_swap_out_prefers_background() {
    let now = Utc.with_ymd_and_hms(2026, 2, 19, 12, 0, 0).unwrap();

    let mut active = vec![
        Task::new("bg", "background")
            .with_duration(30)
            .with_energy(1)
            .with_cognitive(1)
            .with_deadline_urgency(0),
        Task::new("imp", "important")
            .with_duration(30)
            .with_energy(3)
            .with_cognitive(4)
            .with_deadline(now + Duration::hours(3))
            .with_deadline_urgency(9),
    ];

    active[0].status = TaskStatus::Active;
    active[0].priority = Priority::P3Background;
    active[1].status = TaskStatus::Active;
    active[1].priority = Priority::P1Important;

    let res = handle_swap_out(25, &mut active);
    assert_eq!(res.swapped_out.len(), 1);
    assert_eq!(res.swapped_out[0].id, "bg");
}
