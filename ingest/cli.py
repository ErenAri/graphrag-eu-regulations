import argparse

from ingest.pipeline import run_ingest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--source_url", required=True)
    run_parser.add_argument("--work_title", required=True)
    run_parser.add_argument("--jurisdiction", required=True)
    run_parser.add_argument("--authority_level", required=True, type=int)
    run_parser.add_argument("--valid_from", required=True)
    run_parser.add_argument("--published_date")
    run_parser.add_argument("--work_id")
    run_parser.add_argument("--expression_id")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "run":
        run_ingest(
            source_url=args.source_url,
            work_title=args.work_title,
            jurisdiction=args.jurisdiction,
            authority_level=args.authority_level,
            valid_from=args.valid_from,
            published_date=args.published_date,
            work_id=args.work_id,
            expression_id=args.expression_id,
        )


if __name__ == "__main__":
    main()
