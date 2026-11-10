# codeowners-lint

Lint GitHub `CODEOWNERS` files for blank lines, duplicates, invalid patterns, missing ownership, and path ordering.

## About

`codeowners-lint` analyzes `CODEOWNERS` files and reports problems that can make code ownership declarations hard to maintain or silently incorrect.

It is built for GitHub's CODEOWNERS format and supports plain text and markdown reports.

## Features

- Detects blank lines and duplicate rules.
- Reports missing patterns or owners.
- Validates basic pattern formatting.
- Optionally checks lexicographic path ordering to reduce review churn.
- CLI with `--check` for CI-friendly nonzero exit codes.
- `--format plain` or `--format markdown` output.

## Installation

```bash
python -m pip install -e .
```

### Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Usage

```bash
codeowners-lint CODEOWNERS
codeowners-lint --check CODEOWNERS
codeowners-lint --format markdown CODEOWNERS
codeowners-lint --stdin < input.codeowners
```

## Project structure

```text
.github/
  workflows/
    ci.yml
.gitignore
LICENSE
README.md
codeowners_lint.py
pyproject.toml
tests/
  fixtures/
    bad.codeowners
    clean.codeowners
  test_codeowners_lint.py
```

## Tags / keywords

`codeowners` `lint` `github` `cli` `python`
