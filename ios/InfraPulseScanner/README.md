# InfraPulse Scanner (iPhone LiDAR, ARKit)

Safari can't read the LiDAR sensor, so this small native app does. It builds an ARKit
scene mesh, samples motion and GPS, and posts the cloud to the same `/api/scene`
endpoint the web page uses. The server removes outliers, fits the ground plane, prices
the repair (Asphapro base plus LA factors), and drops a pin on the city map.

Needs an iPhone or iPad with LiDAR (iPhone 12 Pro or later Pro/Pro Max), a Mac with
Xcode 15+, and a free Apple ID for on-device signing.

## Build

1. In Xcode: File > New > Project > iOS App. Name it `InfraPulseScanner`, interface
   SwiftUI, language Swift.
2. Delete the generated `ContentView.swift` and app file, then drag the five `.swift`
   files from this folder into the project ("Copy items if needed").
3. Target > Info, add:
   - `Privacy - Camera Usage Description`: "Scans pavement with LiDAR."
   - `Privacy - Location When In Use Usage Description`: "Pins the defect on the city map."
   - `Privacy - Motion Usage Description`: "Records phone steadiness and pressure for scan trust."
   - Only for a laptop server over Wi-Fi (`http://192.168.x.x:8000`):
     `App Transport Security Settings > Allow Local Networking = YES`.
     The Replit HTTPS URL needs nothing extra.
4. Target > Signing & Capabilities: pick your team. Plug in the phone, choose it as the
   run destination, and press Run. On first launch, trust the developer profile under
   Settings > General > VPN & Device Management.

## Use

1. Start the server (`python run.py serve`, or the Replit run button).
2. In the app, set the server field to the Replit URL or `http://<laptop-ip>:8000`.
3. Press Start and walk slowly around the hole, 0.5 to 2 m away, until the mesh covers it.
4. Press Upload scan. The app shows size, base price, LA price, and scan trust. The pin
   appears on the web map after a refresh.

## What gets sent

| Field | Source |
| --- | --- |
| `xyz` | `ARMeshAnchor.geometry.vertices` × `anchor.transform`, metres, within 4 m of the camera, max 40k points, rotated from ARKit Y-up to Z-up |
| `lat`, `lon` | `CLLocationManager` |
| `heading_deg`, `mag_heading_deg` | `CLHeading` true and magnetic heading |
| `gyro_xyz`, `accel_xyz` | `CMMotionManager` device motion at 50 Hz, last 256 samples (rad/s, g) |
| `baro_hpa` | `CMAltimeter` pressure |
| `arkit_tracking` | `ARCamera.trackingState` |
| `capture` | `"arkit"`, so the server keeps the ARKit world frame instead of re-rotating by heading and pitch |
