import SwiftUI

/// Un sujet : manchette, résumé, lecture croisée éventuelle, puis les sources
/// en petit italique. Chaque source qui a un lien ouvre l'article d'origine.
struct TopicRowView: View {
    let topic: Topic
    /// Lettrine sur la première lettre du résumé (premier sujet de la rubrique).
    var dropCap = false

    @ScaledMetric(relativeTo: .body) private var lineSpacing = AuroraTheme.bodyLineSpacing

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(topic.headline)
                .font(AuroraTheme.headline)
                .lineSpacing(2)
                .foregroundStyle(AuroraTheme.primaryText)
                .accessibilityAddTraits(.isHeader)

            if dropCap, topic.summary.first?.isLetter == true {
                DropCapText(text: topic.summary, lineSpacing: lineSpacing)
                    .accessibilityLabel(topic.summary)
            } else {
                Text(topic.summary)
                    .font(AuroraTheme.body)
                    .lineSpacing(lineSpacing)
                    .foregroundStyle(AuroraTheme.primaryText)
            }

            if let angles = topic.angles, !angles.isEmpty {
                AnglesView(text: angles)
                    .padding(.top, 4)
            }

            if !topic.sources.isEmpty {
                Text(sourcesLine)
                    .font(AuroraTheme.sources)
                    .foregroundStyle(AuroraTheme.secondaryText)
                    .tint(AuroraTheme.secondaryText)
                    .padding(.top, 2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .fixedSize(horizontal: false, vertical: true)
    }

    /// « Le Monde, RFI, BBC », chaque nom souligné et cliquable quand l'article est disponible.
    private var sourcesLine: AttributedString {
        var line = AttributedString()
        for (index, source) in topic.sources.enumerated() {
            if index > 0 {
                line += AttributedString(", ")
            }
            var name = AttributedString(source)
            if let url = topic.url(for: source) {
                name.link = url
                name.underlineStyle = .single
            }
            line += name
        }
        return line
    }
}

/// « Lecture croisée » : comment les médias traitent le sujet, sous un filet
/// vertical. Repliée par défaut : le lecteur la déroule s'il le souhaite.
private struct AnglesView: View {
    let text: String
    @State private var isExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    isExpanded.toggle()
                }
            } label: {
                // Un triangle typographique plutôt qu'une icône, dans l'esprit du journal.
                Text("LECTURE CROISÉE  \(isExpanded ? "▾" : "▸")")
                    .font(AuroraTheme.anglesLabel)
                    .tracking(1.8)
                    .foregroundStyle(AuroraTheme.secondaryText)
                    .frame(maxWidth: .infinity, minHeight: 28, alignment: .leading)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Lecture croisée")
            .accessibilityValue(isExpanded ? "dépliée" : "repliée")
            .accessibilityHint("Compare le traitement du sujet par les différents médias")

            if isExpanded {
                Text(text)
                    .font(AuroraTheme.angles)
                    .lineSpacing(3)
                    .foregroundStyle(AuroraTheme.primaryText)
                    .padding(.bottom, 2)
                    .transition(.opacity)
            }
        }
        .padding(.leading, 12)
        .overlay(alignment: .leading) {
            Rectangle()
                .fill(AuroraTheme.rule)
                .frame(width: 2)
        }
    }
}

#Preview {
    VStack(spacing: 28) {
        TopicRowView(topic: Summary.preview.categories[0].topics[0], dropCap: true)
        TopicRowView(topic: Summary.preview.categories[0].topics[1])
    }
    .padding(22)
    .background(AuroraTheme.background)
}
