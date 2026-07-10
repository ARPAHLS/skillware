from skillware.cli import (
    _discover_skills,
    _resolve_pytest_targets,
    _parse_examples_index,
    _load_examples_index,
    _example_counts_by_skill,
    _example_github_url,
    cmd_list,
    cmd_examples,
    cmd_interactive,
    cmd_test,
    _short_description,
    cmd_help,
    cmd_paths,
)

import pytest


def test_discover_skills_returns_skills(tmp_path):
    # Create a fake skill directory structure
    skill_dir = tmp_path / "office" / "pdf_form_filler"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.py").touch()

    manifest = skill_dir / "manifest.yaml"
    manifest.write_text(
        "name: office/pdf_form_filler\n"
        "version: 0.1.0\n"
        "description: Fills PDF forms.\n"
        "requirements:\n"
        "  - pymupdf\n"
    )

    skills = _discover_skills(tmp_path)

    assert len(skills) == 1
    assert skills[0]["id"] == "office/pdf_form_filler"
    assert skills[0]["version"] == "0.1.0"


def test_discover_skills_empty_directory(tmp_path):
    # No skills created, directory is empty
    skills = _discover_skills(tmp_path)

    assert skills == []


def test_discover_skills_nonexistent_override_falls_back(tmp_path, monkeypatch):
    # An override path that does not exist should be ignored
    # and fall back to other roots without crashing
    monkeypatch.chdir(tmp_path)
    fake_path = tmp_path / "nonexistent"

    # Should not raise, just return empty list since no roots have skills
    skills = _discover_skills(fake_path)
    assert skills == []


def test_discover_skills_missing_optional_fields(tmp_path):
    # Manifest with only required fields, no version, description or requirements
    skill_dir = tmp_path / "office" / "minimal_skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.py").touch()

    manifest = skill_dir / "manifest.yaml"
    manifest.write_text("name: minimal_skill\n")

    skills = _discover_skills(tmp_path)

    assert len(skills) == 1
    assert skills[0]["version"] == "?"
    assert skills[0]["description"] == ""
    assert skills[0]["requirements"] == ""


def test_discover_skills_ignores_deeply_nested_manifest(tmp_path):
    # manifest.yaml three levels deep should not be picked up
    skill_dir = tmp_path / "office" / "pdf_form_filler" / "extra"
    skill_dir.mkdir(parents=True)

    manifest = skill_dir / "manifest.yaml"
    manifest.write_text("name: should_not_appear\nversion: 0.1.0\n")

    skills = _discover_skills(tmp_path)

    assert skills == []


def test_discover_skills_includes_issuer(tmp_path):
    # Manifest with issuer github handle
    skill_dir = tmp_path / "office" / "pdf_form_filler"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.py").touch()

    manifest = skill_dir / "manifest.yaml"
    manifest.write_text(
        "name: office/pdf_form_filler\n"
        "version: 0.1.0\n"
        "description: Fills PDF forms.\n"
        "issuer:\n"
        "  name: Ross Peili\n"
        "  github: rosspeili\n"
    )

    skills = _discover_skills(tmp_path)

    assert skills[0]["issuer"] == "rosspeili"


def test_discover_skills_issuer_falls_back_to_name(tmp_path):
    # Manifest with issuer name but no github handle
    skill_dir = tmp_path / "office" / "pdf_form_filler"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.py").touch()

    manifest = skill_dir / "manifest.yaml"
    manifest.write_text(
        "name: office/pdf_form_filler\n"
        "version: 0.1.0\n"
        "description: Fills PDF forms.\n"
        "issuer:\n"
        "  name: Ross Peili\n"
    )

    skills = _discover_skills(tmp_path)

    assert skills[0]["issuer"] == "Ross Peili"


def test_cmd_list_filter_by_category(tmp_path):
    # Only skills matching the category should appear
    import io
    from rich.console import Console

    for category, name in [
        ("office", "pdf_form_filler"),
        ("finance", "wallet_screening"),
    ]:
        skill_dir = tmp_path / category / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.py").touch()
        (skill_dir / "manifest.yaml").write_text(
            f"name: {category}/{name}\nversion: 0.1.0\ndescription: Test.\n"
        )

    buf = io.StringIO()
    cmd_list(
        skills_root_override=tmp_path,
        category_filter="office",
        console=Console(file=buf, force_terminal=False),
    )

    output = buf.getvalue()
    assert "office" in output
    assert "finance" not in output


def test_short_description_uses_short_description_field():
    """short_description field takes priority over description."""
    data = {
        "short_description": "Short one.",
        "description": "This is a much longer description that should not appear.",
    }
    assert _short_description(data) == "Short one."


def test_short_description_truncates_at_80_chars():
    """short_description longer than 80 chars should be truncated with …"""
    data = {"short_description": "A" * 90}
    result = _short_description(data)
    assert len(result) == 81  # 80 + "…"
    assert result.endswith("…")


