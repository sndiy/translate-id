import sys
from pathlib import Path

# Make tests/helpers.py importable as ``helpers`` and src/ importable without installation.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
