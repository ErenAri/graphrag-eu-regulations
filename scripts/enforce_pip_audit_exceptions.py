import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Vulnerability:
    package: str
    vulnerability_id: str
    installed_version: str


@dataclass(frozen=True)
class ExceptionEntry:
    package: str
    vulnerability_id: str
    reason: str
    owner: str
    expires_on: date
    tracking_issue: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="enforce-pip-audit-exceptions")
    parser.add_argument("--audit", required=True, help="Path to pip-audit JSON output.")
    parser.add_argument("--exceptions", required=True, help="Path to exception register JSON file.")
    parser.add_argument(
        "--fail-on-stale",
        action="store_true",
        help="Fail if exception entries do not match current vulnerabilities.",
    )
    return parser.parse_args()


def normalize_key(package: str, vulnerability_id: str) -> tuple[str, str]:
    return package.strip().lower(), vulnerability_id.strip().upper()


def load_audit(path: Path) -> dict[tuple[str, str], Vulnerability]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    vulnerabilities: dict[tuple[str, str], Vulnerability] = {}
    for dependency in payload.get("dependencies", []):
        package = str(dependency.get("name", "")).strip()
        version = str(dependency.get("version", "")).strip()
        for vuln in dependency.get("vulns", []):
            vulnerability_id = str(vuln.get("id", "")).strip()
            if not package or not vulnerability_id:
                continue
            key = normalize_key(package, vulnerability_id)
            vulnerabilities[key] = Vulnerability(
                package=package,
                vulnerability_id=vulnerability_id,
                installed_version=version,
            )
    return vulnerabilities


def load_exception_register(path: Path) -> dict[tuple[str, str], ExceptionEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries: dict[tuple[str, str], ExceptionEntry] = {}
    for raw_entry in payload.get("exceptions", []):
        package = str(raw_entry.get("package", "")).strip()
        vulnerability_id = str(raw_entry.get("vulnerability_id", "")).strip()
        reason = str(raw_entry.get("reason", "")).strip()
        owner = str(raw_entry.get("owner", "")).strip()
        tracking_issue = str(raw_entry.get("tracking_issue", "")).strip()
        expires_raw = str(raw_entry.get("expires_on", "")).strip()
        if not (package and vulnerability_id and reason and owner and tracking_issue and expires_raw):
            raise ValueError("invalid_exception_entry:missing_required_fields")
        expires_on = date.fromisoformat(expires_raw)
        key = normalize_key(package, vulnerability_id)
        entries[key] = ExceptionEntry(
            package=package,
            vulnerability_id=vulnerability_id,
            reason=reason,
            owner=owner,
            expires_on=expires_on,
            tracking_issue=tracking_issue,
        )
    return entries


def main() -> None:
    args = parse_args()
    today = date.today()
    vulnerabilities = load_audit(Path(args.audit))
    exceptions = load_exception_register(Path(args.exceptions))

    approved: list[dict[str, str]] = []
    unapproved: list[dict[str, str]] = []
    expired: list[dict[str, str]] = []

    for key, vulnerability in vulnerabilities.items():
        entry = exceptions.get(key)
        if entry is None:
            unapproved.append(
                {
                    "package": vulnerability.package,
                    "vulnerability_id": vulnerability.vulnerability_id,
                    "installed_version": vulnerability.installed_version,
                    "status": "missing_exception",
                }
            )
            continue
        if entry.expires_on < today:
            expired.append(
                {
                    "package": vulnerability.package,
                    "vulnerability_id": vulnerability.vulnerability_id,
                    "installed_version": vulnerability.installed_version,
                    "status": "exception_expired",
                    "expires_on": entry.expires_on.isoformat(),
                }
            )
            continue
        approved.append(
            {
                "package": vulnerability.package,
                "vulnerability_id": vulnerability.vulnerability_id,
                "installed_version": vulnerability.installed_version,
                "expires_on": entry.expires_on.isoformat(),
            }
        )

    stale = []
    for key, entry in exceptions.items():
        if key not in vulnerabilities:
            stale.append(
                {
                    "package": entry.package,
                    "vulnerability_id": entry.vulnerability_id,
                    "status": "stale_exception",
                    "expires_on": entry.expires_on.isoformat(),
                }
            )

    report = {
        "date": today.isoformat(),
        "total_vulnerabilities": len(vulnerabilities),
        "approved_count": len(approved),
        "unapproved_count": len(unapproved),
        "expired_count": len(expired),
        "stale_count": len(stale),
        "approved": approved,
        "unapproved": unapproved,
        "expired": expired,
        "stale": stale,
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if unapproved or expired:
        raise SystemExit(1)
    if args.fail_on_stale and stale:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
