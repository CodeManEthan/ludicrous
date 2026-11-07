"""The web server: request validation, work budgets, stopping a batch whose
client is gone, gzip, and status codes. Standard library only."""
import contextlib
import gzip
import http.client
import io
import json
import multiprocessing
import socket
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

import server
from engine import batch
from engine.batch import BatchCancelled, _parallel, _run_one


class TestBlackjackBudget(unittest.TestCase):
    def test_refuses_over_budget_and_names_what_fits(self):
        config = {"game": "blackjack", "players": 200, "rounds": 100, "games": 1000}
        with self.assertRaises(ValueError) as caught:
            server.run_batch_api(config)
        message = str(caught.exception)
        self.assertIn("about 20.0 million hands", message)
        self.assertIn("the budget is 10 million", message)
        self.assertIn("up to 500 games fit", message)

    def test_budget_edge(self):
        server.check_blackjack_budget(200, 100, 500)  # exactly the budget
        with self.assertRaises(ValueError):
            server.check_blackjack_budget(200, 100, 501)

    def test_largest_request_still_fits_some_games(self):
        with self.assertRaises(ValueError) as caught:
            server.check_blackjack_budget(200, server.MAX_BJ_ROUNDS, 6)
        self.assertIn("up to 5 games fit", str(caught.exception))

    def test_client_default_fits(self):
        # The page's Blackjack batch form opens at no more than 8 seats,
        # 100 rounds and 1,000 games.
        server.check_blackjack_budget(8, 100, 1000)

    def test_accepts_the_server_default(self):
        result = server.run_batch_api({"game": "blackjack", "seed": 7})
        self.assertEqual(result["config"]["players"] * result["config"]["rounds"]
                         * result["config"]["games"], 4 * 100 * 100)
        self.assertEqual(result["aggregate"]["games"], 100)

    def test_refuses_201_seats(self):
        with self.assertRaisesRegex(ValueError, "seats must be between 1 and 200"):
            server.run_batch_api({"game": "blackjack", "players": 201, "games": 1})


class TestWarBudget(unittest.TestCase):
    def test_refuses_over_budget(self):
        config = {"players": 1000, "decks": 1000, "games": 100, "max_rounds": 0}
        with self.assertRaisesRegex(ValueError, "the budget is 5 billion"):
            server.run_batch_api(config)

    def test_typical_rounds_never_below_a_measured_edge(self):
        # The budget reads the grid; at a row's edge (the fewest decks that
        # deal every player a card) it must not read below what was measured.
        grid = json.loads(server.ROUNDS_GRID.read_text())
        self.assertEqual(sorted(grid["edges"], key=int), ["128", "256", "512", "1000"])
        for players, (decks, median, *_rest) in grid["edges"].items():
            with self.subTest(players=players, decks=decks):
                self.assertGreaterEqual(server.typical_rounds(int(players), decks), median)


