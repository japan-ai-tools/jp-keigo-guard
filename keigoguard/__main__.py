"""CLI: python -m keigoguard FILE.txt         (exit 1 when an error is found; - reads stdin)
     python -m keigoguard --fix FILE.txt   (print the fixed text)"""
import argparse
import json
import sys

from .guard import check, fix


def main(argv=None):
    p = argparse.ArgumentParser(prog="keigoguard", description="Find 二重敬語 and 不適切な敬語連結 in Japanese text.")
    p.add_argument("file", help="text file (- for stdin)")
    p.add_argument("--fix", action="store_true", help="print the text with the suggested fixes applied")
    p.add_argument("--apply-warnings", action="store_true", help="with --fix, also apply warning-level fixes")
    a = p.parse_args(argv)
    for s in (sys.stdin, sys.stdout):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    text = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
    if a.fix:
        r = fix(text, a.apply_warnings)
        print(r["text"], end="" if r["text"].endswith("\n") else "\n")
        return 0 if r["remaining"]["error"] == 0 else 1
    r = check(text)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
