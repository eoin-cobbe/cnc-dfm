import Foundation

struct BackendInstallation {
    let repoRoot: URL
    let apiScript: URL
    let executableURL: URL
    let launchPrefix: [String]
    let launchDescription: String
}

enum BackendLocator {
    static func locate() throws -> BackendInstallation {
        let backendRoot = try locateBackendRoot()
        let apiScript = backendRoot.appendingPathComponent("src/dfm_app_api.py")

        if let explicitPython = ProcessInfo.processInfo.environment["CNC_DFM_PYTHON"], !explicitPython.isEmpty {
            let executableURL = URL(fileURLWithPath: explicitPython)
            return BackendInstallation(
                repoRoot: backendRoot,
                apiScript: apiScript,
                executableURL: executableURL,
                launchPrefix: [apiScript.path],
                launchDescription: "\(explicitPython) \(apiScript.path)"
            )
        }

        let bundledPython = backendRoot.appendingPathComponent(".conda-env/bin/python")
        if FileManager.default.isExecutableFile(atPath: bundledPython.path) {
            return BackendInstallation(
                repoRoot: backendRoot,
                apiScript: apiScript,
                executableURL: bundledPython,
                launchPrefix: [apiScript.path],
                launchDescription: "\(bundledPython.path) \(apiScript.path)"
            )
        }

        let envExecutable = URL(fileURLWithPath: "/usr/bin/env")
        return BackendInstallation(
            repoRoot: backendRoot,
            apiScript: apiScript,
            executableURL: envExecutable,
            launchPrefix: ["python3", apiScript.path],
            launchDescription: "/usr/bin/env python3 \(apiScript.path)"
        )
    }

    private static func locateBackendRoot() throws -> URL {
        let fileManager = FileManager.default
        if let explicitRoot = ProcessInfo.processInfo.environment["CNC_DFM_REPO_ROOT"], !explicitRoot.isEmpty {
            let candidate = URL(fileURLWithPath: explicitRoot).standardizedFileURL
            if fileManager.fileExists(atPath: candidate.appendingPathComponent("src/dfm_app_api.py").path) {
                return candidate
            }
            throw BackendLocatorError.invalidExplicitRoot(candidate.path)
        }

        if let bundledRoot = bundledBackendRoot() {
            return bundledRoot
        }

        let compileTimeSourceURL = URL(fileURLWithPath: #filePath)
        if let repoRoot = ascendToRepoRoot(startingAt: compileTimeSourceURL.deletingLastPathComponent()) {
            return repoRoot
        }

        let cwdURL = URL(fileURLWithPath: fileManager.currentDirectoryPath)
        if let repoRoot = ascendToRepoRoot(startingAt: cwdURL) {
            return repoRoot
        }

        throw BackendLocatorError.repoRootNotFound
    }

    private static func bundledBackendRoot() -> URL? {
        guard let resourcesURL = Bundle.main.resourceURL else {
            return nil
        }

        let markerURL = resourcesURL.appendingPathComponent("backend-root.txt")
        if let rawPath = try? String(contentsOf: markerURL, encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines),
           !rawPath.isEmpty {
            let candidate = URL(fileURLWithPath: rawPath).standardizedFileURL
            if FileManager.default.fileExists(atPath: candidate.appendingPathComponent("src/dfm_app_api.py").path) {
                return candidate
            }
        }

        let bundledBackend = resourcesURL.appendingPathComponent("backend")
        if FileManager.default.fileExists(atPath: bundledBackend.appendingPathComponent("src/dfm_app_api.py").path) {
            return bundledBackend
        }

        return nil
    }

    private static func ascendToRepoRoot(startingAt startURL: URL) -> URL? {
        var candidate = startURL.standardizedFileURL
        while candidate.path != "/" {
            let apiScript = candidate.appendingPathComponent("src/dfm_app_api.py")
            if FileManager.default.fileExists(atPath: apiScript.path) {
                return candidate
            }
            candidate.deleteLastPathComponent()
        }
        return nil
    }
}

enum BackendLocatorError: LocalizedError {
    case invalidExplicitRoot(String)
    case repoRootNotFound

    var errorDescription: String? {
        switch self {
        case .invalidExplicitRoot(let path):
            return "CNC_DFM_REPO_ROOT does not contain src/dfm_app_api.py: \(path)"
        case .repoRootNotFound:
            return "Could not locate the cnc-dfm repo root for the backend."
        }
    }
}
