import ARKit
import RealityKit
import simd

/// Collects LiDAR mesh vertices from ARMeshAnchor while the user walks the defect.
final class ScanSession: NSObject, ObservableObject, ARSessionDelegate {
    @Published var vertexCount = 0
    @Published var tracking = "unavailable"
    @Published var isScanning = false

    static var isSupported: Bool {
        ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh)
    }

    private var anchors: [UUID: ARMeshAnchor] = [:]
    private var cameraPosition = SIMD3<Float>(0, 0, 0)
    weak var arView: ARView?

    func start() {
        guard let arView, Self.isSupported else { return }
        let config = ARWorldTrackingConfiguration()
        config.sceneReconstruction = .mesh
        config.worldAlignment = .gravity
        if ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) {
            config.frameSemantics.insert(.sceneDepth)
        }
        anchors.removeAll()
        vertexCount = 0
        arView.debugOptions.insert(.showSceneUnderstanding)
        arView.session.delegate = self
        arView.session.run(config, options: [.resetTracking, .removeExistingAnchors])
        isScanning = true
    }

    func stop() {
        arView?.session.pause()
        isScanning = false
    }

    func session(_ session: ARSession, didAdd anchors: [ARAnchor]) { absorb(anchors) }
    func session(_ session: ARSession, didUpdate anchors: [ARAnchor]) { absorb(anchors) }

    func session(_ session: ARSession, didRemove anchors: [ARAnchor]) {
        for anchor in anchors { self.anchors.removeValue(forKey: anchor.identifier) }
        refreshCount()
    }

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        let t = frame.camera.transform.columns.3
        cameraPosition = SIMD3<Float>(t.x, t.y, t.z)
        let state: String
        switch frame.camera.trackingState {
        case .normal: state = "normal"
        case .limited: state = "limited"
        case .notAvailable: state = "unavailable"
        }
        if state != tracking {
            DispatchQueue.main.async { self.tracking = state }
        }
    }

    private func absorb(_ list: [ARAnchor]) {
        for case let mesh as ARMeshAnchor in list {
            anchors[mesh.identifier] = mesh
        }
        refreshCount()
    }

    private func refreshCount() {
        let total = anchors.values.reduce(0) { $0 + $1.geometry.vertices.count }
        DispatchQueue.main.async { self.vertexCount = total }
    }

    /// World-space mesh vertices in metres, converted from ARKit Y-up to Z-up
    /// (x, -z, y) so the server's 2 cm voxel merge treats the pavement as XY.
    /// Only points within `radius` metres of the camera are kept, then thinned.
    func exportPoints(radius: Float = 4.0, limit: Int = 40_000) -> [[Double]] {
        var out: [SIMD3<Float>] = []
        let center = SIMD2<Float>(cameraPosition.x, cameraPosition.z)
        for anchor in anchors.values {
            let source = anchor.geometry.vertices
            let base = source.buffer.contents()
            for i in 0..<source.count {
                let ptr = base.advanced(by: source.offset + source.stride * i)
                let local = ptr.assumingMemoryBound(to: SIMD3<Float>.self).pointee
                let world = anchor.transform * SIMD4<Float>(local, 1)
                if simd_distance(SIMD2<Float>(world.x, world.z), center) > radius { continue }
                out.append(SIMD3<Float>(world.x, -world.z, world.y))
            }
        }
        if out.count > limit {
            let step = Double(out.count) / Double(limit)
            out = (0..<limit).map { out[Int(Double($0) * step)] }
        }
        return out.map { p in
            [Double(p.x), Double(p.y), Double(p.z)].map { ($0 * 10_000).rounded() / 10_000 }
        }
    }
}
