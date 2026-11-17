import os
import sys
import shutil
import hashlib
from pathlib import Path

SOURCE_DIR = Path(r"C:\Users\admin\Desktop\Strawberry-RUL-prediction")
DEST_DIR = Path(r"C:\Users\admin\Downloads\fruitchain\fruitchain\ml_model")

def main():
    print(f"Source exists: {SOURCE_DIR.is_dir()} ({SOURCE_DIR})")
    print(f"Target: {DEST_DIR}")

    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Source directory not found: {SOURCE_DIR}")

    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy src
    src_src = SOURCE_DIR / "src"
    dest_src = DEST_DIR / "src"
    copied_src_count = 0
    for root, dirs, files in os.walk(src_src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        rel = Path(root).relative_to(src_src)
        for f in files:
            if f.endswith(".pyc"):
                continue
            s_file = Path(root) / f
            d_file = dest_src / rel / f
            d_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s_file, d_file)
            copied_src_count += 1
    print(f"Copied {copied_src_count} files into {dest_src}")

    # 2. Copy configs
    cfg_src = SOURCE_DIR / "configs"
    dest_cfg = DEST_DIR / "configs"
    copied_cfg_count = 0
    for root, dirs, files in os.walk(cfg_src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        rel = Path(root).relative_to(cfg_src)
        for f in files:
            s_file = Path(root) / f
            d_file = dest_cfg / rel / f
            d_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s_file, d_file)
            copied_cfg_count += 1
    print(f"Copied {copied_cfg_count} files into {dest_cfg}")

    # 3. Copy model weights
    model_rel = Path("models/strawberry/production/model_D/best_model.pt")
    s_model = SOURCE_DIR / model_rel
    d_model = DEST_DIR / model_rel
    d_model.parent.mkdir(parents=True, exist_ok=True)
    print(f"Copying model from {s_model} to {d_model}...")
    shutil.copy2(s_model, d_model)
    print(f"Copied model weights, size: {d_model.stat().st_size} bytes")

    # 4. Copy sample images
    data_subdirs = [
        Path("data/02_processed/strawberry/assigned_01-04-2026/F01"),
        Path("data/02_processed/strawberry/assigned_01-04-2026/F02"),
    ]
    copied_img_count = 0
    for sub in data_subdirs:
        s_sub = SOURCE_DIR / sub
        d_sub = DEST_DIR / sub
        d_sub.mkdir(parents=True, exist_ok=True)
        for img_file in s_sub.glob("*.png"):
            shutil.copy2(img_file, d_sub / img_file.name)
            copied_img_count += 1
    print(f"Copied {copied_img_count} sample images into {DEST_DIR / 'data'}")

    # 5. Copy README and requirements for documentation
    for extra in ["README.md", "requirements.txt"]:
        s_extra = SOURCE_DIR / extra
        if s_extra.exists():
            shutil.copy2(s_extra, DEST_DIR / extra)
            print(f"Copied {extra}")

    # 6. Verification
    print("\n--- Running Verification ---")
    
    # Verify best_model.pt SHA256 and size
    s_hash = hashlib.sha256(s_model.read_bytes()).hexdigest()
    d_hash = hashlib.sha256(d_model.read_bytes()).hexdigest()
    print(f"Source best_model.pt SHA256: {s_hash}")
    print(f"Target best_model.pt SHA256: {d_hash}")
    assert s_hash == d_hash, f"SHA256 mismatch! {s_hash} != {d_hash}"
    assert d_model.stat().st_size == s_model.stat().st_size == 13102227, "File size mismatch!"
    print("Model weights SHA256 and size verification: PASSED")

    # Verify crucial files exist and are readable
    crucial_files = [
        dest_src / "strawberry" / "services" / "predictor.py",
        dest_src / "strawberry" / "services" / "preprocessing.py",
        dest_src / "strawberry" / "config_app" / "config.json",
        dest_src / "strawberry" / "training" / "models.py",
        dest_src / "strawberry" / "utils_app" / "image_utils.py",
        dest_src / "strawberry" / "shared" / "cbam.py",
        dest_cfg / "strawberry_config.yaml",
        dest_cfg / "strawberry_training.json",
        d_model,
        DEST_DIR / "data" / "02_processed" / "strawberry" / "assigned_01-04-2026" / "F01" / "frame-10_10-15-07_F01.png",
    ]
    for cf in crucial_files:
        assert cf.is_file(), f"Missing file: {cf}"
        data = cf.read_bytes()
        assert len(data) > 0, f"File is empty: {cf}"
        print(f"File verified: {cf.relative_to(DEST_DIR)} ({len(data)} bytes)")

    # Test integration with custom adapter
    backend = (DEST_DIR.parent / "backend").resolve()
    sys.path.insert(0, str(backend))
    from app.services.rul_adapters.custom import find_project_root, inspect_folder, CustomModel

    proj = find_project_root(DEST_DIR)
    print(f"\nfind_project_root({DEST_DIR}): {proj}")
    assert proj is not None, "find_project_root returned None!"
    assert proj[1] == "strawberry", f"Expected package strawberry, got {proj[1]}"

    info = inspect_folder(DEST_DIR)
    print(f"inspect_folder kind: {info.get('kind')}")
    print(f"inspect_folder checkpoints: {info.get('checkpoints')}")
    print(f"inspect_folder defaultCheckpoint: {info.get('defaultCheckpoint')}")
    assert info.get("kind") == "project"
    assert len(info.get("checkpoints", [])) >= 1
    assert "best_model.pt" in str(info.get("defaultCheckpoint"))

    # Test loading and predicting through CustomModel
    from app.services.rul_adapters.base import RulInput
    import cv2

    model = CustomModel(DEST_DIR, checkpoint=str(d_model), device="cpu", fruits=["strawberry"])
    model.load()
    print(f"CustomModel loaded: version={model.version}, hash={model.model_hash()[:12]}")
    sample_img_path = DEST_DIR / "data" / "02_processed" / "strawberry" / "assigned_01-04-2026" / "F01" / "frame-10_10-15-07_F01.png"
    img_bgr = cv2.imread(str(sample_img_path))
    roi, pre_info = model.preprocess(img_bgr)
    print(f"CustomModel preprocess OK: shape={roi.shape}, info={pre_info}")
    
    # Save preprocessed image to a temp location and run model.predict
    out_pre = DEST_DIR.parent / "backend" / "storage" / "test_migrator_pre.png"
    out_pre.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_pre), roi)
    rul_out = model.predict(RulInput(batch_id="TEST-001", fruit_id="strawberry", image_path=str(out_pre)))
    print(f"CustomModel predict OK: rul_days={rul_out.rul_days}, extra={rul_out.extra}")
    assert rul_out.rul_days > 0, f"Expected rul_days > 0, got {rul_out.rul_days}"
    if out_pre.exists():
        out_pre.unlink()

    print("\nAll files and CustomModel verification tests passed successfully!")

if __name__ == "__main__":
    main()
