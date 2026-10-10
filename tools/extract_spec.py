#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regenerate ``seqkit_gui/data/commands.json`` from the seqkit source.

Pipeline::

    seqkit source --(tools/spec-dumper)--> spec_raw.json --(this script)--> commands.json

``spec-dumper`` walks seqkit's own cobra tree, so flag names, shorthands, types and
defaults cannot drift from the CLI. Everything this script adds is either a widget
hint or a usage contract read out of the matching command's ``Run`` body; the file
and line that the contract came from is recorded next to it.

Usage::

    python tools/extract_spec.py            # normalise the cached raw dump
    python tools/extract_spec.py --build    # rebuild the raw dump first (needs Go)

``--seqkit-src`` points at an unpacked seqkit source tree (the default is the
``seqkit-2.14.0`` folder next to this project).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
RAW = TOOLS / "_build" / "spec_raw.json"
OUTPUT = ROOT / "seqkit_gui" / "data" / "commands.json"
WORKLIST = TOOLS / "_build" / "translation_worklist.json"
USAGE_ZH = TOOLS / "translations" / "usage_zh.json"
COMMAND_ZH = TOOLS / "translations" / "command_zh.json"

# ---------------------------------------------------------------------------
# Which widget a flag renders as. Names come from the flags seqkit registers;
# anything not listed falls back to a plain text field.
# ---------------------------------------------------------------------------
INPUT_FILE_FLAGS = {
    "primer-file", "pattern-file", "bed", "gtf", "kv-file", "fasta-file",
    "query-fastx", "region-file", "read1", "read2", "infile-list", "file",
    "top-bam", "seq-file", "out-bam", "log", "dup-num-file", "dup-seqs-file",
    "save-unmatched", "img",
}
OUTPUT_FILE_FLAGS = {"out-file", "out-bam", "img", "log", "dup-num-file",
                     "dup-seqs-file", "save-unmatched", "file"}
DIR_FLAGS = {"out-dir", "tmp-dir"}

# ---------------------------------------------------------------------------
# Some defaults are not literals in seqkit's source but the result of resolving
# ``~`` against the home directory while the command tree is built -- cobra's
# ``flag.DefValue`` therefore carries whatever absolute path spec-dumper ran on.
# Neutralising it here keeps the published parameter table from freezing the
# maintainer's account name into a value every user would then be shown.
# ---------------------------------------------------------------------------
HOME_TOKEN = "$HOME"

_HOME_PATH_RE = re.compile(
    # <drive>:\Users\<name>\  <drive>:/Documents and Settings/<name>/
    r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/:*?\"<>|]+[\\/]"
    # /home/<user>/  /Users/<user>/  /export/home/<user>/
    r"|\A/(?:home|Users|export/home)/[^/\s]+/"
    r"|(?<=[\s,;=\"'])/(?:home|Users|export/home)/[^/\s]+/"
)

# Already-relative spellings of the same thing, collapsed onto one rendering.
_HOME_ENV_RE = re.compile(
    r"(?:%USERPROFILE%|%HOMEPATH%|\$\{?(?:HOME|HOMEPATH|USERPROFILE)\}?|~)(?=[\\/])",
    re.IGNORECASE)


def _local_home_dir() -> str:
    """Home directory of the machine running this script, for residue matching."""
    for key in ("USERPROFILE", "HOME"):
        value = os.environ.get(key, "")
        if value:
            return value.rstrip("\\/")
    return ""


def neutralise_home(value: str) -> str:
    """Rewrite any home-rooted default to a ``$HOME/``-relative spelling."""
    if not isinstance(value, str) or not value:
        return value
    out, hits = _HOME_PATH_RE.subn(HOME_TOKEN + "/", value)
    local_home = _local_home_dir()
    if local_home and local_home in out:
        out = out.replace(local_home + "\\", HOME_TOKEN + "/")
        out = out.replace(local_home + "/", HOME_TOKEN + "/")
        out = out.replace(local_home, HOME_TOKEN)
        hits += 1
    env_out = _HOME_ENV_RE.sub(HOME_TOKEN, out)
    if env_out != out:
        out, hits = env_out, hits + 1
    # A home path was present: render it with forward slashes so the schema no
    # longer states which OS the dumper ran on.
    return out.replace("\\", "/") if hits else value


