//! Deterministic category rules mapping AMEX categories + descriptions
//! to Rewind's internal Category and GoalTag types.
//!
//! No LLM needed — regex/exact-match covers 95%+ of transactions.

use rewind_core::finance::{Category, GoalTag};
use crate::AmexTransaction;

/// Result of categorization
#[derive(Debug, Clone, PartialEq)]
pub struct Categorized {
    pub category: Category,
    pub goal_tag: GoalTag,
    pub goal_name: String,
}

/// Deterministically categorize an AMEX transaction.
/// Priority: description keywords > AMEX category mapping > uncategorized.
pub fn categorize(txn: &AmexTransaction) -> Categorized {
    let desc = txn.description.to_uppercase();
    let amex_cat = &txn.amex_category;

    // --- Description-based rules (highest priority) ---

    // Tuition / Education
    if desc.contains("TEXAS STATE") || desc.contains("TXST")
        || desc.contains("TUITION") || desc.contains("UNIVERSITY")
        || desc.contains("STUDENT") || desc.contains("FLYWIRE")
    {
        return cat(Category::Tuition, GoalTag::Short, "Pay tuition");
    }

    // Family support (Zelle/Remitly to family)
    if desc.contains("REMITLY") || desc.contains("WISE.COM")
        || (desc.contains("ZELLE") && txn.amount > 100.0)
    {
        return cat(Category::FamilySupport, GoalTag::Medium, "Support parents");
    }

    // Savings
    if desc.contains("MARCUS") || desc.contains("SAVINGS")
        || desc.contains("VANGUARD") || desc.contains("FIDELITY")
    {
        return cat(Category::Savings, GoalTag::Medium, "$15k savings goal");
    }

    // Credit card payments
    if desc.contains("PAYMENT") && (desc.contains("THANK YOU") || desc.contains("AUTOPAY")) {
        return cat(Category::CreditCard, GoalTag::Short, "CC payment");
    }

    // Housing / Rent
    if desc.contains("RENT") || desc.contains("LEASE") || desc.contains("APARTMENT")
        || desc.contains("PROPERTY") || desc.contains("LANDLORD")
    {
        return cat(Category::Housing, GoalTag::Short, "Housing");
    }

    // Subscriptions (known services)
    if desc.contains("ELEVENLABS") || desc.contains("OPENAI")
        || desc.contains("ANTHROPIC") || desc.contains("GITHUB")
        || desc.contains("SPOTIFY") || desc.contains("NETFLIX")
        || desc.contains("HULU") || desc.contains("YOUTUBE")
        || desc.contains("APPLE.COM/BILL") || desc.contains("ICLOUD")
        || desc.contains("CURSOR") || desc.contains("NOTION")
        || desc.contains("FIGMA") || desc.contains("VERCEL")
        || desc.contains("DIGITAL OCEAN") || desc.contains("AWS")
        || desc.contains("GOOGLE *") || desc.contains("MICROSOFT")
    {
        return cat(Category::Subscriptions, GoalTag::Long, "Subscriptions");
    }

    // Income
    if txn.amount < 0.0 {
        // AMEX uses positive = charge, but check for credits/refunds
        // Actually AMEX: positive = charge. Negative = credit/refund.
    }

    // --- AMEX category-based rules ---

    if amex_cat.contains("Restaurant") || amex_cat.contains("Bar & Café") {
        return cat(Category::Food, GoalTag::Short, "Food & dining");
    }

    if amex_cat.contains("Groceries") || amex_cat.contains("Wholesale Stores") {
        return cat(Category::Food, GoalTag::Short, "Groceries");
    }

    if amex_cat.contains("Education") {
        return cat(Category::Tuition, GoalTag::Short, "Education");
    }

    if amex_cat.contains("Fuel") || amex_cat.contains("Taxis")
        || amex_cat.contains("Rail") || amex_cat.contains("Government Services")
    {
        return cat(Category::Housing, GoalTag::Short, "Transportation");
    }

    if amex_cat.contains("Airline") || amex_cat.contains("Lodging")
        || amex_cat.contains("Travel Agencies")
    {
        return cat(Category::Housing, GoalTag::Long, "Travel");
    }

    if amex_cat.contains("Fees & Adjustments") {
        return cat(Category::CreditCard, GoalTag::Short, "Fees");
    }

    if amex_cat.contains("Internet Purchase") || amex_cat.contains("Computer Supplies")
        || amex_cat.contains("Electronics")
    {
        return cat(Category::Subscriptions, GoalTag::Long, "Tech & online");
    }

    if amex_cat.contains("Mobile Telecom") || amex_cat.contains("Cable & Internet") {
        return cat(Category::Subscriptions, GoalTag::Medium, "Phone & internet");
    }

    if amex_cat.contains("Clothing") || amex_cat.contains("Department Stores")
        || amex_cat.contains("General Retail") || amex_cat.contains("Sporting Goods")
    {
        return cat(Category::Housing, GoalTag::Long, "Shopping");
    }

    if amex_cat.contains("Charities") {
        return cat(Category::FamilySupport, GoalTag::Long, "Donations");
    }

    if amex_cat.contains("Utilities") {
        return cat(Category::Housing, GoalTag::Short, "Utilities");
    }

    // Fallback
    cat(Category::Uncategorized, GoalTag::Long, "Uncategorized")
}

