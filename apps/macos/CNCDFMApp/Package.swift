// swift-tools-version: 6.1
import PackageDescription

let package = Package(
    name: "CNCDFMApp",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(
            name: "CNCDFMApp",
            targets: ["CNCDFMApp"]
        ),
    ],
    targets: [
        .executableTarget(
            name: "CNCDFMApp",
            path: "Sources"
        ),
        .testTarget(
            name: "CNCDFMAppTests",
            dependencies: ["CNCDFMApp"],
            path: "Tests"
        ),
    ]
)
