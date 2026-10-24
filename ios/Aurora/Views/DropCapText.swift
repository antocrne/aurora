import SwiftUI
import UIKit

/// Paragraphe avec lettrine : la première lettre occupe la hauteur de
/// `lines` lignes et le texte s'enroule autour. SwiftUI ne sait pas faire
/// d'habillage de texte, d'où le passage par TextKit.
struct DropCapText: UIViewRepresentable {
    let text: String
    var lineSpacing: CGFloat
    var lines = 3

    // Lu pour que SwiftUI redessine la vue quand la taille du texte change.
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    func makeUIView(context: Context) -> DropCapTextView {
        DropCapTextView()
    }

    func updateUIView(_ view: DropCapTextView, context: Context) {
        view.configure(text: text, lineSpacing: lineSpacing, lines: lines)
    }

    func sizeThatFits(_ proposal: ProposedViewSize, uiView: DropCapTextView, context: Context) -> CGSize? {
        let width = proposal.width ?? 340
        return CGSize(width: width, height: uiView.height(forWidth: width))
    }
}

final class DropCapTextView: UIView {
    private let textView = UITextView(usingTextLayoutManager: false)
    private let capLabel = UILabel()
    private var capSize = CGSize.zero
    private var capBaseline: CGFloat = 0
    private var exclusionHeight: CGFloat = 0
    private static let capGap: CGFloat = 6

    override init(frame: CGRect) {
        super.init(frame: frame)
        textView.isScrollEnabled = false
        textView.isEditable = false
        textView.isSelectable = false
        textView.backgroundColor = .clear
        textView.textContainerInset = .zero
        textView.textContainer.lineFragmentPadding = 0
        textView.isAccessibilityElement = false
        capLabel.isAccessibilityElement = false
        addSubview(textView)
        addSubview(capLabel)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) non utilisé") }

    func configure(text: String, lineSpacing: CGFloat, lines: Int) {
        guard let first = text.first else { return }
        let bodyFont = AuroraTheme.uiSerif(.body)
        let advance = bodyFont.lineHeight + lineSpacing

        // La lettrine s'étend de la hauteur de capitale de la 1re ligne
        // jusqu'à la ligne de base de la ligne `lines`.
        let targetCapHeight = CGFloat(lines - 1) * advance + bodyFont.capHeight
        let reference = AuroraTheme.uiSerif(.body, weight: .bold, size: 100)
        let capFont = reference.withSize(100 * targetCapHeight / reference.capHeight)

        capLabel.attributedText = NSAttributedString(
            string: String(first),
            attributes: [.font: capFont, .foregroundColor: AuroraTheme.uiPrimaryText]
        )
        let glyphWidth = (String(first) as NSString).size(withAttributes: [.font: capFont]).width
        capSize = CGSize(width: ceil(glyphWidth), height: ceil(capFont.lineHeight))
        capBaseline = bodyFont.ascender + CGFloat(lines - 1) * advance
        capLabel.frame = CGRect(x: 0, y: capBaseline - capFont.ascender, width: capSize.width, height: capSize.height)

        let paragraph = NSMutableParagraphStyle()
        paragraph.lineSpacing = lineSpacing
        textView.attributedText = NSAttributedString(
            string: String(text.dropFirst()),
            attributes: [
                .font: bodyFont,
                .foregroundColor: AuroraTheme.uiPrimaryText,
                .paragraphStyle: paragraph,
            ]
        )
        exclusionHeight = CGFloat(lines) * advance - 1
        textView.textContainer.exclusionPaths = [
            UIBezierPath(rect: CGRect(x: 0, y: 0, width: capSize.width + Self.capGap, height: exclusionHeight)),
        ]
        setNeedsLayout()
        invalidateIntrinsicContentSize()
    }

    func height(forWidth width: CGFloat) -> CGFloat {
        let fitted = textView.sizeThatFits(CGSize(width: width, height: .greatestFiniteMagnitude))
        return ceil(max(fitted.height, exclusionHeight))
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        textView.frame = CGRect(x: 0, y: 0, width: bounds.width, height: height(forWidth: bounds.width))
    }
}