def test_short_description_falls_back_to_first_sentence():
    """Without short_description, use first sentence of description."""
    data = {"description": "First sentence. Second sentence follows."}
    assert _short_description(data) == "First sentence."


def test_short_description_empty_manifest():
    """Empty manifest should return empty string."""
    assert _short_description({}) == ""


def test_cmd_interactive_exits_on_q(monkeypatch):
    """Entering q should exit cleanly."""
    import io
    from rich.console import Console

    monkeypatch.setattr("builtins.input", lambda _: "q")
    buf = io.StringIO()
    cmd_interactive(console=Console(file=buf, force_terminal=False))
    assert "Bye" in buf.getvalue()


def test_cmd_interactive_unknown_command(monkeypatch):
    """Unknown command should print error then exit on q."""
    import io
    from rich.console import Console

    responses = iter(["unknown_cmd", "q"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))
    buf = io.StringIO()
    cmd_interactive(console=Console(file=buf, force_terminal=False))
    assert "Unknown command" in buf.getvalue()


def test_cmd_interactive_list_dispatch(tmp_path, monkeypatch):
    """Entering 1 or list should dispatch to cmd_list."""
    import io
    from rich.console import Console

    skill_dir = tmp_path / "office" / "test_skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.py").touch()
    (skill_dir / "manifest.yaml").write_text(
        "name: test_skill\nversion: 0.1.0\ndescription: Test.\n"
        "short_description: Test skill.\n"
    )

    responses = iter(["1", "q"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))
    monkeypatch.chdir(tmp_path)

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False)
    cmd_interactive(console=console)

    output = buf.getvalue()
    assert "test_skill" in output


def test_main_module_invocation():
    """python -m skillware should be importable and callable."""
    import skillware.__main__  # noqa: F401 — just verify it imports cleanly
    from skillware.__main__ import main

    assert callable(main)


def test_cmd_help_includes_list_examples(capsys):
    """cmd_help should include category, test, and issuer examples."""
    import io
    from rich.console import Console

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False)
    cmd_help(console=console)

    output = buf.getvalue()
    assert "--category" in output
    assert "--issuer" in output
    assert "skillware test" in output
    assert "skillware examples" in output


