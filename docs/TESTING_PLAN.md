# Testing plan — iPhone Pro Max (no Pi)

## Capture

1. Walk a 20 m stretch with the **rear LiDAR** aimed at pavement (3D Scanner / Polycam / ARKit).
2. Keep the phone steady (gyro pose quality should stay high).
3. Export **PLY**. Have a second person scan the same GPS cluster.
4. Confirm `data/scenes/<id>/merged.ply` grew and `contributors == 2`.

## LA classes

Walk: wheel-path alligator, utility trench pothole, 110-style rut, ficus root uplift if you can do sidewalk. Notes field should mention heat / trench / rut so the LLM prior can remap generic `crack`.

## Demo for judges

1. `python run.py demo` — LA-weighted queue.
2. Two PLY drops of the same spot — depth/coverage improves.
3. Offline still works for the JSON outbox; LiDAR files live in `scene.ipulse.json`.

Stop claiming structural capacity. Screening + merged geometry only.
