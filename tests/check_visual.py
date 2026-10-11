"""Stage-zero renderer proof; not the full plugin acceptance check."""

import argparse
from html import escape
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout import Machine, layout
from herdr_harness import BASE_CONFIG, PROOF_ROWS, HerdrHarness, PROFILE_ID, SESSION


def sidebar_lines(lines, width):
    start = next(i for i, line in enumerate(lines) if line[1:width].strip().startswith("agents")) + 2
    return [(i, line[:width-1]) for i, line in enumerate(lines) if i >= start and i < len(lines)-1]


def capture_svg(screen, rows, path, width, *, title="Native Herdr 0.9.3 sidebar captured from two isolated servers"):
    """Export actual captured terminal cells, not a separately rendered mock."""
    output = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width*10+16}" height="{len(rows)*22+16}" viewBox="0 0 {width*10+16} {len(rows)*22+16}">',
              f'<title>{escape(title)}</title>',
              '<rect width="100%" height="100%" fill="#181825"/>',
              '<g font-family="DejaVu Sans Mono, monospace" font-size="16">']
    for index, (y, _) in enumerate(rows):
        for x in range(width-1):
            cell = screen.buffer[y][x]
            char = cell.data.replace("\u2800", " ")
            if not char.strip():
                continue
            color = "#"+cell.fg if len(cell.fg)==6 else "#cdd6f4"
            weight = "bold" if cell.bold else "normal"
            output.append(f'<text x="{x*10+8}" y="{index*22+24}" fill="{color}" font-weight="{weight}">{escape(char)}</text>')
    output.append('</g></svg>\n')
    path.write_text('\n'.join(output))


