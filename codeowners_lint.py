from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------

@dataclass
class Issue:
    path: Optional[str]
    line: int
    code: str
    message: str


@dataclass
class Rule:
    raw: str
    pattern: str
    owners: List[str]
    line: int
    normalized_pattern: str = ""
    is_blank: bool = False
    is_comment: bool = False
    is_section_header: bool = False


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_TAB = re.compile(r"\t+")
_MULTI_WHITE = re.compile(r"\s{2,}")
_PATTERN_PART = re.compile(r"^(/.*|[^*?]+)")


def _normalize_pattern(pattern: str) -> str:
    pattern = _TAB.sub(" ", pattern)
    pattern = pattern.strip()
    pattern = _MULTI_WHITE.sub(" ", pattern)
    return pattern


def _is_section_header(pattern: str) -> bool:
    return pattern.strip() in ("#", "##", "###", "####", "#####", "######")


def _is_blank(pattern: str) -> bool:
    return pattern.strip() == ""


def parse_codeowners(text: str, source: str = "<text>") -> Tuple[List[Rule], Dict[str, List[int]], Dict[str, List[int]]]:
    rules: List[Rule] = []
    seen_patterns: Dict[str, List[int]] = {}
    seen_exact: Dict[str, List[int]] = {}

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip("\n").rstrip("\r")
        if not line.strip() or line.strip().startswith("#"):
            # preserve blank/comment lines so line numbering stays accurate
            rule = Rule(raw=line, pattern=line, owners=[], line=line_no)
            if not line.strip():
                rule.is_blank = True
            else:
                rule.is_comment = True
            rules.append(rule)
            continue

        parts = line.split()
        if len(parts) < 2:
            rule = Rule(raw=line, pattern=line, owners=[], line=line_no)
            rules.append(rule)
            continue

        pattern = parts[0]
        owners = parts[1:]
        normalized = _normalize_pattern(pattern)
        rule = Rule(
            raw=line,
            pattern=pattern,
            owners=owners,
            line=line_no,
            normalized_pattern=normalized,
        )

        if _is_section_header(normalized):
            rule.is_section_header = True

        exact = f"{normalized}\t{' '.join(owners)}"
        seen_exact.setdefault(exact, []).append(line_no)
        seen_patterns.setdefault(normalized, []).append(line_no)

        rules.append(rule)

    return rules, seen_patterns, seen_exact


# ---------------------------------------------------------------------------
# Linter rules
# ---------------------------------------------------------------------------

def _lint(rules: List[Rule], source: str, *, check_duplicates: bool = True, check_ordering: bool = True) -> List[Issue]:
    issues: List[Issue] = []
    prev: Optional[Rule] = None

    prev_owners: List[str] = []

    for rule in rules:
        if rule.is_blank:
            issues.append(Issue(source, rule.line, "CO001", "Blank line in CODEOWNERS"))
            prev = None
            continue

        if rule.is_comment:
            if rule.raw.strip().startswith("#") and len(rule.raw.strip()) > 1 and not _is_section_header(rule.pattern):
                pass
            prev = None
            continue

        if not rule.normalized_pattern:
            issues.append(Issue(source, rule.line, "CO004", "Missing pattern or owners"))
            prev = rule
            continue

        if not rule.owners:
            issues.append(Issue(source, rule.line, "CO004", "Missing owners for pattern"))
            prev = rule
            continue

        if not re.match(r"^(/.*|\*|.*/\*|[^/]|/\*\*)$", rule.normalized_pattern):
            issues.append(Issue(source, rule.line, "CO002", f"Invalid pattern format: {rule.normalized_pattern}"))

        if rule.raw != " ".join(rule.raw.split()):
            issues.append(Issue(source, rule.line, "CO005", "Pattern or owners contain excessive whitespace"))

        if check_ordering and prev is not None and not prev.is_comment and not prev.is_blank:
            try:
                if rule.normalized_pattern < prev.normalized_pattern:
                    issues.append(Issue(source, rule.line, "CO003", f"Path ordering violation: {rule.normalized_pattern} after {prev.normalized_pattern}"))
            except TypeError:
                pass

        prev = rule
        prev_owners = rule.owners

    if check_duplicates:
        exact: dict[str, List[int]] = {}
        for rule in rules:
            if rule.is_blank or rule.is_comment:
                continue
            key = f"{rule.normalized_pattern}\t{' '.join(rule.owners)}"
            exact.setdefault(key, []).append(rule.line)

        for key, lines in exact.items():
            if len(lines) > 1:
                for line in lines[1:]:
                    issues.append(Issue(source, line, "CO001", f"Duplicate rule: {key}"))

    return issues


