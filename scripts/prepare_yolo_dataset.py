"""from ultralytics import YOLO

Fine-tune YOLO11n on a pavement dataset (RDD, custom Roboflow, etc.).

    yolo detect train data=datasets/pavement.yaml model=yolo11n.pt epochs=50 imgsz=640
"""

from pathlib import Path

YAML = """# Pavement distress classes for InfraPulse
path: datasets/pavement
train: images/train
val: images/val

names:
  0: crack
  1: pothole
  2: other_distress
  3: patch
  4: raveling
"""


def write_dataset_stub(root: Path = Path("datasets/pavement")) -> None:
    (root / "images/train").mkdir(parents=True, exist_ok=True)
    (root / "images/val").mkdir(parents=True, exist_ok=True)
    (root / "labels/train").mkdir(parents=True, exist_ok=True)
    (root / "labels/val").mkdir(parents=True, exist_ok=True)
    Path("datasets/pavement.yaml").write_text(YAML, encoding="utf-8")
    print("Wrote datasets/pavement.yaml — drop YOLO-format labels into labels/train")


if __name__ == "__main__":
    write_dataset_stub()
