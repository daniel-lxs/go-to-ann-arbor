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
    static let feedHosts: Set<String> = ["rt.theride.org", "opensky-network.org", "gbfs.spin.pm", "mdotjboss.state.mi.us"]

    @MainActor static func register() {
        LampNative.on("openRepo") { _ in
            #if os(macOS)
            NSWorkspace.shared.open(repo)
            #else
            await UIApplication.shared.open(repo)
            #endif
            return true
        }
        /// A live public feed the page can't read itself (its server doesn't let a page ask): TheRide's bus positions,
        /// OpenSky's aircraft, Spin's scooters and MDOT's highway work. Only these hosts; the body comes back as base64.
        LampNative.on("feed") { args in
            guard let text = args["url"] as? String, let url = URL(string: text), url.scheme == "https",
                  let host = url.host, feedHosts.contains(host) else { throw LampNative.Failure("not a feed") }
            var request = URLRequest(url: url, timeoutInterval: 20)
            request.setValue("GoToAnnArbor/1.0", forHTTPHeaderField: "User-Agent")
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                throw LampNative.Failure("status \((response as? HTTPURLResponse)?.statusCode ?? 0)")
            }
            return data.base64EncodedString()
        }
        /// Recording mode: a video of the drive, sent from the page a second at a time and written into
        /// Movies/Go To Ann Arbor (the iPhone's or iPad's Files, in the app's folder), then shown in Finder on the Mac
        LampNative.on("videoStart") { args in
            let ext = (args["ext"] as? String) == "webm" ? "webm" : "mp4"
            Recording.handle?.closeFile()
            #if os(macOS)
            let base = FileManager.default.urls(for: .moviesDirectory, in: .userDomainMask)[0]
            #else
            let base = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            #endif
            let folder = base.appendingPathComponent("Go To Ann Arbor", isDirectory: true)
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            let stamp = DateFormatter()
            stamp.dateFormat = "yyyy-MM-dd 'at' h.mm.ss a"
            let url = folder.appendingPathComponent("Ann Arbor \(stamp.string(from: Date())).\(ext)")
            FileManager.default.createFile(atPath: url.path, contents: nil)
            Recording.handle = try FileHandle(forWritingTo: url)
            Recording.url = url
            return url.lastPathComponent
        }
        LampNative.on("videoChunk") { args in
            guard let text = args["data"] as? String, let data = Data(base64Encoded: text), let handle = Recording.handle
            else { throw LampNative.Failure("no recording") }
            try handle.write(contentsOf: data)
            return true
        }
        LampNative.on("videoEnd") { _ in
            guard let url = Recording.url else { throw LampNative.Failure("no recording") }
            try Recording.handle?.close()
            Recording.handle = nil
            Recording.url = nil
            #if os(macOS)
            NSWorkspace.shared.activateFileViewerSelecting([url])
            #endif
            return url.lastPathComponent
        }
        /// How much memory this device has, in gigabytes: the page builds less of the city on one with 16 GB or less
        LampNative.on("memory") { _ in
            Double(ProcessInfo.processInfo.physicalMemory) / 1_073_741_824
        }
    }
}

/// The video being written while the page records
@MainActor enum Recording {
    static var handle: FileHandle?
    static var url: URL?
}
