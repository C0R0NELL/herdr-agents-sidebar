"""Identity isolation and token updates at the native snapshot boundary."""

import unittest

from layout import AgentKey, Machine, layout, patches


def snapshot(names=("first", "second"), workspace="w1", tokens=None):
    return {
        "workspaces": [{"workspace_id": workspace, "label": "project"}],
        "panes": [{"pane_id": f"{workspace}:p{i}", "workspace_id": workspace,
                   "tokens": (tokens or {}).get(f"{workspace}:p{i}", {})}
                  for i, _ in enumerate(names, 1)],
        "agents": [{"pane_id": f"{workspace}:p{i}", "workspace_id": workspace, "name": name,
                    "agent": "codex", "tokens": (tokens or {}).get(f"{workspace}:p{i}", {})}
                   for i, name in enumerate(names, 1)],
    }


class LayoutTests(unittest.TestCase):
    def test_repeated_native_ids_and_labels_stay_independent(self):
        machines = [Machine("local", "one", "machine01", snapshot()),
                    Machine("remote", "two", "machine02", snapshot())]
        result = layout(machines, gap_between_machines=True)
        self.assertEqual(len(result), 4)
        local = AgentKey("local", "one", "w1", "w1:p1")
        remote = AgentKey("remote", "two", "w1", "w1:p1")
        self.assertEqual(result[local]["has_machine"], "machine01")
        self.assertEqual(result[remote]["has_machine"], "machine02")
        self.assertEqual(result[local]["has_project"], "project")
        self.assertEqual(result[AgentKey("local", "one", "w1", "w1:p2")]["has_gap"], "·")
        self.assertIsNone(result[AgentKey("remote", "two", "w1", "w1:p2")]["has_gap"])

    def test_old_anchor_is_cleared_before_new_anchor_is_set(self):
        old = {"w1:p1": {"has_machine": "machine01", "has_project": ">> project", "foreign": "preserve"}}
        data = snapshot(tokens=old)
        data["agents"].reverse()
        machine = Machine("local", "one", "machine01", data)
        desired = layout([machine], gap_between_machines=False)
        removals, updates = patches([machine], desired)
        self.assertEqual(removals[0].key.pane_id, "w1:p1")
        self.assertEqual(removals[0].tokens, {"has_machine": None, "has_project": None})
        new_anchor = next(patch for patch in updates if patch.key.pane_id == "w1:p2")
        self.assertEqual(new_anchor.tokens["has_machine"], "machine01")
        self.assertNotIn("foreign", removals[0].tokens)
        self.assertTrue(all("foreign" not in patch.tokens for patch in updates))

    def test_native_icons_and_names_align_without_visible_markers(self):
        data = snapshot()
        for field in ("workspaces", "panes", "agents"):
            data[field] += snapshot(names=("third",), workspace="w2")[field]
        machine = Machine("local", "one", "machine", data)
        desired = layout([machine], gap_between_machines=False)
        for tokens in desired.values():
            native_indent = 3 if tokens["has_machine"] or tokens["has_project"] else 1
            prefix = tokens["has_agent_prefix"]
            self.assertTrue(prefix and set(prefix) == {"\u2800"})
            # Native custom-to-icon separator is three cells, then icon + space.
            self.assertEqual(native_indent + len(prefix) + 3, 8)
            self.assertEqual(native_indent + len(prefix) + 5, 10)
            self.assertEqual(tokens["has_agent"], tokens["has_agent"].lstrip("\u2800"))
            self.assertNotIn(">", tokens["has_agent"])
            if tokens["has_project"]:
                project_indent = 3 if tokens["has_machine"] else 1
                project_line = tokens["has_project"].replace("\u2800", " ")
                self.assertEqual(project_indent + len(project_line) - len(project_line.lstrip()), 3)
                self.assertNotIn(">", project_line)

    def test_live_agents_replace_the_previous_visible_marker(self):
        data = snapshot(tokens={"w1:p1": {"has_agent_prefix": "\u2800\u2800>", "foreign": "keep"}})
        machine = Machine("local", "one", "machine", data)
        _, updates = patches([machine], layout([machine], gap_between_machines=False))
        updated = next(patch.tokens for patch in updates if patch.key.pane_id == "w1:p1")
        self.assertEqual(updated["has_agent_prefix"], "\u2800\u2800")
        self.assertNotIn("foreign", updated)

    def test_sessions_and_homonymous_workspaces_are_separate_groups(self):
        data = snapshot(names=("same",))
        second = snapshot(names=("same",), workspace="w2")
        for field in ("workspaces", "panes", "agents"):
            data[field] += second[field]
        result = layout([Machine("local","one","machine",data),
                         Machine("local","two","machine",snapshot(names=("same",)))], gap_between_machines=False)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(tokens["has_project"] for tokens in result.values()))
        self.assertTrue(all(tokens["has_gap"] is None for tokens in result.values()))

    def test_native_pane_without_agent_loses_only_owned_tokens(self):
        data = snapshot(names=())
        data["panes"] = [{"pane_id":"w1:p1", "workspace_id":"w1", "tokens": {
            "has_machine":"machine", "has_agent":"old", "has_agent_prefix":"\u2800\u2800>", "foreign":"keep"}}]
        machine = Machine("local","one","machine",data)
        removals, updates = patches([machine], layout([machine],gap_between_machines=False))
        self.assertEqual(removals[0].tokens, {"has_machine":None,"has_agent":None,"has_agent_prefix":None})
        self.assertEqual(updates, [])

    def test_matching_state_is_quiet_until_a_ttl_renewal(self):
        machine = Machine("local","one","machine",snapshot(names=("first",)))
        desired = layout([machine],gap_between_machines=False)
        current = next(iter(desired.values()))
        for field in ("panes","agents"):
            machine.snapshot[field][0]["tokens"] = current.copy()
        self.assertEqual(patches([machine],desired), ([],[]))
        clears, updates = patches([machine],desired,renew=True)
        self.assertEqual(clears, [])
        self.assertEqual(updates[0].tokens, {k:v for k,v in current.items() if v is not None})

    def test_disconnected_cache_does_not_publish_or_disappear(self):
        live = Machine("local","one","machine01",snapshot(names=("first",)))
        stale = Machine("remote","two","machine02",snapshot(names=("first",)),stale=True)
        desired = layout([live,stale],gap_between_machines=True)
        self.assertEqual(len(desired),2)
        self.assertEqual(desired[AgentKey("local","one","w1","w1:p1")]["has_gap"],"·")
        clears, updates = patches([live,stale],desired,renew=True)
        self.assertTrue(all(patch.key.machine=="local" for patch in clears+updates))

    def test_labels_are_bounded_and_controls_cannot_change_presentation(self):
        machine = Machine("local","one","\x1bmachine\n",snapshot(names=("é工作\u202e"*100,)))
        desired = layout([machine],gap_between_machines=False)
        tokens = next(iter(desired.values()))
        self.assertEqual(tokens["has_machine"],"machine")
        self.assertTrue(tokens["has_agent"].startswith("é工作"))
        self.assertLessEqual(len(tokens["has_agent"]),80)
        self.assertNotIn("\u202e",tokens["has_agent"])

    def test_ambiguous_or_noncontiguous_native_order_is_rejected(self):
        data = snapshot()
        data["agents"].append(data["agents"][0].copy())
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            layout([Machine("local","one","machine",data)],gap_between_machines=False)
        data = snapshot()
        data["agents"].insert(1,{"pane_id":"w2:p1","workspace_id":"w2","name":"third"})
        with self.assertRaisesRegex(ValueError,"Noncontiguous"):
            layout([Machine("local","one","machine",data)],gap_between_machines=False)


if __name__ == "__main__":
    unittest.main()
