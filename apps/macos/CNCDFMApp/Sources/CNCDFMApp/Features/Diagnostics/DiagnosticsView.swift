import SwiftUI

struct DiagnosticsView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                PanelCard(title: "Backend Status", subtitle: "What the app is launching right now.") {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack(spacing: 12) {
                            Circle()
                                .fill(model.health?.analysisRuntime.available == true ? AppTheme.success : AppTheme.warning)
                                .frame(width: 10, height: 10)
                            Text(statusText)
                                .font(.headline)
                        }

                        keyValueRow("Launch Command", model.backendInfo?.launchDescription ?? "Unavailable")
                        keyValueRow("Repo Root", model.backendInfo?.repoRoot.path ?? "Unavailable")
                        keyValueRow("API Script", model.backendInfo?.apiScript.path ?? "Unavailable")
                        keyValueRow("Python", model.health?.pythonExecutable ?? "Unavailable")
                        keyValueRow("Config Path", model.health?.configPath ?? "Unavailable")
                    }
                }

                if let analysisRuntime = model.health?.analysisRuntime, analysisRuntime.available == false {
                    PanelCard(title: "Runtime Error") {
                        VStack(alignment: .leading, spacing: 10) {
                            keyValueRow("Error Type", analysisRuntime.errorType ?? "Unknown")
                            keyValueRow("Message", analysisRuntime.message ?? "Unknown backend startup error.")
                        }
                    }
                }

                PanelCard(title: "Health Payload", subtitle: "Direct backend status for app diagnostics.") {
                    VStack(alignment: .leading, spacing: 10) {
                        keyValueRow("Status", model.health?.status ?? "Unavailable")
                        keyValueRow("API Version", "\(model.health?.apiVersion ?? 0)")
                        keyValueRow("Platform", model.health?.platform ?? "Unavailable")
                        keyValueRow("Working Directory", model.health?.cwd ?? "Unavailable")
                    }
                }

                HStack {
                    Button("Refresh Diagnostics") {
                        Task {
                            await model.refreshDiagnostics()
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    Spacer()
                }
            }
            .padding(24)
        }
    }

    private var statusText: String {
        if model.health?.analysisRuntime.available == true {
            return "Analysis runtime available"
        }
        return "Analysis runtime unavailable"
    }

    private func keyValueRow(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased())
                .font(.caption2.weight(.medium))
                .foregroundStyle(AppTheme.mutedText)
            Text(value)
                .font(.subheadline)
                .textSelection(.enabled)
        }
    }
}
