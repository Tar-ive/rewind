//! rewind-core: Core types and utilities for the Rewind scheduler

pub mod finance;
pub mod goals;
pub mod planner;
pub mod signals;
pub mod user_goals;
pub mod routing;
pub mod time;
pub mod task;
pub mod task_buffer;
pub mod sts;
pub mod mts;
pub mod mts_task_buffer;
pub mod reminders;
pub mod scheduler_kernel;
pub mod disruption;

pub use finance::{FinanceRecord, Category, GoalTag};
pub use goals::{GoalDescriptor, GoalTimeframe, ReadinessScore};
pub use signals::{ExplicitSignal, ImplicitSignal, PatternType};
pub use user_goals::{UserGoal, Horizon, parse_goals_md};
pub use routing::{route_task, TaskLike, RouteResult, RouteConfidence};
pub use task::{Task, TaskStatus, Priority};
pub use task_buffer::TaskBuffer;
pub use sts::ShortTermScheduler;
pub use mts::{SwapResult, handle_swap_in, handle_swap_out, maybe_delegate_low_energy};
pub use mts_task_buffer::handle_swap_in_buffer;
pub use reminders::{project_task_reminders, ReminderIntent, ReminderPolicy, ReminderSource};
pub use scheduler_kernel::{
    ContextSentinel, DisruptionDetector, EnergyProvider, ProfilerProvider, SchedulerKernel,
    KernelOutput, ProfileSnapshot,
};
pub use disruption::{
    ContextChangeEvent,
    ContextSource,
    DisruptionEvent,
    DisruptionSeverity,
    UpdatedSchedule,
    DelegationQueue,
    DelegationItem,
};

/// Utility for categorizing transaction descriptions
pub mod categorizer {
    use super::{Category, GoalTag};

    /// Categorization result
    #[derive(Debug, Clone, Copy)]
    pub struct CategoryResult {
        pub category: Category,
        pub goal_tag: GoalTag,
        pub goal_name: &'static str,
    }

    /// Categorize a description using regex patterns
    pub fn categorize(description: &str) -> CategoryResult {
        let desc = description.to_lowercase();
        
        // Tuition / education
        if desc.contains("tuition") 
            || desc.contains("university")
            || desc.contains("txstate")
            || desc.contains("texas state")
            || desc.contains("student")
            || desc.contains("registrar")
            || desc.contains("education") {
            return CategoryResult {
                category: Category::Tuition,
                goal_tag: GoalTag::Short,
                goal_name: "Pay tuition",
            };
        }
        
        // Credit card payments
        if desc.contains("amex")
            || desc.contains("american express")
            || desc.contains("credit card")
            || desc.contains("visa payment")
            || desc.contains("chase payment")
            || desc.contains("autopay") {
            return CategoryResult {
                category: Category::CreditCard,
                goal_tag: GoalTag::Short,
                goal_name: "Pay off credit card",
            };
        }
        
        // Family support
        if (desc.contains("zelle") && (desc.contains("mom") || desc.contains("dad")))
            || desc.contains("nepal")
            || desc.contains("family")
            || desc.contains("western union")
            || desc.contains("remit")
            || desc.contains("gifts")
            || desc.contains("charity") {
            return CategoryResult {
                category: Category::FamilySupport,
                goal_tag: GoalTag::Short,
                goal_name: "Support parents monthly",
            };
        }
        
        // Savings / investment
        if desc.contains("savings")
            || desc.contains("invest")
            || desc.contains("transfer to savings")
            || desc.contains("deposit to savings") {
            return CategoryResult {
                category: Category::Savings,
                goal_tag: GoalTag::Medium,
                goal_name: "Save 15k by semester",
            };
        }
        
        // Rent / housing
        if desc.contains("rent")
            || desc.contains("housing")
            || desc.contains("apartment")
            || desc.contains("lease")
            || desc.contains("landlord") {
            return CategoryResult {
                category: Category::Housing,
                goal_tag: GoalTag::Long,
                goal_name: "Move to SF",
            };
        }
        
        // Income
        if desc.contains("payroll")
            || desc.contains("salary")
            || desc.contains("stipend")
            || desc.contains("freelance")
            || desc.contains("direct deposit")
            || desc.contains("income") {
            return CategoryResult {
                category: Category::Income,
                goal_tag: GoalTag::Medium,
                goal_name: "Save 15k by semester",
            };
        }
        
        // Food
        if desc.contains("grocery")
            || desc.contains("restaurant")
            || desc.contains("uber eats")
            || desc.contains("doordash")
            || desc.contains("grubhub")
            || desc.contains("dining")
            || desc.contains("food") {
            return CategoryResult {
                category: Category::Food,
                goal_tag: GoalTag::Short,
                goal_name: "Daily expenses",
            };
        }
        
        // Subscriptions
        if desc.contains("spotify")
            || desc.contains("netflix")
            || desc.contains("openai")
            || desc.contains("anthropic")
            || desc.contains("github")
            || desc.contains("subscription")
            || desc.contains("music")
            || desc.contains("gym") {
            return CategoryResult {
                category: Category::Subscriptions,
                goal_tag: GoalTag::Short,
                goal_name: "Daily expenses",
            };
        }
        
        // Default
        CategoryResult {
            category: Category::Uncategorized,
            goal_tag: GoalTag::Short,
            goal_name: "Daily expenses",
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn test_categorize_tuition() {
            let result = categorize("Texas State University tuition payment");
            assert_eq!(result.category, Category::Tuition);
            assert_eq!(result.goal_tag, GoalTag::Short);
        }

        #[test]
        fn test_categorize_credit_card() {
            let result = categorize("AMEX autopay statement");
            assert_eq!(result.category, Category::CreditCard);
            assert_eq!(result.goal_name, "Pay off credit card");
        }

        #[test]
        fn test_categorize_family_support() {
            let result = categorize("Zelle to Mom for monthly support");
            assert_eq!(result.category, Category::FamilySupport);
            assert_eq!(result.goal_name, "Support parents monthly");
        }

        #[test]
        fn test_categorize_savings() {
            let result = categorize("Transfer to savings account");
            assert_eq!(result.category, Category::Savings);
            assert_eq!(result.goal_tag, GoalTag::Medium);
        }

        #[test]
        fn test_categorize_housing() {
            let result = categorize("Monthly rent payment - apartment");
            assert_eq!(result.category, Category::Housing);
            assert_eq!(result.goal_tag, GoalTag::Long);
        }

        #[test]
        fn test_categorize_income() {
            let result = categorize("Direct deposit - payroll");
            assert_eq!(result.category, Category::Income);
        }
    }
}

pub use categorizer::{categorize, CategoryResult};
