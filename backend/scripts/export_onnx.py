"""One-time script: export BAAI/bge-small-en-v1.5 to ONNX format.
Run locally with:  python backend/scripts/export_onnx.py
Output:           backend/models/onnx/  (3 files)
"""
from pathlib import Path

from optimum.onnxruntime import ORTModelForFeatureExtraction
from transformers import AutoTokenizer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "models" / "onnx"

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Exporting {MODEL_NAME} to ONNX...")
    model = ORTModelForFeatureExtraction.from_pretrained(
        MODEL_NAME,
        export=True,                        # triggers the ONNX export
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    print(f"Saved ONNX model to: {OUTPUT_DIR}")
    # Expected files: model.onnx, tokenizer_config.json, special_tokens_map.json,
    #                 vocab.txt, tokenizer.json, config.json, etc.
    total_mb = sum(f.stat().st_size for f in OUTPUT_DIR.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"Total size: {total_mb:.1f} MB")

if __name__ == "__main__":
    main()
