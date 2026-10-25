"""Paths and constants shared by the Chapter 3 experiments."""
import os
from pathlib import Path

DATA = Path(os.environ.get("PG_DATA", "/tmp/claude-0/data"))
OUT = Path(os.environ.get("PG_OUT", Path(__file__).resolve().parent.parent / "results" / "chapter3"))
FIG = Path(__file__).resolve().parent.parent / "docs" / "chapter3" / "figures"
SEED = 42
PERSON_MID = "/m/01g317"   # Open Images machine id for Person
for p in (OUT, FIG):
    p.mkdir(parents=True, exist_ok=True)
