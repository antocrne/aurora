import Foundation

enum SummaryServiceError: LocalizedError {
    case badStatus(Int)

    var errorDescription: String? {
        switch self {
        case .badStatus(let code): "Le serveur a répondu avec le code \(code)."
        }
    }
}

/// Télécharge `summaries.json` depuis GitHub Pages et garde la dernière édition
/// reçue en cache, pour pouvoir lire le journal hors ligne.
struct SummaryService: Sendable {
    static let defaultURL = URL(string: "https://antocrne.github.io/aurora/summaries.json")!

    let url: URL

    /// La variable d'environnement `AURORA_FEED_URL` permet de pointer l'app
    /// vers un autre serveur (ex. `python3 -m http.server` sur `docs/`).
    init(url: URL? = nil) {
        if let override = ProcessInfo.processInfo.environment["AURORA_FEED_URL"],
           let overrideURL = URL(string: override) {
            self.url = overrideURL
        } else {
            self.url = url ?? Self.defaultURL
        }
    }

    func fetch() async throws -> Summary {
        let request = URLRequest(
            url: url,
            cachePolicy: .reloadIgnoringLocalCacheData,
            timeoutInterval: 20
        )
        let (data, response) = try await URLSession.shared.data(for: request)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw SummaryServiceError.badStatus(http.statusCode)
        }
        let summary = try Self.decode(data)
        try? data.write(to: Self.cacheURL, options: .atomic)
        return summary
    }

    func cached() -> Summary? {
        guard let data = try? Data(contentsOf: Self.cacheURL) else { return nil }
        return try? Self.decode(data)
    }

    static func decode(_ data: Data) throws -> Summary {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(Summary.self, from: data)
    }

    private static var cacheURL: URL {
        URL.cachesDirectory.appending(path: "summaries.json")
    }
}
