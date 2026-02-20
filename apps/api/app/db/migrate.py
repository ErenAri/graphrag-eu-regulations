import argparse
import json

from app.db.migrations import run_migrations
from app.db.schema import ensure_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="db-migrate")
    parser.add_argument("--include-seed", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    applied = run_migrations(include_seed=args.include_seed)
    ensure_schema()
    print(json.dumps({"applied": applied, "schema_reconciled": True}, indent=2))


if __name__ == "__main__":
    main()
