import sys
from pathlib import Path

# make the origami package importable when pytest runs from this project dir
sys.path.insert(0, str(Path(__file__).parent))
