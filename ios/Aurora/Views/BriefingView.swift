import SwiftUI

/// Écran unique de l'app : en-tête fixe, rubriques, puis les sujets.
/// On passe d'une rubrique à l'autre en touchant son nom ou en balayant.
struct BriefingView: View {
    @State var store: BriefingStore
    @State private var selection = Category.defaults[0].id
    @Environment(\.scenePhase) private var scenePhase

    private var categories: [Category] {
        store.summary?.categories ?? Category.defaults
    }

    private var currentCategory: Category {
        categories.first { $0.id == selection } ?? categories[0]
    }

    private var swipeBetweenCategories: some Gesture {
        DragGesture(minimumDistance: 30)
            .onEnded { value in
                let dx = value.translation.width
                guard abs(dx) > 60, abs(dx) > abs(value.translation.height) * 1.5,
                      let index = categories.firstIndex(where: { $0.id == selection })
                else { return }
                let next = dx < 0 ? index + 1 : index - 1
                guard categories.indices.contains(next) else { return }
                withAnimation(.easeInOut(duration: 0.25)) {
                    selection = categories[next].id
                }
            }
    }

    var body: some View {
        VStack(spacing: 0) {
            HeaderView(date: store.summary?.generatedAt ?? Date())
            CategoryTabView(categories: categories, selection: $selection)

            // Une seule liste à la fois (le TabView en mode page ne suit pas
            // toujours une sélection modifiée par code) ; `.id` remet le
            // défilement en haut à chaque changement de rubrique.
            TopicListView(
                category: currentCategory,
                summary: store.summary,
                isLoading: store.isLoading,
                errorMessage: store.errorMessage,
                refresh: { await store.refresh() }
            )
            .id(selection)
            .transition(.opacity)
            .simultaneousGesture(swipeBetweenCategories)
        }
        .background(AuroraTheme.background.ignoresSafeArea())
        .tint(AuroraTheme.primaryText)
        .task { await store.load() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active {
                Task { await store.refreshIfStale() }
            }
        }
    }
}

#Preview {
    BriefingView(store: BriefingStore(summary: .preview))
}
