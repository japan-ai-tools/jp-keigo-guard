"""Find double honorifics (二重敬語) and mismatched honorific chains (不適切な敬語連結) in Japanese text.

Rules follow 文化審議会答申「敬語の指針」(2007-02-02), 第2章 第2 の6(2), p.31-32:
- 二重敬語 = one word with the same kind of honorific applied twice (例: お読みになられる).
  It is "generally not appropriate", except the forms the guideline lists as settled by custom:
  お召し上がりになる・お見えになる (尊敬語), お伺いする・お伺いいたす・お伺い申し上げる (謙譲語I).
- 敬語連結 (two honorific words joined by て) is basically allowed (お読みになっていらっしゃる),
  but a 謙譲語I form joined to くださる/いただく is listed as inappropriate
  (伺ってくださる・伺っていただく・御案内してくださる・御案内していただく).

Deterministic regular expressions. Standard library only, no network.
It checks the form of words, not who the subject is: it cannot tell whether a 尊敬語 is used for
the writer's own action.
"""
import re
import unicodedata

GUIDELINE = "文化審議会答申「敬語の指針」(平成19年2月2日) p.31-32"
GUIDELINE_URL = "https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/pdf/keigo_tosin.pdf"

ACCEPTED = ["お召し上がりになる", "お見えになる", "お伺いする", "お伺いいたす", "お伺い申し上げる"]

# endings that can follow られ / れ, longest first
ENDINGS = ["ませんでした", "ました", "ません", "ます", "なかった", "ない", "まし", "る", "た", "て", "れば"]
_END = "|".join(ENDINGS)

# how the ending is written once the extra られ is removed, per verb class
_IRASSHARU = {"る": "る", "た": "った", "て": "って", "ます": "います", "ました": "いました", "まし": "いまし",
              "ません": "いません", "ませんでした": "いませんでした", "ない": "らない", "なかった": "らなかった",
              "れば": "れば"}
_RU = {"る": "る", "た": "った", "て": "って", "ます": "ります", "ました": "りました", "まし": "りまし",
       "ません": "りません", "ませんでした": "りませんでした", "ない": "らない", "なかった": "らなかった",
       "れば": "れば"}

_KANA_I = "ぁ-ゖ"
# お + verb stem (連用形 ends in kana: 読み, 越し, 帰り, 召し上がり, 見え)
_O_STEM = rf"[おお](?:[一-龥々]+[{_KANA_I}]{{1,2}}){{1,2}}"

RULES = [
    # (code, severity, regex, stem group, verb class, reason)
    ("E_DOUBLE_KEIGO", "error", re.compile(rf"(ご覧にな)られ({_END})"), _RU,
     "ご覧になる is already 尊敬語; adding られる makes it 二重敬語"),
    ("E_DOUBLE_KEIGO", "error", re.compile(rf"({_O_STEM}にな)られ({_END})"), _RU,
     "お〜になる is already 尊敬語; adding られる makes it 二重敬語 (例: お読みになられる)"),
    ("E_DOUBLE_KEIGO", "error", re.compile(rf"(おっしゃ|いらっしゃ|なさ|くださ)られ({_END})"), _IRASSHARU,
     "the verb is already 尊敬語; adding られる makes it 二重敬語"),
    ("E_DOUBLE_KEIGO", "error", re.compile(rf"(?<![おお])(召し上が)られ({_END})"), _RU,
     "召し上がる is already 尊敬語; adding られる makes it 二重敬語"),
    ("W_DOUBLE_KEIGO_NOUN", "warning", re.compile(rf"([ごご御][一-龥]{{2,3}}にな)られ({_END})"), _RU,
     "ご〜になる is already 尊敬語; adding られる makes it 二重敬語. Warning only: "
     "after a plain noun (ご両親になられる = become parents) なられる is correct"),
]

