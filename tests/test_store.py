import os
import tempfile
import unittest

from forge.model import Graph, GraphError, STATUS_DONE
from forge.store import EVENT_FILE, Store, load_project


def commit(store, graph, ev):
    stamped = store.append([ev])[0]
    graph.apply(stamped)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.store = Store(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_creates_log(self):
        self.store.init()
        self.assertTrue(os.path.exists(os.path.join(self.dir, EVENT_FILE)))

    def test_roundtrip_reconstructs_graph(self):
        g = Graph()
        commit(self.store, g, g.create_task("Snake Game"))
        commit(self.store, g, g.expand("snake-game", [{"title": "Window"}, {"title": "Renderer"}]))
        commit(self.store, g, g.start("window"))
        commit(self.store, g, g.verify_pass("window"))
        self.assertEqual(g.tasks["window"].status, STATUS_DONE)
        # fresh load from disk == same graph
        store2, g2 = load_project(self.dir)
        self.assertEqual(g2.tasks["window"].status, STATUS_DONE)
        self.assertEqual(g2.tasks["snake-game"].depends_on, ["window", "renderer"])
        self.assertEqual(len(store2.read_events()), 4)

    def test_seq_is_monotonic_across_appends(self):
        g = Graph()
        commit(self.store, g, g.create_task("A"))
        commit(self.store, g, g.create_task("B"))
        seqs = [ev["seq"] for ev in self.store.read_events()]
        self.assertEqual(seqs, [1, 2])

    def test_undo_truncates_and_refolds(self):
        g = Graph()
        commit(self.store, g, g.create_task("A"))
        commit(self.store, g, g.create_task("B"))
        commit(self.store, g, g.add_dependency("b", "a"))
        removed = self.store.undo(1)
        self.assertEqual(removed[0]["op"], "dependency_added")
        g2 = Graph.from_events(self.store.read_events())
        self.assertEqual(g2.tasks["b"].depends_on, [])
        with self.assertRaises(GraphError):
            self.store.undo(99)  # more than available

    def test_undo_everything(self):
        g = Graph()
        commit(self.store, g, g.create_task("A"))
        commit(self.store, g, g.create_task("B"))
        self.store.undo(2)
        self.assertEqual(self.store.read_events(), [])

    def test_torn_last_line_is_skipped(self):
        g = Graph()
        commit(self.store, g, g.create_task("A"))
        with open(self.store.path, "a", encoding="utf-8") as f:
            f.write('{"op": "task_created", "id": "brok')
        events = self.store.read_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(Graph.from_events(events).tasks["a"].title, "A")


    def test_append_after_multibyte_titles_does_not_corrupt_log(self):
        """Regression: _recover_tail computed byte offsets in character
        space, so an em-dash title (3 bytes/char) made the next append
        truncate a VALID last event and glue the new event onto it —
        corrupting the log exactly like a torn write. SPEC §12.5."""
        self.store.init()
        self.store.append([{"op": "task_created", "id": "snake",
                            "title": "Build a Snake game — Foundation"}])
        out = self.store.append([{"op": "task_created", "id": "renderer",
                                  "title": "Renderer"}])
        self.assertEqual([e["seq"] for e in out], [2])
        evs = self.store.read_events()
        self.assertEqual([e["seq"] for e in evs], [1, 2])
        self.assertEqual(evs[1]["id"], "renderer")
        with open(self.store.path, encoding="utf-8") as f:
            for i, ln in enumerate(f, 1):
                if ln.strip():
                    import json
                    json.loads(ln)  # every line must parse

    def test_recover_tail_truncates_torn_tail_after_multibyte_lines(self):
        """Torn-tail recovery must still work when the log contains
        multi-byte UTF-8: the torn line is discarded, seqs re-stamp."""
        self.store.init()
        self.store.append([{"op": "task_created", "id": "a",
                            "title": "Alpha — Foundation"},
                           {"op": "task_created", "id": "b", "title": "Beta"}])
        # simulate a crash: last line truncated mid-JSON (no trailing \n)
        with open(self.store.path, encoding="utf-8") as f:
            raw = f.read()
        cut = raw.rfind("\n") + 1  # keep every complete line
        with open(self.store.path, "w", encoding="utf-8") as f:
            f.write(raw[:cut])
            f.write('{"op": "task_created", "id": "x", "title": "Torn')
        out = self.store.append([{"op": "task_created", "id": "c", "title": "Gamma"}])
        self.assertEqual([e["seq"] for e in out], [3])
        self.assertEqual([e["id"] for e in self.store.read_events()], ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
