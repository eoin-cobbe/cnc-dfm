import Foundation

struct BackendProcessService {
    let installation: BackendInstallation
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init() {
        do {
            installation = try BackendLocator.locate()
        } catch {
            fatalError((error as? LocalizedError)?.errorDescription ?? error.localizedDescription)
        }

        let decoder = JSONDecoder()
        self.decoder = decoder

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        self.encoder = encoder
    }

    func fetchHealth() async throws -> HealthResponse {
        try await run(["health"], decode: HealthResponse.self)
    }

    func fetchConfig() async throws -> ConfigResponse {
        try await run(["config", "show"], decode: ConfigResponse.self)
    }

    func fetchMaterials() async throws -> MaterialsResponse {
        try await run(["materials"], decode: MaterialsResponse.self)
    }

    func saveConfig(_ config: ConfigValues) async throws -> ConfigResponse {
        let payload = try encoder.encode(config)
        return try await run(["config", "save", "--json-input", "-"], stdin: payload, decode: ConfigResponse.self)
    }

    func analyze(fileURL: URL, qty: Int) async throws -> AnalysisResponse {
        try await run(
            ["analyze", "--input", fileURL.path, "--qty", String(qty)],
            decode: AnalysisResponse.self
        )
    }

    private func run<T: Decodable>(_ arguments: [String], stdin: Data? = nil, decode type: T.Type) async throws -> T {
        let output = try await runRaw(arguments, stdin: stdin)
        if output.exitCode != 0 {
            if let apiError = try? decoder.decode(APIErrorEnvelope.self, from: output.stdout) {
                throw BackendProcessError.api(apiError.error)
            }
            let stderrText = String(decoding: output.stderr, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
            throw BackendProcessError.nonZeroExit(output.exitCode, stderrText.isEmpty ? "Backend command failed." : stderrText)
        }

        if let apiError = try? decoder.decode(APIErrorEnvelope.self, from: output.stdout) {
            throw BackendProcessError.api(apiError.error)
        }

        do {
            return try decoder.decode(T.self, from: output.stdout)
        } catch {
            let body = String(decoding: output.stdout, as: UTF8.self)
            throw BackendProcessError.decodeFailed(Self.describeDecodingError(error), body)
        }
    }

    private func runRaw(_ arguments: [String], stdin: Data?) async throws -> ProcessOutput {
        try await withCheckedThrowingContinuation { continuation in
            let process = Process()
            process.currentDirectoryURL = installation.repoRoot
            process.executableURL = installation.executableURL
            process.arguments = installation.launchPrefix + arguments

            let stdoutPipe = Pipe()
            let stderrPipe = Pipe()
            process.standardOutput = stdoutPipe
            process.standardError = stderrPipe

            let stdinPipe = Pipe()
            if stdin != nil {
                process.standardInput = stdinPipe
            }

            process.terminationHandler = { process in
                let stdout = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
                let stderr = stderrPipe.fileHandleForReading.readDataToEndOfFile()
                continuation.resume(
                    returning: ProcessOutput(
                        exitCode: process.terminationStatus,
                        stdout: stdout,
                        stderr: stderr
                    )
                )
            }

            do {
                try process.run()
                if let stdin {
                    stdinPipe.fileHandleForWriting.write(stdin)
                    try? stdinPipe.fileHandleForWriting.close()
                }
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }
}

struct ProcessOutput {
    let exitCode: Int32
    let stdout: Data
    let stderr: Data
}

enum BackendProcessError: LocalizedError {
    case api(APIErrorPayload)
    case nonZeroExit(Int32, String)
    case decodeFailed(String, String)

    var errorDescription: String? {
        switch self {
        case .api(let payload):
            return "\(payload.type): \(payload.message)"
        case .nonZeroExit(let code, let message):
            return "Backend exited with status \(code): \(message)"
        case .decodeFailed(let detail, let body):
            return "Failed to decode backend JSON response (\(detail)): \(body)"
        }
    }
}

private extension BackendProcessService {
    static func describeDecodingError(_ error: Error) -> String {
        switch error {
        case let DecodingError.keyNotFound(key, context):
            return "missing key '\(key.stringValue)' at \(codingPath(context.codingPath))"
        case let DecodingError.typeMismatch(type, context):
            return "type mismatch for \(type) at \(codingPath(context.codingPath)): \(context.debugDescription)"
        case let DecodingError.valueNotFound(type, context):
            return "missing value for \(type) at \(codingPath(context.codingPath)): \(context.debugDescription)"
        case let DecodingError.dataCorrupted(context):
            return "data corrupted at \(codingPath(context.codingPath)): \(context.debugDescription)"
        default:
            return error.localizedDescription
        }
    }

    static func codingPath(_ path: [CodingKey]) -> String {
        if path.isEmpty {
            return "<root>"
        }
        return path.map(\.stringValue).joined(separator: ".")
    }
}