LINK_FIXED = [
    # (regex, fix template, reason)
    (re.compile(r"伺って(くださ|いただ)"), None,
     "伺う is 謙譲語I (raises the person you visit); joined to くださる/いただく it is listed as 不適切な敬語連結. "
     "For the other person's visit use お越し/おいで: お越しくださる・お越しいただく"),
    (re.compile(r"([ごご御]案内)して(くださ|いただ)"), r"\1\2",
     "ご案内する is 謙譲語I; joined to くださる/いただく it is listed as 不適切な敬語連結. Use ご案内くださる・ご案内いただく"),
]
LINK_GENERIC = re.compile(rf"((?:[ごご御][一-龥]{{1,3}})|(?:{_O_STEM}))して(くださ|いただ)")
LINK_GENERIC_REASON = ("お/ご〜する is 謙譲語I; joined to くださる/いただく it is a 不適切な敬語連結 by the same rule as "
                       "御案内していただく. Use お/ご〜くださる・お/ご〜いただく")

_ACCEPTED_RE = re.compile(r"お召し上がりにな(?!られ)|お見えにな(?!られ)|お伺い(?:する|します|した|して|いたす|いたします|"
                          r"いたしました|いたしたく|申し上げ)")


def _norm(text):
    # keep length stable: NFKC only on ASCII/full-width letters would change offsets, so map per char
    return "".join(unicodedata.normalize("NFKC", ch) if len(unicodedata.normalize("NFKC", ch)) == 1 else ch
                   for ch in text)


def _overlaps(span, taken):
    return any(span[0] < e and s < span[1] for s, e in taken)


def check(text):
    """Return {ok, issues, accepted, counts}. ok is False when any error is found."""
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    t = _norm(text)
    issues, taken = [], []
    for code, sev, rx, table, reason in RULES:
        for m in rx.finditer(t):
            span = (m.start(), m.end())
            if _overlaps(span, taken):
                continue
            stem, ending = m.group(1), m.group(2)
            taken.append(span)
            issues.append({"code": code, "severity": sev, "text": text[span[0]:span[1]], "start": span[0],
                           "end": span[1], "fix": stem + table.get(ending, ending), "reason": reason,
                           "source": GUIDELINE})
    for rx, tmpl, reason in LINK_FIXED:
        for m in rx.finditer(t):
            span = (m.start(), m.end())
            if _overlaps(span, taken):
                continue
            taken.append(span)
            issues.append({"code": "E_BAD_KEIGO_LINK", "severity": "error", "text": text[span[0]:span[1]],
                           "start": span[0], "end": span[1], "fix": m.expand(tmpl) if tmpl else None,
                           "reason": reason, "source": GUIDELINE})
    for m in LINK_GENERIC.finditer(t):
        span = (m.start(), m.end())
        if _overlaps(span, taken):
            continue
        taken.append(span)
        issues.append({"code": "W_BAD_KEIGO_LINK", "severity": "warning", "text": text[span[0]:span[1]],
                       "start": span[0], "end": span[1], "fix": m.group(1) + m.group(2),
                       "reason": LINK_GENERIC_REASON, "source": GUIDELINE})
    issues.sort(key=lambda i: i["start"])
    accepted = [{"text": text[m.start():m.end()], "start": m.start(),
                 "note": "settled by custom (習慣として定着している二重敬語), " + GUIDELINE}
                for m in _ACCEPTED_RE.finditer(t)]
    counts = {"error": sum(i["severity"] == "error" for i in issues),
              "warning": sum(i["severity"] == "warning" for i in issues)}
    return {"ok": counts["error"] == 0, "issues": issues, "accepted": accepted, "counts": counts}


def fix(text, apply_warnings=False):
    """Apply the suggested fixes. Errors always; warnings only when apply_warnings is True.
    Issues without a fix (伺っていただく needs a different verb) are left and returned in 'unfixed'."""
    r = check(text)
    out, pos, applied, unfixed = [], 0, [], []
    for i in r["issues"]:
        if i["severity"] == "warning" and not apply_warnings:
            continue
        if i["fix"] is None:
            unfixed.append(i)
            continue
        out.append(text[pos:i["start"]])
        out.append(i["fix"])
        pos = i["end"]
        applied.append({"from": i["text"], "to": i["fix"], "code": i["code"]})
    out.append(text[pos:])
    return {"text": "".join(out), "applied": applied, "unfixed": unfixed, "remaining": check("".join(out))["counts"]}
