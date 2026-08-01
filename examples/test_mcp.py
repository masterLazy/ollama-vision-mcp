"""End-to-end MCP protocol test.

Spawns the server over stdio (the same way VS Code Copilot launches it), then
performs the MCP handshake and calls each tool to verify the protocol layer.

Usage:
    python examples/test_mcp.py
    VISION_MCP_MODEL=qwen3.5:9b python examples/test_mcp.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

SERVER_CMD = [sys.executable, "-m", "ollama_vision_mcp"]


def main() -> int:
    proc = subprocess.Popen(
        SERVER_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=os.getcwd(),
    )
    assert proc.stdin and proc.stdout

    req_id = 0

    def request(method: str, params: dict | None = None) -> dict:
        nonlocal req_id
        req_id += 1
        msg: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line.strip():
            raise RuntimeError("server closed stdout unexpectedly")
        return json.loads(line)

    def notify(method: str) -> None:
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        proc.stdin.flush()

    # 1) initialize handshake
    init = request("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "ollama-vision-mcp-test", "version": "0.0.1"},
    })
    print("initialize ->", init.get("result", {}).get("serverInfo"))
    notify("notifications/initialized")

    # 2) tools/list
    tl = request("tools/list")
    names = [t["name"] for t in tl["result"]["tools"]]
    print("tools ->", names)
    expected = {"describe_image", "list_images", "extract_text", "vision_status"}
    assert set(names) == expected, f"unexpected tools: {names}"

    # 3) vision_status
    vs = request("tools/call", {"name": "vision_status", "arguments": {}})
    vs_text = vs["result"]["content"][0]["text"]
    print("vision_status ->", " ".join(vs_text.split())[:160])

    # 4) describe_image on the first inbox image (if any)
    inbox = os.path.abspath(os.path.join(os.getcwd(), ".ai", "inbox"))
    images = [
        os.path.join(inbox, f)
        for f in (os.listdir(inbox) if os.path.isdir(inbox) else [])
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))
    ]
    if images:
        di = request("tools/call", {
            "name": "describe_image",
            "arguments": {"path": images[0], "mode": "ui"},
        })
        di_text = di["result"]["content"][0]["text"]
        print("describe_image ->", " ".join(di_text.split())[:160])

        et = request("tools/call", {
            "name": "extract_text",
            "arguments": {"path": images[0]},
        })
        et_text = et["result"]["content"][0]["text"]
        print("extract_text   ->", " ".join(et_text.split())[:160])

        li = request("tools/call", {
            "name": "list_images",
            "arguments": {},
        })
        li_text = li["result"]["content"][0]["text"]
        print("list_images    ->", " ".join(li_text.split())[:120])
    else:
        print("describe_image -> skipped (no image in .ai/inbox)")

    # 5) negative case: missing file
    neg = request("tools/call", {
        "name": "describe_image",
        "arguments": {"path": os.path.join(inbox, "does_not_exist.png")},
    })
    neg_text = neg["result"]["content"][0]["text"]
    print("describe_image(missing) ->", " ".join(neg_text.split())[:120])

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("MCP e2e OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
