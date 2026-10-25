"""Builds docs/Chapter3_Research_Methodology_Full.docx from chapter3_full_content.py (numbers come from results/chapter3/*.json)."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from chapter3_full_content import C  # noqa: E402
from docbuilder import PH, build  # noqa: E402


def lint():
    out = []
    for it in C:
        if it[0] != "p": continue
        t = PH.sub("X", it[1]); sents = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", t) if s.strip()]
        if "—" in t or "–" in t: out.append(("dash", t[:70]))
        if re.search(r"\b\w+n't\b|\b(it|that|there)'s\b|\b\w+'(ll|re|ve|d)\b", t): out.append(("contraction", t[:70]))
        if re.search(r"\b(I|we|our|my|We|Our)\b", t): out.append(("first person", t[:70]))
        if re.search(r"\bwill\b|\bshall\b|\bgoing to\b", t): out.append(("future", t[:70]))
        if re.search(r"(Furthermore|Moreover|Additionally|In summary|Overall|In conclusion|In addition),", t): out.append(("transition", t[:70]))
        if re.search(r"\b(delve|leverage|robust|holistic|seamless|pivotal|foster|harness|myriad|tapestry|crucial|underscore)", t, re.I): out.append(("AI word", t[:70]))
        if len(sents) < 3: out.append((f"{len(sents)} sentences", t[:70]))
        for s in sents:
            if re.match(r"\d", s): out.append(("numeral start", s[:70]))
    return out


if __name__ == "__main__":
    for x in lint(): print("LINT", x)
    out = Path(__file__).parent / "Chapter3_Research_Methodology_Full.docx"; build(C, out, Path(__file__).parent); print("wrote", out)