# ---------------------------------------------------------------------------
# Positional-argument contract and required flags, read from each command's Run
# body in the seqkit source (file:line recorded in ``evidence``).
#
# kind: files      -- sequence files, STDIN when omitted
#       paths      -- files or directories, walked recursively
#       none       -- the command rejects positional arguments
# ---------------------------------------------------------------------------
CONTRACTS: dict[str, dict] = {
    "amplicon": {
        "inputs": {"kind": "files"},
        "requires_any": [["bed", "primer-file", "forward", "reverse"]],
        "evidence": "amplicon.go:124,695",
        "notes": ["primer-file 与 forward/reverse 二选一；--bed 从 BED 文件读取引对"],
    },
    "bam": {
        "inputs": {"kind": "files", "accept": "bam|sam"},
        "requires_any": [["stat", "idx-stat", "idx-count", "count", "grep-ids",
                         "dump", "top-bam", "tool", "list-fields"]],
        "evidence": "bam.go:516,523 + Long text",
        "notes": ["--stat/--idx-stat 可多文件，其余模式只接受一个 BAM/SAM 文件"],
    },
    "common": {
        "inputs": {"kind": "files", "min": 2},
        "conditional": [["only-positive-strand", "by-seq"], ["check-embedded-seqs", "by-seq"]],
        "evidence": "common.go:92-102",
        "notes": ["至少 2 个文件"],
    },
    "concat": {"inputs": {"kind": "files", "min": 2}, "evidence": "concat.go:73-76",
               "notes": ["至少 2 个文件"]},
    "convert": {"inputs": {"kind": "files"}, "evidence": "convert.go:68",
                "notes": ["无法推断来源编码时需显式指定 --from"]},
    "duplicate": {"inputs": {"kind": "files"}, "evidence": "dup.go:56"},
    "fa2fq": {
        "inputs": {"kind": "files"},
        "requires_all": ["fasta-file"],
        "evidence": "fa2fq.go:61,65",
        "notes": ["--fasta-file 必填，位置参数为 FASTQ 文件"],
    },
    "faidx": {
        "inputs": {"kind": "files", "min": 1, "allow_stdin": False, "allow_compressed": False},
        "evidence": "faidx.go:78-93",
        "notes": ["不支持 stdin，也不支持 gz/xz/zst 压缩文件"],
    },
    "fish": {
        "inputs": {"kind": "files"},
        "requires_any": [["query-fastx", "query-sequences"]],
        "evidence": "fish.go:143-144",
    },
    "fq2fa": {"inputs": {"kind": "files"}, "evidence": "fq2fa.go:56"},
    "fx2tab": {"inputs": {"kind": "files"}, "evidence": "fx2tab.go:69"},
    "genautocomplete": {
        "inputs": {"kind": "none"},
        "evidence": "genautocomplete.go:66-86",
        "notes": ["生成 shell 自动补全脚本，无输入文件"],
    },
    "grep": {
        "inputs": {"kind": "files"},
        "requires_any": [["pattern", "pattern-file"]],
        "evidence": "grep.go:106,133",
    },
    "head": {"inputs": {"kind": "files"}, "evidence": "head.go:79"},
    "head-genome": {"inputs": {"kind": "files"}, "evidence": "head-genome.go:73"},
    "locate": {
        "inputs": {"kind": "files"},
        "requires_any": [["pattern", "pattern-file"]],
        "forbid_pairs": [["degenerate", "max-mismatch"], ["use-regexp", "max-mismatch"]],
        "evidence": "locate.go:80,109,130-133",
    },
    "merge-slides": {"inputs": {"kind": "files"}, "evidence": "merge-slides.go:97,117",
                     "notes": ["输出文件不能是输入文件之一"]},
    "mutate": {
        "inputs": {"kind": "files"},
        "requires_any": [["point", "insertion", "deletion", "pattern", "pattern-file"]],
        "forbid_pairs": [["insertion", "deletion"]],
        "evidence": "mutate.go:83-135,99",
    },
    "pair": {
        "inputs": {"kind": "none"},
        "requires_all": ["read1", "read2"],
        "evidence": "pair.go:81-92",
        "notes": ["不接受位置参数，用 -1/--read1 与 -2/--read2 指定双端文件"],
    },
    "range": {"inputs": {"kind": "files"}, "requires_all": ["range"], "evidence": "range.go:69,93"},
    "rename": {"inputs": {"kind": "files"}, "evidence": "rename.go:75"},
    "replace": {
        "inputs": {"kind": "files"},
        "requires_any": [["pattern", "f-pattern"]],
        "conditional": [["keep-key", "pattern"]],
        "evidence": "replace.go:110,131,167",
    },
    "restart": {
        "inputs": {"kind": "files"},
        "requires_any": [["new-start", "start-with"]],
        "evidence": "restart.go:87,97",
    },
    "rmdup": {
        "inputs": {"kind": "files"},
        "conditional": [["only-positive-strand", "by-seq"]],
        "evidence": "rmdup.go:81,84",
    },
    "sample": {
        "inputs": {"kind": "files", "max": 1},
        "requires_any": [["number", "proportion"]],
        "evidence": "sample.go:66-67,105",
    },
    "sample2": {
        "inputs": {"kind": "files", "max": 1},
        "requires_any": [["number", "proportion"]],
        "evidence": "sample2.go:68-69,107",
    },
    "sana": {"inputs": {"kind": "files"}, "evidence": "sana.go:90"},
    "scat": {
        "inputs": {"kind": "paths", "min": 1},
        "evidence": "scat.go:109,132",
        "notes": ["位置参数是目录或文件列表，目录会被递归读取"],
    },
    "seq": {
        "inputs": {"kind": "files"},
        "forbid_pairs": [["lower-case", "upper-case"], ["dna2rna", "rna2dna"]],
        "evidence": "seq.go:139",
    },
    "shuffle": {
        "inputs": {"kind": "files"},
        "conditional": [["keep-temp", "two-pass"], ["update-faidx", "two-pass"]],
        "evidence": "shuffle.go:73,99-102,177",
        "notes": ["--two-pass 模式下只接受一个文件"],
    },
    "sliding": {"inputs": {"kind": "files"}, "requires_all": ["step", "window"],
                "evidence": "sliding.go:53,65"},
    "sort": {
        "inputs": {"kind": "files"},
        "conditional": [["keep-temp", "two-pass"], ["update-faidx", "two-pass"]],
        "evidence": "sort.go:77,265",
        "notes": ["--two-pass 模式下只接受一个文件"],
    },
    "split": {
        "inputs": {"kind": "files", "max": 1},
        "requires_any": [["by-size", "by-part", "by-id", "by-region"]],
        "conditional": [["keep-temp", "two-pass"], ["update-faidx", "two-pass"]],
        "evidence": "split.go:78-79,95,108-111,1037",
    },
    "split2": {
        "inputs": {"kind": "files", "max": 1},
        "requires_any": [["by-size", "by-part", "by-length"]],
        "evidence": "split2.go:81-82,153,200-206",
        "notes": ["双端数据用 -1/--read1 与 -2/--read2；配对时输出前缀需含 {read}"],
    },
    "stats": {"inputs": {"kind": "files"}, "evidence": "stat.go:145"},
    "subseq": {
        "inputs": {"kind": "files"},
        "requires_any": [["region", "bed", "gtf"]],
        "forbid_pairs": [["bed", "feature"], ["only-flank", "up-stream"]],
        "evidence": "subseq.go:80,115-124,195,220",
    },
    "sum": {"inputs": {"kind": "files"}, "evidence": "sum.go:114"},
    "tab2fx": {"inputs": {"kind": "files"}, "evidence": "tab2fx.go:49,104"},
    "translate": {"inputs": {"kind": "files"}, "evidence": "translate.go:165"},
    "version": {"inputs": {"kind": "none"}, "evidence": "version.go:71",
                "notes": ["打印版本信息，可选 --check-update 联网检查更新"]},
    "watch": {
        "inputs": {"kind": "files", "min": 1},
        "evidence": "watch.go:167,65,139",
        "notes": ["实时监控正在写入的文件，只接受一个字段，需手动停止"],
    },
}


