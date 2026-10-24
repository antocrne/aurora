import SwiftUI

/// En-tête fixe : titre du journal, double filet, date de l'édition, filet simple.
struct HeaderView: View {
    let date: Date

    var body: some View {
        VStack(spacing: 0) {
            Text("AURORA")
                .font(AuroraTheme.masthead)
                .tracking(6)
                .foregroundStyle(AuroraTheme.primaryText)
                .padding(.top, 6)
                .padding(.bottom, 8)
                .accessibilityAddTraits(.isHeader)

            DoubleRule()

            Text(FrenchDate.long(date))
                .font(AuroraTheme.date)
                .foregroundStyle(AuroraTheme.secondaryText)
                .padding(.vertical, 7)

            Rule()
        }
        .padding(.horizontal, AuroraTheme.horizontalMargin)
    }
}

#Preview {
    HeaderView(date: Date())
        .background(AuroraTheme.background)
}
