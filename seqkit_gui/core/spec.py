# SPDX-License-Identifier: MIT
"""Data model for the generated seqkit schema."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import paths


@dataclass(frozen=True)
class Flag:
    name: str
    shorthand: str = ""
    type: str = "string"
    default: str = ""
    usage: str = ""
    usage_zh: str = ""
    widget: str = "text"
    options: tuple[str, ...] = ()
    required: bool = False
    hidden: bool = False

    @property
    def cli(self) -> str:
        return f"--{self.name}"

    @property
    def is_bool(self) -> bool:
        return self.widget == "bool"

    @property
    def is_list(self) -> bool:
        return self.widget == "list"

    @property
    def default_is_true(self) -> bool:
        return self.default.strip().lower() in {"true", "1", "yes", "on"}

    def describe(self, chinese: bool) -> str:
        if chinese and self.usage_zh:
            return self.usage_zh
        return self.usage


@dataclass(frozen=True)
class Inputs:
    kind: str = "files"
    min: int = 0
    max: int | None = None
    allow_stdin: bool = True
    allow_compressed: bool = True
    accept: str = ""

    @property
    def positional(self) -> bool:
        return self.kind in {"files", "paths"}


@dataclass(frozen=True)
class Command:
    path: tuple[str, ...]
    name: str
    group: str
    short: str
    short_zh: str
    long: str
    example: str
    inputs: Inputs
    flags: tuple[Flag, ...]
    global_flags: tuple[Flag, ...]
    aliases: tuple[str, ...] = ()
    hidden: bool = False
    runnable: bool = True
    requires_any: tuple[tuple[str, ...], ...] = ()
    requires_all: tuple[str, ...] = ()
    forbid_pairs: tuple[tuple[str, str], ...] = ()
    conditional: tuple[tuple[str, str], ...] = ()
    notes: tuple[str, ...] = ()
    evidence: str = ""

    @property
    def key(self) -> str:
        return " ".join(self.path[1:]) or self.name

    @property
    def display(self) -> str:
        return " ".join(self.path)

    @property
    def all_flags(self) -> tuple[Flag, ...]:
        seen: set[str] = set()
        out: list[Flag] = []
        for flag in (*self.flags, *self.global_flags):
            if flag.name not in seen and not flag.hidden:
                seen.add(flag.name)
                out.append(flag)
        return tuple(out)

    @property
    def required_names(self) -> frozenset[str]:
        names: set[str] = set(self.requires_all)
        for group in self.requires_any:
            names.update(group)
        return frozenset(names)

    def flag(self, name: str) -> Flag | None:
        for flag in self.all_flags:
            if flag.name == name:
                return flag
        return None

    def summary(self, chinese: bool) -> str:
        if chinese and self.short_zh:
            return self.short_zh
        return self.short

    def command_tokens(self) -> tuple[str, ...]:
        return tuple(self.path[1:]) or (self.name,)


@dataclass(frozen=True)
class Group:
    id: str
    title: str
    title_zh: str

    def label(self, chinese: bool) -> str:
        if chinese and self.title_zh:
            return self.title_zh
        return self.title


@dataclass(frozen=True)
class Schema:
    seqkit_version: str
    groups: tuple[Group, ...]
    commands: tuple[Command, ...]

    def get(self, key: str) -> Command | None:
        for command in self.commands:
            if command.key == key:
                return command
        return None

    @property
    def usable(self) -> tuple[Command, ...]:
        return tuple(item for item in self.commands if item.runnable and not item.hidden)

    def in_groups(self) -> list[tuple[Group, tuple[Command, ...]]]:
        buckets: dict[str, list[Command]] = {}
        for command in self.usable:
            buckets.setdefault(command.group, []).append(command)
        ordered: list[tuple[Group, tuple[Command, ...]]] = []
        for group in self.groups:
            items = tuple(sorted(buckets.pop(group.id, []), key=lambda item: item.name))
            if items:
                ordered.append((group, items))
        for leftover_id in sorted(buckets):
            # seqkit registers a few commands without a group; they need a heading of
            # their own that does not collide with the real "misc" group.
            group = Group(id=leftover_id or "other",
                          title="Other" if not leftover_id else leftover_id.replace("-", " ").title(),
                          title_zh="其他" if not leftover_id else "")
            ordered.append((group, tuple(sorted(buckets[leftover_id], key=lambda item: item.name))))
        return ordered

    @property
    def flag_entries(self) -> int:
        """Command-specific flag rows; global flags are counted separately."""
        return sum(len(command.flags) for command in self.commands)

    @property
    def global_flag_names(self) -> frozenset[str]:
        return frozenset(
            flag.name for command in self.commands for flag in command.global_flags
        )


def _flag(data: dict) -> Flag:
    return Flag(
        name=data["name"],
        shorthand=data.get("shorthand", "") or "",
        type=data.get("type", "string"),
        default=data.get("default", "") or "",
        usage=data.get("usage", "") or "",
        usage_zh=data.get("usage_zh", "") or "",
        widget=data.get("widget", "text"),
        options=tuple(data.get("options") or ()),
        required=bool(data.get("required")),
        hidden=bool(data.get("hidden")),
    )


def _inputs(data: dict) -> Inputs:
    return Inputs(
        kind=data.get("kind", "files"),
        min=int(data.get("min", 0) or 0),
        max=data.get("max"),
        allow_stdin=bool(data.get("allow_stdin", True)),
        allow_compressed=bool(data.get("allow_compressed", True)),
        accept=data.get("accept", "") or "",
    )


def _command(data: dict) -> Command:
    return Command(
        path=tuple(data["path"]),
        name=data["name"],
        group=data.get("group", ""),
        short=data.get("short", ""),
        short_zh=data.get("short_zh", ""),
        long=data.get("long", ""),
        example=data.get("example", ""),
        inputs=_inputs(data.get("inputs", {})),
        flags=tuple(_flag(item) for item in data.get("flags", [])),
        global_flags=tuple(_flag(item) for item in data.get("global_flags", [])),
        aliases=tuple(data.get("aliases") or ()),
        hidden=bool(data.get("hidden")),
        runnable=bool(data.get("runnable", True)),
        requires_any=tuple(tuple(group) for group in data.get("requires_any") or ()),
        requires_all=tuple(data.get("requires_all") or ()),
        forbid_pairs=tuple(tuple(pair) for pair in data.get("forbid_pairs") or ()),
        conditional=tuple(tuple(pair) for pair in data.get("conditional") or ()),
        notes=tuple(data.get("notes") or ()),
        evidence=data.get("evidence", ""),
    )


_CACHE: tuple[Schema, Path] | None = None


def load(path: Path | None = None, reload: bool = False) -> Schema:
    """Read ``data/commands.json``; regenerated by ``tools/extract_spec.py``."""
    global _CACHE
    target = Path(path) if path else paths.spec_path()
    if not reload and _CACHE and _CACHE[1] == target:
        return _CACHE[0]
    payload = json.loads(target.read_text(encoding="utf-8"))
    schema = Schema(
        seqkit_version=payload.get("seqkit_version", ""),
        groups=tuple(
            Group(id=item["id"], title=item["title"], title_zh=item.get("title_zh", ""))
            for item in payload.get("groups", [])
        ),
        commands=tuple(_command(item) for item in payload.get("commands", [])),
    )
    _CACHE = (schema, target)
    return schema
