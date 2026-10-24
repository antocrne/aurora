import SwiftUI

/// Navigation entre rubriques : MONDE · EUROPE · FRANCE.
struct CategoryTabView: View {
    let categories: [Category]
    @Binding var selection: String

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                ForEach(Array(categories.enumerated()), id: \.element.id) { index, category in
                    if index > 0 {
                        Text("·")
                            .font(AuroraTheme.categoryLabel)
                            .foregroundStyle(AuroraTheme.secondaryText)
                            .accessibilityHidden(true)
                    }
                    tab(for: category)
                }
            }
            .padding(.vertical, 10)

            Rule()
        }
        .padding(.horizontal, AuroraTheme.horizontalMargin)
    }

    private func tab(for category: Category) -> some View {
        let isSelected = category.id == selection
        return Button {
            withAnimation(.easeInOut(duration: 0.25)) {
                selection = category.id
            }
        } label: {
            Text(category.label.uppercased())
                .font(AuroraTheme.categoryLabel)
                .fontWeight(isSelected ? .bold : .regular)
                .tracking(2.5)
                .foregroundStyle(isSelected ? AuroraTheme.primaryText : AuroraTheme.secondaryText)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isSelected ? [.isSelected] : [])
    }
}

#Preview {
    @Previewable @State var selection = "monde"
    CategoryTabView(categories: Category.defaults, selection: $selection)
        .background(AuroraTheme.background)
}
