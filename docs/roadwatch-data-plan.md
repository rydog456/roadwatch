# Roadwatch: competition MVP and data plan

This plan distills the supplied concept notes and lean canvas into a road-focused first product. Roadwatch remains the working name of the app; the canvas's broader GroundSignal concept (bridges, utilities, and other assets) is a later expansion, not a claim about the current prototype.

## The three-day demonstration

Use a vehicle that is already driving a route. Capture a forward/downward road image, vehicle motion and GPS with aligned timestamps. A specialized vision detector can propose a visible defect; a calibrated IMU can corroborate an impact. Send a geolocated observation to a review queue, explain the supporting evidence, and recommend the cheapest appropriate next inspection. Repeat passes can *eventually* establish whether a defect is recurring, worsening, or no longer visible after a documented repair.

The current app has **one illustrative detection** and **live NWS/USGS environmental context for selectable demo cities**. It does not ingest device data, train/run YOLO11, draw a Google severity map, track real assets, create work orders, assign crews, or measure deterioration. Do not present any of those as live capabilities.

### Detection to action

1. **Sense:** camera + GPS + IMU are the low-cost MVP. A phone or Raspberry Pi can capture data; heavy vision inference can run off-device. LiDAR/depth and thermal are optional inputs when available.
2. **Identify:** a purpose-trained computer-vision model (YOLO11 is a candidate, not an LLM) returns defect class, confidence, model version and an image reference. It needs suitable model weights and representative labeled road images before it can run or be evaluated.
3. **Corroborate:** align the camera frame, IMU window, GPS fix and optional depth/thermal samples by capture time. Keep independent measurements separate; no single model score is a structural-safety probability.
4. **Prioritize for inspection:** a transparent, provisional rule can flag strong corroborated signals for early human review. Missing or conflicting evidence means **uncertain / request review or another pass**, not “healthy.” Weather alerts and earthquakes are location/time context; they do not independently prove a defect or upgrade a sensor confidence value.
5. **Act and learn (later):** a human approves inspection or maintenance. Save the reviewer decision, work-order status and subsequent observation before claiming dispatch, repair verification or worsening trend. Bridges and suspected subsurface issues require targeted engineering/NDT inspection, not a drive-by safety diagnosis.

## Proposed input contract — **not yet an implemented API**

The device's real payload and transport have not been provided. Confirm these field names and units against its firmware before creating an ingestion endpoint or database schema.

| Input | Minimum field(s) | Why |
| --- | --- | --- |
| Identity/provenance | `eventId`, pseudonymous `deviceId`, `sourceType`, schema version | Deduplicate events and trace the producing device without presenting a demo as live. |
| Capture time | UTC `capturedAt` (ISO 8601), clock quality/sync method | Join modalities and distinguish a new observation from an old one. |
| Location | `latitude`, `longitude`, `accuracyMeters`; ideally heading, speed, GPS fix timestamp | Locate a defect without claiming lane- or segment-level accuracy that GPS cannot support. |
| Vision | image/video reference, defect label, confidence from 0–1, model name/version; ideally detection box or mask | Let an inspector review evidence and assess the detector's errors. Start with pothole, crack and other surface distress. |
| Motion | timestamped IMU window (accelerometer axes in m/s², optional gyroscope in rad/s), sample rate, mounting orientation, calibration/baseline; optionally computed impact in standard deviations | Distinguish a localized road impact from braking, a speed bump or vehicle-specific suspension behavior. |
| Optional geometry | depth/rut estimate in millimetres, sensor type, calibration/measurement quality and matching timestamp | Quantify surface shape; do not infer underground capacity from depth alone. |
| Optional thermal | surface temperature or local delta in °C, reference area, timestamp and quality | An anomaly is supporting context, not a diagnosis of hidden damage. |
| Asset and operations | road segment / lane if known, road name, fleet route, responsible agency, traffic/critical-route data if supplied | Group repeat observations and rank limited inspection resources responsibly. |

Raw images, IMU windows and large point clouds should be kept as referenced evidence with access controls, not stuffed into every event JSON. Minimize incidental people/license-plate imagery and define retention before fleet collection. A vision-only event can be stored but must remain uncorroborated; only verified data should contribute to a condition trend.

### Derived records needed after first ingest

- **Observation:** immutable raw evidence references, device/capture provenance, uncertainty/quality, chosen road location, detector output and reviewer annotation.
- **Road segment history:** segment identifier, time-ordered passes from independent drives, same-defect matching, baseline, change since baseline and number of corroborating passes. Trend is **not available** from one observation.
- **Inspection case:** provisional priority, rule/model version and explanation, recommended inspection type, human approval/status, assignee only when actually assigned, work-order link only when created, before/after evidence and explicit verification outcome.
- **Environmental snapshot:** provider, source URL, source status/error and retrieved time, joined to an observation by *its* coordinates and capture time; do not attach the dashboard's selected demo-city context to a device event.

## What to measure in a pilot

Evaluate detection precision/recall by defect type, false positives per mile, geolocation error, multi-sensor confirmation, time from capture to reviewer action, unique miles/segments covered, repeat-pass rate, and whether prioritized cases actually help crews. Treat pricing in the lean canvas as hypotheses, not market facts.

## Inputs still needed from the team

1. One real or sanitized device event plus a short raw sample from each sensor: exact names, units, sampling rates, timestamps, file formats and transport (upload/API/Bluetooth/Wi-Fi).
2. Which hardware will actually be on the demo vehicle: phone model, camera, GPS, IMU, and whether calibrated depth/LiDAR or thermal readings exist.
3. Vision model weights or labeled example images if YOLO11 inference is desired; a model name alone cannot produce detections.
4. Whether road-segment GIS, traffic/critical-route layers, historical inspections or repair records are available. Without them, recurrence, deterioration and resource optimization remain unverified future work.
5. The Google Maps SDK for iOS key through the secure secrets flow for the planned severity map. Do not paste it into code or documentation.

The first working end-to-end milestone after these inputs is **one real capture → validated observation → explainable inspection recommendation at its real position**. Add history and human-approved work orders only after that path works.