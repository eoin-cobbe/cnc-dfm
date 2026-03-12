import AppKit
import SceneKit
import SwiftUI

struct PartPreview3DView: View {
    let fileURL: URL
    let highlightedInsights: [FeatureInsightPayload]
    let focusedInsightID: String?

    @State private var scene: SCNScene?
    @State private var loadError: String?

    private var highlightSignature: String {
        let ids = highlightedInsights.map(\.id).joined(separator: ",")
        return "\(ids)|\(focusedInsightID ?? "")"
    }

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(AppTheme.panelBackground)

            if let scene {
                PartPreviewSceneView(
                    scene: scene,
                    pointOfView: scene.rootNode.childNode(withName: SceneNames.camera, recursively: false),
                    focusTarget: currentFocusTarget(scene: scene)
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
        .aspectRatio(1.0, contentMode: .fit)
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(AppTheme.panelBorder, lineWidth: 1)
        )
        .task(id: fileURL) {
            loadPreviewScene()
        }
        .onChange(of: highlightSignature) { _, _ in
            applyHighlightState(animated: true)
        }
    }

    private func loadPreviewScene() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            loadError = "Preview mesh file was not found at \(fileURL.path)."
            scene = nil
            return
        }

        do {
            let loadedScene = try STLSceneBuilder.buildScene(from: fileURL)
            configureScene(loadedScene)
            scene = loadedScene
            loadError = nil
            applyHighlightState(animated: false)
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
        cameraNode.name = SceneNames.camera
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

        let highlightRoot = SCNNode()
        highlightRoot.name = SceneNames.highlightRoot
        scene.rootNode.addChildNode(highlightRoot)

        scene.background.contents = NSColor.clear
    }

    private func applyHighlightState(animated: Bool) {
        guard let scene else {
            return
        }
        guard let meshNode = scene.rootNode.childNode(withName: SceneNames.mesh, recursively: false) else {
            return
        }
        let highlightRoot = scene.rootNode.childNode(withName: SceneNames.highlightRoot, recursively: false) ?? {
            let node = SCNNode()
            node.name = SceneNames.highlightRoot
            scene.rootNode.addChildNode(node)
            return node
        }()

        highlightRoot.childNodes.forEach { $0.removeFromParentNode() }

        for insight in highlightedInsights {
            let isFocused = insight.id == focusedInsightID
            if let highlightNode = makeHighlightNode(for: insight, focused: isFocused) {
                highlightRoot.addChildNode(highlightNode)
            }
        }

        guard let cameraNode = scene.rootNode.childNode(withName: SceneNames.camera, recursively: false) else {
            return
        }
        let focusInsight = highlightedInsights.first(where: { $0.id == focusedInsightID }) ?? highlightedInsights.first
        if let focusInsight {
            focusCamera(on: focusInsight, meshNode: meshNode, cameraNode: cameraNode, animated: animated)
        }
    }

    private func makeHighlightNode(for insight: FeatureInsightPayload, focused: Bool) -> SCNNode? {
        let color = focused
            ? NSColor(calibratedRed: 0.07, green: 0.28, blue: 0.72, alpha: 1.0)
            : NSColor(calibratedRed: 0.42, green: 0.76, blue: 1.0, alpha: 1.0)
        let node = SCNNode()
        node.name = "highlight-\(insight.id)"

        for meshPath in insight.overlayMeshPaths {
            let meshURL = URL(fileURLWithPath: meshPath)
            if let overlayNode = try? STLSceneBuilder.buildOverlayNode(
                from: meshURL,
                color: color,
                normalOffset: focused ? 0.12 : 0.08,
                alpha: focused ? 0.82 : 0.56
            ) {
                node.addChildNode(overlayNode)
            }
        }

        if let start = insight.segmentStart?.scnVector, let end = insight.segmentEnd?.scnVector {
            let edgeNode = lineNode(
                from: start,
                to: end,
                color: color,
                radius: focused ? 0.72 : 0.48,
                emissionStrength: focused ? 0.95 : 0.55
            )
            node.addChildNode(edgeNode)
        }

        return node.childNodes.isEmpty ? nil : node
    }

    private func lineNode(
        from start: SCNVector3,
        to end: SCNVector3,
        color: NSColor,
        radius: CGFloat,
        emissionStrength: CGFloat
    ) -> SCNNode {
        let vector = end - start
        let length = CGFloat(vector.length)
        let cylinder = SCNCylinder(radius: radius, height: max(length, 0.001))
        cylinder.radialSegmentCount = 10
        cylinder.firstMaterial?.diffuse.contents = color
        cylinder.firstMaterial?.emission.contents = color.withAlphaComponent(emissionStrength)
        cylinder.firstMaterial?.lightingModel = .constant

        let node = SCNNode(geometry: cylinder)
        node.position = (start + end) * 0.5
        node.look(at: end, up: sceneUp, localFront: SCNVector3(0, 1, 0))
        return node
    }

    private func focusCamera(on insight: FeatureInsightPayload, meshNode: SCNNode, cameraNode: SCNNode, animated: Bool) {
        let target = focusTarget(for: insight, fallback: meshNode.boundingSphere.center)

        let radius = CGFloat(max(meshNode.boundingSphere.radius, 1.0))
        let nextPosition = SCNVector3(
            target.x + radius * 1.35,
            target.y + radius * 0.95,
            target.z + radius * 1.6
        )

        let update = {
            cameraNode.position = nextPosition
            cameraNode.look(at: target)
        }

        if animated {
            SCNTransaction.begin()
            SCNTransaction.animationDuration = 0.35
            update()
            SCNTransaction.commit()
        } else {
            update()
        }
    }

    private func currentFocusTarget(scene: SCNScene) -> SCNVector3 {
        guard let meshNode = scene.rootNode.childNode(withName: SceneNames.mesh, recursively: false) else {
            return SCNVector3Zero
        }
        let focusInsight = highlightedInsights.first(where: { $0.id == focusedInsightID }) ?? highlightedInsights.first
        if let focusInsight {
            return focusTarget(for: focusInsight, fallback: meshNode.boundingSphere.center)
        }
        return meshNode.boundingSphere.center
    }

    private func focusTarget(for insight: FeatureInsightPayload, fallback: SCNVector3) -> SCNVector3 {
        if let anchor = insight.anchor?.scnVector {
            return anchor
        }
        if let start = insight.segmentStart?.scnVector,
           let end = insight.segmentEnd?.scnVector {
            return (start + end) * 0.5
        }
        return fallback
    }
}

