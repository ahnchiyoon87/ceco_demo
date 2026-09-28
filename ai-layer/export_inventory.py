"""CLI wrapper for the source preparation used by the knowledge service."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "knowledge"))
from backend.src.modules.ontology.inventory import export_inventory

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "simulator/plant.yaml")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = export_inventory(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(result['nodes'])} candidate nodes and {len(result['relationships'])} relationships")
