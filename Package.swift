// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "NewYork3",
    platforms: [.macOS(.v14), .iOS(.v17)],
    targets: [.executableTarget(name: "NewYork3", path: "Sources")]
)