private struct PartPreviewSceneView: NSViewRepresentable {
    let scene: SCNScene
    let pointOfView: SCNNode?
    let focusTarget: SCNVector3

    func makeNSView(context: Context) -> DefaultSceneView {
        let view = DefaultSceneView()
        view.scene = scene
        view.pointOfView = pointOfView
        view.allowsCameraControl = true
        view.autoenablesDefaultLighting = true
        view.antialiasingMode = .multisampling4X
        view.backgroundColor = .clear
        view.focusTarget = focusTarget
        return view
    }

    func updateNSView(_ nsView: DefaultSceneView, context: Context) {
        nsView.scene = scene
        nsView.pointOfView = pointOfView
        nsView.focusTarget = focusTarget
    }
}

private final class DefaultSceneView: SCNView {
    var focusTarget = SCNVector3Zero

    override func magnify(with event: NSEvent) {
        guard let cameraNode = pointOfView else {
            super.magnify(with: event)
            return
        }
        applyPinchZoom(delta: event.magnification, cameraNode: cameraNode)
    }

    private func applyPinchZoom(delta: CGFloat, cameraNode: SCNNode) {
        let offset = cameraNode.position - focusTarget
        let distance = max(offset.length, 0.001)
        let direction = offset.normalized
        let scale = max(0.2, 1.0 - (delta * 0.9))
        let nextDistance = max(1.0, distance * scale)
        cameraNode.position = focusTarget + (direction * nextDistance)
    }
}

private enum SceneNames {
    static let mesh = "part-mesh"
    static let creaseLines = "part-crease-lines"
    static let camera = "preview-camera"
    static let highlightRoot = "highlight-root"
}

