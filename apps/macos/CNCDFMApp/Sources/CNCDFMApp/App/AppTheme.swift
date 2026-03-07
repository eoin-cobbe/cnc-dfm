import SwiftUI

enum AppTheme {
    static let accentColor = Color(nsColor: .systemBlue)
    static let windowBackground = Color(nsColor: .windowBackgroundColor)
    static let panelBackground = Color(nsColor: .controlBackgroundColor)
    static let panelBorder = Color(nsColor: .separatorColor).opacity(0.55)
    static let mutedText = Color.secondary
    static let success = Color(nsColor: .systemGreen)
    static let failure = Color(nsColor: .systemRed)
    static let warning = Color(nsColor: .systemOrange)
}
