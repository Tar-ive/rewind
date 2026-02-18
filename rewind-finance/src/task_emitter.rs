//! Task emitter: converts categorized AMEX transactions into actionable tasks
//! grouped by goal horizon (short/medium/long).

use rewind_core::finance::{Category, GoalTag, FinanceRecord};
use crate::amex_parser::AmexTransaction;
use crate::category_rules::{categorize, Categorized};
use chrono::NaiveDate;
use std::collections::HashMap;

/// A task generated from financial data
#[derive(Debug, Clone)]
pub struct FinanceTask {
    pub goal_tag: GoalTag,
    pub goal_name: String,
    pub category: Category,
    pub urgency: f64,
    pub total_amount: f64,
    pub transaction_count: usize,
    pub summary: String,
}

/// Emits tasks from a set of AMEX transactions
pub struct TaskEmitter;

impl TaskEmitter {
    /// Process transactions into grouped tasks
    pub fn emit(txns: &[AmexTransaction]) -> Vec<FinanceTask> {
        // Group by (goal_name, category)
        let mut groups: HashMap<(String, Category), Vec<(&AmexTransaction, Categorized)>> =
            HashMap::new();

        for txn in txns {
            let cat = categorize(txn);
            groups
                .entry((cat.goal_name.clone(), cat.category))
                .or_default()
                .push((txn, cat));
        }

        let mut tasks: Vec<FinanceTask> = groups
            .into_iter()
            .map(|((goal_name, category), items)| {
                let total: f64 = items.iter().map(|(t, _)| t.amount).sum();
                let count = items.len();
                let goal_tag = items[0].1.goal_tag;

                // Urgency: base from category + amount boost
                let base = category.urgency_threshold();
                let amount_boost = (total.abs() / 1000.0).min(0.3);
                let urgency = (base + amount_boost).min(1.0);

                let summary = format!(
                    "{}: ${:.2} across {} transactions — {}",
                    goal_name,
                    total.abs(),
                    count,
                    goal_tag.due_hint()
                );

                FinanceTask {
                    goal_tag,
                    goal_name,
                    category,
                    urgency,
                    total_amount: total,
                    transaction_count: count,
                    summary,
                }
            })
            .collect();

        // Sort by urgency descending
        tasks.sort_by(|a, b| b.urgency.partial_cmp(&a.urgency).unwrap());
        tasks
    }

    /// Convert to FinanceRecords for integration with rewind-core
    pub fn to_records(txns: &[AmexTransaction], account: &str) -> Vec<FinanceRecord> {
        txns.iter()
            .enumerate()
            .map(|(i, txn)| {
                let cat = categorize(txn);
                FinanceRecord::new(
                    format!("amex-{:04}", i),
                    txn.date,
                    &txn.description,
                    -txn.amount, // AMEX positive = charge = expense
                    account,
                    cat.category,
                    cat.goal_tag,
                    &cat.goal_name,
                )
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::amex_parser::parse_amex_csv;
    use std::path::PathBuf;

    fn amex_path() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .join("amex.csv")
    }

    #[test]
    fn test_emit_tasks_from_real_data() {
        let txns = parse_amex_csv(amex_path()).unwrap();
        let tasks = TaskEmitter::emit(&txns);

        assert!(!tasks.is_empty());
        // Should have food, subscriptions at minimum
        assert!(tasks.iter().any(|t| t.category == Category::Food));
        assert!(tasks.iter().any(|t| t.category == Category::Subscriptions));
    }

    #[test]
    fn test_tasks_sorted_by_urgency() {
        let txns = parse_amex_csv(amex_path()).unwrap();
        let tasks = TaskEmitter::emit(&txns);

        for w in tasks.windows(2) {
            assert!(w[0].urgency >= w[1].urgency, "Tasks not sorted by urgency");
        }
    }

    #[test]
    fn test_to_records() {
        let txns = parse_amex_csv(amex_path()).unwrap();
        let records = TaskEmitter::to_records(&txns, "AMEX");

        assert_eq!(records.len(), txns.len());
        // AMEX charges are positive, records should flip to negative (expense)
        let first = &records[0];
        assert!(first.is_expense(), "AMEX charges should become negative");
        assert_eq!(first.account, "AMEX");
    }

    #[test]
    fn test_food_spending_total() {
        let txns = parse_amex_csv(amex_path()).unwrap();
        let tasks = TaskEmitter::emit(&txns);
        let food_tasks: Vec<_> = tasks.iter().filter(|t| t.category == Category::Food).collect();
        let total_food: f64 = food_tasks.iter().map(|t| t.total_amount.abs()).sum();
        // From our analysis: ~$808 groceries + ~$720 restaurants = ~$1528
        assert!(total_food > 1000.0, "Expected >$1000 food spending, got ${:.2}", total_food);
    }
}
