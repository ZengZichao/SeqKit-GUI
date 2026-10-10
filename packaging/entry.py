# SPDX-License-Identifier: MIT
"""PyInstaller entry point.

The application is normally started with ``python -m seqkit_gui``, where relative
imports inside the package resolve. A spec file hands PyInstaller a single script
that is bundled without its package context, so the entry has to import through the
package name for ``seqkit_gui.*`` lookups to work in the frozen app.
"""

import sys

from seqkit_gui.main import main

if __name__ == "__main__":
    sys.exit(main())
