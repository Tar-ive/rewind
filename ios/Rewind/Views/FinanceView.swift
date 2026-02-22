import SwiftUI

struct FinanceView: View {
    @EnvironmentObject var storage: StorageService
    @State private var records: [FinanceRecord] = []
    @State private var filterCategory: FinanceCategory? = nil
    @State private var showImportSheet = false
    @State private var showCSVPicker = false
    @State private var sortBy: SortOption = .date
    
    enum SortOption {
        case date
        case amount
        case readiness
    }
    
    var filteredRecords: [FinanceRecord] {
        var result = records
        if let filter = filterCategory {
            result = result.filter { $0.category == filter }
        }
        
        switch sortBy {
        case .date:
            result.sort { $0.date > $1.date }
        case .amount:
            result.sort { abs($0.amount) > abs($1.amount) }
        case .readiness:
            result.sort { ($0.readiness ?? 0) > ($1.readiness ?? 0) }
        }
        
        return result
    }
    
    var categoryStats: [FinanceCategory: (count: Int, total: Double)] {
        var stats: [FinanceCategory: (Int, Double)] = [:]
        for record in records {
            let current = stats[record.category] ?? (0, 0)
            stats[record.category] = (current.0 + 1, current.1 + record.amount)
        }
        return stats
    }
    
    var body: some View {
        ZStack {
            Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.10, green: 0.10, blue: 0.12, alpha: 1.0) : UIColor(red: 0.95, green: 0.95, blue: 0.97, alpha: 1.0) })
                .ignoresSafeArea()
            
            NavigationStack {
                VStack(spacing: 0) {
                    // Summary cards
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 12) {
                            ForEach(Array(categoryStats.keys).sorted { $0.displayName < $1.displayName }, id: \.self) { category in
                                let stat = categoryStats[category] ?? (0, 0)
                                CategoryCard(category: category, count: stat.count, total: stat.total)
                            }
                        }
                        .padding(.horizontal)
                    }
                    .padding(.vertical, 12)
                    .background(Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.15, green: 0.15, blue: 0.17, alpha: 1.0) : UIColor(red: 0.90, green: 0.90, blue: 0.92, alpha: 1.0) }))
                    
                    // Toolbar
                    HStack(spacing: 8) {
                        Menu {
                            Picker("Filter", selection: $filterCategory) {
                                Text("All Categories").tag(Optional<FinanceCategory>(nil))
                                Divider()
                                ForEach(FinanceCategory.allCases, id: \.self) { category in
                                    Label(category.displayName, systemImage: category.icon).tag(Optional(category))
                                }
                            }
                        } label: {
                            Label("Filter", systemImage: "funnel.fill")
                                .font(.caption)
                        }
                        .buttonStyle(.bordered)
                        
                        Menu {
                            Picker("Sort", selection: $sortBy) {
                                Text("Date").tag(SortOption.date)
                                Text("Amount").tag(SortOption.amount)
                                Text("Readiness").tag(SortOption.readiness)
                            }
                        } label: {
                            Label("Sort", systemImage: "arrow.up.arrow.down")
                                .font(.caption)
                        }
                        .buttonStyle(.bordered)
                        
                        Spacer()
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 8)
                    
                    // Records list
                    if records.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "creditcard.circle")
                                .font(.system(size: 48))
                                .foregroundColor(.gray)
                            Text("No transactions")
                                .font(.headline)
                                .foregroundColor(.gray)
                            Button(action: { showImportSheet = true }) {
                                Label("Import CSV", systemImage: "plus.circle.fill")
                            }
                            .buttonStyle(.bordered)
                        }
                        .frame(maxHeight: .infinity)
                        .frame(maxWidth: .infinity)
                    } else {
                        List {
                            ForEach(filteredRecords) { record in
                                FinanceRow(record: record)
                                    .listRowBackground(
                                        Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.12, green: 0.12, blue: 0.14, alpha: 1.0) : UIColor(red: 0.93, green: 0.93, blue: 0.95, alpha: 1.0) })
                                    )
                            }
                        }
                        .listStyle(.plain)
                        .scrollContentBackground(.hidden)
                    }
                }
                .navigationTitle("Finance")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .primaryAction) {
                        Button(action: { showImportSheet = true }) {
                            Image(systemName: "plus.circle.fill")
                                .foregroundColor(.blue)
                        }
                    }
                }
            }
        }
        .sheet(isPresented: $showImportSheet) {
            ImportCSVView { csvContent in
                importTransactions(csvContent)
                showImportSheet = false
            }
        }
        .onAppear {
            records = storage.financialRecords.isEmpty ? FinanceRecord.mockRecords : storage.financialRecords
        }
    }
    
    private func importTransactions(_ csvContent: String) {
        let result = RewindBridge.shared.parseFinanceCSV(csvContent)
        
        switch result {
        case .success(let parsed):
            records = parsed
            storage.saveFinancialRecords(parsed)
            storage.saveCSVFile(csvContent)
        case .failure(let error):
            print("Error importing CSV: \(error.displayMessage)")
        }
    }
}

