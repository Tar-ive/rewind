import SwiftUI

struct RemindersView: View {
    @EnvironmentObject var storage: StorageService
    @State private var reminders: [ReminderIntent] = []
    @State private var tasks: [Task] = []
    @State private var showAdvancedSettings = false
    @State private var policy = ReminderPolicy.default
    @State private var completedReminders: Set<String> = []
    
    var upcomingReminders: [ReminderIntent] {
        reminders
            .filter { !completedReminders.contains($0.id) }
            .filter { $0.sendAt > Date().addingTimeInterval(-3600) }
            .sorted { $0.sendAt < $1.sendAt }
    }
    
    var missedReminders: [ReminderIntent] {
        reminders
            .filter { !completedReminders.contains($0.id) }
            .filter { $0.sendAt <= Date().addingTimeInterval(-3600) }
            .sorted { $0.sendAt > $1.sendAt }
    }
    
    var body: some View {
        ZStack {
            Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.10, green: 0.10, blue: 0.12, alpha: 1.0) : UIColor(red: 0.95, green: 0.95, blue: 0.97, alpha: 1.0) })
                .ignoresSafeArea()
            
            NavigationStack {
                VStack(spacing: 0) {
                    // Policy settings
                    HStack {
                        Text("Reminder Policy")
                            .font(.caption)
                            .foregroundColor(.gray)
                        Spacer()
                        Button(action: { showAdvancedSettings = true }) {
                            Image(systemName: "gear.circle.fill")
                                .foregroundColor(.blue)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 12)
                    .background(Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.15, green: 0.15, blue: 0.17, alpha: 1.0) : UIColor(red: 0.90, green: 0.90, blue: 0.92, alpha: 1.0) }))
                    
                    // Content
                    if reminders.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "bell.circle")
                                .font(.system(size: 48))
                                .foregroundColor(.gray)
                            Text("No reminders")
                                .font(.headline)
                                .foregroundColor(.gray)
                            Text("Reminders will appear based on your tasks and goals")
                                .font(.caption)
                                .foregroundColor(.gray)
                                .multilineTextAlignment(.center)
                        }
                        .frame(maxHeight: .infinity)
                        .frame(maxWidth: .infinity)
                    } else {
                        List {
                            if !upcomingReminders.isEmpty {
                                Section("Upcoming") {
                                    ForEach(upcomingReminders) { reminder in
                                        ReminderRow(
                                            reminder: reminder,
                                            isCompleted: completedReminders.contains(reminder.id),
                                            onComplete: { completeReminder(reminder.id) }
                                        )
                                        .listRowBackground(
                                            Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.12, green: 0.12, blue: 0.14, alpha: 1.0) : UIColor(red: 0.93, green: 0.93, blue: 0.95, alpha: 1.0) })
                                        )
                                    }
                                }
                            }
                            
                            if !missedReminders.isEmpty {
                                Section("Missed") {
                                    ForEach(missedReminders) { reminder in
                                        ReminderRow(
                                            reminder: reminder,
                                            isCompleted: completedReminders.contains(reminder.id),
                                            onComplete: { completeReminder(reminder.id) }
                                        )
                                        .opacity(0.6)
                                        .listRowBackground(
                                            Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.12, green: 0.12, blue: 0.14, alpha: 1.0) : UIColor(red: 0.93, green: 0.93, blue: 0.95, alpha: 1.0) })
                                        )
                                    }
                                }
                            }
                        }
                        .listStyle(.plain)
                        .scrollContentBackground(.hidden)
                    }
                }
                .navigationTitle("Reminders")
                .navigationBarTitleDisplayMode(.inline)
            }
        }
        .sheet(isPresented: $showAdvancedSettings) {
            ReminderPolicyView(policy: $policy)
        }
        .onAppear {
            tasks = storage.currentTasks
            generateReminders()
        }
    }
    
    private func generateReminders() {
        reminders = ReminderIntent.mockReminders
        
        // Call Rust bridge to project reminders for each task
        for task in tasks {
            let result = RewindBridge.shared.projectReminders(for: task, policy: policy)
            switch result {
            case .success(let projected):
                reminders.append(contentsOf: projected)
            case .failure(let error):
                print("Error projecting reminders: \(error.displayMessage)")
            }
        }
        
        // Deduplicate by dedupeKey
        var seen = Set<String>()
        reminders = reminders.filter { reminder in
            if seen.contains(reminder.dedupeKey) {
                return false
            }
            seen.insert(reminder.dedupeKey)
            return true
        }
    }
    
    private func completeReminder(_ id: String) {
        completedReminders.insert(id)
    }
}

