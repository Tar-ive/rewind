import SwiftUI

struct GoalsView: View {
    @EnvironmentObject var storage: StorageService
    @State private var goals: [Goal] = []
    @State private var showAddGoal = false
    @State private var selectedGoal: Goal? = nil
    @State private var filterTimeframe: GoalTimeframe? = nil
    
    var filteredGoals: [Goal] {
        if let filter = filterTimeframe {
            return goals.filter { $0.timeframe == filter }
        }
        return goals
    }
    
    var body: some View {
        ZStack {
            Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.10, green: 0.10, blue: 0.12, alpha: 1.0) : UIColor(red: 0.95, green: 0.95, blue: 0.97, alpha: 1.0) })
                .ignoresSafeArea()
            
            NavigationStack {
                VStack(spacing: 0) {
                    // Filter tabs
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            FilterButton(
                                title: "All",
                                isSelected: filterTimeframe == nil,
                                action: { filterTimeframe = nil }
                            )
                            
                            ForEach(GoalTimeframe.allCases, id: \.self) { timeframe in
                                FilterButton(
                                    title: timeframe.rawValue,
                                    isSelected: filterTimeframe == timeframe,
                                    action: { filterTimeframe = timeframe }
                                )
                            }
                        }
                        .padding(.horizontal)
                    }
                    .padding(.vertical, 12)
                    .background(Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.15, green: 0.15, blue: 0.17, alpha: 1.0) : UIColor(red: 0.90, green: 0.90, blue: 0.92, alpha: 1.0) }))
                    
                    // Goals list
                    if filteredGoals.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "target")
                                .font(.system(size: 48))
                                .foregroundColor(.gray)
                            Text("No goals yet")
                                .font(.headline)
                                .foregroundColor(.gray)
                            Button(action: { showAddGoal = true }) {
                                Label("Add Goal", systemImage: "plus.circle.fill")
                            }
                            .buttonStyle(.bordered)
                        }
                        .frame(maxHeight: .infinity)
                        .frame(maxWidth: .infinity)
                    } else {
                        List {
                            ForEach(filteredGoals) { goal in
                                GoalRow(goal: goal)
                                    .onTapGesture {
                                        selectedGoal = goal
                                    }
                                    .listRowBackground(
                                        Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.12, green: 0.12, blue: 0.14, alpha: 1.0) : UIColor(red: 0.93, green: 0.93, blue: 0.95, alpha: 1.0) })
                                    )
                            }
                        }
                        .listStyle(.plain)
                        .scrollContentBackground(.hidden)
                    }
                }
                .navigationTitle("Goals")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .primaryAction) {
                        Button(action: { showAddGoal = true }) {
                            Image(systemName: "plus.circle.fill")
                                .foregroundColor(.blue)
                        }
                    }
                }
            }
        }
        .sheet(isPresented: $showAddGoal) {
            AddGoalView { newGoal in
                goals.append(newGoal)
                storage.saveGoals(goals)
            }
        }
        .sheet(item: $selectedGoal) { goal in
            GoalDetailView(goal: goal)
        }
        .onAppear {
            goals = storage.currentGoals.isEmpty ? Goal.mockGoals : storage.currentGoals
        }
    }
}

// MARK: - Goal Row
struct GoalRow: View {
    let goal: Goal
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        Image(systemName: goal.timeframe.icon)
                            .foregroundColor(goal.timeframe.color)
                            .font(.body)
                        
                        Text(goal.name)
                            .font(.headline)
                            .foregroundColor(.white)
                    }
                    
                    Text(goal.description ?? "No description")
                        .font(.caption)
                        .foregroundColor(.gray)
                        .lineLimit(2)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    HStack(spacing: 4) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.caption)
                            .foregroundColor(.green)
                        Text("\(goal.confidencePercent)%")
                            .font(.caption2)
                            .foregroundColor(.green)
                    }
                    
                    Text(goal.horizonLabel)
                        .font(.caption2)
                        .foregroundColor(.gray)
                }
            }
            
            // Confidence progress bar
            ProgressView(value: goal.ideaConfidence)
                .tint(goal.timeframe.color)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Add Goal View
struct AddGoalView: View {
    @Environment(\.dismiss) var dismiss
    @State private var name = ""
    @State private var description = ""
    @State private var timeframe: GoalTimeframe = .medium
    @State private var horizonYears = 1.0
    @State private var confidence = 0.8
    
    let onSave: (Goal) -> Void
    
    var body: some View {
        NavigationStack {
            List {
                Section("Goal Information") {
                    TextField("Goal name", text: $name)
                    TextField("Description", text: $description, axis: .vertical)
                        .lineLimit(3)
                }
                
                Section("Timeline") {
                    Picker("Timeframe", selection: $timeframe) {
                        ForEach(GoalTimeframe.allCases, id: \.self) { tf in
                            Label(tf.rawValue, systemImage: tf.icon).tag(tf)
                        }
                    }
                    
                    Stepper("Horizon: \(String(format: "%.1f", horizonYears)) years", value: $horizonYears, in: 0.1...10, step: 0.5)
                }
                
                Section("Confidence") {
                    HStack {
                        Text("Idea Confidence")
                        Spacer()
                        Text("\(Int(confidence * 100))%")
                            .foregroundColor(.blue)
                    }
                    Slider(value: $confidence, in: 0...1)
                }
            }
            .navigationTitle("New Goal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        let goal = Goal(
                            id: UUID().uuidString,
                            name: name,
                            horizonYears: horizonYears,
                            ideaConfidence: confidence,
                            timeframe: timeframe,
                            priority: "user-defined",
                            description: description.isEmpty ? nil : description
                        )
                        onSave(goal)
                        dismiss()
                    }
                    .disabled(name.isEmpty)
                }
            }
        }
    }
}

// MARK: - Goal Detail View
struct GoalDetailView: View {
    @Environment(\.dismiss) var dismiss
    let goal: Goal
    
    var body: some View {
        NavigationStack {
            List {
                Section("Overview") {
                    HStack {
                        Text("Timeframe")
                        Spacer()
                        Label(goal.timeframe.rawValue, systemImage: goal.timeframe.icon)
                            .foregroundColor(goal.timeframe.color)
                    }
                    
                    HStack {
                        Text("Horizon")
                        Spacer()
                        Text(goal.horizonLabel)
                            .foregroundColor(.gray)
                    }
                    
                    HStack {
                        Text("Confidence")
                        Spacer()
                        HStack(spacing: 4) {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)
                            Text("\(goal.confidencePercent)%")
                                .foregroundColor(.green)
                        }
                    }
                }
                
                if let description = goal.description {
                    Section("Description") {
                        Text(description)
                    }
                }
                
                Section("Metrics") {
                    HStack {
                        Text("Priority")
                        Spacer()
                        Text(goal.priority).foregroundColor(.gray)
                    }
                }
            }
            .navigationTitle(goal.name)
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

// MARK: - Filter Button
struct FilterButton: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.caption)
                .fontWeight(.semibold)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(isSelected ? Color.blue : Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.20, green: 0.20, blue: 0.22, alpha: 1.0) : UIColor(red: 0.85, green: 0.85, blue: 0.87, alpha: 1.0) }))
                .foregroundColor(isSelected ? .white : .gray)
                .cornerRadius(6)
        }
    }
}

#Preview {
    GoalsView()
        .environmentObject(StorageService.shared)
}