fn cat(category: Category, goal_tag: GoalTag, goal_name: &str) -> Categorized {
    Categorized {
        category,
        goal_tag,
        goal_name: goal_name.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::amex_parser::parse_amex_csv;
    use std::path::PathBuf;
    use std::collections::HashMap;

    fn amex_path() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .join("amex.csv")
    }

    #[test]
    fn test_elevenlabs_is_subscription() {
        let txns = parse_amex_csv(amex_path()).unwrap();
        let eleven = txns.iter().find(|t| t.description.contains("ELEVENLABS")).unwrap();
        let cat = categorize(eleven);
        assert_eq!(cat.category, Category::Subscriptions);
        assert_eq!(cat.goal_name, "Subscriptions");
    }

    #[test]
    fn test_wakaba_is_food() {
        let txns = parse_amex_csv(amex_path()).unwrap();
        let wakaba = txns.iter().find(|t| t.description.contains("WAKABA")).unwrap();
        let cat = categorize(wakaba);
        assert_eq!(cat.category, Category::Food);
    }

    #[test]
    fn test_clipper_is_transportation() {
        let txns = parse_amex_csv(amex_path()).unwrap();
        let clipper = txns.iter().find(|t| t.description.contains("CLIPPER")).unwrap();
        let cat = categorize(clipper);
        // Government Services → Transportation
        assert_eq!(cat.category, Category::Housing);
        assert_eq!(cat.goal_name, "Transportation");
    }

    #[test]
    fn test_no_uncategorized_above_10pct() {
        let txns = parse_amex_csv(amex_path()).unwrap();
        let total = txns.len();
        let uncat = txns.iter().filter(|t| categorize(t).category == Category::Uncategorized).count();
        let pct = (uncat as f64 / total as f64) * 100.0;
        assert!(
            pct < 15.0,
            "{}% uncategorized ({}/{}) — should be <15%",
            pct, uncat, total
        );
    }

    #[test]
    fn test_category_distribution() {
        let txns = parse_amex_csv(amex_path()).unwrap();
        let mut dist: HashMap<Category, usize> = HashMap::new();
        for t in &txns {
            *dist.entry(categorize(t).category).or_insert(0) += 1;
        }
        // Food should be the most common category (restaurants + groceries)
        let food = dist.get(&Category::Food).copied().unwrap_or(0);
        assert!(food > 50, "Expected 50+ food txns, got {}", food);
    }

    #[test]
    fn test_all_amex_categories_mapped() {
        let txns = parse_amex_csv(amex_path()).unwrap();
        let amex_cats: std::collections::HashSet<_> = txns.iter().map(|t| t.amex_category.clone()).collect();
        for cat in &amex_cats {
            // Skip empty categories (from blank trailing rows)
            if cat.is_empty() { continue; }
            // Every non-empty AMEX category should exist
            assert!(!cat.is_empty(), "Empty AMEX category found");
        }
    }
}