private let sceneUp = SCNVector3(0, 0, 1)

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
        material.diffuse.contents = NSColor(calibratedRed: 0.93, green: 0.95, blue: 0.98, alpha: 1.0)
        material.metalness.contents = 0.0
        material.roughness.contents = 0.62
        material.specular.contents = NSColor(calibratedWhite: 0.25, alpha: 1.0)
        geometry.materials = [material]

        let node = SCNNode(geometry: geometry)
        node.name = SceneNames.mesh
        let scene = SCNScene()
        scene.rootNode.addChildNode(node)
        let creaseNode = buildCreaseOverlayNode(from: mesh)
        creaseNode.name = SceneNames.creaseLines
        scene.rootNode.addChildNode(creaseNode)
        return scene
    }

    static func buildOverlayNode(
        from fileURL: URL,
        color: NSColor,
        normalOffset: Float,
        alpha: CGFloat
    ) throws -> SCNNode {
        let text = try String(contentsOf: fileURL, encoding: .utf8)
        let mesh = try parseASCIISTL(text)
        return buildOverlayNode(from: mesh, color: color, normalOffset: normalOffset, alpha: alpha)
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
            indicesData: indices.withUnsafeBufferPointer { Data(buffer: $0) },
            creaseEdges: buildCreaseEdges(vertices: vertices, normals: normals)
        )
    }

    static func buildCreaseOverlayNode(from mesh: TriangleMesh) -> SCNNode {
        let root = SCNNode()
        for (start, end) in mesh.creaseEdges {
            let vector = end - start
            let length = CGFloat(vector.length)
            guard length > 0.001 else {
                continue
            }

            let cylinder = SCNCylinder(radius: 0.085, height: length)
            cylinder.radialSegmentCount = 6
            cylinder.firstMaterial?.diffuse.contents = NSColor(calibratedWhite: 0.06, alpha: 0.96)
            cylinder.firstMaterial?.emission.contents = NSColor(calibratedWhite: 0.04, alpha: 0.16)
            cylinder.firstMaterial?.lightingModel = .constant

            let node = SCNNode(geometry: cylinder)
            node.position = (start + end) * 0.5
            node.look(at: end, up: sceneUp, localFront: SCNVector3(0, 1, 0))
            root.addChildNode(node)
        }
        return root
    }

    static func buildOverlayNode(
        from mesh: TriangleMesh,
        color: NSColor,
        normalOffset: Float,
        alpha: CGFloat
    ) -> SCNNode {
        let root = SCNNode()
        root.addChildNode(
            overlaySurfaceNode(
                mesh: mesh,
                color: color,
                alpha: alpha,
                normalOffset: normalOffset
            )
        )
        root.addChildNode(
            overlaySurfaceNode(
                mesh: mesh,
                color: color,
                alpha: alpha,
                normalOffset: -normalOffset
            )
        )
        return root
    }

    static func overlaySurfaceNode(
        mesh: TriangleMesh,
        color: NSColor,
        alpha: CGFloat,
        normalOffset: Float
    ) -> SCNNode {
        let liftedVertices = zip(mesh.vertices, mesh.normals).map { vertex, normal in
            vertex + (normal.normalized * CGFloat(normalOffset))
        }
        let geometry = SCNGeometry(
            sources: [
                SCNGeometrySource(vertices: liftedVertices),
                SCNGeometrySource(normals: mesh.normals),
            ],
            elements: [
                SCNGeometryElement(
                    data: mesh.indicesData,
                    primitiveType: .triangles,
                    primitiveCount: liftedVertices.count / 3,
                    bytesPerIndex: MemoryLayout<UInt32>.size
                ),
            ]
        )

        let material = SCNMaterial()
        material.diffuse.contents = color.withAlphaComponent(alpha)
        material.emission.contents = color.withAlphaComponent(alpha * 0.45)
        material.specular.contents = NSColor.clear
        material.lightingModel = .constant
        material.isDoubleSided = true
        material.writesToDepthBuffer = false
        if #available(macOS 10.13, *) {
            material.readsFromDepthBuffer = true
        }
        geometry.materials = [material]

        return SCNNode(geometry: geometry)
    }

    static func buildCreaseEdges(vertices: [SCNVector3], normals: [SCNVector3]) -> [(SCNVector3, SCNVector3)] {
        guard vertices.count == normals.count, vertices.count.isMultiple(of: 3) else {
            return []
        }

        struct QuantizedPoint: Hashable {
            let x: Int
            let y: Int
            let z: Int
        }

        struct EdgeKey: Hashable {
            let a: Int
            let b: Int
        }

        struct EdgeRecord {
            var normals: [SCNVector3]
            let start: SCNVector3
            let end: SCNVector3
        }

        func quantize(_ point: SCNVector3) -> QuantizedPoint {
            QuantizedPoint(
                x: Int((point.x * 1000.0).rounded()),
                y: Int((point.y * 1000.0).rounded()),
                z: Int((point.z * 1000.0).rounded())
            )
        }

        var pointIndexByKey: [QuantizedPoint: Int] = [:]
        var uniquePoints: [SCNVector3] = []
        var edges: [EdgeKey: EdgeRecord] = [:]

        func pointIndex(for point: SCNVector3) -> Int {
            let key = quantize(point)
            if let existing = pointIndexByKey[key] {
                return existing
            }
            let index = uniquePoints.count
            uniquePoints.append(point)
            pointIndexByKey[key] = index
            return index
        }

        let creaseDotThreshold: CGFloat = 0.985

        for triangleStart in stride(from: 0, to: vertices.count, by: 3) {
            let triangleVertices = Array(vertices[triangleStart..<(triangleStart + 3)])
            let triangleNormal = normals[triangleStart].normalized
            let pointIndices = triangleVertices.map(pointIndex(for:))
            let edgePairs = [(0, 1), (1, 2), (2, 0)]

            for (lhs, rhs) in edgePairs {
                let a = pointIndices[lhs]
                let b = pointIndices[rhs]
                let key = EdgeKey(a: min(a, b), b: max(a, b))
                if var existing = edges[key] {
                    existing.normals.append(triangleNormal)
                    edges[key] = existing
                } else {
                    edges[key] = EdgeRecord(
                        normals: [triangleNormal],
                        start: triangleVertices[lhs],
                        end: triangleVertices[rhs]
                    )
                }
            }
        }

        return edges.values.compactMap { record in
            if record.normals.count <= 1 {
                return (record.start, record.end)
            }
            let baseNormal = record.normals[0]
            let hasCrease = record.normals.dropFirst().contains { normal in
                abs(baseNormal.dot(normal)) < creaseDotThreshold
            }
            return hasCrease ? (record.start, record.end) : nil
        }
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
    let creaseEdges: [(SCNVector3, SCNVector3)]
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

private extension Point3Payload {
    var scnVector: SCNVector3 {
        SCNVector3(Float(x), Float(y), Float(z))
    }
}

private extension SCNVector3 {
    static func - (lhs: SCNVector3, rhs: SCNVector3) -> SCNVector3 {
        SCNVector3(lhs.x - rhs.x, lhs.y - rhs.y, lhs.z - rhs.z)
    }

    static func + (lhs: SCNVector3, rhs: SCNVector3) -> SCNVector3 {
        SCNVector3(lhs.x + rhs.x, lhs.y + rhs.y, lhs.z + rhs.z)
    }

    static func * (lhs: SCNVector3, rhs: CGFloat) -> SCNVector3 {
        SCNVector3(lhs.x * rhs, lhs.y * rhs, lhs.z * rhs)
    }

    var length: CGFloat {
        let xx = x * x
        let yy = y * y
        let zz = z * z
        return sqrt(xx + yy + zz)
    }

    var normalized: SCNVector3 {
        let magnitude = max(length, 0.0001)
        return SCNVector3(x / magnitude, y / magnitude, z / magnitude)
    }

    func dot(_ other: SCNVector3) -> CGFloat {
        (x * other.x) + (y * other.y) + (z * other.z)
    }

    func cross(_ other: SCNVector3) -> SCNVector3 {
        SCNVector3(
            (y * other.z) - (z * other.y),
            (z * other.x) - (x * other.z),
            (x * other.y) - (y * other.x)
        )
    }
}
