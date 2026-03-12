import AppKit
import Combine
import Foundation
import UniformTypeIdentifiers

@MainActor
final class AppModel: ObservableObject {
    @Published var selectedScreen: SidebarScreen = .recommendations
    @Published var backendInfo: BackendInstallation?
    @Published var health: HealthResponse?
    @Published var availableMaterials: [MaterialSpecPayload] = []
    @Published var savedConfig: ConfigValues?
    @Published var configDraft: ConfigValues?
    @Published var selectedFileURL: URL?
    @Published var quantity: Int = 1
    @Published var analysis: AnalysisResponse?
    @Published var previewFileURL: URL?
    @Published var pendingAnalysisFileName: String?
    @Published var selectedRecommendationID: String?
    @Published var selectedFeatureGroupID: String?
    @Published var selectedFeatureInstanceID: String?
    @Published var isBootstrapping = false
    @Published var isAnalyzing = false
    @Published var isGeneratingPreview = false
    @Published var isRunningNextAnalysis = false
    @Published var isSavingSettings = false
    @Published var lastErrorMessage: String?

    let backendService: BackendProcessService
    private var analysisTask: Task<Void, Never>?

    init(backendService: BackendProcessService = BackendProcessService()) {
        self.backendService = backendService
        self.backendInfo = backendService.installation
    }

    var hasAnalysisRuntime: Bool {
        health?.analysisRuntime.available == true
    }

    var displayedProcessData: PartProcessDataPayload? {
        guard let analysis else {
            return nil
        }
        let config = configDraft ?? savedConfig
        let qtyLearningRate = config?.qtyLearningRate ?? 0.76
        let qtyFactorFloor = config?.qtyFactorFloor ?? 0.29
        return analysis.processData.applyingQuantity(
            quantity,
            qtyLearningRate: qtyLearningRate,
            qtyFactorFloor: qtyFactorFloor
        )
    }

    var settingsAreDirty: Bool {
        guard let savedConfig, let configDraft else {
            return false
        }
        return savedConfig != configDraft
    }

    func bootstrapIfNeeded() async {
        if isBootstrapping || health != nil {
            return
        }
        await bootstrap()
    }

    func bootstrap() async {
        isBootstrapping = true
        defer { isBootstrapping = false }

        do {
            async let healthRequest = backendService.fetchHealth()
            async let configRequest = backendService.fetchConfig()
            async let materialsRequest = backendService.fetchMaterials()

            let (health, configResponse, materialsResponse) = try await (healthRequest, configRequest, materialsRequest)
            self.health = health
            self.savedConfig = configResponse.values
            self.configDraft = configResponse.values
            self.availableMaterials = materialsResponse.materials
            self.backendInfo = backendService.installation
            self.lastErrorMessage = nil
        } catch {
            present(error)
        }
    }

    func refreshDiagnostics() async {
        do {
            health = try await backendService.fetchHealth()
            backendInfo = backendService.installation
            lastErrorMessage = nil
        } catch {
            present(error)
        }
    }