class TestParallelCancel(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        batch._shutdown_pool()
        # The worker processes are gone with the pool.
        deadline = time.monotonic() + 10
        while multiprocessing.active_children() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not multiprocessing.active_children(), multiprocessing.active_children()

    def test_stops_queued_chunks_when_progress_says_stop(self):
        workers = batch._get_pool()._max_workers
        # One game per chunk and eight chunks per worker: the executor hands
        # out at most about 2 x workers + 1 before the first result comes
        # back, so most chunks are still pending when progress says stop.
        total = workers * 8
        args = [(20, 10, seed, 5000) for seed in range(total)]  # ~15 ms each
        calls = []
        calls_lock = threading.Lock()

        def progress(done, of):
            with calls_lock:
                calls.append(done)
                return len(calls) > 1  # False on the first chunk only

        with self.assertRaises(BatchCancelled) as caught:
            _parallel(_run_one, args, progress=progress)
        cancelled = caught.exception
        self.assertEqual(cancelled.total, total)
        self.assertGreaterEqual(cancelled.ran, 1)
        # About 2 x workers + 1 of the 8 x workers chunks were already handed
        # out; everything else was dropped.
        self.assertLessEqual(cancelled.ran, total // 2)
        self.assertEqual(str(cancelled), f"batch cancelled: {cancelled.ran} of {total} chunks ran")
        # Only chunks that ran are ever counted as done.
        with calls_lock:
            self.assertLessEqual(max(calls), cancelled.ran)

        # The pool is still good for the next batch.
        rows = _parallel(_run_one, args[:workers * 2], progress=lambda d, t: True)
        self.assertEqual([r["seed"] for r in rows], list(range(workers * 2)))

    def test_raising_progress_counts_as_stop(self):
        workers = batch._get_pool()._max_workers
        args = [(20, 10, seed, 5000) for seed in range(workers * 8)]

        def progress(done, of):
            raise OSError("socket gone")

        with self.assertRaises(BatchCancelled):
            _parallel(_run_one, args, progress=progress)


class QuietHandler(server.Handler):
    def log_message(self, format, *args):
        pass


class JoiningServer(ThreadingHTTPServer):
    # server_close() then waits for every request thread, so no test leaves
    # one running.
    daemon_threads = False
    block_on_close = True


class TestHandler(unittest.TestCase):
    def setUp(self):
        self.httpd = JoiningServer(("127.0.0.1", 0), QuietHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=30)
        self.assertFalse(self.thread.is_alive())

    def post(self, path, body, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        try:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            conn.request("POST", path, body=data,
                         headers={"Content-Type": "application/json", **(headers or {})})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_simulate_gzips_when_asked(self):
        config = {"game": "blackjack", "players": 1, "rounds": 5, "seed": 3}
        status, headers, body = self.post("/api/simulate", config, {"Accept-Encoding": "gzip"})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Encoding"), "gzip")
        zipped = json.loads(gzip.decompress(body))
        self.assertEqual(zipped["game"], "blackjack")

        status, headers, body = self.post("/api/simulate", config)
        self.assertEqual(status, 200)
        self.assertNotIn("Content-Encoding", headers)
        self.assertEqual(json.loads(body), zipped)

    def test_bad_body_is_400(self):
        status, _, body = self.post("/api/simulate", b"{not json")
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(body))

        status, _, body = self.post("/api/simulate", {"players": 1})
        self.assertEqual(status, 400)
        self.assertIn("players", json.loads(body)["error"])

    def test_unknown_path_is_404(self):
        status, _, _ = self.post("/api/nothing-here", {})
        self.assertEqual(status, 404)

    def test_over_budget_blackjack_batch(self):
        config = {"game": "blackjack", "players": 200, "rounds": 100, "games": 1000}
        status, _, body = self.post("/api/batch", config)
        self.assertEqual(status, 400)
        self.assertIn("up to 500 games fit", json.loads(body)["error"])

        # The stream route has sent its 200 before it validates, so the
        # refusal is its one line.
        status, headers, body = self.post("/api/batch/stream", config)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "application/x-ndjson")
        lines = [json.loads(line) for line in body.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        self.assertIn("the budget is 10 million", lines[0]["error"])

    def test_stream_stops_when_client_leaves(self):
        # Inside the budget but several seconds of work; the client reads
        # one progress line and hangs up.
        config = {"game": "blackjack", "players": 50, "rounds": 100, "games": 1000, "seed": 1}
        body = json.dumps(config).encode()
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            sock = socket.create_connection(("127.0.0.1", self.port), timeout=60)
            try:
                sock.sendall(b"POST /api/batch/stream HTTP/1.1\r\nHost: test\r\n"
                             b"Content-Type: application/json\r\n"
                             b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
                received = b""
                while b'{"progress"' not in received:
                    chunk = sock.recv(4096)
                    self.assertTrue(chunk, "stream closed before any progress")
                    received += chunk
            finally:
                sock.close()
            deadline = time.monotonic() + 60
            while "batch cancelled" not in captured.getvalue() and time.monotonic() < deadline:
                time.sleep(0.05)
            log = captured.getvalue()
        lines = [line for line in log.splitlines() if "batch cancelled" in line]
        self.assertEqual(len(lines), 1, log)
        self.assertRegex(lines[0], r"^\[ludicrous\] batch cancelled: \d+ of \d+ chunks ran$")
        ran, total = (int(n) for n in lines[0].split(": ")[1].split(" chunks")[0].split(" of "))
        self.assertLess(ran, total)


if __name__ == "__main__":
    unittest.main()
