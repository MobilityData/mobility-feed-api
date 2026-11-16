#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Make this package importable the way the deployed functions import it.

Every function that consumes these helpers gets them symlinked to `src/shared/helpers`,
so production code says `from shared.helpers.sizing import ...`. This package's own
tests run with the directory itself on the path, where the same module is just `sizing`.

`function-python-setup.sh` cannot bridge that - it refuses to link a folder into its own
descendant - so the alias is registered here, as a submodule of the real `shared`
package rather than in place of it. Without this a wrong import path passes the test
suite and fails on deploy, which is not hypothetical: it happened.
"""

import importlib
import sys
import types
from pathlib import Path

_HELPERS = Path(__file__).resolve().parent.parent

try:
    _shared = importlib.import_module("shared")
except ImportError:  # pragma: no cover - only when src/shared has not been linked
    _shared = None

if _shared is not None and "shared.helpers" not in sys.modules:
    _alias = types.ModuleType("shared.helpers")
    _alias.__path__ = [str(_HELPERS)]
    sys.modules["shared.helpers"] = _alias
    _shared.helpers = _alias