# ---------------------------------------------------------------------------
# Scanning / report
# ---------------------------------------------------------------------------

@dataclass
class LintReport:
    source: str
    issues: List[Issue]

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.code] = counts.get(issue.code, 0) + 1
        return f"{self.source}: {sum(counts.values())} issue(s) " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))

    def render(self, fmt: str = "plain") -> str:
        if fmt == "markdown":
            lines = [f"# codeowners-lint report", "", f"- Source: {self.source}", f"- Issues: {len(self.issues)}", ""]
            if not self.issues:
                lines.extend(["No issues found.", ""])
                return "\n".join(lines)
            lines.extend(["## Issues", "", "| Line | Code | Message |", "|------|------|---------|"])
            for issue in self.issues:
                path = issue.path or self.source
                lines.append(f"| {path}:{issue.line} | `{issue.code}` | {issue.message} |")
            lines.append("")
            return "\n".join(lines)
        if fmt == "json":
            raise NotImplementedError("JSON report format is not implemented in this scaffold.")
        return self._render_plain()

    def _render_plain(self) -> str:
        if not self.issues:
            return f"{self.source}: OK\n"
        lines = [f"{self.source}: {len(self.issues)} issue(s)", "-" * 40]
        for issue in self.issues:
            location = f"{issue.path or self.source}:{issue.line}" if issue.path else f"{self.source}:{issue.line}"
            lines.append(f"{location} [{issue.code}] {issue.message}")
        lines.append("")
        return "\n".join(lines)


def lint_text(text: str, source: str = "<text>", *, check_duplicates: bool = True, check_ordering: bool = True) -> LintReport:
    rules, _, _ = parse_codeowners(text, source=source)
    issues = _lint(rules, source, check_duplicates=check_duplicates, check_ordering=check_ordering)
    if not check_duplicates:
        issues = [issue for issue in issues if issue.code != "CO001"]
    return LintReport(source=source, issues=issues)


def lint_path(path: str, *, check_duplicates: bool = True, check_ordering: bool = True) -> LintReport:
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    return lint_text(text, source=path, check_duplicates=check_duplicates, check_ordering=check_ordering)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codeowners-lint", description="Lint GitHub CODEOWNERS files.")
    parser.add_argument("paths", nargs="*", help="CODEOWNERS file paths to lint")
    parser.add_argument("--check", action="store_true", help="Lint and return non-zero exit code on issues")
    parser.add_argument("--format", choices=["plain", "markdown"], default="plain", help="Report format")
    parser.add_argument("--no-duplicates", action="store_true", help="Disable duplicate rule checks")
    parser.add_argument("--no-ordering", action="store_true", help="Disable path ordering checks")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin when no path is provided")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    sources: List[str] = list(args.paths)
    if not sources and args.stdin:
        text = sys.stdin.read()
        report = lint_text(text, source="<stdin>")
        print(report.render(args.format))
        if args.check and report.issues:
            return 1
        return 0
    if not sources:
        parser.print_help(sys.stderr)
        return 2

    reports: List[LintReport] = []
    for path in sources:
        reports.append(lint_path(path))

    total_issues = 0
    for report in reports:
        print(report.render(args.format))
        total_issues += len(report.issues)

    if args.check and total_issues:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
