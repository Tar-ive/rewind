import Foundation

// MARK: - Updated Schedule (from Rust scheduler_kernel)
/// Represents the output of the scheduling engine after handling disruption
struct UpdatedSchedule: Codable {
    let day: Date
    let taskOrder: [String] // task IDs in priority order
    let swappedOut: [String] // tasks removed due to disruption
    let swappedIn: [String] // tasks added from backlog
    let energyLevel: Int // 1-5
    
    var displayDate: String {
        day.formatted(date: .abbreviated, time: .omitted)
    }
    
    var energyBars: String {
        String(repeating: "🔋", count: energyLevel) +
        String(repeating: "⚪", count: 5 - energyLevel)
    }
}

// MARK: - Disruption Event
/// Represents a detected disruption that triggers replanning
struct DisruptionEvent: Codable {
    let severity: DisruptionSeverity
    let cascadeCount: Int
    let reason: String
    let contextEventId: String
    let timestamp: Date
    
    var icon: String {
        switch severity {
        case .minor: return "exclamationmark.circle"
        case .major: return "exclamationmark.circle.fill"
        case .critical: return "xmark.circle.fill"
        }
    }
    
    var color: Color {
        switch severity {
        case .minor: return .yellow
        case .major: return .orange
        case .critical: return .red
        }
    }
}

// MARK: - Disruption Severity
enum DisruptionSeverity: String, Codable, CaseIterable {
    case minor = "minor"
    case major = "major"
    case critical = "critical"
    
    var displayName: String {
        self.rawValue.capitalized
    }
}

// MARK: - Delegation Queue Item
/// Represents a task that can be automated/delegated
struct DelegationQueueItem: Identifiable, Codable {
    let id: String
    let taskId: String
    let channel: String // "email", "slack", "sms", etc.
    let draftType: String // "reply", "new_message", etc.
    let priority: Int
    
    var icon: String {
        switch channel.lowercased() {
        case "email": return "envelope.fill"
        case "slack": return "bubble.right.fill"
        case "sms", "imessage": return "message.fill"
        default: return "paperplane.fill"
        }
    }
}

// MARK: - Reminder Intent
/// Represents a reminder to surface for a task
struct ReminderIntent: Identifiable, Codable {
    let id: String
    let taskId: String
    let title: String
    let body: String
    let sendAt: Date
    let dedupeKey: String // prevent duplicate reminders
    
    var displayTime: String {
        sendAt.formatted(time: .shortened)
    }
    
    var displayDate: String {
        sendAt.formatted(date: .abbreviated, time: .omitted)
    }
    
    var relativeTime: String {
        let now = Date()
        let components = Calendar.current.dateComponents([.day, .hour, .minute], from: now, to: sendAt)
        
        if let day = components.day, day > 0 {
            return "in \(day)d"
        } else if let hour = components.hour, hour > 0 {
            return "in \(hour)h"
        } else if let minute = components.minute, minute > 0 {
            return "in \(minute)m"
        } else {
            return "now"
        }
    }
}

// MARK: - Sample Data
extension UpdatedSchedule {
    static func sample(
        day: Date = Date(),
        taskOrder: [String] = ["task_1", "task_2", "task_3"],
        swappedOut: [String] = ["task_old"],
        swappedIn: [String] = ["task_new"],
        energyLevel: Int = 4
    ) -> UpdatedSchedule {
        UpdatedSchedule(
            day: day,
            taskOrder: taskOrder,
            swappedOut: swappedOut,
            swappedIn: swappedIn,
            energyLevel: energyLevel
        )
    }
}

extension DisruptionEvent {
    static func sample(
        severity: DisruptionSeverity = .major,
        cascadeCount: Int = 1,
        reason: String = "Meeting extended by 45 minutes",
        contextEventId: String = "gcal:abc123",
        timestamp: Date = Date()
    ) -> DisruptionEvent {
        DisruptionEvent(
            severity: severity,
            cascadeCount: cascadeCount,
            reason: reason,
            contextEventId: contextEventId,
            timestamp: timestamp
        )
    }
}

extension ReminderIntent {
    static var mockReminders: [ReminderIntent] {
        [
            ReminderIntent(
                id: UUID().uuidString,
                taskId: "task_1",
                title: "Review PSET",
                body: "You have focused blocks to work on your problem set",
                sendAt: Date().addingTimeInterval(3600),
                dedupeKey: "task_1:1"
            ),
            ReminderIntent(
                id: UUID().uuidString,
                taskId: "task_2",
                title: "Pay credit card",
                body: "Quick task: settle your credit card balance",
                sendAt: Date().addingTimeInterval(7200),
                dedupeKey: "task_2:1"
            ),
        ]
    }
}
