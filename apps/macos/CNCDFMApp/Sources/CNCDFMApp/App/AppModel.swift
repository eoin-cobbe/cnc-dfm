import AppKit
import Combine
import Foundation
import UniformTypeIdentifiers

@MainActor
final class AppModel: ObservableObject {
    @Published var selectedScreen: SidebarScreen = .check
    @Published var backendInfo: BackendInstallation?
    @Published var health: HealthResponse?
    @Published var availableMaterials: [MaterialSpecPayload] = []
    @Published var savedConfig: ConfigValues?
    @Published var configDraft: ConfigValues?
    @Published var selectedFileURL: URL?
    @Published var quantity: Int = 1
    @Published var analysis: AnalysisResponse?
    @Published var isBootstrapping = false
    @Published var isAnalyzing = false
    @Published var isSavingSettings = false
    @Published var lastErrorMessage: String?

    let backendService: BackendProcessService

    init(backendService: BackendProcessService = BackendProcessService()) {
        self.backendService = backendService
        self.backendInfo = backendService.installation
    }

    var hasAnalysisRuntime: Bool {
        health?.analysisRuntime.available == true
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
            selectedFileURL = panel.url
        }
    }

    func acceptDroppedFile(_ url: URL) {
        guard url.isFileURL, ["step", "stp"].contains(url.pathExtension.lowercased()) else {
            return
        }
        selectedFileURL = url
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
        isAnalyzing = true
        defer { isAnalyzing = false }

        do {
            analysis = try await backendService.analyze(fileURL: selectedFileURL, qty: quantity)
            lastErrorMessage = nil
        } catch {
            present(error)
        }
    }

    func clearError() {
        lastErrorMessage = nil
    }

    private func present(_ error: Error) {
        lastErrorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
    }
}

enum SidebarScreen: String, CaseIterable, Identifiable {
    case check
    case settings
    case diagnostics

    var id: String { rawValue }

    var title: String {
        switch self {
        case .check:
            return "Check"
        case .settings:
            return "Settings"
        case .diagnostics:
            return "Diagnostics"
        }
    }

    var symbolName: String {
        switch self {
        case .check:
            return "checklist"
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
