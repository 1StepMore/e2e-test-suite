"""E2E: ``omni-suite pipeline`` over a GENERIC OpenAI-compatible endpoint.

e2e-test-suite#448 — the "reuse an existing model" path must work end-to-end
with NO provider key and NO FAKE_LLM: a local HTTP server stands in for any
OpenAI-compatible service (company gateway, local Ollama, new third-party host),
and the pipeline is driven with only ``LLM_BASE_URL`` + ``LLM_API_KEY`` +
``LLM_MODEL``. Hermetic: localhost only, no external network, no real keys.

The wire fake mimics ``ol_pool.fake._FakeModelPool`` behavior over HTTP —
translation echoes the delimited source prefixed with the target language
(the exact output shape the ``--fake-llm`` e2e runs are green with), the
judge returns fixed high scores, profiling returns the fake StyleGuide dict.
That makes the gates deterministic without weakening what this test proves:
the REAL router, REAL config resolution (pipeline-pinned
``config/test_universal.yaml`` incl. its generic endpoint entries), REAL
litellm HTTP call against ``{LLM_BASE_URL}/chat/completions``.

Also locks the run-record contract (#448 acceptance criteria): the machine
payload carries the endpoint provenance (mode, base_url source, model) and
never records the key value.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent

# Same canned responses as ol_pool.fake._FakeModelPool, over the wire.
JUDGE_RESPONSE = {
    "accuracy": 95,
    "fluency": 95,
    "adequacy": 95,
    "terminology_consistency": 95,
    "format_preservation": 95,
    "score": 95,
    "format_errors": [],
}
PROFILE_RESPONSE = {
    "tone": "neutral",
    "register": "general",
    "target_audience": "general readers",
    "key_conventions": [
        "Use clear, concise language",
        "Preserve technical terms verbatim when first introduced",
    ],
    "vocabulary": [],
    "avoid": ["obscure jargon", "ambiguous pronouns"],
    "summary": "Auto-generated profile (wire fake).",
}


class _EndpointRecorder:
    """Thread-safe request log shared with the HTTP handler."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.requests: list[dict[str, str]] = []

    def record(self, path: str, auth: str, kind: str) -> None:
        with self.lock:
            self.requests.append({"path": path, "auth": auth, "kind": kind})

    @property
    def kinds(self) -> list:
        with self.lock:
            return [r["kind"] for r in self.requests]


def _extract_delimited(text: str, start: str, end: str) -> str | None:
    if start not in text or end not in text:
        return None
    return text.split(start, 1)[1].split(end, 1)[0].strip()


