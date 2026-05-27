from skillware.cli import (
    _discover_skills,
    cmd_list,
    cmd_interactive,
    _short_description,
)


def test_discover_skills_returns_skills(tmp_path):
    # Create a fake skill directory structure
    skill_dir = tmp_path / "office" / "pdf_form_filler"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.py").touch()

    manifest = skill_dir / "manifest.yaml"
    manifest.write_text(
        "name: pdf_form_filler\n"
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
        "name: pdf_form_filler\n"
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
        "name: pdf_form_filler\n"
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
            f"name: {name}\nversion: 0.1.0\ndescription: Test.\n"
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
