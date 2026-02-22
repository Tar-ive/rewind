import SwiftUI

struct DayPlanView: View {
    @EnvironmentObject var storage: StorageService
    @State private var tasks: [Task] = []
    @State private var isLoading = false
    @State private var selectedTask: Task? = nil
    @State private var showDisruptionAlert = false
    @State private var disruption: DisruptionEvent? = nil
    
    var body: some View {
        ZStack {
            Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.10, green: 0.10, blue: 0.12, alpha: 1.0) : UIColor(red: 0.95, green: 0.95, blue: 0.97, alpha: 1.0) })
                .ignoresSafeArea()
            
            NavigationStack {
                VStack(spacing: 0) {
                    // Header with date and energy
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Today's Plan")
                                    .font(.title2)
                                    .fontWeight(.bold)
                                Text(Date().formatted(date: .abbreviated, time: .omitted))
                                    .font(.caption)
                                    .foregroundColor(.gray)
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: 4) {
                                Text("Energy")
                                    .font(.caption)
                                    .foregroundColor(.gray)
                                Text(String(repeating: "🔋", count: storage.currentEnergyLevel) +
                                     String(repeating: "⚪", count: 5 - storage.currentEnergyLevel))
                                    .font(.body)
                            }
                        }
                        
                        // Quick action buttons
                        HStack(spacing: 8) {
                            Button(action: { refetchPlan() }) {
                                Label("Replan", systemImage: "arrow.counterclockwise.circle.fill")
                                    .font(.caption)
                            }
                            .buttonStyle(.bordered)
                            
                            Button(action: { simulateDisruption() }) {
                                Label("Disrupt", systemImage: "exclamationmark.triangle.fill")
                                    .font(.caption)
                            }
                            .buttonStyle(.bordered)
                            
                            Spacer()
                        }
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 16)
                    .background(Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.15, green: 0.15, blue: 0.17, alpha: 1.0) : UIColor(red: 0.90, green: 0.90, blue: 0.92, alpha: 1.0) }))
                    
                    // Task list
                    if isLoading {
                        ProgressView()
                            .frame(maxHeight: .infinity)
                    } else if tasks.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "checkmark.circle")
                                .font(.system(size: 48))
                                .foregroundColor(.gray)
                            Text("No tasks for today")
                                .font(.headline)
                                .foregroundColor(.gray)
                            Text("Add goals or import transactions to get started")
                                .font(.caption)
                                .foregroundColor(.gray)
                                .multilineTextAlignment(.center)
                        }
                        .frame(maxHeight: .infinity)
                        .frame(maxWidth: .infinity)
                    } else {
                        List {
                            ForEach(tasks) { task in
                                TaskRow(task: task, selectedTask: $selectedTask)
                                    .listRowBackground(
                                        Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.12, green: 0.12, blue: 0.14, alpha: 1.0) : UIColor(red: 0.93, green: 0.93, blue: 0.95, alpha: 1.0) })
                                    )
                            }
                        }
                        .listStyle(.plain)
                        .scrollContentBackground(.hidden)
                    }
                    
                    Spacer(minLength: 0)
                }
                .navigationTitle("Daily Plan")
                .navigationBarTitleDisplayMode(.inline)
            }
        }
        .sheet(item: $selectedTask) { task in
            TaskDetailView(task: task)
        }
        .alert("Disruption Detected", isPresented: $showDisruptionAlert, presenting: disruption) { disruption in
            Button("View Changes", role: .default) {
                // Would show the updated schedule
            }
            Button("Dismiss", role: .cancel) { }
        } message: { disruption in
            Text("\(disruption.severity.displayName): \(disruption.reason)")
        }
        .onAppear {
            loadTasks()
        }
    }
    
    private func loadTasks() {
        isLoading = true
        // Call Rust bridge to plan day
        let result = RewindBridge.shared.planDay(
            goals: storage.currentGoals,
            financialRecords: storage.financialRecords.isEmpty ? nil : storage.financialRecords,
            energyLevel: storage.currentEnergyLevel
        )
        
        switch result {
        case .success(let plannedTasks):
            self.tasks = plannedTasks
        case .failure(let error):
            print("Error planning day: \(error.displayMessage)")
            // Fall back to mock tasks
            self.tasks = Task.mockTasks
        }
        isLoading = false
    }
    
    private func refetchPlan() {
        loadTasks()
    }
    
    private func simulateDisruption() {
        let disruption = DisruptionEvent(
            severity: .major,
            cascadeCount: 2,
            reason: "Meeting extended by 45 minutes",
            contextEventId: "gcal:abc123",
            timestamp: Date()
        )
        
        self.disruption = disruption
        showDisruptionAlert = true
        
        // Call Rust bridge to handle disruption
        let result = RewindBridge.shared.handleDisruption(
            disruption,
            currentTasks: tasks,
            backlogTasks: [],
            energyLevel: storage.currentEnergyLevel
        )
        
        switch result {
        case .success(let schedule):
            print("Updated schedule: \(schedule)")
            // Update tasks based on new schedule
            loadTasks()
        case .failure(let error):
            print("Error handling disruption: \(error.displayMessage)")
        }
    }
}