def test_interactive_help_dispatches_to_cmd_help(monkeypatch):
    """Interactive menu option 5 / help should call cmd_help."""
    import io
    from rich.console import Console

    responses = iter(["5", "q"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False)
    cmd_interactive(console=console)

    output = buf.getvalue()
    assert "--category" in output
    assert "--issuer" in output


def test_version_flag(capsys):
    """skillware --version should print the installed version and exit."""
    import sys
    from skillware.cli import main

    monkeypatch_argv = sys.argv
    sys.argv = ["skillware", "--version"]
    try:
        with pytest.raises(SystemExit):
            main()
    finally:
        sys.argv = monkeypatch_argv

    captured = capsys.readouterr()
    assert "skillware" in captured.out.lower()


def _make_bundle(tmp_path, category, name, with_test=True):
    skill_dir = tmp_path / category / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.py").touch()
    (skill_dir / "manifest.yaml").write_text(
        f"name: {category}/{name}\nversion: 0.1.0\ndescription: Test.\n"
    )
    if with_test:
        (skill_dir / "test_skill.py").touch()
    return skill_dir


def test_resolve_pytest_targets_skill_id(tmp_path):
    _make_bundle(tmp_path, "office", "pdf_form_filler")
    targets, error = _resolve_pytest_targets(
        skills_root_override=tmp_path,
        skill_id="office/pdf_form_filler",
    )
    assert error is None
    assert targets == [tmp_path / "office" / "pdf_form_filler" / "test_skill.py"]


def test_resolve_pytest_targets_category(tmp_path):
    _make_bundle(tmp_path, "office", "pdf_form_filler")
    _make_bundle(tmp_path, "finance", "wallet_screening")
    targets, error = _resolve_pytest_targets(
        skills_root_override=tmp_path,
        category="office",
    )
    assert error is None
    assert targets == [tmp_path / "office"]


def test_resolve_pytest_targets_all_roots(tmp_path):
    _make_bundle(tmp_path, "office", "pdf_form_filler")
    targets, error = _resolve_pytest_targets(skills_root_override=tmp_path)
    assert error is None
    assert targets == [tmp_path]


def test_resolve_pytest_targets_missing_skill(tmp_path):
    targets, error = _resolve_pytest_targets(
        skills_root_override=tmp_path,
        skill_id="office/missing",
    )
    assert targets == []
    assert "No bundle test found" in error


def test_resolve_pytest_targets_skill_id_and_category_conflict():
    targets, error = _resolve_pytest_targets(
        skill_id="office/pdf_form_filler",
        category="office",
    )
    assert targets == []
    assert "not both" in error


def test_cmd_test_invokes_pytest(tmp_path, monkeypatch):
    import sys

    _make_bundle(tmp_path, "office", "pdf_form_filler")
    captured = {}

    def fake_run(cmd, check=False):
        captured["cmd"] = cmd

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("skillware.cli.subprocess.run", fake_run)

    rc = cmd_test(
        skills_root_override=tmp_path,
        skill_id="office/pdf_form_filler",
    )
    assert rc == 0
    assert captured["cmd"][0] == sys.executable
    assert captured["cmd"][1:3] == ["-m", "pytest"]
    assert (
        str(tmp_path / "office" / "pdf_form_filler" / "test_skill.py")
        in captured["cmd"]
    )


def test_cmd_test_verbose_flag(tmp_path, monkeypatch):
    _make_bundle(tmp_path, "office", "pdf_form_filler")
    captured = {}

    def fake_run(cmd, check=False):
        captured["cmd"] = cmd

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("skillware.cli.subprocess.run", fake_run)

    cmd_test(
        skills_root_override=tmp_path,
        skill_id="office/pdf_form_filler",
        verbose=True,
        no_header=True,
    )
    assert "-v" in captured["cmd"]
    assert "--no-header" in captured["cmd"]


def test_cmd_test_missing_bundle_returns_nonzero(tmp_path):
    rc = cmd_test(
        skills_root_override=tmp_path,
        skill_id="office/missing",
    )
    assert rc == 1


def test_main_test_subcommand_exits_with_cmd_test_code(monkeypatch):
    import sys
    from skillware.cli import main

    monkeypatch.setattr("skillware.cli.cmd_test", lambda **kwargs: 0)

    argv = sys.argv
    sys.argv = ["skillware", "test", "office/pdf_form_filler"]
    try:
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
    finally:
        sys.argv = argv


def test_interactive_test_dispatch(tmp_path, monkeypatch):
    """Entering 3 or test should dispatch to cmd_test."""
    import io
    from rich.console import Console

    _make_bundle(tmp_path, "office", "test_skill")
    captured = {}

    def fake_test(**kwargs):
        captured["called"] = True
        return 0

    monkeypatch.setattr("skillware.cli.cmd_test", fake_test)

    responses = iter(["test", "q"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))

    buf = io.StringIO()
    cmd_interactive(console=Console(file=buf, force_terminal=False))

    assert captured.get("called") is True


def test_interactive_examples_dispatch(examples_readme, monkeypatch):
    """Entering examples should prompt and dispatch to cmd_examples."""
    import io
    from rich.console import Console

    captured = {}

    def fake_examples(**kwargs):
        captured["skill_id"] = kwargs.get("skill_id")
        return 0

    monkeypatch.setattr("skillware.cli.cmd_examples", fake_examples)

    responses = iter(["examples", "", "q"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))

    buf = io.StringIO()
    cmd_interactive(console=Console(file=buf, force_terminal=False))

    assert captured.get("skill_id") is None


SAMPLE_EXAMPLES_README = """# Examples

## Runnable Scripts

| Script | Skill ID | Provider | Required extra | Required env vars | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `gemini_tos_evaluator.py` | `compliance/tos_evaluator` | Gemini | `[gemini]` | `GOOGLE_API_KEY` | Demo. |
| `ollama_skills_test.py` | `finance/wallet_screening`, `office/pdf_form_filler` | Ollama | `[office]` | None | Multi. |
"""


@pytest.fixture
def examples_readme(tmp_path, monkeypatch):
    readme = tmp_path / "examples" / "README.md"
    readme.parent.mkdir(parents=True)
    readme.write_text(SAMPLE_EXAMPLES_README, encoding="utf-8")
    monkeypatch.setattr("skillware.cli._examples_readme_path", lambda: readme)
    return readme


def test_parse_examples_index_handles_multi_skill_ids(examples_readme):
    rows = _parse_examples_index(examples_readme)
    assert len(rows) == 2
    assert rows[1]["skill_ids"] == [
        "finance/wallet_screening",
        "office/pdf_form_filler",
    ]


def test_example_counts_by_skill_includes_multi_skill_rows(examples_readme):
    rows = _parse_examples_index(examples_readme)
    counts = _example_counts_by_skill(rows)
    assert counts["compliance/tos_evaluator"] == 1
    assert counts["finance/wallet_screening"] == 1
    assert counts["office/pdf_form_filler"] == 1


def test_cmd_list_examples_column(tmp_path, examples_readme):
    import io
    from rich.console import Console

    _make_bundle(tmp_path, "compliance", "tos_evaluator")
    _make_bundle(tmp_path, "finance", "wallet_screening")
    _make_bundle(tmp_path, "office", "pdf_form_filler")
    _make_bundle(tmp_path, "data_engineering", "novelty_extractor")

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=200)
    cmd_list(
        skills_root_override=tmp_path,
        show_examples=True,
        console=console,
    )

    output = buf.getvalue()
    assert "EXAMPLES" in output
    assert "compliance" in output
    assert "finance" in output


