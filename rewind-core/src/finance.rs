//! Finance record types for tracking transactions and goals

use chrono::NaiveDate;
use serde::{Deserialize, Serialize};

/// A financial transaction or obligation, tagged with goal metadata
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct FinanceRecord {
    /// Unique identifier for this record
    pub id: String,
    /// Date of the transaction (YYYY-MM-DD)
    pub date: NaiveDate,
    /// Human-readable description
    pub description: String,
    /// Positive = income, negative = expense
    pub amount: f64,
    /// Account/source (Chase, AMEX, Zelle, etc.)
    pub account: String,
    /// Deterministic category
    pub category: Category,
    /// Goal classification
    pub goal_tag: GoalTag,
    /// Associated goal name
    pub goal_name: String,
    /// Readiness score (0.0 - 1.0)
    pub readiness: f64,
}

/// Transaction categories matched deterministically
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum Category {
    #[serde(rename = "tuition")]
    Tuition,
    #[serde(rename = "credit-card")]
    CreditCard,
    #[serde(rename = "family-support")]
    FamilySupport,
    #[serde(rename = "savings")]
    Savings,
    #[serde(rename = "housing")]
    Housing,
    #[serde(rename = "food")]
    Food,
    #[serde(rename = "subscriptions")]
    Subscriptions,
    #[serde(rename = "income")]
    Income,
    #[serde(rename = "uncategorized")]
    Uncategorized,
}

impl Category {
    /// Get the base urgency threshold for this category
    pub fn urgency_threshold(&self) -> f64 {
        match self {
            Category::Tuition => 0.9,
            Category::CreditCard => 0.85,
            Category::FamilySupport => 0.8,
            Category::Savings => 0.6,
            Category::Housing => 0.5,
            Category::Food => 0.3,
            Category::Subscriptions => 0.2,
            Category::Income => 0.1,
            Category::Uncategorized => 0.4,
        }
    }

    /// Get the default action type
    pub fn action(&self) -> &'static str {
        match self {
            Category::Tuition | Category::CreditCard | Category::FamilySupport => "pay",
            Category::Savings => "save",
            _ => "review",
        }
    }
}

/// Goal timeframe classification
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum GoalTag {
    #[serde(rename = "long")]
    Long,
    #[serde(rename = "medium")]
    Medium,
    #[serde(rename = "short")]
    Short,
}

impl GoalTag {
    /// Get due hint based on timeframe
    pub fn due_hint(&self) -> &'static str {
        match self {
            GoalTag::Long => "This quarter",
            GoalTag::Medium => "This month",
            GoalTag::Short => "This week",
        }
    }
}

impl FinanceRecord {
    /// Create a new FinanceRecord
    pub fn new(
        id: impl Into<String>,
        date: NaiveDate,
        description: impl Into<String>,
        amount: f64,
        account: impl Into<String>,
        category: Category,
        goal_tag: GoalTag,
        goal_name: impl Into<String>,
    ) -> Self {
        Self {
            id: id.into(),
            date,
            description: description.into(),
            amount,
            account: account.into(),
            category,
            goal_tag,
            goal_name: goal_name.into(),
            readiness: 0.0,
        }
    }

    /// Returns true if this is an expense (negative amount)
    pub fn is_expense(&self) -> bool {
        self.amount < 0.0
    }

    /// Returns true if this is income (positive amount)
    pub fn is_income(&self) -> bool {
        self.amount > 0.0
    }

    /// Get the absolute amount
    pub fn abs_amount(&self) -> f64 {
        self.amount.abs()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_finance_record_creation() {
        let date = NaiveDate::from_ymd_opt(2026, 2, 18).unwrap();
        let record = FinanceRecord::new(
            "fr-001",
            date,
            "Texas State tuition",
            -4500.0,
            "Chase",
            Category::Tuition,
            GoalTag::Short,
            "Pay tuition",
        );
        assert_eq!(record.amount, -4500.0);
        assert!(record.is_expense());
        assert_eq!(record.category.urgency_threshold(), 0.9);
    }

    #[test]
    fn test_category_thresholds() {
        assert_eq!(Category::Tuition.urgency_threshold(), 0.9);
        assert_eq!(Category::CreditCard.urgency_threshold(), 0.85);
        assert_eq!(Category::Income.urgency_threshold(), 0.1);
    }
}
