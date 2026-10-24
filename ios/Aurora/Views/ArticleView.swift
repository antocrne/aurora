import SafariServices
import SwiftUI

/// Article d'origine ouvert dans l'app, en mode lecture quand le site le permet.
struct ArticleView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        let configuration = SFSafariViewController.Configuration()
        configuration.entersReaderIfAvailable = true
        let controller = SFSafariViewController(url: url, configuration: configuration)
        controller.preferredControlTintColor = AuroraTheme.uiPrimaryText
        controller.dismissButtonStyle = .close
        return controller
    }

    func updateUIViewController(_ controller: SFSafariViewController, context: Context) {}
}

/// Enveloppe identifiable pour présenter un article avec `.sheet(item:)`.
struct ArticleLink: Identifiable {
    let url: URL
    var id: String { url.absoluteString }
}