def widget_for(flag: dict, command_name: str) -> str:
    name, type_ = flag["name"], flag["type"]
    if type_ in {"bool"}:
        return "bool"
    if type_ in {"int", "int64", "int32", "uint", "uint64", "count"}:
        return "int"
    if type_ in {"float32", "float64"}:
        return "float"
    if type_ in {"stringSlice", "stringArray", "intSlice", "float64Slice"}:
        return "list"
    if name in DIR_FLAGS:
        return "dir"
    if name in OUTPUT_FILE_FLAGS and command_name != "genautocomplete":
        return "out_file"
    if name == "seq-type":
        return "enum"
    if name in INPUT_FILE_FLAGS:
        return "in_file"
    if enum_options(flag["usage"]):
        return "enum"
    return "text"


_ENUM_RE = re.compile(r"\(([^()]*(?:\|[^()]*)+)\)")
_TOKEN_RE = re.compile(r"[\w.,:/@{}*+-]{1,24}")


def enum_options(usage: str) -> list[str]:
    """Choices seqkit lists inside parentheses in the flag's own usage text."""
    for match in _ENUM_RE.finditer(usage):
        options = [item.strip() for item in match.group(1).split("|")]
        if 2 <= len(options) <= 16 and all(_TOKEN_RE.fullmatch(item) for item in options):
            return options
    return []


