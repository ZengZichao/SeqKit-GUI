"""The shipped parameter table must not carry any machine-local home directory.

``tools/spec-dumper`` records ``pflag``'s ``DefValue`` verbatim, and seqkit builds a
few of those defaults by expanding ``~`` while its command tree is constructed. The
normaliser in ``tools/extract_spec.py`` is what keeps the resulting absolute path --
which belongs to whoever ran the dumper -- out of the published schema, so both the
shipped file and the normaliser itself are guarded here.
"""

import json
import os
import re
import sys

import pytest

#: Anything that looks like a resolved home directory of a real account.
HOME_SHAPED = re.compile(
    r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]"
    r"|(?:^|[\s,;=\"'])/(?:home|Users|export/home)/"
    r"|%USERPROFILE%|os\.UserHomeDir",
    re.IGNORECASE,
)


@pytest.fixture(scope="module")
def generator(root):
    tools = str(root / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import extract_spec

    return extract_spec


def test_no_default_in_the_schema_is_home_rooted(schema):
    offenders = [
        (command.key, flag.name, flag.default)
        for command in schema.commands
        for flag in command.all_flags
        if HOME_SHAPED.search(flag.default or "")
    ]
    assert not offenders, f"machine-local defaults shipped: {offenders}"


def test_schema_file_holds_no_local_home(root):
    """Byte-level check of the committed file, independent of the loader."""
    path = root / "seqkit_gui" / "data" / "commands.json"
    text = path.read_text("utf-8")
    unescaped = text.replace("\\\\", "\\")  # JSON doubles every backslash
    assert re.search(r"[A-Za-z]:\\+(?:Users|home|Documents and Settings)", unescaped) is None
    assert "USERPROFILE" not in text
    home = os.path.expanduser("~")
    if len(home) > 3:
        for spelling in {home, home.replace("\\", "\\\\"), home.replace("\\", "/")}:
            assert spelling not in text, spelling
    assert json.loads(text)["seqkit_version"]


def test_genautocomplete_file_default_is_neutral(schema):
    command = next(c for c in schema.commands if c.name == "genautocomplete")
    flag = next(f for f in command.flags if f.name == "file")
    assert flag.default == "$HOME/.bash_completion.d/seqkit.sh"
    assert flag.usage == "autocompletion file"


@pytest.mark.parametrize(
    "raw, expected",
    [
        (r"C:\Users\nobody\.bash_completion.d\seqkit.sh",
         "$HOME/.bash_completion.d/seqkit.sh"),
        (r"D:\Documents and Settings\Bob\AppData\Local\x", "$HOME/AppData/Local/x"),
        ("/home/alice/.config/seqkit/rc", "$HOME/.config/seqkit/rc"),
        ("/Users/carol/.zfunc/_seqkit", "$HOME/.zfunc/_seqkit"),
        ("/export/home/dave/.seqkit.conf", "$HOME/.seqkit.conf"),
        (r"-e C:\Users\someone\x", "-e $HOME/x"),
        ("%USERPROFILE%\\seqkit.sh", "$HOME/seqkit.sh"),
        ("~/.bash_completion.d/seqkit.sh", "$HOME/.bash_completion.d/seqkit.sh"),
        ("$HOME/.bash_completion.d/seqkit.sh", "$HOME/.bash_completion.d/seqkit.sh"),
    ],
)
def test_home_rooted_defaults_are_neutralised(generator, raw, expected):
    got = generator.neutralise_home(raw)
    assert got == expected
    assert HOME_SHAPED.search(got) is None
    # Running the generator twice must not keep rewriting the value.
    assert generator.neutralise_home(got) == got


@pytest.mark.parametrize(
    "value",
    [r"^(\S+)\s?", r"^(.+)_sliding:(\d+)-(\d+)", "auto", "-1", "10000", "a,b,c", "",
     "[#,//]", "./", "false", "seqkit"],
)
def test_literal_defaults_survive_untouched(generator, value):
    """Regex defaults legitimately contain backslashes; they are not paths."""
    assert generator.neutralise_home(value) == value


def test_home_of_the_machine_running_the_generator_is_stripped(generator, monkeypatch):
    """The dumper and the generator usually run on the same box, so the local home
    directory is a second, account-name-specific way to recognise a leak -- and it
    also catches a bare home directory the generic pattern cannot anchor on."""
    monkeypatch.setenv("USERPROFILE", r"C:\Users\nobody")
    assert generator.neutralise_home(r"C:\Users\nobody") == "$HOME"
    got = generator.neutralise_home(r"C:\Users\nobody\.seqkit\config.yaml")
    assert got == "$HOME/.seqkit/config.yaml"
    assert HOME_SHAPED.search(got) is None


def test_normalise_end_to_end_keeps_every_other_field(generator):
    """A tainted raw dump goes through the real pipeline and comes out neutral."""
    raw = {
        "seqkit_version": "2.14.0",
        "groups": [{"id": "utility", "title": "Commands for Utility:"}],
        "commands": [
            {
                "name": "genautocomplete",
                "path": ["seqkit", "genautocomplete"],
                "short": "generate shell autocompletion script",
                "use": "genautocomplete",
                "use_line": "seqkit genautocomplete",
                "runnable": True,
                "flags": [
                    {"name": "file", "type": "string",
                     "default": r"C:\Users\someone\.bash_completion.d\seqkit.sh",
                     "usage": "autocompletion file"},
                    {"name": "shell", "type": "string", "default": "bash",
                     "usage": "autocompletion type (bash|zsh|fish|powershell)"},
                ],
                "global_flags": [
                    {"name": "threads", "shorthand": "j", "type": "int", "default": "4",
                     "usage": "number of CPU threads to use simultaneously"},
                ],
            }
        ],
    }
    payload, _ = generator.normalise(raw)
    flags = payload["commands"][0]["flags"]
    assert flags[0]["default"] == "$HOME/.bash_completion.d/seqkit.sh"
    assert flags[0]["widget"] == "in_file"
    # Untouched fields keep their dumped values.
    assert flags[1]["default"] == "bash"
    assert flags[1]["options"] == ["bash", "zsh", "fish", "powershell"]
    assert payload["commands"][0]["global_flags"][0]["default"] == "4"
    assert payload["commands"][0]["evidence"] == "genautocomplete.go:66-86"