def check(width, evidence=None, *, show_separator=False):
    with HerdrHarness() as h:
        h.start("local", width)
        h.start("remote", width)
        local, remote = h.populate("local"), h.populate("remote")
        assert local[0][0] == remote[0][0], "Fixture must repeat native IDs across machines"
        machines = [Machine(name, SESSION, label, h.api(name,"session.snapshot")["snapshot"])
                    for name,label in (("local","machine01"),("remote","machine02"))]
        desired = layout(machines, gap_between_machines=show_separator)
        for machine in machines:
            h.publish(machine.id, [(key.pane_id,tokens) for key,tokens in desired.items() if key.machine==machine.id])
        h.connect_remote()
        # This command crosses the actual native saved-machine API bridge.
        import subprocess
        env = h.environment("local")
        env["PATH"] = str(h.root/"bin") + ":" + env["PATH"]
        result = subprocess.run([h.binary, "--machine", PROFILE_ID, "api", "snapshot"],
                                env=env, cwd=h.root, capture_output=True, text=True, timeout=15, check=True)
        snapshot = json.loads(result.stdout)["result"]["snapshot"]
        assert snapshot["agents"][0]["tokens"]["has_machine"] == "machine02"

        term = h.terminal()
        try:
            lines = term.wait(lambda lines: sum("machine02" in line[:width] for line in lines) == 2
                             and sum(line[10:16] == "agente" for line in lines) == 6)
            rows = sidebar_lines(lines, width)
            visible = [(y, text) for y, text in rows if text.strip()]
            expected = ["machine01", "projeto01", "agente01", "agente02",
                        "projeto02", "agente03"] + (["·"] if show_separator else []) + ["machine02",
                        "projeto01", "agente01", "agente02",
                        "projeto02", "agente03"]
            assert len(visible) == len(expected), visible
            assert [y for y, _ in visible] == list(range(visible[0][0], visible[0][0]+len(expected))), "Unexpected blank row"
            for (y, text), wanted in zip(visible, expected):
                assert ">" not in text, text
                if wanted.startswith("agente"):
                    # Blank prefix compensates the native first/continuation offsets.
                    available = width - 11
                    name = wanted
                    clipped = name if len(name) <= available else name[:available-1] + "…"
                    assert text[6:].rstrip() == "· ○ " + clipped, text
                    assert text.index("·") == 6, text
                    assert text.index("○") == 8, text
                    assert not text[:6].replace("\u2800", " ").strip(), text
                    assert text.count("○") == 1, text
                    name_cell = term.screen.buffer[y][10]
                    assert name_cell.fg == "bd93f9" and not name_cell.bold, name_cell
                else:
                    assert text.replace("\u2800", " ").strip() == wanted, text
                    x = text.index(wanted)
                    if wanted.startswith("projeto"):
                        assert x == 3, text
                    cell = term.screen.buffer[y][x]
                    assert cell.fg == ("89b4fa" if wanted.startswith("projeto") else "f1fa8c") and cell.bold, cell

            if evidence and width == 36:
                evidence.parent.mkdir(parents=True, exist_ok=True)
                capture_svg(term.screen, visible, evidence.with_suffix(".svg"), width)

            # Keep the native indicator, including its state-dependent color.
            # Exercise a real fixture transition without rewriting its tokens.
            agent_y = visible[5][0]
            icon_x = visible[5][1].index("○")
            for seq, (state, glyph, color) in enumerate(
                    (("working", "◐", "f9e2af"), ("blocked", "×", "f38ba8"),
                     ("idle", "✓", "94e2d5")), 1):
                h.api("local", "pane.report_agent", {
                    "pane_id": local[-1][0], "source": "test:fixture",
                    "agent": "codex", "state": state, "seq": seq,
                })
                term.wait(lambda lines: lines[agent_y][icon_x] == glyph)
                assert term.screen.buffer[agent_y][icon_x].fg == color
            # Herdr shows an unseen completed turn as Done; native focus marks
            # it seen and returns the idle indicator. Preserve that distinction.
            term.click(5, agent_y)
            term.wait(lambda lines: lines[agent_y][icon_x] == "○")
            assert term.screen.buffer[agent_y][icon_x].fg == "a6e3a1"

            # Machine/project headers focus their own real anchor, across machines.
            remote_start = 6 + int(show_separator)
            for row_index, machine, pane in ((0,"local",local[0][0]), (4,"local",local[-1][0]),
                                            (remote_start,"remote",remote[0][0]),
                                            (remote_start+4,"remote",remote[-1][0])):
                term.click(4, visible[row_index][0])
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    term.read(.1)
                    if h.api(machine,"session.snapshot")["snapshot"]["focused_pane_id"] == pane:
                        break
                else:
                    raise AssertionError("Header did not focus its native anchor")
                label = "Local" if machine == "local" else "machine02"
                term.wait(lambda lines: any("new · " + label[:4] in line[:width] for line in lines))

            if evidence and width == 36:
                evidence.parent.mkdir(parents=True, exist_ok=True)
                evidence.write_text(json.dumps({
                    "herdr": "0.9.3", "protocol": 22, "width": width,
                    "show_separator": show_separator,
                    "transport": "local SSH shim, real Herdr servers and bridges",
                    "rows": [text.replace("\u2800", " ").rstrip() for _,text in visible],
                }, ensure_ascii=False, indent=2)+"\n")

            if width == 36:
                h.environment("solo")
                h.config_path("solo").write_text(BASE_CONFIG.replace("WIDTH", "36") + PROOF_ROWS)
                solo = h.terminal("solo", attach="local")
                try:
                    one = solo.wait(lambda lines: sum(line[10:16] == "agente" for line in lines) == 3)
                    body = [text.replace("\u2800", " ").strip() for _,text in sidebar_lines(one,width) if text.strip()]
                    if show_separator:
                        assert body[-1] == "·", "Expected shared-token limitation was not reproduced"
                        result = "shared gap token trails the final local agent"
                        print("REPRODUCED: a shared gap token becomes trailing in a local-only client")
                    else:
                        assert "·" not in body, "Disabled separator appeared in a local-only client"
                        result = "disabled machine gaps remain absent in a local-only client"
                    assert "machine02" not in body, "Second client unexpectedly has a remote catalog"
                    if evidence:
                        report = json.loads(evidence.read_text())
                        report["different_client_catalog"] = {
                            "rows": body, "result": result,
                        }
                        evidence.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
                finally:
                    solo.close()

            # The API normalizes controls; native clipping handles wide characters.
            h.api("local", "pane.report_metadata", {
                "pane_id": local[0][0], "source": "plugin:c0r0nell.agents-sidebar",
                "tokens": {"has_agent": "café 工作\x1b\nlabel"}, "ttl_ms": 60000,
            })
            updated = h.api("local", "session.snapshot")["snapshot"]["agents"][0]["tokens"]["has_agent"]
            assert all(ord(char) >= 32 for char in updated), "Unnormalized control in metadata"
            lines = term.wait(lambda lines: any("café" in line[:width] for line in lines))
            assert all(term.screen.buffer[y][width-1].data == "│" for y in range(1,59)), "Wide text spilled into the pane"
        finally:
            term.close()
    print(f"PASS: native layout/colors/focus at {width} columns, separator {'On' if show_separator else 'Off'}, two isolated servers")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--show-separator", action="store_true", help="enable optional machine gaps (default: Off)")
    args = parser.parse_args()
    for width in (18, 22, 36):
        check(width, args.evidence, show_separator=args.show_separator)


if __name__ == "__main__":
    main()