def load_raw(build: bool, seqkit_src: Path | None) -> dict:
    if build or not RAW.is_file():
        dumper = TOOLS / "spec-dumper"
        env = dict(os.environ)
        env.setdefault("GOPROXY", "https://goproxy.cn,https://proxy.golang.org,direct")
        env["GOFLAGS"] = "-mod=mod"
        RAW.parent.mkdir(parents=True, exist_ok=True)
        if seqkit_src:
            subprocess.run(
                ["go", "mod", "edit", f"-replace=github.com/shenwei356/seqkit/v2=>{seqkit_src}"],
                cwd=dumper, env=env, check=True,
            )
        result = subprocess.run(["go", "run", "."], cwd=dumper, env=env,
                                stdout=subprocess.PIPE, check=True)
        # The dumper prints the JSON on stdout (progress goes to stderr), so the
        # capture lands in the file directly instead of through a stream handle.
        RAW.write_bytes(result.stdout)
    return json.loads(RAW.read_text(encoding="utf-8"))


def _text(value) -> str:
    """Translation tables hold either a string or a {"short": ...} record."""
    if isinstance(value, dict):
        value = value.get("short", "")
    return str(value or "").strip().rstrip(":：").strip()


def read_translations(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _flag_records(flags: list[dict], command_name: str,
                  usage_zh: dict) -> tuple[list[dict], list[str]]:
    """One normalised row per dumped pflag, plus the usages still untranslated."""
    records = []
    untranslated = []
    for flag in flags:
        usage = flag["usage"]
        if usage not in usage_zh:
            untranslated.append(usage)
        records.append({
            "name": flag["name"],
            "shorthand": flag.get("shorthand", ""),
            "type": flag["type"],
            "default": neutralise_home(flag["default"]),
            "usage": usage,
            "usage_zh": usage_zh.get(usage, ""),
            "widget": widget_for(flag, command_name),
            "options": enum_options(usage),
            "required": bool(flag.get("required")),
            "hidden": bool(flag.get("hidden")),
        })
    return records, untranslated


def normalise(raw: dict) -> tuple[dict, list[str]]:
    usage_zh = read_translations(USAGE_ZH)
    command_zh = read_translations(COMMAND_ZH)
    worklist: list[str] = []

    commands = []
    for entry in raw["commands"]:
        contract = CONTRACTS.get(entry["name"], {"inputs": {"kind": "files"}})
        inputs = dict({"kind": "files", "min": 0, "max": None, "allow_stdin": True,
                       "accept": "fasta|fastq|fa|fq(+ compressed)"}, **contract["inputs"])
        flags, untranslated = _flag_records(entry["flags"], entry["name"], usage_zh)
        globals_, untranslated_globals = _flag_records(
            entry.get("global_flags", []), entry["name"], usage_zh)
        worklist.extend(untranslated + untranslated_globals)

        zh = command_zh.get(entry["name"], {})
        commands.append({
            "path": entry["path"],
            "name": entry["name"],
            "group": entry.get("group", ""),
            "aliases": entry.get("aliases", []),
            "short": entry["short"],
            "short_zh": _text(zh),
            "long": entry.get("long", ""),
            "example": entry.get("example", ""),
            "hidden": bool(entry.get("hidden")),
            "runnable": bool(entry.get("runnable", True)),
            "inputs": inputs,
            "requires_any": contract.get("requires_any", []),
            "requires_all": contract.get("requires_all", []),
            "forbid_pairs": contract.get("forbid_pairs", []),
            "conditional": contract.get("conditional", []),
            "notes": contract.get("notes", []),
            "evidence": contract.get("evidence", ""),
            "flags": flags,
            "global_flags": globals_,
        })

    payload = {
        "seqkit_version": raw["seqkit_version"],
        "generator": "tools/extract_spec.py + tools/spec-dumper",
        "groups": [
            {**group, "title_zh": _text(command_zh.get("group:" + group["id"]))
                            or group["title"].rstrip(":").strip()}
            for group in raw["groups"]
        ],
        "commands": commands,
    }
    return payload, sorted(set(worklist))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="run the Go dumper first")
    parser.add_argument("--seqkit-src", type=Path, default=None)
    args = parser.parse_args()

    raw = load_raw(args.build, args.seqkit_src)
    payload, worklist = normalise(raw)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    WORKLIST.parent.mkdir(parents=True, exist_ok=True)
    WORKLIST.write_text(json.dumps(worklist, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    flag_count = sum(len(item["flags"]) for item in payload["commands"])
    global_count = sum(len(item["global_flags"]) for item in payload["commands"])
    print(f"commands: {len(payload['commands'])}  "
          f"local flags: {flag_count}  inherited flags: {global_count}")
    print(f"unique usage strings: {len(worklist)}")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    missing = [item["name"] for item in payload["commands"] if not item["short_zh"]]
    if missing:
        print(f"commands without Chinese summary: {len(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
