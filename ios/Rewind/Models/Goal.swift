import Foundation

// MARK: - Goal Model
/// Mirrors the Rust GoalDescriptor struct from rewind-core
struct Goal: Identifiable, Codable {
    let id: String
    let name: String
    let horizonYears: Double
    let ideaConfidence: Double // 0.0-1.0
    let timeframe: GoalTimeframe
    let priority: String // category
    let description: String?
    
    var confidencePercent: Int {
        Int(ideaConfidence * 100)
    }
    
    var horizonLabel: String {
        let years = Int(horizonYears)
        if years == 0 {
            return "Immediate"
        } else if years == 1 {
            return "1 year"
        } else {
            return "\(years) years"
        }
    }
}

// MARK: - Goal Timeframe
enum GoalTimeframe: String, Codable, CaseIterable {
    case long = "Long"
    case medium = "Medium"
    case short = "Short"
    
    var icon: String {
        switch self {
        case .long: return "hourglass.bottomhalf.fill"
        case .medium: return "hourglass.tophalf.fill"
        case .short: return "bolt.horizontal.fill"
        }
    }
    
    var color: Color {
        switch self {
        case .long: return .purple
        case .medium: return .blue
        case .short: return .green
        }
    }
    
    var displayName: String {
        self.rawValue
    }
}

// MARK: - Readiness Score
struct ReadinessScore: Codable {
    let confidence: Double // 0.0-1.0
    let milestone: String?
    let nextSteps: [String]?
    let signals: [String: Double]? // signal name -> boost
    
    var confidencePercent: Int {
        Int(confidence * 100)
    }
}

// MARK: - Goal Builder
extension Goal {
    static func sample(
        id: String = UUID().uuidString,
        name: String = "Sample Goal",
        horizonYears: Double = 1.0,
        ideaConfidence: Double = 0.8,
        timeframe: GoalTimeframe = .medium,
        priority: String = "development",
        description: String? = nil
    ) -> Goal {
        Goal(
            id: id,
            name: name,
            horizonYears: horizonYears,
            ideaConfidence: ideaConfidence,
            timeframe: timeframe,
            priority: priority,
            description: description
        )
    }
    
    static var mockGoals: [Goal] {
        [
            Goal.sample(
                name: "Move to SF for internship",
                horizonYears: 2.0,
                ideaConfidence: 0.9,
                timeframe: .long,
                priority: "career",
                description: "Secure internship and relocate"
            ),
            Goal.sample(
                name: "Save 15k emergency fund",
                horizonYears: 1.5,
                ideaConfidence: 0.85,
                timeframe: .medium,
                priority: "financial",
                description: "Build stable financial cushion"
            ),
            Goal.sample(
                name: "Pay credit card",
                horizonYears: 0.25,
                ideaConfidence: 1.0,
                timeframe: .short,
                priority: "financial",
                description: "Monthly payment due"
            ),
            Goal.sample(
                name: "Exercise 3x/week",
                horizonYears: 1.0,
                ideaConfidence: 0.7,
                timeframe: .short,
                priority: "health",
                description: "Build consistent fitness habit"
            ),
        ]
    }
}
