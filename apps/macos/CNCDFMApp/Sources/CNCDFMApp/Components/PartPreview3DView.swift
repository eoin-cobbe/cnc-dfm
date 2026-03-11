import SceneKit
import SwiftUI

struct PartPreview3DView: View {
    let fileURL: URL

    @State private var scene: SCNScene?
    @State private var loadError: String?

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(AppTheme.panelBackground)

            if let scene {
                SceneView(
                    scene: scene,
                    pointOfView: nil,
                    options: [.allowsCameraControl, .autoenablesDefaultLighting, .temporalAntialiasingEnabled]
                )
                .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            } else if let loadError {
                ContentUnavailableView(
                    "Preview Unavailable",
                    systemImage: "cube.transparent",
                    description: Text(loadError)
                )
            } else {
                ProgressView("Loading 3D preview…")
            }
        }
        .frame(maxWidth: .infinity)
        .aspectRatio(16.0 / 9.0, contentMode: .fit)
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(AppTheme.panelBorder, lineWidth: 1)
        )
        .task(id: fileURL) {
            loadPreviewScene()
        }
    }

    private func loadPreviewScene() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            loadError = "Preview mesh file was not found at \(fileURL.path)."
            scene = nil
            return
        }

        do {
            let scene = try STLSceneBuilder.buildScene(from: fileURL)
            configureScene(scene)
            self.scene = scene
            self.loadError = nil
        } catch {
            loadError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            scene = nil
        }
    }

    private func configureScene(_ scene: SCNScene) {
        let bounds = scene.rootNode.boundingBox
        let center = SCNVector3(
            (bounds.min.x + bounds.max.x) * 0.5,
            (bounds.min.y + bounds.max.y) * 0.5,
            (bounds.min.z + bounds.max.z) * 0.5
        )
        let size = SCNVector3(
            max(bounds.max.x - bounds.min.x, 0.001),
            max(bounds.max.y - bounds.min.y, 0.001),
            max(bounds.max.z - bounds.min.z, 0.001)
        )
        let maxDimension = max(size.x, max(size.y, size.z))

        let cameraNode = SCNNode()
        let camera = SCNCamera()
        camera.usesOrthographicProjection = false
        camera.fieldOfView = 32
        camera.zNear = 0.001
        camera.zFar = Double(maxDimension * 100.0)
        cameraNode.camera = camera
        cameraNode.position = SCNVector3(
            center.x + maxDimension * 1.45,
            center.y + maxDimension * 1.05,
            center.z + maxDimension * 1.8
        )
        cameraNode.look(at: center)
        scene.rootNode.addChildNode(cameraNode)

        let keyLightNode = SCNNode()
        let keyLight = SCNLight()
        keyLight.type = .directional
        keyLight.intensity = 1_200
        keyLightNode.light = keyLight
        keyLightNode.eulerAngles = SCNVector3(-0.8, 0.9, 0.0)
        scene.rootNode.addChildNode(keyLightNode)

        let ambientLightNode = SCNNode()
        let ambientLight = SCNLight()
        ambientLight.type = .ambient
        ambientLight.intensity = 250
        ambientLightNode.light = ambientLight
        scene.rootNode.addChildNode(ambientLightNode)

        scene.background.contents = NSColor.clear
    }
}

private enum STLSceneBuilder {
    static func buildScene(from fileURL: URL) throws -> SCNScene {
        let text = try String(contentsOf: fileURL, encoding: .utf8)
        let mesh = try parseASCIISTL(text)

        let geometry = SCNGeometry(
            sources: [
                SCNGeometrySource(vertices: mesh.vertices),
                SCNGeometrySource(normals: mesh.normals),
            ],
            elements: [
                SCNGeometryElement(
                    data: mesh.indicesData,
                    primitiveType: .triangles,
                    primitiveCount: mesh.vertices.count / 3,
                    bytesPerIndex: MemoryLayout<UInt32>.size
                ),
            ]
        )
        let material = SCNMaterial()
        material.diffuse.contents = NSColor.windowBackgroundColor.blended(withFraction: 0.12, of: .white)
        material.metalness.contents = 0.05
        material.roughness.contents = 0.35
        geometry.materials = [material]

        let node = SCNNode(geometry: geometry)
        let scene = SCNScene()
        scene.rootNode.addChildNode(node)
        return scene
    }

    static func parseASCIISTL(_ text: String) throws -> TriangleMesh {
        var vertices: [SCNVector3] = []
        var normals: [SCNVector3] = []
        var currentNormal = SCNVector3(0, 0, 1)

        for rawLine in text.components(separatedBy: .newlines) {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !line.isEmpty else {
                continue
            }

            if line.hasPrefix("facet normal") {
                currentNormal = try parseVector(from: line, prefix: "facet normal")
                continue
            }

            if line.hasPrefix("vertex") {
                vertices.append(try parseVector(from: line, prefix: "vertex"))
                normals.append(currentNormal)
            }
        }

        guard !vertices.isEmpty, vertices.count.isMultiple(of: 3) else {
            throw STLSceneError.invalidMesh
        }

        let indices = (0..<vertices.count).map { UInt32($0) }
        return TriangleMesh(
            vertices: vertices,
            normals: normals,
            indicesData: indices.withUnsafeBufferPointer { Data(buffer: $0) }
        )
    }

    static func parseVector(from line: String, prefix: String) throws -> SCNVector3 {
        let parts = line
            .replacingOccurrences(of: prefix, with: "")
            .split(whereSeparator: \.isWhitespace)

        guard parts.count == 3,
              let x = Float(parts[0]),
              let y = Float(parts[1]),
              let z = Float(parts[2]) else {
            throw STLSceneError.invalidVector(line)
        }
        return SCNVector3(x, y, z)
    }
}

private struct TriangleMesh {
    let vertices: [SCNVector3]
    let normals: [SCNVector3]
    let indicesData: Data
}

private enum STLSceneError: LocalizedError {
    case invalidMesh
    case invalidVector(String)

    var errorDescription: String? {
        switch self {
        case .invalidMesh:
            return "Generated STL preview did not contain complete triangle data."
        case .invalidVector(let line):
            return "Could not parse STL vector line: \(line)"
        }
    }
}
