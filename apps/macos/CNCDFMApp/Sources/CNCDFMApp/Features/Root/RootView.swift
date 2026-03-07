import SwiftUI

struct RootView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        NavigationSplitView {
            List(SidebarScreen.allCases, selection: $model.selectedScreen) { screen in
                Label(screen.title, systemImage: screen.symbolName)
                    .tag(screen)
            }
            .listStyle(.sidebar)
            .scrollContentBackground(.hidden)
            .background(AppTheme.windowBackground)
        } detail: {
            contentView
                .background(AppTheme.windowBackground)
        }
        .navigationSplitViewStyle(.balanced)
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

    @ViewBuilder
    private var contentView: some View {
        switch model.selectedScreen {
        case .check:
            CheckView(model: model)
        case .settings:
            SettingsView(model: model)
        case .diagnostics:
            DiagnosticsView(model: model)
        }
    }
}
