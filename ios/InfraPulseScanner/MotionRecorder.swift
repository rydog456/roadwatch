import CoreLocation
import CoreMotion

/// Gyro, accelerometer, barometer, GPS, and compass while a scan runs.
final class MotionRecorder: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published var location: CLLocation?
    @Published var heading: CLHeading?

    private let motion = CMMotionManager()
    private let altimeter = CMAltimeter()
    private let locations = CLLocationManager()
    private let queue = OperationQueue()
    private let window = 256

    private(set) var gyro: [[Double]] = []
    private(set) var accel: [[Double]] = []
    private(set) var pressureHpa: Double?
    private(set) var pitch = 0.0
    private(set) var roll = 0.0

    override init() {
        super.init()
        locations.delegate = self
        locations.desiredAccuracy = kCLLocationAccuracyBest
        locations.requestWhenInUseAuthorization()
    }

    func start() {
        gyro.removeAll()
        accel.removeAll()
        locations.startUpdatingLocation()
        if CLLocationManager.headingAvailable() { locations.startUpdatingHeading() }

        motion.deviceMotionUpdateInterval = 1.0 / 50.0
        if motion.isDeviceMotionAvailable {
            motion.startDeviceMotionUpdates(using: .xArbitraryZVertical, to: queue) { [weak self] data, _ in
                guard let self, let data else { return }
                let r = data.rotationRate
                let g = data.gravity
                let u = data.userAcceleration
                self.push(&self.gyro, [r.x, r.y, r.z])
                self.push(&self.accel, [g.x + u.x, g.y + u.y, g.z + u.z])
                self.pitch = data.attitude.pitch
                self.roll = data.attitude.roll
            }
        }
        if CMAltimeter.isRelativeAltitudeAvailable() {
            altimeter.startRelativeAltitudeUpdates(to: queue) { [weak self] data, _ in
                guard let data else { return }
                self?.pressureHpa = data.pressure.doubleValue * 10.0
            }
        }
    }

    func stop() {
        motion.stopDeviceMotionUpdates()
        altimeter.stopRelativeAltitudeUpdates()
        locations.stopUpdatingHeading()
    }

    private func push(_ buffer: inout [[Double]], _ sample: [Double]) {
        buffer.append(sample)
        if buffer.count > window { buffer.removeFirst(buffer.count - window) }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        if let last = locations.last { DispatchQueue.main.async { self.location = last } }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateHeading newHeading: CLHeading) {
        DispatchQueue.main.async { self.heading = newHeading }
    }
}
