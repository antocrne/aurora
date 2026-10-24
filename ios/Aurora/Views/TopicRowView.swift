import SwiftUI

/// Un sujet : manchette, résumé, puis les sources en petit italique.
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

            if !topic.sources.isEmpty {
                Text(topic.sources.joined(separator: ", "))
                    .font(AuroraTheme.sources)
                    .foregroundStyle(AuroraTheme.secondaryText)
                    .padding(.top, 2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .fixedSize(horizontal: false, vertical: true)
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
