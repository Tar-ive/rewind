import SwiftUI

struct ContentView: View {
    @EnvironmentObject var storage: StorageService
    @EnvironmentObject var calendar: CalendarService
    @State private var selectedTab = 0
    @State private var showSettings = false
    
    var body: some View {
        ZStack {
            // Dark theme background
            Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.10, green: 0.10, blue: 0.12, alpha: 1.0) : UIColor(red: 0.95, green: 0.95, blue: 0.97, alpha: 1.0) })
                .ignoresSafeArea()
            
            TabView(selection: $selectedTab) {
                // Day Plan Tab
                DayPlanView()
                    .tabItem {
                        Label("Today", systemImage: "calendar.circle.fill")
                    }
                    .tag(0)
                
                // Goals Tab
                GoalsView()
                    .tabItem {
                        Label("Goals", systemImage: "target")
                    }
                    .tag(1)
                
                // Finance Tab
                FinanceView()
                    .tabItem {
                        Label("Finance", systemImage: "creditcard.circle.fill")
                    }
                    .tag(2)
                
                // Reminders Tab
                RemindersView()
                    .tabItem {
                        Label("Reminders", systemImage: "bell.circle.fill")
                    }
                    .tag(3)
            }
            .preferredColorScheme(.dark)
        }
        .sheet(isPresented: $showSettings) {
            SettingsView()
                .environmentObject(storage)
        }
    }
}

// MARK: - Settings View
struct SettingsView: View {
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var storage: StorageService
    @State private var timezone: String = ""
    @State private var energyLevel: Int = 5
    
    var body: some View {
        NavigationStack {
            List {
                Section("User Preferences") {
                    Picker("Timezone", selection: $timezone) {
                        ForEach(TimeZone.knownTimeZoneIdentifiers, id: \.self) { tz in
                            Text(tz).tag(tz)
                        }
                    }
                    
                    Stepper("Energy Level: \(energyLevel)", value: $energyLevel, in: 1...5)
                }
                
                Section("App Info") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("1.0.0").foregroundColor(.gray)
                    }
                    HStack {
                        Text("Build")
                        Spacer()
                        Text("2026.02.22").foregroundColor(.gray)
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        storage.setTimezone(timezone)
                        storage.setEnergyLevel(energyLevel)
                        dismiss()
                    }
                }
            }
            .onAppear {
                timezone = storage.userTimezone
                energyLevel = storage.currentEnergyLevel
            }
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(StorageService.shared)
        .environmentObject(CalendarService.shared)
}
