"""Encode three generated covers without changing their illustrated content."""
from pathlib import Path
import argparse
import hashlib
import json
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/design/drafts/renderer-studies-assets"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pony", type=Path)
    parser.add_argument("pixels", type=Path)
    parser.add_argument("pilot", type=Path)
    args = parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = {"generator": "built-in image_gen", "classification": "conceptual editorial illustrations, not gameplay or Blender screenshots", "assets": []}
    for note, source in zip(("009", "010", "011"), (args.pony, args.pixels, args.pilot)):
        with Image.open(source) as original:
            image = original.convert("RGB")
            record = {"note": note, "original_sha256": digest(source), "original_dimensions": list(image.size), "variants": []}
            for width in (1600, 800):
                height = round(image.height * width / image.width)
                target = DEST / f"{note}-cover-{width}.webp"
                if target.exists():
                    raise FileExistsError(target)
                image.resize((width, height), Image.Resampling.LANCZOS).save(target, "WEBP", quality=86, method=6)
                record["variants"].append({"file": target.name, "dimensions": [width, height], "bytes": target.stat().st_size, "sha256": digest(target)})
            manifest["assets"].append(record)
    target = DEST / "image-provenance.json"
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Prepared six WebP cover variants and image provenance.")

if __name__ == "__main__":
    main()
