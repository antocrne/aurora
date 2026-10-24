import SwiftUI

@main
struct AuroraApp: App {
    var body: some Scene {
        WindowGroup {
            BriefingView(store: BriefingStore())
        }
    }
}
