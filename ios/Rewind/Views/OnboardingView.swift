import SwiftUI

struct OnboardingView: View {
    @EnvironmentObject var storage: StorageService
    @State private var currentStep = 0
    @State private var goals: [Goal] = []
    @State private var timezone: String = TimeZone.current.identifier
    @State private var showError = false
    @State private var errorMessage = ""
    
    var body: some View {
        ZStack {
            Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.10, green: 0.10, blue: 0.12, alpha: 1.0) : UIColor(red: 0.95, green: 0.95, blue: 0.97, alpha: 1.0) })
                .ignoresSafeArea()
            
            VStack {
                // Progress indicator
                HStack(spacing: 4) {
                    ForEach(0..<3, id: \.self) { index in
                        RoundedRectangle(cornerRadius: 2)
                            .fill(index <= currentStep ? Color.blue : Color.gray.opacity(0.3))
                            .frame(height: 4)
                    }
                }
                .padding(.horizontal)
                .padding(.top, 16)
                
                // Step content
                VStack(alignment: .leading, spacing: 0) {
                    switch currentStep {
                    case 0:
                        WelcomeStep()
                    case 1:
                        GoalsSetupStep(goals: $goals)
                    case 2:
                        TimezoneStep(timezone: $timezone)
                    default:
                        EmptyView()
                    }
                    
                    Spacer()
                    
                    // Navigation buttons
                    HStack(spacing: 12) {
                        if currentStep > 0 {
                            Button(action: { currentStep -= 1 }) {
                                Text("Back")
                                    .font(.headline)
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.bordered)
                        }
                        
                        Button(action: { nextStep() }) {
                            Text(currentStep == 2 ? "Complete" : "Next")
                                .font(.headline)
                                .frame(maxWidth: .infinity)
                                .foregroundColor(.white)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(currentStep == 1 && goals.isEmpty)
                    }
                    .padding(.horizontal)
                    .padding(.bottom, 32)
                }
            }
        }
        .alert("Setup Error", isPresented: $showError, actions: {
            Button("OK") { showError = false }
        }, message: {
            Text(errorMessage)
        })
    }
    
    private func nextStep() {
        if currentStep < 2 {
            currentStep += 1
        } else {
            completeOnboarding()
        }
    }
    
    private func completeOnboarding() {
        let result = RewindBridge.shared.setupApply(goals: goals, timezone: timezone)
        
        switch result {
        case .success:
            storage.saveGoals(goals)
            storage.setTimezone(timezone)
            storage.markOnboardingComplete()
        case .failure(let error):
            errorMessage = error.displayMessage
            showError = true
        }
    }
}

// MARK: - Welcome Step
struct WelcomeStep: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            VStack(alignment: .leading, spacing: 12) {
                Text("Welcome to Rewind")
                    .font(.title)
                    .fontWeight(.bold)
                
                Text("Your AI-powered scheduler that adapts to disruptions in real time")
                    .font(.body)
                    .foregroundColor(.gray)
                    .lineLimit(3)
            }
            
            VStack(alignment: .leading, spacing: 16) {
                FeatureRow(icon: "target", title: "Goal-Driven Planning", description: "Align your daily tasks with long, medium, and short-term goals")
                
                FeatureRow(icon: "creditcard.circle.fill", title: "Smart Finance Integration", description: "Automatically categorize transactions and map them to goals")
                
                FeatureRow(icon: "bolt.fill", title: "Disruption Recovery", description: "When plans change, Rewind automatically reschedules your day")
                
                FeatureRow(icon: "bell.fill", title: "Intelligent Reminders", description: "Get timely reminders tailored to your energy level and priorities")
            }
            
            Spacer()
        }
        .padding(.horizontal)
        .padding(.top, 32)
    }
}

struct FeatureRow: View {
    let icon: String
    let title: String
    let description: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.blue)
                .frame(width: 32)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)
                    .foregroundColor(.white)
                
                Text(description)
                    .font(.caption)
                    .foregroundColor(.gray)
            }
        }
    }
}

// MARK: - Goals Setup Step
struct GoalsSetupStep: View {
    @Binding var goals: [Goal]
    @State private var showAddGoal = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Define Your Goals")
                    .font(.title2)
                    .fontWeight(.bold)
                
