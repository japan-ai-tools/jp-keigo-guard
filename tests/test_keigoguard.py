import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from keigoguard import ACCEPTED, check, fix  # noqa: E402
from keigoguard.bench import load, score  # noqa: E402
from keigoguard.server import TOOLS, handle  # noqa: E402


def codes(text):
    return [i["code"] for i in check(text)["issues"]]


def fixes(text):
    return [i["fix"] for i in check(text)["issues"]]


class TestDoubleKeigo(unittest.TestCase):
    def test_guideline_example(self):
        # 「お読みになられる」は敬語の指針 p.31 の例
        self.assertEqual(codes("お読みになられる"), ["E_DOUBLE_KEIGO"])
        self.assertEqual(fixes("お読みになられる"), ["お読みになる"])

    def test_conjugations(self):
        self.assertEqual(fixes("お読みになられました"), ["お読みになりました"])
        self.assertEqual(fixes("お待ちになられて"), ["お待ちになって"])
        self.assertEqual(fixes("おっしゃられた"), ["おっしゃった"])
        self.assertEqual(fixes("いらっしゃられます"), ["いらっしゃいます"])
        self.assertEqual(fixes("おっしゃられない"), ["おっしゃらない"])
        self.assertEqual(fixes("召し上がられる"), ["召し上がる"])
        self.assertEqual(fixes("ご覧になられましたか"), ["ご覧になりました"])

    def test_triple(self):
        self.assertEqual(fixes("お召し上がりになられますか"), ["お召し上がりになります"])
        self.assertEqual(codes("お見えになられた"), ["E_DOUBLE_KEIGO"])

    def test_noun_is_warning_only(self):
        self.assertEqual(codes("ご出席になられる"), ["W_DOUBLE_KEIGO_NOUN"])
        self.assertTrue(check("ご出席になられる")["ok"])

    def test_correct_text_not_flagged(self):
        for t in ["先生になられる", "お客様になられる方", "お読みになる", "おっしゃった", "拝見いたしました",
                  "お読みになっていらっしゃる", "ご確認いただけますか", "部長がいらっしゃいます"]:
            self.assertEqual(codes(t), [], t)


class TestAccepted(unittest.TestCase):
    def test_accepted_forms(self):
        self.assertEqual(len(ACCEPTED), 5)
        for t in ["お召し上がりになってください", "お見えになりました", "お伺いいたします", "お伺い申し上げます"]:
            r = check(t)
            self.assertEqual(r["issues"], [], t)
            self.assertTrue(r["accepted"], t)


class TestLinks(unittest.TestCase):
    def test_guideline_list(self):
        # p.31-32 不適切な敬語連結の例
        for t in ["伺ってくださる", "伺っていただく", "ご案内してくださる", "御案内していただく"]:
            self.assertEqual(codes(t), ["E_BAD_KEIGO_LINK"], t)
        self.assertEqual(fixes("ご案内していただけますか"), ["ご案内いただ"])
        self.assertEqual(fixes("伺っていただけますか"), [None])

    def test_generic_warning(self):
        self.assertEqual(codes("ご説明していただけますか"), ["W_BAD_KEIGO_LINK"])
        self.assertEqual(fixes("お送りしてくださいました"), ["お送りくださ"])


class TestFix(unittest.TestCase):
    def test_fix_and_unfixed(self):
        r = fix("部長がお読みになられました。明日伺っていただけますか。")
        self.assertEqual(r["text"], "部長がお読みになりました。明日伺っていただけますか。")
        self.assertEqual(len(r["unfixed"]), 1)
        self.assertEqual(r["remaining"]["error"], 1)

    def test_warnings_optional(self):
        self.assertEqual(fix("ご説明していただけますか")["text"], "ご説明していただけますか")
        self.assertEqual(fix("ご説明していただけますか", True)["text"], "ご説明いただけますか")

    def test_offsets(self):
        t = "本日、部長がおっしゃられた件です。"
        i = check(t)["issues"][0]
        self.assertEqual(t[i["start"]:i["end"]], i["text"])

    def test_fullwidth_and_bad_input(self):
        self.assertEqual(codes("ＡＢＣ社の部長がおっしゃられた"), ["E_DOUBLE_KEIGO"])
        with self.assertRaises(ValueError):
            check(None)


class TestBench(unittest.TestCase):
    def test_all_cases(self):
        r = score(load())
        self.assertEqual(r["cases"], 30)
        self.assertEqual(r["keigo_guard_exact"], 30)
        self.assertLess(r["naive_flag"], r["keigo_guard_flag"])


class TestServer(unittest.TestCase):
    def call(self, method, params=None, mid=1):
        return handle({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})

    def test_initialize_and_list(self):
        r = self.call("initialize", {"protocolVersion": "2025-06-18"})["result"]
        self.assertEqual(r["serverInfo"]["name"], "jp-keigo-guard")
        tools = self.call("tools/list")["result"]["tools"]
        self.assertEqual({t["name"] for t in tools}, {"jp_keigo_check", "jp_keigo_fix"})
        for t in TOOLS:
            self.assertTrue(t["annotations"]["readOnlyHint"])
            self.assertFalse(t["annotations"]["openWorldHint"])

    def test_call(self):
        r = self.call("tools/call", {"name": "jp_keigo_check", "arguments": {"text": "おっしゃられた"}})["result"]
        self.assertFalse(r["isError"])
        self.assertFalse(r["structuredContent"]["ok"])
        r = self.call("tools/call", {"name": "jp_keigo_fix", "arguments": {"text": "おっしゃられた"}})["result"]
        self.assertEqual(r["structuredContent"]["text"], "おっしゃった")

    def test_errors(self):
        r = self.call("tools/call", {"name": "jp_keigo_check", "arguments": {"text": 1}})["result"]
        self.assertTrue(r["isError"])
        self.assertIn("error", self.call("tools/call", {"name": "nope"}))
        self.assertIn("error", self.call("nope"))
        self.assertIsNone(handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_stdio(self):
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "jp_keigo_check", "arguments": {"text": "ご覧になられましたか"}}}]
        p = subprocess.run([sys.executable, "-m", "keigoguard.server"], cwd=ROOT, capture_output=True,
                           input="\n".join(json.dumps(m) for m in msgs) + "\n", text=True, encoding="utf-8",
                           timeout=30)
        lines = [json.loads(x) for x in p.stdout.splitlines() if x.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1]["result"]["structuredContent"]["counts"]["error"], 1)


class TestCli(unittest.TestCase):
    def test_cli_exit_code(self):
        p = subprocess.run([sys.executable, "-m", "keigoguard", "-"], cwd=ROOT, capture_output=True,
                           input="おっしゃられた", text=True, encoding="utf-8", timeout=30)
        self.assertEqual(p.returncode, 1)
        p = subprocess.run([sys.executable, "-m", "keigoguard", "--fix", "-"], cwd=ROOT, capture_output=True,
                           input="おっしゃられた", text=True, encoding="utf-8", timeout=30)
        self.assertEqual(p.stdout.strip(), "おっしゃった")


if __name__ == "__main__":
    unittest.main()
