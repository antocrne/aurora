import Foundation
import Observation

/// État de l'édition affichée : chargement, édition courante, erreur éventuelle.
@MainActor
@Observable
final class BriefingStore {
    private(set) var summary: Summary?
    private(set) var isLoading = false
    private(set) var errorMessage: String?
    private var lastRefresh: Date?

    private let service: SummaryService

    init(service: SummaryService = SummaryService(), summary: Summary? = nil) {
        self.service = service
        self.summary = summary
    }

    /// Affiche tout de suite l'édition en cache, puis va chercher la plus récente.
    func load() async {
        if summary == nil {
            summary = service.cached()
        }
        await refresh()
    }

    /// Recharge au retour au premier plan, au plus une fois toutes les 15 minutes.
    func refreshIfStale() async {
        guard let lastRefresh, Date().timeIntervalSince(lastRefresh) > 15 * 60 else { return }
        await refresh()
    }

    func refresh() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            summary = try await service.fetch()
            errorMessage = nil
            lastRefresh = Date()
        } catch {
            errorMessage = summary == nil
                ? "L'édition du jour n'a pas pu être chargée."
                : "Hors ligne : édition précédente affichée."
        }
    }
}
