import Foundation

// MARK: - Task Model
/// Mirrors the Rust Task struct from rewind-core
struct Task: Identifiable, Codable {
    let id: String
    let title: String
    let status: TaskStatus
    let priority: Priority
    let estimatedDuration: Int // minutes
    let energyCost: Int // 1-5
    let cognitiveCost: Int // 1-5
    let deadline: Date?
    let deadlineUrgency: Int // 0-10
    let goalId: String?
    
    var displayDeadline: String {
        guard let deadline else { return "No deadline" }
        return deadline.formatted(date: .abbreviated, time: .shortened)
    }
    
    var energyBars: String {
        String(repeating: "⚡", count: energyCost)
    }
    
    var cognitiveIndicator: String {
        switch cognitiveCost {
        case 1...2: return "🟢"
        case 3...4: return "🟡"
        case 5: return "🔴"
        default: return "⚪"
        }
    }
}

// MARK: - Task Status
enum TaskStatus: String, Codable {
    case backlog = "Backlog"
    case active = "Active"
    case inProgress = "InProgress"
    case completed = "Completed"
    case swappedOut = "SwappedOut"
    case delegated = "Delegated"
    
    var icon: String {
        switch self {
        case .backlog: return "inbox.stack"
        case .active: return "checkmark.circle"
        case .inProgress: return "play.circle"
        case .completed: return "checkmark.circle.fill"
        case .swappedOut: return "x.circle"
        case .delegated: return "hand.raised.circle"
        }
    }
    
    var color: String {
        switch self {
        case .completed: return "green"
        case .inProgress: return "blue"
        case .swappedOut: return "red"
        case .delegated: return "orange"
        default: return "gray"
        }
    }
}

// MARK: - Priority
enum Priority: String, Codable, CaseIterable {
    case p0Urgent = "P0Urgent"
    case p1Important = "P1Important"
    case p2Normal = "P2Normal"
    case p3Background = "P3Background"
    
    var level: Int {
        switch self {
        case .p0Urgent: return 0
        case .p1Important: return 1
        case .p2Normal: return 2
        case .p3Background: return 3
        }
    }
    
    var displayName: String {
        switch self {
        case .p0Urgent: return "Urgent"
        case .p1Important: return "Important"
        case .p2Normal: return "Normal"
        case .p3Background: return "Background"
        }
    }
    
    var badgeColor: Color {
        switch self {
        case .p0Urgent: return .red
        case .p1Important: return .orange
        case .p2Normal: return .blue
        case .p3Background: return .gray
        }
    }
}

// MARK: - Task Builder (for creating mock data)
extension Task {
    static func sample(
        id: String = UUID().uuidString,
        title: String = "Sample Task",
        status: TaskStatus = .backlog,
        priority: Priority = .p2Normal,
        energyCost: Int = 3,
        cognitiveCost: Int = 3,
        deadline: Date? = nil,
        deadlineUrgency: Int = 5,
        goalId: String? = nil
    ) -> Task {
        Task(
            id: id,
            title: title,
            status: status,
            priority: priority,
            estimatedDuration: 45,
            energyCost: energyCost,
            cognitiveCost: cognitiveCost,
            deadline: deadline,
            deadlineUrgency: deadlineUrgency,
            goalId: goalId
        )
    }
    
    static var mockTasks: [Task] {
        [
            Task.sample(title: "Review PSET", priority: .p1Important, energyCost: 4, cognitiveCost: 5, deadline: Date().addingTimeInterval(86400)),
            Task.sample(title: "Pay credit card", priority: .p0Urgent, energyCost: 1, cognitiveCost: 1),
            Task.sample(title: "Gym session", priority: .p2Normal, energyCost: 5, cognitiveCost: 1),
            Task.sample(title: "Email clients", priority: .p2Normal, energyCost: 2, cognitiveCost: 2),
            Task.sample(title: "Prep for standup", priority: .p1Important, energyCost: 2, cognitiveCost: 3),
        ]
    }
}
