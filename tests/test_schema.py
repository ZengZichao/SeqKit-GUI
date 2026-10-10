"""The generated schema must cover every seqkit 2.14.0 subcommand exactly."""

import json

from seqkit_gui.core import paths
from seqkit_gui.core.spec import load


def test_schema_lists_every_subcommand_from_the_cli(schema, seqkit_binary):
    """Command names must equal what seqkit itself advertises in its help."""
    listed = cli_command_names(seqkit_binary)
    schema_names = {command.name for command in schema.commands}
    aliases = {alias for command in schema.commands for alias in command.aliases}
    assert listed - schema_names - aliases == set()
    assert listed, "seqkit reported no subcommands"
    # Every name the schema claims must really exist in the CLI.
    for command in schema.commands:
        assert command.name in listed or command.name in aliases, command.name
    assert len(schema.usable) == len(listed)


def cli_command_names(binary) -> set[str]:
    """Subcommand names from cobra's own completion list, not parsed help text."""
    import subprocess

    done = subprocess.run([str(binary), "__complete", ""], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    names = set()
    for line in (done.stdout or "").splitlines():
        if not line or line.startswith(":"):
            continue
        head = line.split("\t", 1)[0].strip()
        if head and " " not in head:
            names.add(head)
    if names:
        return names
    raise AssertionError("could not read the subcommand list from seqkit")


def test_every_command_help_is_reachable(schema, seqkit_binary):
    """Each schema entry must correspond to a real, documented CLI command."""
    import subprocess

    for command in schema.commands:
        done = subprocess.run([str(seqkit_binary), *command.command_tokens(), "--help"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert done.returncode == 0, (command.key, done.stderr[:200])
        assert "Usage:" in done.stdout or "Flags:" in done.stdout, command.key
        for flag in command.flags:
            if flag.shorthand:
                assert f"-{flag.shorthand}, --{flag.name}" in done.stdout or \
                       f"-{flag.shorthand}, " in done.stdout, (command.key, flag.name)


def test_flag_names_appear_in_cli_help(schema, seqkit_binary):
    """A spot check that the dumper's flag names are the ones the CLI accepts."""
    import subprocess

    for command in list(schema.commands)[:12]:
        done = subprocess.run([str(seqkit_binary), *command.command_tokens(), "--help"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        for flag in command.flags:
            assert f"--{flag.name}" in done.stdout, (command.key, flag.name)


def test_schema_version_matches_source(schema):
    assert schema.seqkit_version == "2.14.0"


def test_schema_surface_has_a_pinned_size(schema):
    """41 subcommands, 353 of their own flags, 11 inherited ones and 8 groups is
    the whole surface of seqkit 2.14.0. A generator change must not silently move
    any of these counts -- only ``default`` values are allowed to be rewritten."""
    assert len(schema.commands) == 41
    assert sum(len(command.flags) for command in schema.commands) == 353
    assert len({flag.name for command in schema.commands
                for flag in command.global_flags}) == 11
    assert len(schema.groups) == 8


def test_every_command_has_flags_and_groups(schema):
    assert schema.groups, "command groups are required by the sidebar"
    for command in schema.commands:
        assert command.path[0] == "seqkit"
        assert command.short, command.key
        assert isinstance(command.flags, tuple)
        assert command.inputs.kind in {"files", "paths", "none"}


def test_flag_records_are_wellformed(schema):
    for command in schema.commands:
        for flag in command.all_flags:
            assert flag.name
            assert flag.widget in {
                "bool", "int", "float", "text", "enum", "list",
                "in_file", "out_file", "dir",
            }, (command.key, flag.name, flag.widget)
            if flag.widget == "enum":
                assert flag.options, (command.key, flag.name)
            assert flag.usage, (command.key, flag.name)


def test_global_flags_reach_every_command(schema):
    """The eleven root persistent flags must be offered by every subcommand."""
    names = {"seq-type", "threads", "line-width", "id-regexp", "id-ncbi", "out-file",
             "quiet", "alphabet-guess-seq-length", "infile-list", "skip-file-check",
             "compress-level"}
    for command in schema.commands:
        available = {flag.name for flag in command.all_flags}
        assert names <= available, (command.key, names - available)


def test_usage_strings_are_translated(schema):
    """Chinese help text is part of the deliverable, not optional polish."""
    untranslated = [
        (command.key, flag.name)
        for command in schema.commands
        for flag in command.all_flags
        if not flag.usage_zh
    ]
    assert not untranslated, f"{len(untranslated)} flags without Chinese description"
    missing_summary = [command.key for command in schema.commands if not command.short_zh]
    assert not missing_summary, missing_summary


def test_chinese_translation_is_not_the_english_original(schema):
    for command in schema.commands:
        for flag in command.all_flags:
            if flag.usage_zh:
                assert flag.usage_zh != flag.usage, (command.key, flag.name)
                assert any("\u4e00" <= char <= "\u9fff" for char in flag.usage_zh), \
                    (command.key, flag.name, flag.usage_zh)


def test_input_contracts_are_recorded_with_source_evidence(schema):
    for command in schema.commands:
        assert command.evidence, f"{command.key} has no source reference for its contract"


def test_schema_file_is_committed(root):
    payload = json.loads((root / "seqkit_gui" / "data" / "commands.json").read_text("utf-8"))
    assert payload["seqkit_version"]
    assert len(payload["commands"]) == len(load().commands)


def test_generated_from_dumper_not_handwritten(root):
    assert paths.spec_path().is_file()
    assert (root / "tools" / "spec-dumper" / "main.go").is_file()
