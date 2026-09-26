import Foundation

struct ScanUpload: Encodable {
    let contributor_id: String
    let lat: Double
    let lon: Double
    let heading_deg: Double
    let mag_heading_deg: Double?
    let xyz: [[Double]]
    let gyro_xyz: [[Double]]
    let accel_xyz: [[Double]]
    let baro_hpa: Double?
    let arkit_tracking: String
    let capture = "arkit"
    let notes: String
}

struct ScanCost: Decodable {
    let length_ft: Double
    let width_ft: Double
    let depth_in: Double
    let base_usd: Double
    let adjusted_usd: Double
    let uplift: Double
    let note: String
}

struct ScanReply: Decodable {
    let cost: ScanCost
    let scan_trust: Double
}

enum Uploader {
    /// POST to the same /api/scene the web page uses.
    static func send(_ payload: ScanUpload, server: String) async throws -> ScanReply {
        let trimmed = server.trimmingCharacters(in: CharacterSet(charactersIn: "/ "))
        guard let url = URL(string: trimmed + "/api/scene") else { throw URLError(.badURL) }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 60
        request.httpBody = try JSONEncoder().encode(payload)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            let detail = String(data: data, encoding: .utf8) ?? "upload failed"
            throw NSError(domain: "InfraPulse", code: 1, userInfo: [NSLocalizedDescriptionKey: detail])
        }
        return try JSONDecoder().decode(ScanReply.self, from: data)
    }
}
