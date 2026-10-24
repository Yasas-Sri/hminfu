"""Write the OpenAPI schema to a file without running a server.

Usage (from backend/): uv run python -m scripts.export_openapi [output_path]
"""

import json
import sys
from pathlib import Path

from app.main import create_app


def main() -> None:
    default = Path(__file__).resolve().parents[1] / "openapi.json"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    out.write_text(json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
