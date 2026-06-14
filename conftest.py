import sys
from pathlib import Path

# Make `import cover_sizer` and `import app` work when pytest runs from repo root.
sys.path.insert(0, str(Path(__file__).parent))
