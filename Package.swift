// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "GoToAnnArbor",
    platforms: [.macOS(.v14), .iOS(.v17)],
    targets: [.executableTarget(name: "GoToAnnArbor", path: "Sources")]
)
