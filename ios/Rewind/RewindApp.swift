import SwiftUI

@main
struct RewindApp: App {
    @StateObject private var storage = StorageService.shared
    @StateObject private var calendar = CalendarService.shared
    
    var body: some Scene {
        WindowGroup {
            if storage.isOnboardingComplete {
                ContentView()
                    .environmentObject(storage)
                    .environmentObject(calendar)
            } else {
                OnboardingView()
                    .environmentObject(storage)
            }
        }
    }
}
