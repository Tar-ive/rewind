import Foundation

// MARK: - Rewind Bridge Protocol
/// Interface to communicate with Rust rewind-core via FFI
/// This protocol defines all operations that the iOS app needs from the Rust library.
/// Implementation will use UniFFI bindings to call rewind-core functions.
protocol RewindBridgeProtocol: AnyObject {
    // MARK: - Setup & Onboarding
    /// Parse goals from markdown format
    func parseGoalsMarkdown(_ markdown: String) -> Result<[Goal], BridgeError>
    
    /// Apply setup answers (store goals, profile)
    func setupApply(goals: [Goal], timezone: String) -> Result<Void, BridgeError>
    
    // MARK: - Finance
    /// Categorize a transaction by description
    func categorizeTransaction(_ description: String) -> Result<FinanceCategory, BridgeError>
    
    /// Parse and categorize AMEX CSV
    func parseFinanceCSV(_ csvContent: String) -> Result<[FinanceRecord], BridgeError>
    
    // MARK: - Scheduling
    /// Plan today given goals and optional finance records
    func planDay(goals: [Goal], financialRecords: [FinanceRecord]?, energyLevel: Int) -> Result<[Task], BridgeError>
    
    /// Handle a disruption event and replan
    func handleDisruption(_ event: DisruptionEvent, currentTasks: [Task], backlogTasks: [Task], energyLevel: Int) -> Result<UpdatedSchedule, BridgeError>
    
    // MARK: - Reminders
    /// Project reminders for a task
    func projectReminders(for task: Task, policy: ReminderPolicy) -> Result<[ReminderIntent], BridgeError>
    
    // MARK: - Task Routing
    /// Route a task to the best matching goal
    func routeTask(_ task: Task, goals: [Goal]) -> Result<RouteResult, BridgeError>
}

// MARK: - Rewind Bridge Implementation
/// Concrete implementation that will use UniFFI bindings
/// For now, provides mock implementations for UI development
class RewindBridge: RewindBridgeProtocol {
    static let shared = RewindBridge()
    
    private init() {
        // Initialize connection to Rust FFI if needed
        // This will be where we set up UniFFI bindings
    }
    
    // MARK: - Setup & Onboarding
    func parseGoalsMarkdown(_ markdown: String) -> Result<[Goal], BridgeError> {
        do {
            // TODO: Call Rust FFI: ios_parse_goals_md(markdown)
            // For now, mock implementation
            let goals = parseGoalsMockImpl(markdown)
            return .success(goals)
        } catch {
            return .failure(.parsingFailed(error.localizedDescription))
        }
    }
    
    func setupApply(goals: [Goal], timezone: String) -> Result<Void, BridgeError> {
        do {
            // TODO: Call Rust FFI: ios_setup_apply(goals_json, timezone)
            // Would serialize to JSON and call Rust
            print("Setup applied: \(goals.count) goals, timezone: \(timezone)")
            return .success(())
        } catch {
            return .failure(.setupFailed(error.localizedDescription))
        }
    }
    
    // MARK: - Finance
    func categorizeTransaction(_ description: String) -> Result<FinanceCategory, BridgeError> {
        // TODO: Call Rust FFI: ios_categorize_transaction(description)
        let category = categorizeMockImpl(description)
        return .success(category)
    }
    
    func parseFinanceCSV(_ csvContent: String) -> Result<[FinanceRecord], BridgeError> {
        do {
            // TODO: Call Rust FFI: ios_parse_amex_csv(csvContent)
            let records = parseCSVMockImpl(csvContent)
            return .success(records)
        } catch {
            return .failure(.parsingFailed(error.localizedDescription))
        }
    }
    
    // MARK: - Scheduling
    func planDay(goals: [Goal], financialRecords: [FinanceRecord]?, energyLevel: Int) -> Result<[Task], BridgeError> {
        do {
            // TODO: Call Rust FFI: ios_plan_day(goals_json, records_json, energy_level)
            let tasks = planDayMockImpl(goals: goals, records: financialRecords, energy: energyLevel)
            return .success(tasks)
        } catch {
            return .failure(.schedulingFailed(error.localizedDescription))
        }
    }
    
    func handleDisruption(_ event: DisruptionEvent, currentTasks: [Task], backlogTasks: [Task], energyLevel: Int) -> Result<UpdatedSchedule, BridgeError> {
        do {
            // TODO: Call Rust FFI: ios_handle_disruption(event_json, tasks_json, backlog_json, energy)
            let schedule = handleDisruptionMockImpl(event: event, current: currentTasks, backlog: backlogTasks, energy: energyLevel)
            return .success(schedule)
        } catch {
            return .failure(.schedulingFailed(error.localizedDescription))
        }
    }
    