def test_cmd_examples_lists_all_scripts(examples_readme):
    import io
    from rich.console import Console

    buf = io.StringIO()
    rc = cmd_examples(console=Console(file=buf, force_terminal=False, width=200))
    assert rc == 0
    output = buf.getvalue()
    assert "gemini_tos_evaluator.py" in output
    assert "ollama_skills_test.py" in output
    assert "Full notes:" in output
    assert "examples/README.md" in output


def test_cmd_examples_filters_by_skill_id(examples_readme):
    import io
    from rich.console import Console

    buf = io.StringIO()
    rc = cmd_examples(
        skill_id="compliance/tos_evaluator",
        console=Console(file=buf, force_terminal=False, width=200),
    )
    assert rc == 0
    output = buf.getvalue()
    assert "gemini_tos_evaluator.py" in output
    assert "ollama_skills_test.py" not in output


def test_example_github_url():
    url = _example_github_url("build_dataset_demo.py")
    assert url == (
        "https://github.com/ARPAHLS/skillware/blob/main/examples/build_dataset_demo.py"
    )


def test_cmd_examples_includes_github_links(examples_readme):
    import io
    from rich.console import Console

    buf = io.StringIO()
    cmd_examples(
        skill_id="compliance/tos_evaluator",
        console=Console(file=buf, force_terminal=False, width=220),
    )
    output = buf.getvalue()
    assert "gemini_tos_evaluator.py" in output
    assert "github.com/ARPAHLS/skillware/blob/main/examples/" in output


def test_cmd_examples_unknown_skill_returns_nonzero(examples_readme):
    rc = cmd_examples(skill_id="compliance/missing")
    assert rc == 1


def test_load_examples_index_prefers_local_readme(examples_readme):
    rows, source = _load_examples_index()
    assert len(rows) == 2
    assert source == examples_readme


def test_load_examples_index_github_fallback(monkeypatch):
    monkeypatch.setattr("skillware.cli._examples_readme_path", lambda: None)

    class FakeResponse:
        text = SAMPLE_EXAMPLES_README

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "skillware.cli.requests.get",
        lambda url, timeout: FakeResponse(),
    )

    rows, source = _load_examples_index()
    assert len(rows) == 2
    assert source == (
        "https://github.com/ARPAHLS/skillware/blob/main/examples/README.md"
    )


def test_load_examples_index_github_failure(monkeypatch):
    monkeypatch.setattr("skillware.cli._examples_readme_path", lambda: None)

    def raise_error(url, timeout):
        raise OSError("offline")

    monkeypatch.setattr("skillware.cli.requests.get", raise_error)

    rows, source = _load_examples_index()
    assert rows == []
    assert source is None


def test_main_examples_subcommand_exits_with_cmd_examples_code(monkeypatch):
    import sys
    from skillware.cli import main

    monkeypatch.setattr("skillware.cli.cmd_examples", lambda **kwargs: 0)

    argv = sys.argv
    sys.argv = ["skillware", "examples", "compliance/tos_evaluator"]
    try:
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
    finally:
        sys.argv = argv


def test_cmd_paths_shows_roots_and_tiers(tmp_path, monkeypatch):
    import io
    from rich.console import Console

    root = tmp_path / "skills"
    root.mkdir()
    skill_dir = root / "office" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.py").touch()
    (skill_dir / "manifest.yaml").write_text(
        "name: office/demo\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    assert cmd_paths(console=console) == 0

    output = buf.getvalue()
    assert "Skill path resolution" in output
    assert "project" in output
    assert "bundled" in output
    assert str(root) in output or "skills" in output.lower()
    assert " 1 " in output or output.rstrip().endswith("1")


def test_cmd_help_includes_paths_command():
    import io
    from rich.console import Console

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False)
    cmd_help(console=console)
    output = buf.getvalue()
    assert "skillware paths" in output
    assert "available now" in output
    assert "coming soon" not in output.lower()


def test_main_paths_subcommand(monkeypatch):
    import sys
    from skillware.cli import main

    monkeypatch.setattr("skillware.cli.cmd_paths", lambda **kwargs: 0)

    argv = sys.argv
    sys.argv = ["skillware", "paths"]
    try:
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
    finally:
        sys.argv = argv


def test_interactive_paths_dispatches(monkeypatch):
    import io
    from rich.console import Console

    responses = iter(["4", "q"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    cmd_interactive(console=console)

    output = buf.getvalue()
    assert "Skill path resolution" in output
    assert "not yet implemented" not in output.lower()
