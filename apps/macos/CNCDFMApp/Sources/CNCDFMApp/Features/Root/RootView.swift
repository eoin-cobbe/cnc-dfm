import SwiftUI

struct RootView: View {
    @ObservedObject var model: AppModel

    private let outputScreens: [SidebarScreen] = [.recommendations, .ruleResults, .summary]
    private let utilityScreens: [SidebarScreen] = [.settings, .diagnostics]

    var body: some View {
        NavigationSplitView {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    runAnalysisButton

                    VStack(spacing: 10) {
                        ForEach(outputScreens) { screen in
                            sidebarButton(for: screen)
                        }
                    }

                    Divider()
                        .padding(.vertical, 2)

                    VStack(spacing: 10) {
                        ForEach(utilityScreens) { screen in
                            sidebarButton(for: screen)
                        }
                    }
                }
                .padding(18)
            }
            .frame(minWidth: 232, idealWidth: 248, maxWidth: 272, maxHeight: .infinity, alignment: .topLeading)
            .background(AppTheme.windowBackground)
        } detail: {
            contentView
                .background(AppTheme.windowBackground)
        }
        .navigationSplitViewStyle(.balanced)
        .navigationSplitViewColumnWidth(min: 232, ideal: 248)
        .background(AppTheme.windowBackground)
        .overlay(alignment: .bottomLeading) {
            if let lastErrorMessage = model.lastErrorMessage {
                HStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(AppTheme.warning)
                    Text(lastErrorMessage)
                        .font(.subheadline)
                    Spacer(minLength: 0)
                    Button("Dismiss") {
                        model.clearError()
                    }
                    .buttonStyle(.plain)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .frame(maxWidth: 560)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .padding(18)
            }
        }
        .task {
            await model.bootstrapIfNeeded()
        }
    }

    private var runAnalysisButton: some View {
        Button {
            model.launchNewAnalysisPicker()
        } label: {
            VStack(spacing: 9) {
                Image(systemName: "doc.badge.plus")
                    .font(.system(size: 30, weight: .regular))
                    .foregroundStyle(AppTheme.accentColor)

                VStack(spacing: 4) {
                    Text("Run New Analysis")
                        .font(.headline.weight(.semibold))
                        .foregroundStyle(.primary)
                        .lineLimit(2)
                        .multilineTextAlignment(.center)

                    if model.isRunningNextAnalysis, let pendingAnalysisFileName = model.pendingAnalysisFileName {
                        Text("Loading \(pendingAnalysisFileName)")
                            .font(.caption)
                            .foregroundStyle(AppTheme.mutedText)
                            .lineLimit(2)
                            .multilineTextAlignment(.center)
                    } else {
                        Text("Choose a STEP file and start the next run")
                            .font(.caption)
                            .foregroundStyle(AppTheme.mutedText)
                            .lineLimit(3)
                            .multilineTextAlignment(.center)
                    }
                }
            }
            .frame(maxWidth: .infinity, minHeight: 116)
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(Color(nsColor: .controlColor))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .strokeBorder(Color(nsColor: .separatorColor).opacity(0.45), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    private func sidebarButton(for screen: SidebarScreen) -> some View {
        let isSelected = model.selectedScreen == screen

        return Button {
            model.selectedScreen = screen
        } label: {
            HStack(spacing: 14) {
                Image(systemName: screen.symbolName)
                    .font(.system(size: 18, weight: .medium))
                    .foregroundStyle(isSelected ? AppTheme.accentColor : AppTheme.mutedText)
                    .frame(width: 24)

                Text(screen.title)
                    .font(.body.weight(isSelected ? .semibold : .regular))
                    .foregroundStyle(.primary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.9)

                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 9)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(isSelected ? Color(nsColor: .selectedContentBackgroundColor).opacity(0.65) : Color.clear)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(isSelected ? Color(nsColor: .separatorColor).opacity(0.28) : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private var contentView: some View {
        switch model.selectedScreen {
        case .recommendations:
            CheckView(model: model, mode: .recommendations)
        case .ruleResults:
            CheckView(model: model, mode: .ruleResults)
        case .summary:
            CheckView(model: model, mode: .summary)
        case .settings:
            SettingsView(model: model)
        case .diagnostics:
            DiagnosticsView(model: model)
        }
    }
}
