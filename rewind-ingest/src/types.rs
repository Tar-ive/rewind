use chrono::NaiveDate;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum StatementKind {
    CreditCard,
    BankAccount,
}

/// Normalized output of statement parsers (bank-agnostic)
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StatementTransaction {
    pub trans_date: NaiveDate,
    pub post_date: Option<NaiveDate>,
    pub description: String,
    /// Positive number means charge/spend; negative means credit/refund.
    pub amount: f64,
    /// Optional running balance (debit/checking statements often include this)
    pub balance: Option<f64>,
    pub currency: String,
    pub raw_category: Option<String>,
}
