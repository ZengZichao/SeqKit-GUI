"""Argument assembly: the GUI's only real job, so it is tested against the CLI."""

import pytest

from seqkit_gui.core.builder import FlagState, RunRequest, build_argv, display_command, validate


@pytest.fixture
def request_for(schema):
    def make(key, *, inputs=(), flags=None, extra=""):
        command = schema.get(key)
        assert command is not None, key
        states = {}
        for name, value in (flags or {}).items():
            flag = command.flag(name)
            assert flag is not None, (key, name)
            if isinstance(value, bool):
                states[name] = FlagState(enabled=value, value="true" if value else "")
            elif isinstance(value, (list, tuple)):
                states[name] = FlagState(enabled=True, items=tuple(str(item) for item in value))
            else:
                states[name] = FlagState(enabled=True, value=str(value))
        return RunRequest(command=command, inputs=tuple(inputs), flags=states, extra_args=extra)
    return make


def test_command_tokens_come_first(request_for):
    argv = build_argv(request_for("grep", flags={"pattern": "seq1"}))
    assert argv == ["grep", "--pattern", "seq1"]


def test_positional_files_are_appended_last(request_for, sample_fasta):
    argv = build_argv(request_for("stats", inputs=[str(sample_fasta)]))
    assert argv[0] == "stats"
    assert argv[-1] == str(sample_fasta)


def test_bool_flags_are_only_emitted_when_checked(request_for):
    off = build_argv(request_for("seq", flags={"lower-case": False}))
    on = build_argv(request_for("seq", flags={"lower-case": True}))
    assert "--lower-case" not in off
    assert "--lower-case" in on


def test_repeatable_list_flags_become_repeated_options(request_for):
    argv = build_argv(request_for("grep", flags={"pattern": ["seq1", "seq2"]}))
    assert argv == ["grep", "--pattern", "seq1", "--pattern", "seq2"]


def test_integer_and_float_flags_are_passed_as_strings(request_for):
    argv = build_argv(request_for("sample", flags={"number": 100, "rand-seed": 42}))
    assert argv[argv.index("--number") + 1] == "100"
    assert argv[argv.index("--rand-seed") + 1] == "42"
    argv = build_argv(request_for("fish", flags={"min-qual": 30.5}))
    assert argv[argv.index("--min-qual") + 1] == "30.5"


def test_value_starting_with_dash_uses_equals_form(request_for):
    argv = build_argv(request_for("grep", flags={"pattern": "-1"}))
    assert "--pattern=-1" in argv


def test_global_flags_are_supported(request_for, sample_fasta):
    argv = build_argv(request_for("stats", inputs=[str(sample_fasta)],
                                  flags={"threads": 2, "out-file": "out.tsv",
                                         "seq-type": "dna"}))
    assert "--threads" in argv and "2" in argv
    assert argv[argv.index("--out-file") + 1] == "out.tsv"
    assert argv[argv.index("--seq-type") + 1] == "dna"


def test_extra_arguments_are_split_not_evaluated(request_for):
    argv = build_argv(request_for("fq2fa", extra='--by-seq --seq-type dna'))
    assert argv == ["fq2fa", "--by-seq", "--seq-type", "dna"]


def test_file_paths_with_spaces_stay_single_arguments(request_for):
    path = "C:/tmp/my reads 1.fa"
    argv = build_argv(request_for("stats", inputs=[path]))
    assert argv[-1] == path
    assert path in display_command("seqkit", argv)


def test_nested_command_tokens_are_preserved(schema):
    """Sub-command paths in the schema must serialise to every token but 'seqkit'."""
    for command in schema.commands:
        tokens = command.command_tokens()
        assert tokens[0] == command.name
        assert "seqkit" not in tokens


IDENTITY = lambda key, **fmt: key.format(**fmt) if fmt else key


def test_validation_blocks_grep_without_pattern(request_for):
    problems = validate(request_for("grep"))
    assert not problems.ok
    messages = problems.messages(IDENTITY)
    assert any("--pattern" in message for message in messages)
    assert problems.problem_flags == {"pattern", "pattern-file"}


def test_validation_allows_grep_with_pattern_file(request_for):
    assert validate(request_for("grep", flags={"pattern-file": "ids.txt"})).ok


def test_validation_requires_both_step_and_window(request_for):
    assert not validate(request_for("sliding", flags={"step": 10})).ok
    assert validate(request_for("sliding", flags={"step": 10, "window": 100})).ok


def test_validation_counts_input_files(schema, request_for, sample_fasta):
    assert validate(request_for("common", inputs=[str(sample_fasta)])).ok is False
    two = request_for("common", inputs=[str(sample_fasta), str(sample_fasta)])
    assert validate(two).ok


def test_validation_rejects_too_many_files(request_for, sample_fasta):
    assert not validate(request_for("sample", inputs=[str(sample_fasta), str(sample_fasta)])).ok


def test_validation_rejects_positional_files_for_pair(request_for, sample_fasta):
    assert not validate(request_for("pair", inputs=[str(sample_fasta)])).ok


def test_validation_flags_mutually_exclusive_flags(request_for, sample_fasta):
    problems = validate(request_for("seq", inputs=[str(sample_fasta)],
                                    flags={"lower-case": True, "upper-case": True}))
    assert not problems.ok
    assert any("lower-case" in message for message in problems.messages(IDENTITY))


def test_validation_requires_read1_and_read2(request_for):
    assert not validate(request_for("pair")).ok
    assert validate(request_for("pair", flags={"read1": "a.fq", "read2": "b.fq"})).ok


def test_every_command_builds_a_argv(schema, request_for, sample_fasta):
    """No command may produce an empty or malformed argument vector."""
    for command in schema.usable:
        argv = build_argv(request_for(command.key, inputs=[str(sample_fasta)]))
        assert argv and argv[0] == command.name, command.key
        assert all(isinstance(item, str) and item != "" for item in argv), command.key
