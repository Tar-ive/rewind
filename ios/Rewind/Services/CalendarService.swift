import Foundation
import EventKit

// MARK: - Calendar Service
/// Handles calendar integration via EventKit
/// Allows importing calendar events to detect disruptions
class CalendarService: NSObject, ObservableObject {
    static let shared = CalendarService()
    
    private let eventStore = EKEventStore()
    @Published var hasCalendarAccess = false
    @Published var upcomingEvents: [EKEvent] = []
    @Published var lastUpdateTime: Date?
    
    override private init() {
        super.init()
        checkCalendarAccess()
    }
    
    // MARK: - Access Control
    func requestCalendarAccess(completion: @escaping (Bool) -> Void) {
        if #available(iOS 17, *) {
            eventStore.requestFullAccessToEvents { granted, error in
                DispatchQueue.main.async {
                    self.hasCalendarAccess = granted
                    completion(granted)
                }
            }
        } else {
            eventStore.requestAccessToEvents { granted, error in
                DispatchQueue.main.async {
                    self.hasCalendarAccess = granted
                    completion(granted)
                }
            }
        }
    }
    
    func checkCalendarAccess() {
        let status = EKEventStore.authorizationStatus(for: .event)
        DispatchQueue.main.async {
            self.hasCalendarAccess = status == .fullAccess || status == .authorized
        }
    }
    
    // MARK: - Event Fetching
    func fetchUpcomingEvents(days: Int = 7) {
        guard hasCalendarAccess else { return }
        
        let now = Date()
        let endDate = Calendar.current.date(byAdding: .day, value: days, to: now) ?? now
        
        let predicate = eventStore.predicateForEvents(withStart: now, end: endDate, calendars: nil)
        let events = eventStore.events(matching: predicate)
            .sorted { $0.startDate < $1.startDate }
        
        DispatchQueue.main.async {
            self.upcomingEvents = events
            self.lastUpdateTime = Date()
        }
    }
    
    // MARK: - Disruption Detection
    /// Detect if an event has been modified (extended, moved, deleted)
    func checkForDisruptions() -> [DisruptionEvent] {
        var disruptions: [DisruptionEvent] = []
        
        for event in upcomingEvents {
            // TODO: Compare with previously stored state to detect changes
            // For now, this is a stub
            if event.isAllDay == false && Calendar.current.dateComponents([.hour], from: event.startDate).hour ?? 0 >= 18 {
                // Evening event - might indicate schedule pressure
                let disruption = DisruptionEvent(
                    severity: .minor,
                    cascadeCount: 1,
                    reason: "Evening event detected: \(event.title)",
                    contextEventId: "gcal:\(event.eventIdentifier)",
                    timestamp: Date()
                )
                disruptions.append(disruption)
            }
        }
        
        return disruptions
    }
    
    // MARK: - Event Creation
    /// Create a calendar event from a task
    func createEvent(from task: Task, on date: Date, startTime: Date) -> Bool {
        guard hasCalendarAccess else { return false }
        
        let event = EKEvent(eventStore: eventStore)
        event.title = task.title
        event.startDate = startTime
        event.endDate = Calendar.current.date(byAdding: .minute, value: task.estimatedDuration, to: startTime) ?? startTime
        event.notes = "Rewind: \(task.priority.displayName) - \(task.status.rawValue)"
        
        // Try to get the default calendar
        if let defaultCalendar = eventStore.defaultCalendarForNewEvents {
            event.calendar = defaultCalendar
            do {
                try eventStore.save(event, span: .thisEvent, commit: true)
                return true
            } catch {
                print("Error saving event: \(error)")
                return false
            }
        }
        
        return false
    }
    
    /// Create multiple events from a schedule
    func createEventsFromSchedule(_ schedule: UpdatedSchedule, tasks: [Task]) -> Int {
        guard hasCalendarAccess else { return 0 }
        
        var createdCount = 0
        var currentTime = Calendar.current.startOfDay(for: schedule.day)
        
        for taskId in schedule.taskOrder {
            if let task = tasks.first(where: { $0.id == taskId }) {
                if createEvent(from: task, on: schedule.day, startTime: currentTime) {
                    createdCount += 1
                }
                currentTime = Calendar.current.date(byAdding: .minute, value: task.estimatedDuration + 5, to: currentTime) ?? currentTime
            }
        }
        
        return createdCount
    }
    
    // MARK: - ICS Export
    /// Export schedule as ICS (iCalendar) format for import into any calendar
    func exportAsICS(schedule: UpdatedSchedule, tasks: [Task]) -> String {
        var icsContent = """
            BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:-//Rewind//iOS//EN
            CALSCALE:GREGORIAN
            X-WR-CALNAME:Rewind Daily Plan
            X-WR-TIMEZONE:\(TimeZone.current.abbreviation() ?? "UTC")
            BEGIN:VTIMEZONE
            TZID:\(TimeZone.current.identifier)
            BEGIN:STANDARD
            DTSTART:19700101T000000
            TZOFFSETFROM:+0000
            TZOFFSETTO:+0000
            END:STANDARD
            END:VTIMEZONE
            
            """
        
        var currentTime = Calendar.current.startOfDay(for: schedule.day)
        
        for taskId in schedule.taskOrder {
            if let task = tasks.first(where: { $0.id == taskId }) {
                let endTime = Calendar.current.date(byAdding: .minute, value: task.estimatedDuration, to: currentTime) ?? currentTime
                
                let startString = isoDateString(currentTime)
                let endString = isoDateString(endTime)
                
                icsContent += """
                    BEGIN:VEVENT
                    UID:rewind-\(task.id)@rewind.local
                    DTSTAMP:\(isoDateString(Date()))
                    DTSTART:\(startString)
                    DTEND:\(endString)
                    SUMMARY:[\(task.priority.displayName)] \(task.title)
                    DESCRIPTION:Rewind Task\\nPriority: \(task.priority.displayName)\\nEnergy: \(task.energyBars)\\nDuration: \(task.estimatedDuration)m
                    STATUS:CONFIRMED
                    END:VEVENT
                    
                    """
                
                currentTime = Calendar.current.date(byAdding: .minute, value: task.estimatedDuration + 5, to: currentTime) ?? currentTime
            }
        }
        
        icsContent += "END:VCALENDAR"
        
        return icsContent
    }
    
    // MARK: - Helpers
    private func isoDateString(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        return formatter.string(from: date).replacingOccurrences(of: "-", with: "").replacingOccurrences(of: ":", with: "").split(separator: ".")[0]
    }
}
