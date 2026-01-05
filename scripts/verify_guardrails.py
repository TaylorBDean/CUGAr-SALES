from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_AGENTS = REPO_ROOT / "AGENTS.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
INHERIT_MARKER = "Root guardrails apply as-is; no directory-specific overrides."


@dataclass(frozen=True)
class GuardrailConfig:
    allowlisted_dirs: tuple[str, ...]
    guardrail_keywords: tuple[str, ...]
    interface_keywords: tuple[str, ...]
    guarded_prefixes: tuple[str, ...]
    vnext_keywords: tuple[str, ...]
    required_docs: tuple[str, ...]
    inherit_filename: str = ".guardrails-inherit"

    @classmethod
    def from_env(cls) -> "GuardrailConfig":
        def _split(key: str, default: Sequence[str]) -> tuple[str, ...]:
            raw = os.getenv(key)
            if not raw:
                return tuple(default)
            parts = [part.strip() for chunk in raw.split(",") for part in chunk.split() if part.strip()]
            return tuple(parts) if parts else tuple(default)

        allowlisted_dirs = _split(
            "GUARDRAILS_ALLOWLISTED_DIRS",
            (
                "src",
                "docs",
                "config",
                "configurations",
                "scripts",
                "examples",
                ".github",
            ),
        )
        guardrail_keywords = _split(
            "GUARDRAILS_KEYWORDS",
            ("allowlist", "denylist", "escalation", "budget", "redaction"),
        )
        interface_keywords = _split(
            "GUARDRAILS_INTERFACE_KEYWORDS",
            ("planner", "worker", "coordinator"),
        )
        guarded_prefixes = _split(
            "GUARDRAILS_GUARDED_PREFIXES",
            (
                "AGENTS.md",
                "registry.yaml",
                "config/registry",
                "docs/mcp/registry",
                "configurations/registry",
            ),
        )
        vnext_keywords = _split(
            "GUARDRAILS_VNEXT_KEYWORDS",
            ("guardrail", "registry", "sandbox"),
        )
        required_docs = _split(
            "GUARDRAILS_REQUIRED_DOCS",
            ("README.md", "PRODUCTION_READINESS.md", "CHANGELOG.md", "todo1.md"),
        )

        return cls(
            allowlisted_dirs=allowlisted_dirs,
            guardrail_keywords=guardrail_keywords,
            interface_keywords=interface_keywords,
            guarded_prefixes=guarded_prefixes,
            vnext_keywords=vnext_keywords,
            required_docs=required_docs,
        )


CONFIG = GuardrailConfig.from_env()


def _normalize_base_ref(base_ref: str | None) -> str | None:
    if not base_ref:
        return None
    if base_ref.startswith("origin/"):
        return base_ref
    return f"origin/{base_ref}"