class _FakeOpenAIHandler(BaseHTTPRequestHandler):
    """Minimal OpenAI /chat/completions stand-in driven by prompt shape.

    Detection order matters: judge prompts ALSO carry the [USER_TEXT_*]
    delimiters, so the judge signature is matched first.
    """

    recorder: _EndpointRecorder  # injected per server instance

    def log_message(self, *args) -> None:  # noqa: N802 - stdlib signature
        pass  # keep pytest output clean

    def do_POST(self) -> None:  # noqa: N802 - stdlib signature
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        content = ""
        for message in body.get("messages", []):
            if message.get("role") == "user":
                content = message.get("content") or ""
        auth = self.headers.get("Authorization", "")

        if "Return a JSON object with exactly these seven fields" in content:
            kind, payload = "judge", JUDGE_RESPONSE
        elif "[USER_TEXT_START]" in content:
            source = _extract_delimited(content, "[USER_TEXT_START]", "[USER_TEXT_END]")
            target = "zh"
            marker = "Translate from "
            if marker in content:
                pair = content.split(marker, 1)[1].split(":", 1)[0]
                parts = pair.split(" to ")
                if len(parts) == 2:
                    target = parts[1].strip()
            kind = "translate"
            payload = f"[{target}] {source or ''}"
        else:
            kind, payload = "profile", PROFILE_RESPONSE

        self.recorder.record(self.path, auth, kind)
        response = {
            "id": "chatcmpl-e2e-fake-endpoint",
            "object": "chat.completion",
            "created": 0,
            "model": body.get("model", "fake"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": payload},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        data = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def fake_endpoint():
    recorder = _EndpointRecorder()

    class _Handler(_FakeOpenAIHandler):
        pass

    _Handler.recorder = recorder
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1", recorder
    finally:
        server.shutdown()
        server.server_close()


class TestPipelineCustomEndpoint:
    """#448 AC: a local fake endpoint runs the REAL pipeline chain."""

    def test_pipeline_runs_over_generic_endpoint(self, fake_endpoint, tmp_path):
        base_url, recorder = fake_endpoint
        # Random per-run credential for the wire: nothing sensitive is ever
        # hardcoded here — the value exists only inside this test process and
        # the localhost fake.
        endpoint_key = "test-key-" + uuid.uuid4().hex

        # OPP has no markdown extractor (MD is an OUTPUT format), so the
        # pipeline entry document must be a real DOCX — same as every other
        # e2e pipeline test.
        import docx as docx_lib

        sample = tmp_path / "e2e_endpoint_input.docx"
        document = docx_lib.Document()
        document.add_heading("Endpoint E2E", level=1)
        document.add_paragraph(
            "This short paragraph exists only to give the pipeline a source "
            "unit to translate. It mentions one term: Omni Suite."
        )
        document.save(sample)
        run_id = f"endpoint-e2e-{uuid.uuid4().hex[:8]}"
        out_path = tmp_path / "e2e_endpoint_result.html"

        env = {
            **os.environ,
            # The generic triple — no provider key anywhere.
            "LLM_BASE_URL": base_url,
            "LLM_API_KEY": endpoint_key,
            "LLM_MODEL": "e2e-fake-endpoint-model",
            # Neutralize every provider key ("" counts as absent, matching
            # how OL's pool and the suite gate resolve vars) — this also
            # beats Omni_Localizer/.env, whose loader uses setdefault.
            "AMD_API_KEY": "",
            "ZHIPU_API_KEY": "",
            "SPARK_API_KEY": "",
            "OMNI_TEST_FAKE_LLM": "",
            # Fresh per-run cache: OL's persistent ~/.omni_cache would serve
            # the second run of this content without ever dialing the
            # endpoint (validation-loop-log pitfall).
            "OMNI_CACHE_DIR": str(tmp_path / "ol-cache"),
            # The pipeline prints ✅/❌ markers; force UTF-8 so a cp936
            # console cannot crash the child on Windows.
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }

        result = subprocess.run(
            [sys.executable, "-m", "omni_suite", "--json", "pipeline",
             str(sample), "--target-format", "html", "--output", str(out_path),
             "--run-id", run_id],
            capture_output=True, text=True, cwd=str(SUITE_ROOT), env=env,
            timeout=600,
        )

        assert result.returncode == 0, (
            f"pipeline failed (exit {result.returncode})\n"
            f"--- stdout tail ---\n{result.stdout[-2000:]}\n"
            "stderr tail follows\n" + result.stderr[-3000:]
        )

        envelope = json.loads(result.stdout)
        assert envelope["success"] is True, envelope
        content = envelope["content"]
        stages = content["stages"]
        assert {name: stages[name]["status"] for name in ("opp", "ol", "orf")} == {
            "opp": "complete", "ol": "complete", "orf": "complete",
        }, stages

        # Run-record provenance (#448 AC): endpoint mode + base_url source +
        # model, and NEVER the key value.
        llm = content["llm"]
        assert llm["mode"] == "openai-compatible-endpoint", llm
        assert llm["base_url_source"] == "env:LLM_BASE_URL", llm
        assert llm["model"] == "e2e-fake-endpoint-model", llm
        assert llm["provider_keys_present"] == [], llm
        combined = result.stdout + result.stderr
        assert endpoint_key not in combined, (
            "the endpoint key value must never appear in the run output"
        )

        # The traffic really hit the local endpoint with the given key.
        kinds = recorder.kinds
        assert "translate" in kinds, kinds
        for request in recorder.requests:
            assert request["auth"] == f"Bearer {endpoint_key}", request
            assert request["path"].endswith("/chat/completions"), request

        assert out_path.exists(), f"output missing: {out_path}"
        assert out_path.stat().st_size > 0
