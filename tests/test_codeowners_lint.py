from codeowners_lint import lint_text, main


def test_clean_file_returns_zero():
    report = lint_text("/a @octocat\n/z @octocat\n")
    assert report.summary() == "<text>: 0 issue(s) "
    assert main(["tests/fixtures/clean.codeowners"]) == 0


def test_duplicate_rule_is_detected():
    text = "/src @octocat\n/src @octocat\n"
    report = lint_text(text)
    codes = [issue.code for issue in report.issues]
    assert any(code == "CO001" for code in codes)


def test_blank_line_is_detected():
    report = lint_text("/src @octocat\n\n/docs @octocat\n")
    assert any(issue.code == "CO001" for issue in report.issues)


def test_missing_owner_is_detected():
    report = lint_text("/src\n")
    assert any(issue.code == "CO004" for issue in report.issues)


def test_ordering_violation_is_detected():
    report = lint_text("/z/file @octocat\n/a/file @octocat\n", check_ordering=True)
    assert any(issue.code == "CO003" for issue in report.issues)


def test_no_duplicates_flag_skips_duplicate_rule():
    text = "/src @octocat\n/src @octocat\n"
    report = lint_text(text)
    assert any(issue.code == "CO001" for issue in report.issues)
    issues = lint_text(text, check_duplicates=False).issues
    assert not any(issue.code == "CO001" for issue in issues)


def test_main_returns_nonzero_with_check():
    code = main(["--check", "tests/fixtures/bad.codeowners"])
    assert code == 1


def test_markdown_render():
    report = lint_text("/src @octocat\n")
    output = report.render("markdown")
    assert "# codeowners-lint report" in output
    assert "Source: <text>" in output


def test_stdin_mode(monkeypatch, capsys):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("/src @octocat\n"))
    assert main(["--stdin", "--format", "plain"]) == 0
    out, _ = capsys.readouterr()
    assert "<stdin>: OK" in out