def collect_changed_files(base_ref: str | None = None) -> list[str]:
    normalized = _normalize_base_ref(base_ref)
    if not normalized:
        return []

    branch = normalized.removeprefix("origin/")
    subprocess.run(
        ["git", "fetch", "origin", branch], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    diff_args = ["git", "diff", "--name-only", f"{normalized}...HEAD"]
    result = subprocess.run(diff_args, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        fallback = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1...HEAD"], capture_output=True, text=True, check=False
        )
        output = fallback.stdout if fallback.returncode == 0 else ""
    else:
        output = result.stdout

    return [line.strip() for line in output.splitlines() if line.strip()]


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ensure_root_guardrails(content: str) -> list[str]:
    errors: list[str] = []
    lowered = content.lower()
    missing_keywords = [kw for kw in CONFIG.guardrail_keywords if kw.lower() not in lowered]
    if missing_keywords:
        errors.append(
            f"Root guardrails must mention keywords for allowlists/denylist/budgets/escalations/redaction: {', '.join(missing_keywords)}"
        )

    missing_interfaces = [kw for kw in CONFIG.interface_keywords if kw.lower() not in lowered]
    if missing_interfaces:
        errors.append(
            "Root guardrails must document planner/worker/coordinator contracts and trace expectations."
        )

    return errors


def ensure_allowlisted_inherit_markers(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for dirname in CONFIG.allowlisted_dirs:
        target_dir = repo_root / dirname
        if not target_dir.exists():
            continue
        marker = target_dir / CONFIG.inherit_filename
        if not marker.exists():
            errors.append(f"Missing guardrail inheritance marker in {dirname}")
            continue
        content = marker.read_text(encoding="utf-8").strip()
        if INHERIT_MARKER not in content:
            errors.append(
                f"Guardrail inheritance marker in {dirname} must state that root guardrails apply unchanged."
            )
    return errors


def ensure_local_agents_inherit(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for agents_file in repo_root.rglob("AGENTS.md"):
        if agents_file.resolve() == ROOT_AGENTS.resolve():
            continue
        content = agents_file.read_text(encoding="utf-8")
        if "canonical" in content.lower():
            errors.append(
                f"{agents_file} must not claim canonical status; root AGENTS.md is the single source of truth."
            )
        if INHERIT_MARKER not in content:
            errors.append(f"{agents_file} must include the inheritance marker to defer to root guardrails.")
    return errors


def _extract_vnext_entries(changelog: str) -> list[str]:
    lines = changelog.splitlines()
    entries: list[str] = []
    in_vnext = False
    for line in lines:
        if line.startswith("## "):
            if in_vnext and not line.lower().startswith("## vnext"):
                break
            if line.lower().startswith("## vnext"):
                in_vnext = True
                continue
        if in_vnext:
            entries.append(line.strip())
    return [line for line in entries if line]


def ensure_changelog_structure(changelog_text: str) -> list[str]:
    errors: list[str] = []
    entries = _extract_vnext_entries(changelog_text)
    if "## vNext" not in changelog_text:
        errors.append("CHANGELOG.md must contain a '## vNext' section.")
    elif not entries:
        errors.append("CHANGELOG.md must list at least one upcoming change under '## vNext'.")
    return errors


def changelog_mentions_guardrails(changelog_text: str) -> bool:
    entries = _extract_vnext_entries(changelog_text)
    lowered_entries = "\n".join(entries).lower()
    return any(keyword.lower() in lowered_entries for keyword in CONFIG.vnext_keywords)


def _is_guardrail_change(path: str) -> bool:
    posix = Path(path).as_posix()
    if Path(posix).name.lower() == "agents.md":
        return True
    return any(posix.startswith(prefix) for prefix in CONFIG.guarded_prefixes)


def check_guardrail_change_requirements(changed_files: Iterable[str], changelog_text: str) -> list[str]:
    errors: list[str] = []
    changed = {Path(path).as_posix() for path in changed_files}
    guardrail_changed = any(_is_guardrail_change(path) for path in changed)
    if not guardrail_changed:
        return errors

    if not changelog_mentions_guardrails(changelog_text):
        errors.append(
            "Guardrail or registry changes require a '## vNext' entry mentioning guardrails/registry/sandbox updates."
        )

    missing_docs = [doc for doc in CONFIG.required_docs if doc not in changed]
    if missing_docs:
        errors.append(
            "Guardrail changes must update documentation and runbooks; missing updates for: "
            + ", ".join(missing_docs)
        )

    return errors


def run_checks(changed_files: Iterable[str] | None = None, base: str | None = None) -> List[str]:
    errors: list[str] = []
    files = list(changed_files) if changed_files is not None else collect_changed_files(base)

    if not ROOT_AGENTS.exists():
        errors.append("Root AGENTS.md is missing; guardrails must be defined at the repo root.")
        return errors

    root_content = _load_text(ROOT_AGENTS)
    errors.extend(ensure_root_guardrails(root_content))

    errors.extend(ensure_allowlisted_inherit_markers(REPO_ROOT))
    errors.extend(ensure_local_agents_inherit(REPO_ROOT))

    if not CHANGELOG.exists():
        errors.append("CHANGELOG.md is missing; document guardrail and registry changes under '## vNext'.")
    else:
        changelog_text = _load_text(CHANGELOG)
        errors.extend(ensure_changelog_structure(changelog_text))
        errors.extend(check_guardrail_change_requirements(files, changelog_text))

    return errors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate guardrail guardrails, inheritance markers, and doc coverage."
    )
    parser.add_argument(
        "--base", help="Git ref used to collect changed files (defaults to origin/<default-branch>)"
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        dest="changed_files",
        help="Explicitly provide a changed file path; can be used multiple times.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    changed_files = args.changed_files if args.changed_files is not None else None
    errors = run_checks(changed_files=changed_files, base=args.base)

    if errors:
        print("Guardrail verification failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Guardrail verification passed: guardrails, inheritance markers, and docs are in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