// MARK: - Category Card
struct CategoryCard: View {
    let category: FinanceCategory
    let count: Int
    let total: Double
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: category.icon)
                    .foregroundColor(category.color)
                Text(category.displayName)
                    .font(.caption)
                    .fontWeight(.semibold)
            }
            
            Text(String(format: "$%.2f", abs(total)))
                .font(.headline)
                .foregroundColor(.white)
            
            Text("\(count) transactions")
                .font(.caption2)
                .foregroundColor(.gray)
        }
        .padding()
        .background(Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.12, green: 0.12, blue: 0.14, alpha: 1.0) : UIColor(red: 0.93, green: 0.93, blue: 0.95, alpha: 1.0) }))
        .cornerRadius(8)
    }
}

// MARK: - Finance Row
struct FinanceRow: View {
    let record: FinanceRecord
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        Image(systemName: record.category.icon)
                            .foregroundColor(record.category.color)
                        
                        Text(record.description)
                            .font(.headline)
                            .foregroundColor(.white)
                            .lineLimit(1)
                    }
                    
                    Text(record.displayDate)
                        .font(.caption)
                        .foregroundColor(.gray)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text(record.displayAmount)
                        .font(.headline)
                        .foregroundColor(record.amount > 0 ? .green : .red)
                    
                    if let readiness = record.readinessPercent {
                        HStack(spacing: 4) {
                            Image(systemName: "checkmark.circle.fill")
                                .font(.caption)
                                .foregroundColor(.green)
                            Text("\(readiness)%")
                                .font(.caption2)
                                .foregroundColor(.gray)
                        }
                    }
                }
            }
            
            if let goalName = record.goalName {
                HStack {
                    Image(systemName: "target")
                        .font(.caption)
                        .foregroundColor(.blue)
                    Text(goalName)
                        .font(.caption)
                        .foregroundColor(.blue)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Import CSV View
struct ImportCSVView: View {
    @Environment(\.dismiss) var dismiss
    @State private var csvContent = ""
    @State private var isLoading = false
    
    let onImport: (String) -> Void
    
    var body: some View {
        NavigationStack {
            List {
                Section("Paste AMEX CSV") {
                    TextEditor(text: $csvContent)
                        .font(.system(.caption, design: .monospaced))
                        .frame(minHeight: 200)
                }
                
                Section("Format") {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Expected columns:")
                            .font(.caption)
                            .fontWeight(.semibold)
                        
                        VStack(alignment: .leading, spacing: 4) {
                            Text("• Date")
                            Text("• Description")
                            Text("• Amount")
                            Text("• Category")
                        }
                        .font(.caption2)
                        .foregroundColor(.gray)
                    }
                }
            }
            .navigationTitle("Import Transactions")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if isLoading {
                        ProgressView()
                    } else {
                        Button("Import") {
                            isLoading = true
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                                onImport(csvContent)
                                isLoading = false
                                dismiss()
                            }
                        }
                        .disabled(csvContent.isEmpty)
                    }
                }
            }
        }
    }
}

#Preview {
    FinanceView()
        .environmentObject(StorageService.shared)
}
