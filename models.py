from dataclasses import dataclass
from pathlib import Path


@dataclass
class Action:
    old_path: Path
    new_path: Path
    index: int
    classified: bool
