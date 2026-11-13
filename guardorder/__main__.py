"""Runs GuardOrder on one file or a folder. The rules file names each guard and action."""
import json
import sys
from pathlib import Path

from guardorder.check import check


def main(argv):
    """Prints one line per card. Returns 0 when the read finishes (GuardOrder)."""
    if len(argv) < 1:
        print("Usage: python -m guardorder <path> [--rules <file>]", file=sys.stderr)
        return 2
    root = Path(argv[0])
    if not root.exists():
        print("No such path.", file=sys.stderr)
        return 2
    if "--rules" in argv:
        at = argv.index("--rules")
        if at + 1 >= len(argv):
            print("Name a rules file with --rules.", file=sys.stderr)
            return 2
        rules_path = Path(argv[at + 1])
        if not rules_path.is_file():
            print("Name a rules file with --rules.", file=sys.stderr)
            return 2
    elif (root / "rules.json").is_file():
        rules_path = root / "rules.json"
    else:
        print("Name a rules file with --rules.", file=sys.stderr)
        return 2
    rules = json.loads(rules_path.read_text())
    paths = []
    if root.is_file():
        paths.append(root)
    else:
        for path in sorted(root.rglob("*")):
            if path.suffix in (".py", ".js", ".ts", ".tsx"):
                paths.append(path)
    for path in paths:
        text = path.read_text()
        for item in check(str(path), text, rules):
            print(item["file"] + ":" + str(item["line"]) + ": " + item["reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
