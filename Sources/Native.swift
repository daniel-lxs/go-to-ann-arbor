import Foundation
#if os(macOS)
import AppKit
#else
import UIKit
#endif

/// What the page asks of this Mac, iPhone or iPad with `LampNative.call(name, args)` in Web/: the person's own things
/// the page can't reach itself (mail, calendar, reminders, contacts, photos, location…), read with Lamp's building
/// blocks in LampSupport.swift. Each call is registered here once, as the app opens.
enum Native {
    /// The one page the badge's GitHub link may open, in the person's browser
    static let repo = URL(string: "https://github.com/mrubens/go-to-ann-arbor")!

    @MainActor static func register() {
        LampNative.on("openRepo") { _ in
            #if os(macOS)
            NSWorkspace.shared.open(repo)
            #else
            await UIApplication.shared.open(repo)
            #endif
            return true
        }
    }
}
