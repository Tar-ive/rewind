//! MTS integration helpers using TaskBuffer.

use crate::sts::ShortTermScheduler;
use crate::task::TaskStatus;
use crate::task_buffer::TaskBuffer;
use crate::mts::SwapResult;

/// Swap-in using TaskBuffer (bucketed backlog).
///
/// This mirrors `handle_swap_in` but uses TaskBuffer for deterministic candidate selection.
pub fn handle_swap_in_buffer(
    freed_minutes: i32,
    energy_level: i32,
    buffer: &mut TaskBuffer,
    sts: &mut ShortTermScheduler,
    now: chrono::DateTime<chrono::Utc>,
) -> anyhow::Result<SwapResult> {
    let mut swapped_in = Vec::new();

    let picked = buffer.take_swap_in(freed_minutes, energy_level)?;
    for mut t in picked {
        t.status = TaskStatus::Active;
        sts.enqueue(t.clone(), now);
        swapped_in.push(t);
    }

    let used: i32 = swapped_in.iter().map(|t| t.estimated_duration).sum();
    let summary = format!(
        "swap-in(buffer): added {} tasks using {} of {} minutes",
        swapped_in.len(),
        used,
        freed_minutes
    );

    Ok(SwapResult {
        swapped_in,
        swapped_out: vec![],
        delegated: vec![],
        summary,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{TaskBuffer, Task};
    use chrono::Utc;

    #[test]
    fn swap_in_buffer_enqueues() {
        let now = Utc::now();
        let mut buffer = TaskBuffer::new();
        buffer.upsert(Task::new("t1", "a").with_duration(15).with_energy(2).with_deadline_urgency(9));
        buffer.upsert(Task::new("t2", "b").with_duration(15).with_energy(2).with_deadline_urgency(1));

        let mut sts = ShortTermScheduler::new();
        let res = handle_swap_in_buffer(15, 5, &mut buffer, &mut sts, now).unwrap();
        assert_eq!(res.swapped_in.len(), 1);
        assert_eq!(res.swapped_in[0].id, "t1");
    }
}
