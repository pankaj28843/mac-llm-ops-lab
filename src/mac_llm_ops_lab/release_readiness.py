import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

PUBLIC_RELEASE_CHECK_SCHEMA_VERSION = "public-release-check/v1"
USERS_PATH_FRAGMENT = "/" + "Users/"
CALIBRE_PATH_FRAGMENT = "Calibre" + " Library"
LOCAL_LIBRARY_TREE_FRAGMENT = "." + "bo" + "oks/"

FORBIDDEN_TRACKED_PREFIXES = (
    ".env",
    "artifacts/",
    "benchmarks/raw/",
    "data/",
    "model-cache/",
    "models/",
    "secrets/",
    "site/",
    "traces/",
)
PRIVATE_MACHINE_FRAGMENTS = (
    USERS_PATH_FRAGMENT,
    CALIBRE_PATH_FRAGMENT,
    LOCAL_LIBRARY_TREE_FRAGMENT,
)
SECRET_PATTERNS = (
    ("openai_api_key", re.compile(r"\bOPENAI_API_KEY\s*[:=]\s*sk-[A-Za-z0-9_-]+")),
    ("openai_secret_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("huggingface_token", re.compile(r"\bHF_TOKEN\s*[:=]\s*hf_[A-Za-z0-9]{20,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
COPYRIGHT_WORD = "Copy" + "right"
ALL_RIGHTS_RESERVED_WORDS = "All rights " + "reserved"
PROTECTED_WORK_TERMS = ("publication", "work", "material", "bo" + "ok")
COPYRIGHT_NOTICE_PATTERNS = (
    (
        "third_party_copyright_notice",
        re.compile(
            rf"{COPYRIGHT_WORD}.{{0,180}}{ALL_RIGHTS_RESERVED_WORDS}",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "third_party_reproduction_notice",
        re.compile(
            r"No part of this (?:"
            + "|".join(PROTECTED_WORK_TERMS)
            + r").{0,160}(?:reproduced|transmitted)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)


def scan_public_release_files(
    files: Mapping[str, str],
    *,
    git_sha: str,
) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    for path, text in sorted(files.items()):
        normalized_path = path.replace("\\", "/")
        findings.extend(_forbidden_path_findings(normalized_path))
        findings.extend(_private_fragment_findings(normalized_path, text))
        findings.extend(_secret_pattern_findings(normalized_path, text))
        findings.extend(_copyright_notice_findings(normalized_path, text))

    return {
        "schema_version": PUBLIC_RELEASE_CHECK_SCHEMA_VERSION,
        "git_sha": _non_empty_string(git_sha, field_name="git_sha"),
        "passed": not findings,
        "scanned_files_count": len(files),
        "findings_count": len(findings),
        "findings": findings,
        "checks": [
            "forbidden_tracked_paths",
            "private_machine_paths",
            "secret_patterns",
            "copyright_notice_patterns",
        ],
    }


def load_public_release_candidate_files(repo_root: Path) -> dict[str, str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )
    files: dict[str, str] = {}
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative_path = raw_path.decode("utf-8")
        absolute_path = repo_root / relative_path
        if absolute_path.is_file():
            files[relative_path] = absolute_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
    return files


def current_git_sha(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def write_public_release_report(
    report: Mapping[str, object],
    *,
    output_root: Path,
    output_path: Path,
) -> Path:
    _validate_report(report)
    target = output_path if output_path.is_absolute() else output_root / output_path
    if not _is_runtime_artifact_path(target):
        raise ValueError("output_path must be under artifacts/runtime/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def _forbidden_path_findings(path: str) -> list[dict[str, object]]:
    for prefix in FORBIDDEN_TRACKED_PREFIXES:
        if path == prefix.rstrip("/") or path.startswith(prefix):
            return [
                {
                    "kind": "forbidden_tracked_path",
                    "path": path,
                    "pattern": prefix,
                }
            ]
    return []


def _private_fragment_findings(path: str, text: str) -> list[dict[str, object]]:
    findings = []
    for fragment in PRIVATE_MACHINE_FRAGMENTS:
        if fragment in text:
            findings.append(
                {
                    "kind": "private_machine_path",
                    "path": path,
                    "pattern": fragment,
                }
            )
    return findings


def _secret_pattern_findings(path: str, text: str) -> list[dict[str, object]]:
    findings = []
    for name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                {
                    "kind": "secret_pattern",
                    "path": path,
                    "pattern": name,
                    "line": text.count("\n", 0, match.start()) + 1,
                }
            )
    return findings


def _copyright_notice_findings(path: str, text: str) -> list[dict[str, object]]:
    findings = []
    for name, pattern in COPYRIGHT_NOTICE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                {
                    "kind": "copyright_notice_pattern",
                    "path": path,
                    "pattern": name,
                    "line": text.count("\n", 0, match.start()) + 1,
                }
            )
    return findings


def _validate_report(report: Mapping[str, object]) -> None:
    if report.get("schema_version") != PUBLIC_RELEASE_CHECK_SCHEMA_VERSION:
        raise ValueError(
            f"report schema_version must be {PUBLIC_RELEASE_CHECK_SCHEMA_VERSION}",
        )
    if not isinstance(report.get("passed"), bool):
        raise ValueError("report passed must be a boolean")
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError("report findings must be a list")


def _is_runtime_artifact_path(path: Path) -> bool:
    parts = path.parts
    return any(
        parts[index : index + 2] == ("artifacts", "runtime")
        for index in range(max(len(parts) - 1, 0))
    )


def _non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    return value
