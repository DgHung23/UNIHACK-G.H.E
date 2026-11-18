"""Standalone image inference, independent of FastAPI, database and Desktop sources."""
import argparse
import json
from pathlib import Path

from .image import read_image
from .runtime import RulPredictor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    args = parser.parse_args()
    engine = RulPredictor(args.model_dir, device=args.device)
    image = read_image(args.image.read_bytes())
    if image is None:
        parser.error("Input is not a readable image")
    result = engine.preprocess(image)
    hours = engine.predict_hours(result.roi)
    print(json.dumps({"rulHours": max(0, hours), "rulDays": max(0, hours) / 24,
                      "rawRulHours": hours, "device": str(engine.device), "metadata":engine.metadata}, indent=2))


if __name__ == "__main__":
    main()
