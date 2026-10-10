# Third-party licenses

SeqKit GUI itself is released under the **MIT** licence -- SPDX identifier
`MIT`, copyright line `Copyright (c) 2026 SeqKit GUI contributors`, full text in
[`LICENSE`](LICENSE). Those three spellings (this file, `LICENSE`, and the
`license` field of `pyproject.toml`) are checked against each other by
`python tools/license_check.py` (check 2).
This file records the third-party components the project depends on, drives, or
refers to, and the notices that must be preserved.

Every Python file in the repository carries a one-line
`# SPDX-License-Identifier: MIT` header and no licence body: MIT's condition is a
notice, not the text in each file, and `LICENSE` plus this file are where the
notices live.

SeqKit GUI implements no bioinformatics logic of its own: it assembles an
argument vector and runs the `seqkit` executable as a child process (`QProcess`),
streaming its stdout/stderr into the UI. Everything below follows from that.

---

## SeqKit (upstream command-line toolkit) -- MIT

- Project: **SeqKit** by Wei Shen (`shenwei356`)
- Homepage: <https://github.com/shenwei356/seqkit>
- Upstream documentation: <https://bioinf.shenwei.me/seqkit/>
- Recommended citation for 2.14.0, quoted from the "Citation" section of the
  SeqKit 2.14.0 README, which names this single article:

  > Wei Shen\*, Botond Sipos, and Liuyang Zhao. 2024. *SeqKit2: A Swiss Army
  > Knife for Sequence and Alignment Processing.* ***iMeta*** e191.
  > doi:10.1002/imt2.191 (<https://doi.org/10.1002/imt2.191>)

  That DOI resolves (HTTP 302 via the doi.org registrar to the Wiley record) and
  the Crossref record for `10.1002/imt2.191` carries type
  `journal-article`, title *SeqKit2: A Swiss army knife for sequence and
  alignment processing*, authors Wei Shen / Botond Sipos / Liuyang Zhao and
  container-title *iMeta*, published 2024. No NAR / `gkac…` DOI belongs to
  SeqKit 2.x and none is cited here.
- Version targeted by this GUI: **2.14.0** (all 41 subcommands)
- Role here: a separate, externally supplied program that the GUI invokes. The
  SeqKit binary is **not** committed to this repository and is not redistributed
  by it; users provide it themselves (a configured path, `bin/seqkit.exe` next to
  the app, or anywhere on `PATH`), or fetch the official release with
  `python tools/fetch_seqkit.py`.

SeqKit is MIT-licensed, and that license requires its copyright and permission
notice to be preserved, so it is reproduced here **verbatim** from the
`LICENSE` file of the SeqKit 2.14.0 source tree:

```text
The MIT License (MIT)

Copyright © 2016-2019 Wei Shen, 2019 Oxford Nanopore Technologies.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

If you redistribute a build that ships a SeqKit binary alongside this GUI, keep
the notice above together with that binary, and please label the combination as
unofficial: SeqKit GUI is not affiliated with, endorsed by, or maintained by the
SeqKit project.

---

## PySide6 / Qt -- LGPL-3.0-only (option elected from a multi-licence grant)

- Package: **PySide6** (Python bindings for Qt 6) and its companion **shiboken6**
- Copyright: **The Qt Company** and contributors; **Qt** is a trademark of The Qt
  Company Ltd.
- Licence grant (verified from the installed distribution's own metadata,
  `pyside6-<version>.dist-info/METADATA`, and <https://pypi.org/project/PySide6/>):
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`, also offered by the upstream
  project under a paid **Qt Commercial** licence
  (<https://www.qt.io/licensing/>).
- **Option this project elects: LGPL-3.0-only.** The full text of that licence is
  at <https://www.gnu.org/licenses/lgpl-3.0.html>
  (canonical FSF text: <https://www.gnu.org/licenses/lgpl-3.0.txt>).
- **The whole wheel family shares that one grant.** `PySide6` is a meta-package, and
  the distribution that installs it (6.12.0, verified with
  `python -m pip show PySide6 shiboken6 PySide6_Essentials PySide6_Addons PySide6_Pdf
  PySide6_WebEngine tomli`) pulls in `PySide6_Essentials` 6.12.0,
  `PySide6_Addons` 6.12.0, `PySide6_Pdf` 6.12.0.140, `PySide6_WebEngine` 6.12.0.140
  and `shiboken6` 6.12.0, each declaring exactly
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`; `tomli` 2.4.1 is the one
  non-Qt dependency and it arrives only on Python < 3.11, under MIT.
  **PySide6 is dual-licensed, not GPL-only** -- electing LGPL-3.0-only is what keeps
  this project's own MIT licence intact, and none of the wheels' own metadata needs
  rewriting.
- **Translation catalogues are Qt data.** The `translations/` directory copied into
  `_internal/PySide6/` holds 99 compiled `.qm` catalogues, of the `qt_*.qm` and
  `qtbase_*.qm` families; they come from the same Qt repositories and carry the same
  licence. They are conveying material, not a separate dependency, and this
  project's own strings live in `seqkit_gui/i18n/*.json` instead, so no Qt
  catalogue is edited here.
- **Only the modules the app imports reach the bundle.** The imports are `QtCore`,
  `QtGui`, `QtWidgets` (`PySide6_WebEngine`/`PySide6_Addons` are installed by the
  meta-package but no QtWebEngine, QtPositioning, QtMultimedia or Chromium binary
  appears in the built bundle), so the large Chromium/FFmpeg notice sets those
  modules would carry are not part of a release of this app -- with the single
  exception listed in item 7 below.

**How the LGPL-3.0-only conditions are met.** The notes below are an engineer's
reading of the licence, organised by obligation. LGPLv3 is a small set of
additional permissions layered on GNU GPLv3: its section 1 is the exception to
GPLv3 section 6, its section 4 is the permission to convey a Combined Work, and
everything else runs under GPLv3. The clause numbers below are given in those
terms. This mapping is a compliance review, **not legal advice** -- a lawyer or the
project owner should confirm it before release.

1. **(a) A copy of the licence accompanies the Combined Work.** LGPLv3 section 4
   allows the Combined Work to be conveyed only under terms that respect GPLv3, and
   GPLv3 section 4(a) requires each conveyable copy to include "a copy of this
   License" together with the notices -- so both the LGPLv3 and GPLv3 texts have to
   travel with the app, plus a notice that the Qt libraries are used and covered by
   them. The PySide6 wheels installed by `pip` ship
   **only** `LicenseRef-Qt-Commercial.txt` in their `dist-info/licenses/`
   directory -- verified for `pyside6`, `pyside6_essentials`, `pyside6_addons`,
   `pyside6_pdf`, `pyside6_webengine` and `shiboken6` at 6.12.0 -- so they carry
   **no** `LICENSE.LGPLv3` file and the responsibility to convey the LGPL text
   falls to us, not to the wheel. A hyperlink alone is the weakest acceptable form
   and fails for an offline archive, so the release packaging **must bundle the
   full LGPL-3.0-only text** with the app. A PyInstaller onedir bundle places every
   collected data file inside its contents directory, so in the archive that text is
   `_internal/LICENSES/LGPL-3.0-only.txt`, alongside `_internal/LICENSE` and
   `_internal/THIRD-PARTY-LICENSES.md`. The bundled text is the verbatim FSF
   document (`https://www.gnu.org/licenses/lgpl-3.0.txt`): **not one word of it
   may be reworded, reformatted, translated inline, shortened or "tidied"** --
   take the file as published and add nothing inside it. Stating only "PySide6 is
   under LGPLv3" does not discharge obligation (a); the text itself has to be
   conveyed. Status of the built bundle is checked mechanically by
   `python tools/license_check.py` (check 4).
2. **(b) The Qt libraries stay replaceable.** LGPLv3 section 4(d) requires the
   recipient to be able to re-link or otherwise replace the covered library; the
   practical test Qt itself documents is dynamic linking, which a bundled `.dll`
   satisfies. The packaged build is therefore a PyInstaller **onedir** bundle,
   **not** a single-file archive:
   `Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Widgets.dll`, the platform plugins and the
   `PySide6`/`shiboken6` extension modules are left as ordinary, individually
   swappable files under `SeqKit-GUI/_internal/PySide6/`, and the app loads them
   from disk rather than from an embedded blob. Verified against an actual build
   output and codified in `packaging/seqkit_gui.spec` (`EXE(...,
   exclude_binaries=True)` + `COLLECT`, i.e. onedir). See the "Why onedir and not
   onefile" note in that file.
3. **(c) Attribution / notices preserved.** The Qt Company copyright and the "Qt"
   trademark are named above, users are pointed at this file, and the About dialog
   states the licence (see `seqkit_gui/ui/dialogs.py` and the `seqkit_attribution`
   / `License` strings in `seqkit_gui/i18n/*.json`).
4. **(d) Where to obtain the Qt / PySide6 sources.** GPLv3 section 6 -- as modified
   by the exception in LGPLv3 section 1, which is what makes the LGPL option usable
   at all -- lets the Corresponding Source of the library be satisfied by pointing
   at an official location that has the source, at no charge. The version this
   project ships is **PySide6 6.12.0** (sub-wheels
   `PySide6_Essentials`/`PySide6_Addons` 6.12.0, `PySide6_Pdf`/`PySide6_WebEngine`
   6.12.0.140, `shiboken6` 6.12.0), so the pointers to convey are:
   * the wheels and their files page: <https://pypi.org/project/PySide6/6.12.0/>;
   * the bindings source, using the recipe the wheel's own metadata prints in its
     "Building from source" section -- `git clone https://code.qt.io/pyside/pyside-setup`
     followed by `git checkout 6.12.0`;
   * the Qt library itself from The Qt Company's official archive
     <https://download.qt.io> and its per-module repositories on the official code
     host <https://code.qt.io> (notably `qtbase`, which holds QtCore/QtGui/
     QtWidgets/QtNetwork), with the Qt project GitHub mirror
     <https://github.com/qtproject> as the convenience alternative.
5. **(e) No modification of Qt/PySide6.** The bindings are used exactly as
   published; no Qt source, DLL or wheel is patched or vendored into this
   repository, so no "modified version of the Library" obligations are triggered.
6. **The application code touches LGPL-covered Qt modules only.** Every import in
   `seqkit_gui/` and `packaging/` is `QtCore`, `QtGui` or `QtWidgets` (plus the
   `PySide6`/`shiboken6` runtime), all of which Qt publishes under LGPLv3; no
   module whose features need a paid Qt Commercial licence is used. The LGPL
   grant, not the GPL alternatives, is what this project relies on, so the
   application code stays under its own MIT licence.
7. **A packaged bundle picks up a GPL-only Qt module and must shed it.** Qt's own
   licensing page lists *Qt Virtual Keyboard* among "Modules available under GNU
   General Public License v3" -- it is **not** available under LGPLv3 -- and its
   documentation states it plainly ("available under commercial licenses from The
   Qt Company" / "in addition, it is available under the GNU General Public
   License, version 3"). A built bundle contains that module even though no import
   of it exists in this codebase: PySide6's PyInstaller hooks collect Qt's
   `platforminputcontexts` plugin directory wholesale, which brings
   `Qt6VirtualKeyboard.dll` plus `plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll`
   into `_internal/PySide6/`, and that plugin in turn drags in `Qt6Quick.dll`,
   `Qt6Qml*.dll` and `Qt6OpenGL.dll`. Shipping a GPL-only library inside a
   distribution whose own licence is MIT is not covered by the LGPL election in
   item 6, so the release bundle has to **exclude** it (drop
   `qtvirtualkeyboardplugin.dll` and `Qt6VirtualKeyboard.dll`, which also lets the
   Quick/Qml/OpenGL DLLs go); `python tools/license_check.py` (check 4) reports
   any such module still present. Nothing about the GUI's behaviour changes: the
   app never asks Qt for an input method.

### What the release archive has to carry

Commercial use and redistribution are permitted under LGPL-3.0-only as long as the
Qt libraries remain replaceable and the notices travel with the copy. Concretely,
a release archive of the onedir bundle (`SeqKit-GUI/`) contains, at its top level:

| file | content | source of truth |
| --- | --- | --- |
| `LICENSE` | this project's MIT text | the repository's own `LICENSE` |
| `THIRD-PARTY-LICENSES.md` | this file, notices included | the repository |
| `LICENSES/LGPL-3.0-only.txt` | verbatim FSF text, unchanged | `https://www.gnu.org/licenses/lgpl-3.0.txt` |
| `LICENSES/GPL-2.0-only.txt`, `LICENSES/GPL-3.0-only.txt` | the other open-source options PySide6 offers, so the recipient can elect them | `https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt`, `https://www.gnu.org/licenses/gpl-3.0.txt` |

The bundle itself also carries binaries whose own notices must be reproduced in
this file or beside them; they are collected by PyInstaller's PySide6 hooks, not
chosen by this project:

- Qt libraries and plugins: `Qt6Core/Gui/Widgets/Network/OpenGL/Pdf/Qml/QmlMeta/
  QmlModels/QmlWorkerScript/Quick/Svg/VirtualKeyboard.dll`, the `platforms`,
  `imageformats`, `iconengines`, `styles`, `tls`, `generic` and
  `networkinformation` plugin DLLs, and the `translations/*.qm` catalogues
  (Qt data, LGPL-covered except `Qt6VirtualKeyboard`, see item 7).
- `PySide6`/`shiboken6`: `pyside6.abi3.dll`, `shiboken6.abi3.dll`, `QtCore.pyd`,
  `QtGui.pyd`, `QtWidgets.pyd`, `QtNetwork.pyd`.
- `libssl-3-x64.dll` / `libcrypto-3-x64.dll` and `libcrypto-1_1.dll` (OpenSSL,
  collected by the `tls` backends and by CPython's `_ssl`): OpenSSL Apache-2.0 for
  3.x and the dual OpenSSL/SSLeay licence for 1.1, each requiring its copyright
  and "AS IS" notice to be retained.
- `MSVCP140.dll`, `MSVCP140_1.dll`, `MSVCP140_2.dll`, `VCRUNTIME140.dll`,
  `VCRUNTIME140_1.dll`, `ucrtbase.dll` and the `api-ms-win-*` shims: Microsoft
  Visual C++ / Universal CRT runtime, redistributable under the Microsoft SLP only
  as part of an application.
- `opengl32sw.dll` (Mesa's software OpenGL, MIT-style licence).
- `python3.dll` / `python310.dll` and `base_library.zip`: CPython, PSF licence.
- the PyInstaller bootloader inside `SeqKit-GUI.exe`: GPLv2 with PyInstaller's
  GPL-compatible linking exception, which is what lets the frozen app stay MIT.

Qt's statically-linked third-party code (SQLite, zlib, libpng, FreeType, HarfBuzz,
PCRE2, double-conversion, md4c, the JPEG/TIFF/WebP readers, …) is not itemised
here: The Qt Company publishes it as its "Used libraries and their license
information" list, and reproducing that pointer next to the Qt notice is the
customary way of covering it.

If a `bin/seqkit.exe` is ever placed in the archive, SeqKit's MIT notice (the
verbatim block above) has to sit next to that binary too, and the archive must be
labelled unofficial.

---

## Go toolchain and the generated parameter table (`tools/spec-dumper`, `commands.json`)

Go appears in this repository only as the implementation language of the
developer-side schema dumper in `tools/spec-dumper/`. That dumper is a small Go
`main` package that **imports SeqKit's own cobra command tree** to enumerate every
subcommand and flag. Evidence:

- `tools/spec-dumper/main.go` imports `github.com/shenwei356/seqkit/v2/seqkit/cmd`
  and walks `cmd.RootCmd` (plus `spf13/cobra` and `spf13/pflag`).
- `tools/spec-dumper/go.mod` pins `github.com/shenwei356/seqkit/v2 v2.14.0` but
  resolves it through `replace github.com/shenwei356/seqkit/v2 =>
  ../../../seqkit-2.14.0`, i.e. a **local SeqKit source checkout** -- the module
  proxy is never contacted for SeqKit, and (as a `replace`d module) SeqKit
  therefore does **not** appear in `go.sum`.
- The direct dependencies are all permissive and none is copyleft: SeqKit is
  **MIT**; `spf13/cobra` is **Apache-2.0**; `spf13/pflag` is **BSD-3-Clause**
  (verified from the license files in the local Go module cache). So there is no
  GPL/AGPL contamination to guard against -- the remaining obligation for SeqKit
  is attribution, not relicensing.

`seqkit_gui/data/commands.json` is the **mechanical transcription** of that dump:
the parameter names, shorthands, types, defaults and usage strings come straight
from the flags SeqKit registers with pflag (via `tools/extract_spec.py`), so the
table is derived data whose content is SeqKit's own CLI metadata. Our treatment of
that derivation is: (1) **keep SeqKit's copyright/permission notice** (reproduced
verbatim in the "SeqKit" section above), (2) **document the data's provenance** in
the README/CONTRIBUTING (already done: `commands.json` is "generated from SeqKit
2.14.0 source" and must not be hand-edited), and (3) label the project **unofficial
and unaffiliated** so the derived metadata is never mistaken for an endorsement.

The Go toolchain, the dumper and its module dependencies are **build-time,
developer-only** material: nothing Go is compiled into the shipped application,
nothing Go is redistributed with it, and end users never need Go installed. That
is why `go.mod`/`go.sum` are committed (reproducible regeneration of the table) yet
never enter the release bundle. The runtime stack is Python 3.10+ and PySide6 only.

**`spec-dumper` is a derivative work of SeqKit, and that is the one obligation this
directory carries.** `go build` links the imported `seqkit/cmd` package -- and
transitively the rest of SeqKit's code -- *statically into the resulting binary*, so
`spec-dumper(.exe)` is a combined work whose every copy must keep SeqKit's copyright
and permission notice. MIT's condition is exactly that, and it applies to binaries,
not only to source: anyone who rebuilds the dumper and passes the executable on
(mailing it, checking it into another repository, dropping it in a tools archive)
has to ship the verbatim licence block above with it, and label it unofficial. The
repository satisfies this today by holding only `main.go`, `go.mod` and `go.sum` --
`git ls-files tools/spec-dumper` lists those three and no compiled artefact, and the
`.exe` a local build leaves in `tools/_build/` is gitignored -- so the notice people
actually receive is this file, which is why the block above has to stay verbatim.
Committing `go.mod` and `go.sum` is therefore correct and useful: they are text
records of which upstream code a rebuilt dumper would link, they pin
`github.com/shenwei356/seqkit/v2 v2.14.0` for reproducibility, and neither file
contains licensed code. Note the `replace` directive: the SeqKit module is resolved
from a local checkout, so `go.sum` holds no SeqKit entry and a rebuild needs the
sibling `seqkit-2.14.0` tree present -- a build-time requirement on the developer's
machine, never on a user's.

---

## Python standard library

`urllib`, `zipfile`, `tarfile`, `argparse`, `pathlib` and the rest of the CPython
standard library are used where needed. They carry no additional third-party
notice beyond CPython's own PSF licence, and they are not vendored here.
