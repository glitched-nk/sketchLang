"""Tests for server.py (the web UI back end): start the real HTTP server on a free
port and call every endpoint. Standard library only."""
import http.client
import json
import os
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import server  # noqa: E402


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, dict(resp.getheaders()), resp.read()
        finally:
            conn.close()

    def post_json(self, path, obj):
        return self.request("POST", path, body=json.dumps(obj))


class TestStaticAndExamples(ServerCase):
    def test_index_page_is_served(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"SketchLang", body)

    def test_unknown_path_is_404(self):
        self.assertEqual(self.request("GET", "/nope")[0], 404)
        self.assertEqual(self.post_json("/api/nope", {})[0], 404)

    def test_examples_endpoint_lists_every_program_and_error_example(self):
        status, _h, body = self.request("GET", "/api/examples")
        self.assertEqual(status, 200)
        examples = json.loads(body)
        keys = {e["key"] for e in examples}
        on_disk = {f[:-7] for f in os.listdir(server.EXAMPLES) if f.endswith(".sketch")}
        self.assertEqual(keys, on_disk)
        self.assertEqual({e["group"] for e in examples}, {"Programs", "Errors"})
        self.assertTrue(all(e["source"].strip() for e in examples))
        # programs come before error examples
        groups = [e["group"] for e in examples]
        self.assertEqual(groups, sorted(groups, key=lambda g: g != "Programs"))

    def test_every_example_has_a_human_title(self):
        for e in json.loads(self.request("GET", "/api/examples")[2]):
            with self.subTest(key=e["key"]):
                self.assertNotEqual(e["title"], e["key"])

    def test_web_page_tab_ids_are_valid_selectors(self):
        """Regression: tab ids once contained spaces ('tab-Syntax tree'), so $('#tab-Syntax tree')
        returned null and every tab click threw. The page must build ids with slug()."""
        with open(os.path.join(server.WEB, "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn("const slug =", html)
        self.assertNotIn('"#tab-" + t)', html)
        self.assertNotIn('"#panel-" + name)', html)


class TestCompileEndpoint(ServerCase):
    def test_success_payload_shape(self):
        status, headers, body = self.post_json("/api/compile", {"source": "pen red\nforward 50\nturn 90\nforward 50"})
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        d = json.loads(body)
        self.assertTrue(d["ok"])
        for key in ("strip", "timings", "tokens", "ast", "symbols", "procs", "ir_before", "ir_after",
                    "passes", "run_stats", "svg", "plotter", "gcode_counts", "code", "limits"):
            self.assertIn(key, d)
        self.assertEqual(d["ir_before_count"], 2)
        self.assertEqual(set(d["code"]), {"svg", "ps", "gcode"})
        self.assertTrue(d["svg"].startswith("<svg"))
        self.assertTrue(d["code"]["ps"]["text"].startswith("%!PS"))

    def test_every_stage_reports_a_timing(self):
        d = json.loads(self.post_json("/api/compile", {"source": "forward 1"})[2])
        for stage in server.STRIP:
            self.assertIn(stage, d["timings"])

    def test_plotter_summary_is_included(self):
        src = open(os.path.join(server.EXAMPLES, "plotter_mirror.sketch")).read()
        d = json.loads(self.post_json("/api/compile", {"source": src})[2])
        self.assertTrue(d["plotter"]["drawn"])
        self.assertGreater(d["plotter"]["summary"]["travel_saving_pct"], 80)
        self.assertEqual(len(d["plotter"]["before"]), len(d["plotter"]["after"]))

    def test_group_colors_flag_is_honoured(self):
        src = open(os.path.join(server.EXAMPLES, "plotter_checker.sketch")).read()
        grouped = json.loads(self.post_json("/api/compile", {"source": src, "group_colors": True})[2])
        ungrouped = json.loads(self.post_json("/api/compile", {"source": src, "group_colors": False})[2])
        self.assertEqual(grouped["plotter"]["summary"]["after"]["pen_changes"], 1)
        self.assertEqual(ungrouped["plotter"]["summary"]["after"]["pen_changes"], 30)

    def test_each_error_stage_is_reported_with_its_strip_position(self):
        cases = {
            "lexical": ("forward 1 @", 0),
            "syntax": ("repeat 2 { forward 1", 1),
            "semantic": ("forward nothing", 2),
            "runtime": ("proc f(n) { call f(n) }\ncall f(1)", 3),
        }
        for stage, (src, strip_index) in cases.items():
            with self.subTest(stage=stage):
                status, _h, body = self.post_json("/api/compile", {"source": src})
                self.assertEqual(status, 200)
                d = json.loads(body)
                self.assertFalse(d["ok"])
                self.assertEqual(d["error"]["stage"], stage)
                self.assertEqual(d["failed_strip_index"], strip_index)

    def test_error_line_number_is_extracted(self):
        d = json.loads(self.post_json("/api/compile", {"source": "pen red\npen red\nforward nope"})[2])
        self.assertEqual(d["error"]["line"], 3)

    def test_empty_source_compiles(self):
        d = json.loads(self.post_json("/api/compile", {"source": ""})[2])
        self.assertTrue(d["ok"])
        self.assertEqual(d["ir_after_count"], 0)

    def test_large_output_is_previewed_not_sent_whole(self):
        # growing step: every segment is unique, so the optimiser cannot collapse a repeating polygon
        src = "let step = 1\nrepeat 20000 {\n forward step\n turn 7\n let step = step + 0.01\n}\n"
        d = json.loads(self.post_json("/api/compile", {"source": src})[2])
        self.assertTrue(d["ok"])
        self.assertLessEqual(len(d["code"]["svg"]["text"]), server.PREVIEW_CHARS)
        self.assertTrue(d["code"]["svg"]["truncated"])
        self.assertLessEqual(len(d["ir_before"]), 600)
        self.assertEqual(d["ir_before_count"], 20000)

    def test_oversized_drawing_is_not_animated(self):
        src = "let step = 1\nrepeat 20000 {\n forward step\n turn 7\n let step = step + 0.01\n}\n"
        d = json.loads(self.post_json("/api/compile", {"source": src})[2])
        self.assertFalse(d["plotter"]["drawn"])
        self.assertNotIn("before", d["plotter"])
        self.assertIn("summary", d["plotter"])


class TestExportEndpoint(ServerCase):
    SRC = "pen red\nforward 50\nturn 90\nforward 50"

    def export(self, target, **extra):
        return self.post_json("/api/export", {"source": self.SRC, "target": target, **extra})

    def test_svg_ps_gcode_downloads(self):
        expectations = {
            "svg": ("image/svg+xml", "sketch.svg", b"<svg"),
            "ps": ("application/postscript", "sketch.ps", b"%!PS"),
            "gcode": ("text/plain", "sketch.gcode", b"; SketchLang"),
        }
        for target, (ctype, filename, start) in expectations.items():
            with self.subTest(target=target):
                status, headers, body = self.export(target)
                self.assertEqual(status, 200)
                self.assertIn(ctype, headers["Content-Type"])
                self.assertIn(filename, headers["Content-Disposition"])
                self.assertTrue(body.startswith(start))

    def test_gcode_optimise_flag_changes_the_file(self):
        src = open(os.path.join(server.EXAMPLES, "plotter_mirror.sketch")).read()
        _s, _h, raw = self.post_json("/api/export", {"source": src, "target": "gcode", "optimise": False})
        _s, _h, opt = self.post_json("/api/export", {"source": src, "target": "gcode", "optimise": True})
        self.assertNotEqual(raw, opt)
        self.assertEqual(len(raw.splitlines()), len(opt.splitlines()))   # same moves, different order

    def test_unknown_target_is_a_400(self):
        status, _h, body = self.export("pdf")
        self.assertEqual(status, 400)
        self.assertFalse(json.loads(body)["ok"])


class TestBadRequests(ServerCase):
    def test_invalid_json_is_a_400_not_a_crash(self):
        status, _h, body = self.request("POST", "/api/compile", body="{not json")
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["stage"], "input")

    def test_oversized_body_is_a_413(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.putrequest("POST", "/api/compile")
            conn.putheader("Content-Length", str(server.MAX_BODY + 1))
            conn.endheaders()
            resp = conn.getresponse()
            self.assertEqual(resp.status, 413)
            self.assertEqual(json.loads(resp.read())["error"]["stage"], "input")
        finally:
            conn.close()

    def test_server_survives_a_bad_request(self):
        self.request("POST", "/api/compile", body="{not json")
        status, _h, _b = self.post_json("/api/compile", {"source": "forward 1"})
        self.assertEqual(status, 200)

    def test_missing_source_key_compiles_as_empty(self):
        d = json.loads(self.post_json("/api/compile", {})[2])
        self.assertTrue(d["ok"])


if __name__ == "__main__":
    unittest.main()
