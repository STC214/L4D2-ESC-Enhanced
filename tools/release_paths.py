"""Single source of truth for the user's permanent C release filename."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
C_FILENAME = "【00】C_ESC_LED_血条和速度_TUMTaRA.vpk"
OUTPUT = ROOT / "dist" / C_FILENAME
