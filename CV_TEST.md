# Test the camera detector

1. Double-click `start_dashboard.bat` in this project directory, or run `python scripts/serve_dashboard.py --open`.
2. Open **http://127.0.0.1:8765/camera** in Chrome or Edge. The main dashboard also has a **Camera detection** navigation link.
3. Leave **People · test yourself** selected. Press **Start camera**, then allow camera access.
4. Keep your head and upper body visible about 1–2 m from the webcam in good light. Look for a box labeled **person** with a confidence percentage. Move slowly to check that detections update.
5. Press **Stop camera** when done. This stops all webcam tracks. Leaving/hiding the page also stops the camera.

If no box appears, lower minimum confidence from 35% to 20–25%, improve the light, or move farther back. This detector detects people, not just faces. It is not trained to recognize your identity. If the in-app browser blocks camera access, use the same localhost link in Chrome/Edge. If the camera is busy, close other apps using it.

**Test an image instead** accepts a JPEG/PNG and draws the same detections. Choose **People + vehicles** to include bicycle, car, motorcycle, bus and truck. Change confidence/mode to reprocess a selected image.

Frames are sent only to the local Python server, processed in memory, and not saved. There is no audio capture, recording or cloud inference. An image selected for testing stays in the page until another input is selected or the page is closed.

## What is implemented

A pinned, externally pretrained YOLOv10n ONNX detector, local CPU inference, person/vehicle class filters, bounding boxes in original image coordinates, current-frame counts, confidence controls, webcam permission/error handling, image testing and explicit camera stop. No new training was performed on user images. This is not yet a validated traffic tracker, unique-arrival counter, calibrated queue estimator or CCTV-to-QAOA integration.

The model provenance and SHA256 are in `models/cv/manifest.json`. Original model: THU-MIG YOLOv10, https://github.com/THU-MIG/yolov10. ONNX export: https://huggingface.co/onnx-community/YOLOv10, revision `c03e02456387191807059ef0ebe2c56315ddff55`, AGPL-3.0 as declared by the repository. Review its terms when redistributing the model/application.

## Setup on another machine

```powershell
python -m pip install --target .deps -r requirements.txt
python -m pip install --target .deps --no-deps -r requirements-cv.txt
python scripts/download_cv_model.py
python scripts/test_cv.py
python scripts/serve_dashboard.py --open
```

The public Ultralytics bus image is used for a functional smoke test only. It is not your webcam image or a Bengaluru accuracy benchmark. Actual user camera quality remains to be tested by the user. Automated browser media tests use a fake camera backed by that public test image and never open the real webcam.
