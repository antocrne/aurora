import SwiftUI
import UIKit

/// Couleurs, polices et mesures du journal. Tout est en serif (New York, la
/// serif système d'Apple), sans ombre, sans dégradé, sans coin arrondi.
enum AuroraTheme {
    // MARK: Couleurs

    static let background = Color(light: 0xFAF8F5, dark: 0x1C1915)
    static let primaryText = Color(light: 0x1A1A1A, dark: 0xE8E2D8)
    static let secondaryText = Color(light: 0x6B6B6B, dark: 0x8A8478)
    static let rule = Color(light: 0xD4D0CA, dark: 0x3D3830)
    static let accent = Color(light: 0x8B0000, dark: 0xB34040)

    static let uiPrimaryText = UIColor(light: 0x1A1A1A, dark: 0xE8E2D8)

    // MARK: Typographie

    static let masthead = Font.system(size: 40, weight: .black, design: .serif)
    static let date = Font.system(.subheadline, design: .serif).italic()
    static let categoryLabel = Font.system(.subheadline, design: .serif)
    static let headline = Font.system(.title2, design: .serif).weight(.bold)
    static let body = Font.system(.body, design: .serif)
    static let sources = Font.system(.footnote, design: .serif).italic()
    static let footer = Font.system(.caption, design: .serif)

    static func uiSerif(_ style: UIFont.TextStyle, weight: UIFont.Weight = .regular, size: CGFloat? = nil) -> UIFont {
        let base = UIFont.preferredFont(forTextStyle: style)
        let font = UIFont.systemFont(ofSize: size ?? base.pointSize, weight: weight)
        guard let descriptor = font.fontDescriptor.withDesign(.serif) else { return font }
        return UIFont(descriptor: descriptor, size: 0)
    }

    // MARK: Mise en page

    static let horizontalMargin: CGFloat = 22
    static let topicSpacing: CGFloat = 28
    /// Interligne du corps : ~1,45 × la taille du texte (17 pt).
    static let bodyLineSpacing: CGFloat = 7.5
}

// MARK: - Filets

/// Filet horizontal fin.
struct Rule: View {
    var color: Color = AuroraTheme.rule
    var thickness: CGFloat = 1

    var body: some View {
        Rectangle()
            .fill(color)
            .frame(height: thickness)
            .accessibilityHidden(true)
    }
}

/// Double filet, comme sous le titre d'un quotidien.
struct DoubleRule: View {
    var body: some View {
        VStack(spacing: 2) {
            Rule(color: AuroraTheme.primaryText, thickness: 1.5)
            Rule(color: AuroraTheme.primaryText, thickness: 0.5)
        }
    }
}

// MARK: - Couleurs claires / sombres

extension UIColor {
    convenience init(hex: UInt32) {
        self.init(
            red: CGFloat((hex >> 16) & 0xFF) / 255,
            green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255,
            alpha: 1
        )
    }

    convenience init(light: UInt32, dark: UInt32) {
        self.init { traits in
            traits.userInterfaceStyle == .dark ? UIColor(hex: dark) : UIColor(hex: light)
        }
    }
}

extension Color {
    init(light: UInt32, dark: UInt32) {
        self.init(uiColor: UIColor(light: light, dark: dark))
    }
}

// MARK: - Dates en français

enum FrenchDate {
    private static let locale = Locale(identifier: "fr_FR")

    /// « Samedi 24 octobre 2026 » (« 1er » le premier du mois).
    static func long(_ date: Date) -> String {
        let calendar = Calendar.current
        let day = calendar.component(.day, from: date)
        let weekday = date.formatted(.dateTime.weekday(.wide).locale(locale))
        let monthYear = date.formatted(.dateTime.month(.wide).year().locale(locale))
        let text = "\(weekday) \(day == 1 ? "1er" : String(day)) \(monthYear)"
        return text.prefix(1).uppercased() + text.dropFirst()
    }

    /// « 7h03 »
    static func time(_ date: Date) -> String {
        let parts = Calendar.current.dateComponents([.hour, .minute], from: date)
        return String(format: "%dh%02d", parts.hour ?? 0, parts.minute ?? 0)
    }
}