    // MARK: - Reminders
    func projectReminders(for task: Task, policy: ReminderPolicy) -> Result<[ReminderIntent], BridgeError> {
        do {
            // TODO: Call Rust FFI: ios_project_reminders(task_json, policy_json)
            let reminders = projectRemindersMockImpl(for: task, policy: policy)
            return .success(reminders)
        } catch {
            return .failure(.projectionFailed(error.localizedDescription))
        }
    }
    
    // MARK: - Task Routing
    func routeTask(_ task: Task, goals: [Goal]) -> Result<RouteResult, BridgeError> {
        do {
            // TODO: Call Rust FFI: ios_route_task(task_json, goals_json)
            let result = routeTaskMockImpl(task, goals)
            return .success(result)
        } catch {
            return .failure(.routingFailed(error.localizedDescription))
        }
    }
    
    // MARK: - Mock Implementations (for UI development)
    private func parseGoalsMockImpl(_ markdown: String) -> [Goal] {
        // Parse simple markdown format: ## Long-term\n- Goal
        Goal.mockGoals
    }
    
    private func categorizeMockImpl(_ description: String) -> FinanceCategory {
        let lower = description.lowercased()
        if lower.contains("zelle") || lower.contains("mom") || lower.contains("family") {
            return .familySupport
        } else if lower.contains("trader") || lower.contains("food") || lower.contains("restaurant") {
            return .food
        } else if lower.contains("stripe") || lower.contains("subscription") {
            return .subscriptions
        } else if lower.contains("tuition") || lower.contains("school") {
            return .tuition
        } else {
            return .uncategorized
        }
    }
    
    private func parseCSVMockImpl(_ csvContent: String) -> [FinanceRecord] {
        FinanceRecord.mockRecords
    }
    
    private func planDayMockImpl(goals: [Goal], records: [FinanceRecord]?, energy: Int) -> [Task] {
        Task.mockTasks
    }
    
    private func handleDisruptionMockImpl(event: DisruptionEvent, current: [Task], backlog: [Task], energy: Int) -> UpdatedSchedule {
        UpdatedSchedule.sample(energyLevel: energy)
    }
    
    private func projectRemindersMockImpl(for task: Task, policy: ReminderPolicy) -> [ReminderIntent] {
        ReminderIntent.mockReminders
    }
    
    private func routeTaskMockImpl(_ task: Task, _ goals: [Goal]) -> RouteResult {
        if let goal = goals.first {
            return RouteResult(goalId: goal.id, goalName: goal.name, confidence: .high, reason: "Keyword match")
        }
        return RouteResult(goalId: nil, goalName: nil, confidence: .none, reason: "No matching goals")
    }
}

// MARK: - Bridge Error
enum BridgeError: Error, Identifiable {
    case parsingFailed(String)
    case setupFailed(String)
    case categorizationFailed(String)
    case schedulingFailed(String)
    case projectionFailed(String)
    case routingFailed(String)
    case ffiNotAvailable
    case unknownError
    
    var id: String {
        UUID().uuidString
    }
    
    var displayMessage: String {
        switch self {
        case .parsingFailed(let msg):
            return "Failed to parse: \(msg)"
        case .setupFailed(let msg):
            return "Setup failed: \(msg)"
        case .categorizationFailed(let msg):
            return "Categorization failed: \(msg)"
        case .schedulingFailed(let msg):
            return "Scheduling failed: \(msg)"
        case .projectionFailed(let msg):
            return "Projection failed: \(msg)"
        case .routingFailed(let msg):
            return "Routing failed: \(msg)"
        case .ffiNotAvailable:
            return "Rust FFI bridge not available"
        case .unknownError:
            return "An unknown error occurred"
        }
    }
}

// MARK: - Supporting Types
struct ReminderPolicy: Codable {
    let urgentReminders: Int // P0 tasks
    let importantReminders: Int // P1 tasks
    let normalReminders: Int // P2 tasks
    
    static let `default` = ReminderPolicy(urgentReminders: 2, importantReminders: 2, normalReminders: 1)
}

struct RouteResult: Identifiable {
    let id = UUID()
    let goalId: String?
    let goalName: String?
    let confidence: RouteConfidence
    let reason: String
}

enum RouteConfidence {
    case high
    case medium
    case low
    case none
    
    var displayName: String {
        switch self {
        case .high: return "High"
        case .medium: return "Medium"
        case .low: return "Low"
        case .none: return "None"
        }
    }
}