    func pickStepFile() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.stepFile, .stepTextFile]
        panel.prompt = "Select STEP File"
        if panel.runModal() == .OK {
            runNewAnalysis(with: panel.url)
        }
    }

    func acceptDroppedFile(_ url: URL) {
        guard url.isFileURL, ["step", "stp"].contains(url.pathExtension.lowercased()) else {
            return
        }
        runNewAnalysis(with: url)
    }

    func saveSettings() async {
        guard let configDraft else {
            return
        }
        isSavingSettings = true
        defer { isSavingSettings = false }

        do {
            let response = try await backendService.saveConfig(configDraft)
            savedConfig = response.values
            self.configDraft = response.values
            health = try await backendService.fetchHealth()
            lastErrorMessage = nil
        } catch {
            present(error)
        }
    }

    func resetDraftToSaved() {
        configDraft = savedConfig
    }

    func analyzeSelectedFile() async {
        guard let selectedFileURL else {
            lastErrorMessage = "Select a STEP file before running analysis."
            return
        }
        runNewAnalysis(with: selectedFileURL)
    }

    func clearError() {
        lastErrorMessage = nil
    }

    var selectedRecommendation: RecommendationPayload? {
        guard let analysis else {
            return nil
        }
        guard let selectedRecommendationID else {
            return analysis.recommendations.first
        }
        return analysis.recommendations.first(where: { $0.id == selectedRecommendationID }) ?? analysis.recommendations.first
    }

    var visibleFeatureInsights: [FeatureInsightPayload] {
        selectedRecommendation?.featureInsights ?? []
    }

    var focusedFeatureInsight: FeatureInsightPayload? {
        guard let recommendation = selectedRecommendation else {
            return nil
        }
        if let selectedFeatureInstanceID,
           let match = recommendation.featureInsights.first(where: { $0.id == selectedFeatureInstanceID }) {
            return match
        }
        return recommendation.featureInsights.first
    }

    func selectRecommendation(_ recommendation: RecommendationPayload) {
        selectedRecommendationID = recommendation.id
        selectedFeatureGroupID = recommendation.featureGroups.first?.id
        selectedFeatureInstanceID = recommendation.featureGroups.first?.instances.first?.id
    }

    func selectFeatureGroup(_ group: RecommendationFeatureGroup) {
        selectedFeatureGroupID = group.id
        selectedFeatureInstanceID = group.instances.first?.id
    }

    func selectFeatureInstance(_ insight: FeatureInsightPayload) {
        selectedFeatureInstanceID = insight.id
    }

    func stepSelectedFeatureInstance(in group: RecommendationFeatureGroup, delta: Int) {
        guard !group.instances.isEmpty else {
            return
        }
        let currentIndex = group.instances.firstIndex(where: { $0.id == selectedFeatureInstanceID }) ?? 0
        let nextIndex = (currentIndex + delta + group.instances.count) % group.instances.count
        selectedFeatureGroupID = group.id
        selectedFeatureInstanceID = group.instances[nextIndex].id
    }

    func launchNewAnalysisPicker() {
        pickStepFile()
    }

    func runNewAnalysis(with fileURL: URL?) {
        guard let fileURL else {
            return
        }

        analysisTask?.cancel()
        pendingAnalysisFileName = fileURL.lastPathComponent
        isRunningNextAnalysis = true
        lastErrorMessage = nil

        analysisTask = Task { [weak self] in
            guard let self else {
                return
            }
            defer {
                if !Task.isCancelled {
                    self.isRunningNextAnalysis = false
                    self.pendingAnalysisFileName = nil
                    self.analysisTask = nil
                }
            }

            do {
                let nextAnalysis = try await self.backendService.analyze(fileURL: fileURL, qty: self.quantity)
                if Task.isCancelled {
                    return
                }
                self.selectedFileURL = fileURL
                self.analysis = nextAnalysis
                self.quantity = nextAnalysis.processData.qty
                self.selectedRecommendationID = nextAnalysis.recommendations.first?.id
                self.selectedFeatureGroupID = nextAnalysis.recommendations.first?.featureGroups.first?.id
                self.selectedFeatureInstanceID = nextAnalysis.recommendations.first?.featureGroups.first?.instances.first?.id
                self.previewFileURL = nil
                self.isAnalyzing = false
                Task {
                    await self.generatePreview(for: fileURL)
                }
            } catch {
                if Task.isCancelled {
                    return
                }
                self.present(error)
            }
        }
    }

    func generatePreview(for fileURL: URL) async {
        isGeneratingPreview = true
        defer { isGeneratingPreview = false }

        do {
            let preview = try await backendService.generatePreview(fileURL: fileURL)
            guard selectedFileURL == fileURL else {
                return
            }
            previewFileURL = URL(fileURLWithPath: preview.previewPath)
        } catch {
            guard selectedFileURL == fileURL else {
                return
            }
            previewFileURL = nil
            present(error)
        }
    }

    private func present(_ error: Error) {
        lastErrorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
    }

    func setQuantity(_ newValue: Int) {
        quantity = max(1, newValue)
    }

    private func setSelectedFileURL(_ url: URL?) {
        selectedFileURL = url
        analysis = nil
        previewFileURL = nil
        pendingAnalysisFileName = nil
        selectedRecommendationID = nil
        selectedFeatureGroupID = nil
        selectedFeatureInstanceID = nil
        isGeneratingPreview = false
        isRunningNextAnalysis = false
        lastErrorMessage = nil
    }
}

enum SidebarScreen: String, CaseIterable, Identifiable {
    case recommendations
    case ruleResults
    case summary
    case settings
    case diagnostics

    var id: String { rawValue }

    var title: String {
        switch self {
        case .recommendations:
            return "Recommendations"
        case .ruleResults:
            return "Rule Results"
        case .summary:
            return "Analysis Summary"
        case .settings:
            return "Settings"
        case .diagnostics:
            return "Diagnostics"
        }
    }

    var symbolName: String {
        switch self {
        case .recommendations:
            return "text.append"
        case .ruleResults:
            return "list.bullet.clipboard"
        case .summary:
            return "chart.bar.doc.horizontal"
        case .settings:
            return "slider.horizontal.3"
        case .diagnostics:
            return "stethoscope"
        }
    }
}

private extension UTType {
    static let stepFile = UTType(filenameExtension: "step") ?? .data
    static let stepTextFile = UTType(filenameExtension: "stp") ?? .data
}