// MARK: - Task Row
struct TaskRow: View {
    let task: Task
    @Binding var selectedTask: Task?
    
    var body: some View {
        Button(action: { selectedTask = task }) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    // Priority indicator
                    Image(systemName: "circle.fill")
                        .font(.caption)
                        .foregroundColor(task.priority.badgeColor)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text(task.title)
                            .font(.headline)
                            .foregroundColor(.white)
                        
                        HStack(spacing: 12) {
                            Label("\(task.estimatedDuration)m", systemImage: "clock")
                                .font(.caption)
                                .foregroundColor(.gray)
                            
                            Label(task.energyBars, systemImage: "bolt.fill")
                                .font(.caption)
                                .foregroundColor(.gray)
                            
                            if let deadline = task.deadline {
                                Label(deadline.formatted(time: .shortened), systemImage: "calendar")
                                    .font(.caption)
                                    .foregroundColor(.red)
                            }
                        }
                    }
                    
                    Spacer()
                    
                    VStack(alignment: .trailing, spacing: 4) {
                        Text(task.cognitiveIndicator)
                            .font(.body)
                        Text(task.status.icon)
                            .font(.body)
                            .foregroundColor(Color(task.status.color))
                    }
                }
            }
            .padding(.vertical, 8)
        }
    }
}

// MARK: - Task Detail View
struct TaskDetailView: View {
    @Environment(\.dismiss) var dismiss
    let task: Task
    @State private var status: TaskStatus
    
    init(task: Task) {
        self.task = task
        _status = State(initialValue: task.status)
    }
    
    var body: some View {
        NavigationStack {
            List {
                Section("Task Details") {
                    HStack {
                        Text("Title")
                        Spacer()
                        Text(task.title).foregroundColor(.gray)
                    }
                    
                    HStack {
                        Text("Priority")
                        Spacer()
                        Text(task.priority.displayName)
                            .foregroundColor(task.priority.badgeColor)
                    }
                    
                    HStack {
                        Text("Duration")
                        Spacer()
                        Text("\(task.estimatedDuration) minutes")
                            .foregroundColor(.gray)
                    }
                }
                
                Section("Energy & Cognition") {
                    HStack {
                        Text("Energy Cost")
                        Spacer()
                        Text(task.energyBars).font(.body)
                    }
                    
                    HStack {
                        Text("Cognitive Load")
                        Spacer()
                        Text(task.cognitiveIndicator).font(.headline)
                    }
                }
                
                Section("Status") {
                    Picker("Current Status", selection: $status) {
                        ForEach(TaskStatus.allCases, id: \.self) { s in
                            Text(s.rawValue).tag(s)
                        }
                    }
                }
                
                if let deadline = task.deadline {
                    Section("Deadline") {
                        HStack {
                            Text("Due")
                            Spacer()
                            Text(deadline.formatted(date: .abbreviated, time: .shortened))
                                .foregroundColor(.orange)
                        }
                    }
                }
            }
            .navigationTitle(task.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

#Preview {
    DayPlanView()
        .environmentObject(StorageService.shared)
}
