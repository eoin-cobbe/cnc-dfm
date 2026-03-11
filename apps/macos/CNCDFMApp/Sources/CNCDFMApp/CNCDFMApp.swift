import SwiftUI

@main
struct CNCDFMApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView(model: model)
                .frame(minWidth: 1080, minHeight: 720)
                .preferredColorScheme(nil)
                .tint(AppTheme.accentColor)
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified(showsTitle: false))

        Settings {
            SettingsView(model: model)
                .frame(width: 760, height: 640)
                .padding(24)
                .background(AppTheme.windowBackground)
        }
    }
}
