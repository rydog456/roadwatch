import RealityKit
import SwiftUI

struct ARViewContainer: UIViewRepresentable {
    let session: ScanSession

    func makeUIView(context: Context) -> ARView {
        let view = ARView(frame: .zero)
        session.arView = view
        return view
    }

    func updateUIView(_ uiView: ARView, context: Context) {}
}

struct ContentView: View {
    @StateObject private var scan = ScanSession()
    @StateObject private var motion = MotionRecorder()
    @AppStorage("server") private var server = "https://your-repl.replit.dev"
    @AppStorage("who") private var who = "ryan"
    @State private var status = "Aim at the pothole, then press Start."
    @State private var sending = false

    var body: some View {
        VStack(spacing: 0) {
            ZStack(alignment: .top) {
                ARViewContainer(session: scan).ignoresSafeArea(edges: .top)
                Text("\(scan.vertexCount) mesh points · tracking \(scan.tracking)")
                    .font(.footnote)
                    .padding(6)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(.top, 8)
            }
            Form {
                TextField("InfraPulse server", text: $server)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                TextField("Who scanned", text: $who)
                if let loc = motion.location {
                    Text(String(format: "GPS %.6f, %.6f (±%.0f m)", loc.coordinate.latitude, loc.coordinate.longitude, loc.horizontalAccuracy))
                        .font(.footnote)
                } else {
                    Text("Waiting for GPS…").font(.footnote)
                }
                HStack {
                    Button(scan.isScanning ? "Stop" : "Start") { toggle() }
                        .disabled(!ScanSession.isSupported)
                    Spacer()
                    Button(sending ? "Sending…" : "Upload scan") { Task { await upload() } }
                        .disabled(sending || scan.vertexCount < 20 || motion.location == nil)
                }
                Text(ScanSession.isSupported ? status : "This iPhone has no LiDAR. Use Polycam or Scaniverse on a Pro model.")
                    .font(.footnote)
            }
            .frame(height: 300)
        }
    }

    private func toggle() {
        if scan.isScanning {
            scan.stop()
            motion.stop()
            status = "Scan stopped. Upload to price it."
        } else {
            motion.start()
            scan.start()
            status = "Walk slowly around the hole, 0.5–2 m away."
        }
    }

    private func upload() async {
        guard let loc = motion.location else { return }
        if scan.isScanning { toggle() }
        sending = true
        defer { sending = false }
        let payload = ScanUpload(
            contributor_id: who.isEmpty ? "walker" : who,
            lat: loc.coordinate.latitude,
            lon: loc.coordinate.longitude,
            heading_deg: motion.heading.map { $0.trueHeading >= 0 ? $0.trueHeading : $0.magneticHeading } ?? 0,
            mag_heading_deg: motion.heading?.magneticHeading,
            xyz: scan.exportPoints(),
            gyro_xyz: motion.gyro,
            accel_xyz: motion.accel,
            baro_hpa: motion.pressureHpa,
            arkit_tracking: scan.tracking,
            notes: "arkit mesh"
        )
        do {
            let reply = try await Uploader.send(payload, server: server)
            let c = reply.cost
            status = String(format: "%.2f × %.2f ft, %.2f in deep · base $%.0f · LA $%.0f · trust %.0f",
                            c.length_ft, c.width_ft, c.depth_in, c.base_usd, c.adjusted_usd, reply.scan_trust)
        } catch {
            status = error.localizedDescription
        }
    }
}
