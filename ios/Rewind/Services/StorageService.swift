import Foundation

// MARK: - Storage Service
/// Handles local persistence using UserDefaults and FileManager
/// Stores goals, tasks, finance records, and user preferences
class StorageService: ObservableObject {
    static let shared = StorageService()
    
    private let userDefaults = UserDefaults.standard
    private let fileManager = FileManager.default
    
    // MARK: - Keys
    private let goalsKey = "rewind.goals"
    private let tasksKey = "rewind.tasks"
    private let financialRecordsKey = "rewind.financial.records"
    private let onboardingCompleteKey = "rewind.onboarding.complete"
    private let timezoneKey = "rewind.timezone"
    private let energyLevelKey = "rewind.energy.level"
    
    @Published var isOnboardingComplete: Bool = false
    @Published var currentGoals: [Goal] = []
    @Published var currentTasks: [Task] = []
    @Published var financialRecords: [FinanceRecord] = []
    @Published var userTimezone: String = TimeZone.current.identifier
    @Published var currentEnergyLevel: Int = 5
    
    private init() {
        loadAll()
    }
    
    // MARK: - Goals
    func saveGoals(_ goals: [Goal]) {
        currentGoals = goals
        if let encoded = try? JSONEncoder().encode(goals) {
            userDefaults.set(encoded, forKey: goalsKey)
        }
    }
    
    func loadGoals() -> [Goal] {
        if let data = userDefaults.data(forKey: goalsKey),
           let decoded = try? JSONDecoder().decode([Goal].self, from: data) {
            return decoded
        }
        return []
    }
    
    // MARK: - Tasks
    func saveTasks(_ tasks: [Task]) {
        currentTasks = tasks
        if let encoded = try? JSONEncoder().encode(tasks) {
            userDefaults.set(encoded, forKey: tasksKey)
        }
    }
    
    func loadTasks() -> [Task] {
        if let data = userDefaults.data(forKey: tasksKey),
           let decoded = try? JSONDecoder().decode([Task].self, from: data) {
            return decoded
        }
        return []
    }
    
    // MARK: - Financial Records
    func saveFinancialRecords(_ records: [FinanceRecord]) {
        financialRecords = records
        if let encoded = try? JSONEncoder().encode(records) {
            userDefaults.set(encoded, forKey: financialRecordsKey)
        }
    }
    
    func loadFinancialRecords() -> [FinanceRecord] {
        if let data = userDefaults.data(forKey: financialRecordsKey),
           let decoded = try? JSONDecoder().decode([FinanceRecord].self, from: data) {
            return decoded
        }
        return []
    }
    
    // MARK: - Onboarding
    func markOnboardingComplete() {
        isOnboardingComplete = true
        userDefaults.set(true, forKey: onboardingCompleteKey)
    }
    
    func isOnboardingDone() -> Bool {
        userDefaults.bool(forKey: onboardingCompleteKey)
    }
    
    // MARK: - User Preferences
    func setTimezone(_ tz: String) {
        userTimezone = tz
        userDefaults.set(tz, forKey: timezoneKey)
    }
    
    func getTimezone() -> String {
        userDefaults.string(forKey: timezoneKey) ?? TimeZone.current.identifier
    }
    
    func setEnergyLevel(_ level: Int) {
        currentEnergyLevel = max(1, min(5, level))
        userDefaults.set(currentEnergyLevel, forKey: energyLevelKey)
    }
    
    func getEnergyLevel() -> Int {
        let level = userDefaults.integer(forKey: energyLevelKey)
        return level > 0 ? level : 5
    }
    
    // MARK: - File Management
    /// Get the app's Documents directory for storing files
    func documentsDirectory() -> URL {
        fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
    }
    
    /// Get the app's Application Support directory (for non-user-visible files)
    func applicationSupportDirectory() -> URL {
        let paths = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask)
        let appSupport = paths[0]
        
        // Create if needed
        try? fileManager.createDirectory(at: appSupport, withIntermediateDirectories: true)
        
        return appSupport
    }
    
    /// Save goals to markdown file
    func saveGoalsMarkdown(_ goals: [Goal]) {
        let content = goals.reduce("# Rewind Goals\n\n") { acc, goal in
            acc + "## \(goal.timeframe.rawValue)-term\n"
                + "- **\(goal.name)** (horizon: \(goal.horizonLabel), confidence: \(goal.confidencePercent)%)\n"
                + "  \(goal.description ?? "")\n\n"
        }
        
        let fileURL = applicationSupportDirectory().appendingPathComponent("goals.md")
        try? content.write(to: fileURL, atomically: true, encoding: .utf8)
    }
    
    /// Load goals from markdown file if it exists
    func loadGoalsMarkdown() -> String? {
        let fileURL = applicationSupportDirectory().appendingPathComponent("goals.md")
        return try? String(contentsOf: fileURL, encoding: .utf8)
    }
    
    /// Save imported CSV to app support
    func saveCSVFile(_ content: String, filename: String = "transactions.csv") {
        let fileURL = applicationSupportDirectory().appendingPathComponent(filename)
        try? content.write(to: fileURL, atomically: true, encoding: .utf8)
    }
    
    /// Load CSV file
    func loadCSVFile(filename: String = "transactions.csv") -> String? {
        let fileURL = applicationSupportDirectory().appendingPathComponent(filename)
        return try? String(contentsOf: fileURL, encoding: .utf8)
    }
    
    // MARK: - Bulk Operations
    func loadAll() {
        currentGoals = loadGoals()
        currentTasks = loadTasks()
        financialRecords = loadFinancialRecords()
        isOnboardingComplete = isOnboardingDone()
        userTimezone = getTimezone()
        currentEnergyLevel = getEnergyLevel()
    }
    
    func clearAll() {
        userDefaults.removeObject(forKey: goalsKey)
        userDefaults.removeObject(forKey: tasksKey)
        userDefaults.removeObject(forKey: financialRecordsKey)
        userDefaults.removeObject(forKey: onboardingCompleteKey)
        
        currentGoals = []
        currentTasks = []
        financialRecords = []
        isOnboardingComplete = false
    }
}
