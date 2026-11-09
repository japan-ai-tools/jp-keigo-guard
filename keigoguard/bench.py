"""Score on data/jp_keigo_cases_v1.jsonl.

python -m keigoguard.bench
The naive checker is a quick script: flag any sentence containing なられ, られ after an honorific verb
(おっしゃられ, いらっしゃられ) or していただ/してくださ. It flags correct text such as 先生になられる.
Cases and rules come from the same author: this is a regression suite, not proof.
"""
import json
import os
import re
import sys

from .guard import check

CASES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jp_keigo_cases_v1.jsonl")
NAIVE = re.compile(r"なられ|おっしゃられ|いらっしゃられ|していただ|してくださ")


def load(path=CASES):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def ours(case):
    return sorted(i["code"] for i in check(case["text"])["issues"])


def score(cases=None):
    cases = cases or load()
    exact = sum(ours(c) == sorted(c["expected"]) for c in cases)
    flag = sum(bool(ours(c)) == bool(c["expected"]) for c in cases)
    naive = sum(bool(NAIVE.search(c["text"])) == bool(c["expected"]) for c in cases)
    return {"cases": len(cases), "keigo_guard_exact": exact, "keigo_guard_flag": flag, "naive_flag": naive}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cases = load()
    print(json.dumps(score(cases)))
    for c in cases:
        if ours(c) != sorted(c["expected"]):
            print("MISS", c["id"], c["text"], "expected", c["expected"], "got", ours(c))


if __name__ == "__main__":
    main()
