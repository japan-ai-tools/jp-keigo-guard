# JP Keigo Guard

<!-- mcp-name: io.github.japan-ai-tools/jp-keigo-guard -->

**Find double honorifics (二重敬語) and mismatched honorific chains in AI-written Japanese business text, by the rules of the Japanese government guideline 「敬語の指針」. Returns a fix for each one. MCP server, CLI and Python library. Standard library only, no network, MIT.**

Language models write polite Japanese that is sometimes too polite in the wrong way: お読みになられる, おっしゃられる, ご覧になられましたか. A Japanese business-writing guide lists "sending AI-generated text without checking it" as one cause of keigo mistakes in email ([uravation, updated 2026-10-19](https://uravation.com/media/business-email-keigo-mistakes-guide-2026/)). Asking another model to proofread gives a different answer each time. This tool applies fixed rules and gives the same answer every time.

The rules come from 文化審議会答申「敬語の指針」(2007-02-02), chapter 2, section 2-6(2), p.31-32 ([PDF](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/pdf/keigo_tosin.pdf)):

- 二重敬語 is one word with the same kind of honorific applied twice. Example from the guideline: お読みになられる. It is generally not appropriate.
- The guideline lists forms settled by custom: お召し上がりになる, お見えになる, お伺いする, お伺いいたす, お伺い申し上げる. These are not flagged.
- Two honorific words joined by て (敬語連結) are basically allowed: お読みになっていらっしゃる. The guideline lists 伺ってくださる, 伺っていただく, 御案内してくださる, 御案内していただく as inappropriate.

```text
text                              naive search ("なられ" etc.)   this tool
部長がお読みになられました          flagged                       E_DOUBLE_KEIGO → お読みになりました
社長がおっしゃられた件              flagged                       E_DOUBLE_KEIGO → おっしゃった
ご覧になられましたか                flagged                       E_DOUBLE_KEIGO → ご覧になりました
会場までご案内していただけますか      flagged                       E_BAD_KEIGO_LINK → ご案内いただけますか
明日伺っていただけますか            flagged                       E_BAD_KEIGO_LINK (rewrite: お越しいただけますか)
先生になられる方                    flagged (wrong)               ok (なる → なられる is a single honorific)
お客様になられる方                  flagged (wrong)               ok
お召し上がりになってください         not flagged                   ok, listed as accepted by the guideline
```

On the 30 bundled cases this tool matches the expected codes 30/30; the naive search gets 25/30. The cases and the rules come from the same author, so treat this as a regression suite, not proof.

## Codes

| Code | Severity | Example | Fix |
|---|---|---|---|
| `E_DOUBLE_KEIGO` | error | お読みになられる, おっしゃられる, いらっしゃられる, ご覧になられる, 召し上がられる, なさられる | drop the extra られ, keep the tense: お読みになりました |
| `W_DOUBLE_KEIGO_NOUN` | warning | ご出席になられる | ご出席になる. Warning only: after a plain noun (ご両親になられる) なられる is correct |
| `E_BAD_KEIGO_LINK` | error | 伺っていただく, ご案内していただく (listed in the guideline) | ご案内いただく; 伺う needs a different verb (お越し), so no automatic fix |
| `W_BAD_KEIGO_LINK` | warning | ご説明していただけますか, お送りしてくださる | ご説明いただけますか, お送りくださる |

`ok` is false when any error is found. Each issue has `text`, `start`, `end`, `fix`, `reason` and `source` (the guideline page).

## Limits

It checks word forms, not meaning. It cannot tell whether a 尊敬語 is used for the writer's own action (私がおっしゃった), whether the reader is a superior, or whether the tone fits. Use it as a fast first pass before a person or a model reads the text.

## MCP server (for AI agents)

```json
{"mcpServers": {"jp-keigo-guard": {"command": "python", "args": ["-m", "keigoguard.server"], "cwd": "/path/to/jp-keigo-guard"}}}
```

| Tool | Input | Returns |
|---|---|---|
| `jp_keigo_check` | `text` | `ok`, `issues`, `accepted`, `counts` |
| `jp_keigo_fix` | `text`, `apply_warnings` | `text`, `applied`, `unfixed`, `remaining` |

Both tools are read-only and offline. Suggested agent rule: after writing a Japanese email or notice, call `jp_keigo_check`, fix every error and rewrite the items in `unfixed` before sending.

## CLI and Python

```bash
python -m keigoguard mail.txt          # JSON report, exit 1 on an error
python -m keigoguard --fix mail.txt    # print the fixed text
python -m keigoguard.bench             # score on data/jp_keigo_cases_v1.jsonl
```

```python
from keigoguard import check, fix
check("部長がおっしゃられた件です")["issues"][0]["fix"]   # 'おっしゃった'
fix("ご案内していただけますか")["text"]                  # 'ご案内いただけますか'
```

## Files

- keigoguard/guard.py: check(text), fix(text, apply_warnings=False)
- keigoguard/server.py: MCP stdio server
- data/jp_keigo_cases_v1.jsonl: 30 fictional sentences with expected codes
- tests/test_keigoguard.py

---

## 日本語

AIが書いた日本語のメール・案内文から、二重敬語(お読みになられる・おっしゃられる・ご覧になられる)と、「敬語の指針」(文化審議会答申、平成19年)が不適切とする敬語連結(伺っていただく・ご案内していただく)を見つけ、直し案を返します。指針が「習慣として定着している」とする お召し上がりになる・お見えになる・お伺いする などは指摘しません。決まった規則なので、同じ文には毎回同じ答えを返します。標準ライブラリだけ・外部通信なし・MIT。

### できないこと

文の形だけを見ます。自分の動作に尊敬語を使っていないか、相手が目上か、といった意味の判断はしません。送る前の最初の確認として使ってください。

## License

MIT
