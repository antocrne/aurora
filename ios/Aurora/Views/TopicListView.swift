import SwiftUI

/// Les sujets d'une rubrique, séparés par des filets, avec pied de page.
struct TopicListView: View {
    let category: Category
    let summary: Summary?
    let isLoading: Bool
    let errorMessage: String?
    let refresh: () async -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                if let errorMessage, summary != nil {
                    Text(errorMessage)
                        .font(AuroraTheme.sources)
                        .foregroundStyle(AuroraTheme.accent)
                        .frame(maxWidth: .infinity)
                        .padding(.top, 14)
                }

                if summary == nil {
                    placeholder
                } else if category.topics.isEmpty {
                    Text("Aucun sujet dans cette rubrique aujourd'hui.")
                        .font(AuroraTheme.body.italic())
                        .foregroundStyle(AuroraTheme.secondaryText)
                        .frame(maxWidth: .infinity)
                        .padding(.top, 60)
                } else {
                    topics
                }
            }
            .padding(.horizontal, AuroraTheme.horizontalMargin)
            .padding(.bottom, 24)
        }
        .refreshable { await refresh() }
    }

    private var topics: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(category.topics.enumerated()), id: \.offset) { index, topic in
                if index > 0 {
                    Rule()
                }
                TopicRowView(topic: topic, dropCap: index == 0)
                    .padding(.vertical, AuroraTheme.topicSpacing / 2)
            }

            Text("❧")
                .font(.system(size: 22, design: .serif))
                .foregroundStyle(AuroraTheme.secondaryText)
                .frame(maxWidth: .infinity)
                .padding(.top, 12)
                .accessibilityHidden(true)

            if let summary {
                Text("Dernière édition : \(FrenchDate.moment(summary.generatedAt))")
                    .font(AuroraTheme.footer)
                    .foregroundStyle(AuroraTheme.secondaryText)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 10)
            }
        }
    }

    @ViewBuilder
    private var placeholder: some View {
        VStack(spacing: 16) {
            if isLoading || errorMessage == nil {
                Text("Mise sous presse…")
                    .font(AuroraTheme.body.italic())
                    .foregroundStyle(AuroraTheme.secondaryText)
            } else {
                Text(errorMessage ?? "")
                    .font(AuroraTheme.body.italic())
                    .foregroundStyle(AuroraTheme.secondaryText)
                    .multilineTextAlignment(.center)
                Button("Réessayer") {
                    Task { await refresh() }
                }
                .font(AuroraTheme.categoryLabel.weight(.semibold))
                .tracking(1.5)
                .foregroundStyle(AuroraTheme.primaryText)
                .buttonStyle(.plain)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 80)
    }
}

#Preview {
    TopicListView(
        category: Summary.preview.categories[0],
        summary: .preview,
        isLoading: false,
        errorMessage: nil,
        refresh: {}
    )
    .background(AuroraTheme.background)
}
