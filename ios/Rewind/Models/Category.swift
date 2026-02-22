import Foundation

// MARK: - Finance Category
/// Mirrors the 9 categories from rewind-finance
enum FinanceCategory: String, Codable, CaseIterable {
    case tuition = "Tuition"
    case creditCard = "CreditCard"
    case familySupport = "FamilySupport"
    case savings = "Savings"
    case housing = "Housing"
    case food = "Food"
    case subscriptions = "Subscriptions"
    case income = "Income"
    case uncategorized = "Uncategorized"
    
    var icon: String {
        switch self {
        case .tuition: return "book.fill"
        case .creditCard: return "creditcard.fill"
        case .familySupport: return "person.2.fill"
        case .savings: return "banknote.fill"
        case .housing: return "house.fill"
        case .food: return "fork.knife.circle.fill"
        case .subscriptions: return "newspaper.fill"
        case .income: return "dollarsign.circle.fill"
        case .uncategorized: return "questionmark.circle"
        }
    }
    
    var color: Color {
        switch self {
        case .tuition: return .blue
        case .creditCard: return .red
        case .familySupport: return .pink
        case .savings: return .green
        case .housing: return .orange
        case .food: return .yellow
        case .subscriptions: return .purple
        case .income: return .green
        case .uncategorized: return .gray
        }
    }
    
    var displayName: String {
        switch self {
        case .tuition: return "Tuition"
        case .creditCard: return "Credit Card"
        case .familySupport: return "Family Support"
        case .savings: return "Savings"
        case .housing: return "Housing"
        case .food: return "Food & Dining"
        case .subscriptions: return "Subscriptions"
        case .income: return "Income"
        case .uncategorized: return "Uncategorized"
        }
    }
}

// MARK: - Finance Record
/// Represents a transaction with category and goal mapping
struct FinanceRecord: Identifiable, Codable {
    let id: String
    let date: Date
    let description: String
    let amount: Double
    let account: String
    let category: FinanceCategory
    let goalTag: GoalTimeframe? // maps to Long/Medium/Short goal
    let goalName: String?
    let readiness: Double? // confidence this serves a goal
    
    var displayAmount: String {
        if amount > 0 {
            return "+$\(String(format: "%.2f", amount))"
        } else {
            return "-$\(String(format: "%.2f", abs(amount)))"
        }
    }
    
    var displayDate: String {
        date.formatted(date: .abbreviated, time: .omitted)
    }
    
    var readinessPercent: Int? {
        guard let readiness else { return nil }
        return Int(readiness * 100)
    }
}

// MARK: - Finance Record Builder
extension FinanceRecord {
    static func sample(
        id: String = UUID().uuidString,
        date: Date = Date(),
        description: String = "Transaction",
        amount: Double = -100.0,
        account: String = "Amex",
        category: FinanceCategory = .uncategorized,
        goalTag: GoalTimeframe? = nil,
        goalName: String? = nil,
        readiness: Double? = nil
    ) -> FinanceRecord {
        FinanceRecord(
            id: id,
            date: date,
            description: description,
            amount: amount,
            account: account,
            category: category,
            goalTag: goalTag,
            goalName: goalName,
            readiness: readiness
        )
    }
    
    static var mockRecords: [FinanceRecord] {
        [
            FinanceRecord.sample(
                description: "Zelle to Mom",
                amount: -500.0,
                category: .familySupport,
                goalTag: .short,
                goalName: "Family Support",
                readiness: 0.95
            ),
            FinanceRecord.sample(
                description: "Trader Joe's",
                amount: -67.42,
                category: .food,
                goalTag: .short,
                goalName: "Sustenance",
                readiness: 0.7
            ),
            FinanceRecord.sample(
                description: "Stripe subscription",
                amount: -29.00,
                category: .subscriptions,
                goalTag: .medium,
                goalName: "Career Tools",
                readiness: 0.6
            ),
            FinanceRecord.sample(
                description: "Tuition payment",
                amount: -3500.0,
                category: .tuition,
                goalTag: .long,
                goalName: "Education",
                readiness: 1.0
            ),
            FinanceRecord.sample(
                description: "SoFi Transfer",
                amount: 1000.0,
                category: .income,
                goalTag: .medium,
                goalName: "Save 15k",
                readiness: 0.9
            ),
        ]
    }
}
