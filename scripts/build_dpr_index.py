"""Build an exact DPR index from a validated snapshot and local model weights."""

import argparse
import json

from cyber_qa.models import DPRRuntime
from cyber_qa.retrieval.dpr import build_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--model-config", default="configs/dpr-models.v1.json")
    parser.add_argument("--model-root", default="models/dpr")
    args = parser.parse_args()
    runtime = DPRRuntime(device=args.device, model_config=args.model_config, model_root=args.model_root)
    meta = build_index(args.snapshot, args.output, runtime, batch_size=args.batch_size)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
