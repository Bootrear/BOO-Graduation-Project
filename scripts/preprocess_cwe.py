"""Build a traceable token-aware CWE snapshot using local pinned resources."""

import argparse
import json
import time

from cyber_qa.data.preprocess import build_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--receipt")
    parser.add_argument("--model-config", default="configs/dpr-models.v1.json")
    parser.add_argument("--model-root", default="models/dpr")
    args = parser.parse_args()
    started = time.perf_counter()
    manifest, stats = build_snapshot(args.raw, args.output, receipt_path=args.receipt,
        model_config=args.model_config, model_root=args.model_root)
    print(json.dumps({"snapshot_id": manifest.snapshot_id, "statistics": stats,
                      "offline_preprocessing_seconds": time.perf_counter() - started}, indent=2))


if __name__ == "__main__":
    main()
