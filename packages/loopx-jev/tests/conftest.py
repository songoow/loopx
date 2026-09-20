from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "tests"), str(ROOT / "packages/loopx-jev/src")]
sys.path.insert(0, str(ROOT / 'tests/control_plane'))
