import Foundation

/// Une édition complète, telle que publiée dans `docs/summaries.json`.
struct Summary: Codable, Sendable, Equatable {
    let generatedAt: Date
    let edition: String
    let categories: [Category]

    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"
        case edition
        case categories
    }

    func category(_ id: String) -> Category? {
        categories.first { $0.id == id }
    }
}

struct Category: Codable, Sendable, Equatable, Identifiable {
    let id: String
    let label: String
    let topics: [Topic]

    /// Les trois rubriques du journal, affichées même avant le premier chargement.
    static let defaults: [Category] = [
        Category(id: "monde", label: "Monde", topics: []),
        Category(id: "europe", label: "Europe", topics: []),
        Category(id: "france", label: "France", topics: []),
    ]
}

struct Topic: Codable, Sendable, Equatable {
    let headline: String
    let summary: String
    let sources: [String]
}

extension Summary {
    static let preview = Summary(
        generatedAt: Date(),
        edition: "24 octobre 2026",
        categories: [
            Category(id: "monde", label: "Monde", topics: [
                Topic(
                    headline: "Cessez-le-feu annoncé à Olechky",
                    summary: "La Russie et l'Ukraine ont confirmé vendredi un cessez-le-feu local dans la ville d'Olechky, occupée depuis 2022. La situation humanitaire y est jugée critique par les organisations présentes sur place. Les modalités de l'évacuation des civils restent à préciser.",
                    sources: ["Le Monde", "RFI", "BBC"]
                ),
                Topic(
                    headline: "Le Brésil à huit jours du second tour",
                    summary: "Lula et Flavio Bolsonaro se sont affrontés jeudi lors d'un second débat télévisé. Le président sortant a adopté un ton plus offensif, son adversaire un registre plus mesuré.",
                    sources: ["France 24"]
                ),
            ]),
            Category(id: "europe", label: "Europe", topics: []),
            Category(id: "france", label: "France", topics: []),
        ]
    )
}
