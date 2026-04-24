//
//  SetiIconProvider.swift
//
//  CotEditor
//  https://coteditor.com
//
//  Created for the Seti-style file browser icons.
//
//  Licensed under the Apache License, Version 2.0 (the "License").
//  Icon artwork and mapping are vendored from MIT-licensed sources;
//  see THIRD_PARTY_NOTICES.md in the repository root.
//

import AppKit

struct SetiIcon {

    let image: NSImage
    let label: String
}


enum SetiIconProvider {

    /// Rendered icon size in points. The underlying SVGs are vector; this only
    /// governs the rasterization resolution for the NSImage drawing block.
    static let iconSize = NSSize(width: 16, height: 16)

    /// Resolves the Seti icon for a given file node.
    ///
    /// Matching mirrors VS Code's theme-seti lookup order:
    /// 1. Exact filename (case-insensitive).
    /// 2. File extension — longest match first (e.g. `foo.spec.ts` matches `spec.ts` before `ts`).
    /// 3. Fallback to the default Seti file or folder icon.
    ///
    /// The returned image is pre-tinted and non-template. Callers should set it on
    /// `NSImageView.image` directly; do **not** set `contentTintColor` or `isTemplate`.
    @MainActor
    static func icon(for file: File, appearance: NSAppearance? = nil) -> SetiIcon {

        let resolvedAppearance = appearance
            ?? NSApp?.effectiveAppearance
            ?? NSAppearance(named: .aqua)!

        let assetName: String
        let iconKey: String
        if file.isFolder {
            // Seti has no iconDefinition entry for folders, so look up the color
            // under the default key while pointing the image at the folder asset.
            assetName = SetiIconMap.defaultFolder
            iconKey = Self.defaultIconKey
        } else {
            iconKey = Self.iconKey(for: file)
            assetName = SetiIconMap.assetNames[iconKey] ?? SetiIconMap.defaultFile
        }
        let rgb = Self.rgb(forKey: iconKey, appearance: resolvedAppearance)

        let image = Self.cache.image(assetName: assetName, rgb: rgb)
        return SetiIcon(image: image, label: Self.label(for: file))
    }


    // MARK: Private

    private static let cache = ImageCache()


    private static func iconKey(for file: File) -> String {

        let name = file.name.lowercased()

        if let key = SetiIconMap.fileNames[name] {
            return key
        }

        // Longest-extension match: try "foo.spec.ts" → "spec.ts" → "ts".
        let parts = name.split(separator: ".", omittingEmptySubsequences: false)
        if parts.count > 1 {
            for start in 1..<parts.count {
                let ext = parts[start...].joined(separator: ".")
                if let key = SetiIconMap.fileExtensions[ext] {
                    return key
                }
            }
        }

        return Self.defaultIconKey
    }


    private static func label(for file: File) -> String {

        file.kind.label
    }


    /// The Seti icon-key used when nothing else matches.
    private static let defaultIconKey = "_default"


    private static func rgb(forKey key: String, appearance: NSAppearance) -> SetiIconMap.RGB {

        let isLight = appearance.bestMatch(from: [.aqua, .darkAqua]) != .darkAqua
        let palette = isLight ? SetiIconMap.lightColors : SetiIconMap.darkColors
        return palette[key]
            ?? palette[Self.defaultIconKey]
            ?? (r: 0.8, g: 0.8, b: 0.8)
    }
}


// MARK: - Image cache

/// Caches pre-tinted icon images keyed by (asset name, RGB triple).
///
/// Pre-tinting avoids relying on `NSImageView.contentTintColor` + template rendering,
/// which does not reliably tint vector assets marked with `preserves-vector-representation`.
private final class ImageCache: @unchecked Sendable {

    private var storage: [String: NSImage] = [:]
    private let lock = NSLock()


    func image(assetName: String, rgb: SetiIconMap.RGB) -> NSImage {

        let key = Self.cacheKey(assetName: assetName, rgb: rgb)

        self.lock.lock()
        if let cached = self.storage[key] {
            self.lock.unlock()
            return cached
        }
        self.lock.unlock()

        let rendered = Self.render(assetName: assetName, rgb: rgb)

        self.lock.lock()
        self.storage[key] = rendered
        self.lock.unlock()
        return rendered
    }


    private static func cacheKey(assetName: String, rgb: SetiIconMap.RGB) -> String {

        "\(assetName)|\(rgb.r)|\(rgb.g)|\(rgb.b)"
    }


    /// Draws the named asset into a new `NSImage`, recolored with the given sRGB triple.
    ///
    /// The NSImage block-based initializer re-runs the closure per drawing context,
    /// so the result scales cleanly on Retina without manual 2× rep management.
    private static func render(assetName: String, rgb: SetiIconMap.RGB) -> NSImage {

        let size = SetiIconProvider.iconSize
        let color = NSColor(srgbRed: rgb.r, green: rgb.g, blue: rgb.b, alpha: 1)
        let source = NSImage(named: "Seti/\(assetName)")
            ?? NSImage(named: "Seti/\(SetiIconMap.defaultFile)")
            ?? NSImage(size: size)

        return NSImage(size: size, flipped: false) { rect in
            // Draw the template mask, then replace painted pixels with the tint color.
            source.draw(in: rect, from: .zero, operation: .sourceOver, fraction: 1.0)
            color.set()
            rect.fill(using: .sourceIn)
            return true
        }
    }
}