                Text("Start with at least one goal. You can edit these anytime.")
                    .font(.caption)
                    .foregroundColor(.gray)
            }
            
            if goals.isEmpty {
                VStack(spacing: 12) {
                    Button(action: { addSampleGoals() }) {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Image(systemName: "sparkles")
                                    .foregroundColor(.blue)
                                Text("Use Sample Goals")
                                    .fontWeight(.semibold)
                                Spacer()
                                Image(systemName: "chevron.right")
                            }
                            
                            Text("Get started with example goals")
                                .font(.caption)
                                .foregroundColor(.gray)
                        }
                        .padding()
                        .background(Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.15, green: 0.15, blue: 0.17, alpha: 1.0) : UIColor(red: 0.90, green: 0.90, blue: 0.92, alpha: 1.0) }))
                        .cornerRadius(8)
                    }
                    .foregroundColor(.white)
                    
                    Button(action: { showAddGoal = true }) {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Image(systemName: "plus.circle.fill")
                                    .foregroundColor(.green)
                                Text("Add Custom Goal")
                                    .fontWeight(.semibold)
                                Spacer()
                                Image(systemName: "chevron.right")
                            }
                            
                            Text("Create your own goal")
                                .font(.caption)
                                .foregroundColor(.gray)
                        }
                        .padding()
                        .background(Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.15, green: 0.15, blue: 0.17, alpha: 1.0) : UIColor(red: 0.90, green: 0.90, blue: 0.92, alpha: 1.0) }))
                        .cornerRadius(8)
                    }
                    .foregroundColor(.white)
                }
            } else {
                List {
                    ForEach(goals) { goal in
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                HStack(spacing: 4) {
                                    Image(systemName: goal.timeframe.icon)
                                        .foregroundColor(goal.timeframe.color)
                                    Text(goal.name)
                                        .fontWeight(.semibold)
                                }
                                Text(goal.description ?? "")
                                    .font(.caption)
                                    .foregroundColor(.gray)
                            }
                            
                            Spacer()
                            
                            Text("\(goal.confidencePercent)%")
                                .font(.caption)
                                .foregroundColor(.green)
                        }
                    }
                    .onDelete { indices in
                        goals.remove(atOffsets: indices)
                    }
                }
                .listStyle(.plain)
                .scrollContentBackground(.hidden)
                .frame(maxHeight: 300)
                
                Button(action: { showAddGoal = true }) {
                    Label("Add Another Goal", systemImage: "plus.circle.fill")
                        .font(.caption)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            }
            
            Spacer()
        }
        .padding(.horizontal)
        .padding(.top, 32)
        .sheet(isPresented: $showAddGoal) {
            AddGoalOnboardingView { newGoal in
                goals.append(newGoal)
                showAddGoal = false
            }
        }
    }
    
    private func addSampleGoals() {
        goals = Goal.mockGoals
    }
}

// MARK: - Add Goal Onboarding View
struct AddGoalOnboardingView: View {
    @Environment(\.dismiss) var dismiss
    @State private var name = ""
    @State private var description = ""
    @State private var timeframe: GoalTimeframe = .medium
    @State private var horizonYears = 1.0
    
    let onAdd: (Goal) -> Void
    
    var body: some View {
        NavigationStack {
            List {
                Section("Goal Information") {
                    TextField("What do you want to achieve?", text: $name)
                    TextField("Why is this important?", text: $description, axis: .vertical)
                        .lineLimit(3)
                }
                
                Section("Timeline") {
                    Picker("Timeframe", selection: $timeframe) {
                        ForEach(GoalTimeframe.allCases, id: \.self) { tf in
                            Label(tf.rawValue, systemImage: tf.icon).tag(tf)
                        }
                    }
                    
                    Stepper("Target: \(String(format: "%.1f", horizonYears)) years", value: $horizonYears, in: 0.1...10, step: 0.5)
                }
            }
            .navigationTitle("New Goal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        let goal = Goal(
                            id: UUID().uuidString,
                            name: name,
                            horizonYears: horizonYears,
                            ideaConfidence: 0.8,
                            timeframe: timeframe,
                            priority: "user-defined",
                            description: description.isEmpty ? nil : description
                        )
                        onAdd(goal)
                    }
                    .disabled(name.isEmpty)
                }
            }
        }
    }
}

// MARK: - Timezone Step
struct TimezoneStep: View {
    @Binding var timezone: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Set Your Timezone")
                    .font(.title2)
                    .fontWeight(.bold)
                
                Text("This helps Rewind schedule tasks at the right time")
                    .font(.caption)
                    .foregroundColor(.gray)
            }
            
            Picker("Timezone", selection: $timezone) {
                ForEach(TimeZone.knownTimeZoneIdentifiers, id: \.self) { tz in
                    Text(tz).tag(tz)
                }
            }
            .pickerStyle(.navigationLink)
            
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Current timezone")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
                
                Text(timezone)
                    .font(.headline)
                    .foregroundColor(.blue)
            }
            
            Spacer()
        }
        .padding(.horizontal)
        .padding(.top, 32)
    }
}

#Preview {
    OnboardingView()
        .environmentObject(StorageService.shared)
}
