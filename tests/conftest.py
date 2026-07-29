"""Make src/ importable so tests can `import residual_income_model` etc.

The project runs scripts from inside src/ (bare imports like `from config
import ...`), so tests add src/ to sys.path the same way.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