// MARK: - Reminder Row
struct ReminderRow: View {
    let reminder: ReminderIntent
    let isCompleted: Bool
    let onComplete: () -> Void
    
    var body: some View {
        Button(action: onComplete) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 8) {
                            Image(systemName: isCompleted ? "checkmark.circle.fill" : "bell.fill")
                                .foregroundColor(isCompleted ? .green : .blue)
                                .font(.body)
                            
                            Text(reminder.title)
                                .font(.headline)
                                .foregroundColor(.white)
                                .strikethrough(isCompleted)
                        }
                        
                        Text(reminder.body)
                            .font(.caption)
                            .foregroundColor(.gray)
                            .lineLimit(2)
                    }
                    
                    Spacer()
                    
                    VStack(alignment: .trailing, spacing: 4) {
                        Text(reminder.displayTime)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(.blue)
                        
                        Text(reminder.relativeTime)
                            .font(.caption2)
                            .foregroundColor(.gray)
                    }
                }
            }
        }
        .padding(.vertical, 8)
    }
}

// MARK: - Reminder Policy View
struct ReminderPolicyView: View {
    @Environment(\.dismiss) var dismiss
    @Binding var policy: ReminderPolicy
    @State private var localPolicy: ReminderPolicy = .default
    
    var body: some View {
        NavigationStack {
            List {
                Section("Reminder Frequency") {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Label("Urgent (P0)", systemImage: "exclamationmark.circle.fill")
                                .foregroundColor(.red)
                            Spacer()
                            Stepper("\(localPolicy.urgentReminders)", value: Binding(
                                get: { localPolicy.urgentReminders },
                                set: { localPolicy.urgentReminders = $0 }
                            ), in: 0...5)
                        }
                        
                        HStack {
                            Label("Important (P1)", systemImage: "exclamationmark.circle")
                                .foregroundColor(.orange)
                            Spacer()
                            Stepper("\(localPolicy.importantReminders)", value: Binding(
                                get: { localPolicy.importantReminders },
                                set: { localPolicy.importantReminders = $0 }
                            ), in: 0...5)
                        }
                        
                        HStack {
                            Label("Normal (P2)", systemImage: "info.circle")
                                .foregroundColor(.blue)
                            Spacer()
                            Stepper("\(localPolicy.normalReminders)", value: Binding(
                                get: { localPolicy.normalReminders },
                                set: { localPolicy.normalReminders = $0 }
                            ), in: 0...5)
                        }
                    }
                    .padding(.vertical, 8)
                }
                
                Section("Preview") {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("You'll receive reminders for:")
                            .font(.caption)
                            .fontWeight(.semibold)
                        
                        VStack(alignment: .leading, spacing: 4) {
                            if localPolicy.urgentReminders > 0 {
                                Text("• \(localPolicy.urgentReminders) reminder(s) for urgent tasks")
                            }
                            if localPolicy.importantReminders > 0 {
                                Text("• \(localPolicy.importantReminders) reminder(s) for important tasks")
                            }
                            if localPolicy.normalReminders > 0 {
                                Text("• \(localPolicy.normalReminders) reminder(s) for normal tasks")
                            }
                            if localPolicy.urgentReminders == 0 && localPolicy.importantReminders == 0 && localPolicy.normalReminders == 0 {
                                Text("• No reminders (all disabled)")
                            }
                        }
                        .font(.caption)
                        .foregroundColor(.gray)
                    }
                }
            }
            .navigationTitle("Reminder Policy")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        policy = localPolicy
                        dismiss()
                    }
                }
            }
            .onAppear {
                localPolicy = policy
            }
        }
    }
}

#Preview {
    RemindersView()
        .environmentObject(StorageService.shared)
}
