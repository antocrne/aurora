import Foundation
import Observation

/// État de l'édition affichée : chargement, édition courante, erreur éventuelle.
@MainActor
@Observable
final class BriefingStore {
    /// Heures de Paris (heure, minute) où démarre la génération d'une édition,
    /// alignées sur le cron de `.github/workflows/daily.yml` : 6h30 et 18h30,
    /// pour des éditions prêtes à 7h et 19h, été comme hiver.
    static let generationTimes = [(6, 30), (18, 30)]
    static let paris = TimeZone(identifier: "Europe/Paris")!

    private(set) var summary: Summary?
    private(set) var isLoading = false
    private(set) var errorMessage: String?
    private var lastRefresh: Date?

    private let service: SummaryService

    init(service: SummaryService = SummaryService(), summary: Summary? = nil) {
        self.service = service
        self.summary = summary
    }

    /// Affiche tout de suite l'édition en cache, et ne va chercher la suivante
    /// que si elle a pu paraître depuis.
    func load() async {
        if summary == nil {
            summary = service.cached()
        }
        if summary == nil || newEditionDue() {
            await refresh()
        }
    }

    /// Au retour au premier plan : recharge seulement si une édition est
    /// attendue, et au plus une fois toutes les 15 minutes (le cron GitHub
    /// peut publier avec du retard).
    func refreshIfStale() async {
        guard newEditionDue() else { return }
        if let lastRefresh, Date().timeIntervalSince(lastRefresh) < 15 * 60 { return }
        await refresh()
    }

    func refresh() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        lastRefresh = Date()
        do {
            summary = try await service.fetch()
            errorMessage = nil
        } catch is CancellationError {
            return
        } catch let error as URLError where error.code == .cancelled {
            return
        } catch {
            errorMessage = summary == nil
                ? "L'édition du jour n'a pas pu être chargée."
                : "Hors ligne : édition précédente affichée."
        }
    }

    /// Vrai si une génération a démarré depuis celle de l'édition affichée.
    private func newEditionDue(now: Date = Date()) -> Bool {
        guard let generatedAt = summary?.generatedAt else { return true }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = Self.paris
        let nextEdition = Self.generationTimes
            .compactMap { hour, minute in
                calendar.nextDate(
                    after: generatedAt,
                    matching: DateComponents(hour: hour, minute: minute),
                    matchingPolicy: .nextTime
                )
            }
            .min()
        guard let nextEdition else { return true }
        return now >= nextEdition
    }
}
