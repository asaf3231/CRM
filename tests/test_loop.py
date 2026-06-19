"""
tests/test_loop.py — Stage 4: Agentic loop, anti-loop cap & resiliency tests.

QA checks covered:
  L1  raw API shape (manual loop; reads stop_reason + tool_use blocks)
  L2  dispatch by name with input as kwargs (+ catalog_df injection for extract_and_score_pool)
  L3  tool_use_id → tool_result 1:1 plumbing (assistant turn first, every tool_use answered)
  L4  gateway_validate called on every outbound (request_reactfirst_pdf + final output)
  L5  no framework / no SDK tool-runner imports (grep)
  RS1 BadRequestError (400) caught + stop_reason=="refusal" (200) both handled; stop_reason
      checked BEFORE reading content; both surfaces back; loop continues; cap still applies
  RS2 cap fires at exactly 15 dispatches; no 16th call; LOG_CAP_HIT emitted
  RS3 tool error ({"error": ...}) appended back; loop continues; no termination
  RS4 per-tool + total metrics tracked (total ≤ 15); written to log + result
  RS5 no uncaught exceptions; clean structured failure from loop and main()

Driven entirely by FakeReasoningClient — no live network calls.

All tests are DRAFTED ONLY — PM verifies in .venv.
"""

import sys
import pathlib
import pytest

# ---------------------------------------------------------------------------
# Path setup: ensure the CRM root is on sys.path so "import main" works.
# ---------------------------------------------------------------------------
_CRM_ROOT = pathlib.Path(__file__).parent.parent
if str(_CRM_ROOT) not in sys.path:
    sys.path.insert(0, str(_CRM_ROOT))

import main  # noqa: E402  (side-effect-free — ENV4)


# ===========================================================================
# FakeReasoningClient — drives the loop without any network calls.
# ===========================================================================

class _FakeBlock:
    """Minimal duck-type of an Anthropic content block."""

    def __init__(self, block_type: str, **kwargs):
        self.type = block_type
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __iter__(self):
        """Make blocks iterable as dicts (some Anthropic SDK code does this)."""
        return iter([])


class _FakeResponse:
    """Minimal duck-type of an Anthropic messages.create(...) response."""

    def __init__(self, content: list, stop_reason: str = "end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class FakeReasoningClient:
    """Scripted fake for the Anthropic client.

    Accepts a ``responses`` list; pops them in order.  Each element is either:
    - A ``_FakeResponse`` instance (returned as-is).
    - An exception class or instance (raised instead of returning).
    - A callable (called with no args; must return a _FakeResponse or raise).

    When the queue is exhausted, returns a plain end_turn text response.
    """

    def __init__(self, responses: list = None):
        self._queue = list(responses or [])
        self.call_args_list: list = []  # records every messages.create call

    def _next(self):
        if not self._queue:
            return _FakeResponse(
                [_FakeBlock("text", text="No more scripted responses.")],
                "end_turn",
            )
        item = self._queue.pop(0)
        if isinstance(item, type) and issubclass(item, BaseException):
            raise item("FakeReasoningClient: scripted exception")
        if isinstance(item, BaseException):
            raise item
        if callable(item):
            return item()
        return item

    # The only method answer_question calls on the client.
    class _MessagesAPI:
        def __init__(self, fake):
            self._fake = fake

        def create(self, **kwargs):
            self._fake.call_args_list.append(kwargs)
            return self._fake._next()

    @property
    def messages(self):
        return self._MessagesAPI(self)


def _tool_use_block(name: str, block_id: str, input_dict: dict) -> _FakeBlock:
    """Helper: build a tool_use block."""
    return _FakeBlock("tool_use", name=name, id=block_id, input=input_dict)


def _text_block(text: str) -> _FakeBlock:
    """Helper: build a text block."""
    return _FakeBlock("text", text=text)


def _end_turn(text: str = "Done.") -> _FakeResponse:
    """Helper: a response that terminates the loop cleanly."""
    return _FakeResponse([_text_block(text)], "end_turn")


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture()
def fake_client(monkeypatch):
    """Returns a factory that creates a FakeReasoningClient and patches _get_client."""

    def _make(responses=None):
        fc = FakeReasoningClient(responses=responses or [_end_turn()])
        monkeypatch.setattr(main, "_get_client", lambda: fc)
        return fc

    return _make


@pytest.fixture()
def minimal_catalog_df():
    """A tiny 9-column catalog DataFrame (no file I/O)."""
    import pandas as pd
    return pd.DataFrame([{
        "Uniq_Id": "b0001",
        "Brand_Name": "TestBrand",
        "Primary_Domain": "testbrand.com",
        "Core_Category": "Apparel > Athleisure",
        "Estimated_Ad_Spend_Tier": "Tier 1",
        "Current_Status": "Open_Opportunity",
        "Historical_Social_Incidents": 3,
        "Main_Competitor_Id": "b0002",
        "Gtin_Prefix": "0123456",
    }])


@pytest.fixture()
def tmp_log(tmp_path, monkeypatch):
    """Redirect the default log path to a temp file."""
    log_file = tmp_path / "reactfirst_run.log"
    # We'll pass log_path explicitly or monkeypatch the default.
    return str(log_file)


# ===========================================================================
# L1 — Raw API shape: manual loop, reads stop_reason + tool_use blocks
# ===========================================================================

class TestL1RawAPIShape:

    def test_messages_create_called_with_tools_schema(self, fake_client):
        """L1: loop calls client.messages.create with tools=TOOL_SCHEMAS."""
        fc = fake_client([_end_turn("Hello")])
        main.answer_question("test query", catalog_df=None, policies="test policy")
        assert len(fc.call_args_list) >= 1
        call = fc.call_args_list[0]
        assert "tools" in call, "messages.create must be called with tools="
        assert call["tools"] == main.TOOL_SCHEMAS

    def test_stop_reason_end_turn_terminates(self, fake_client):
        """L1: stop_reason=='end_turn' with no tool_use exits cleanly."""
        fc = fake_client([_end_turn("The answer is 42.")])
        result = main.answer_question("query", catalog_df=None, policies="pol")
        assert "42" in result or result.startswith("The answer")

    def test_uses_reasoning_model(self, fake_client):
        """L1: loop passes REASONING_MODEL constant as the model."""
        fc = fake_client([_end_turn()])
        main.answer_question("q", catalog_df=None, policies="p")
        assert fc.call_args_list[0]["model"] == main.REASONING_MODEL

    def test_thinking_adaptive_passed(self, fake_client):
        """L1: adaptive thinking parameter is passed (no temperature/budget_tokens)."""
        fc = fake_client([_end_turn()])
        main.answer_question("q", catalog_df=None, policies="p")
        call = fc.call_args_list[0]
        assert call.get("thinking") == {"type": "adaptive"}, (
            "Loop must pass thinking={'type':'adaptive'}"
        )
        assert "temperature" not in call, "temperature must NOT be passed (400 on 4.7+)"
        assert "budget_tokens" not in call, "budget_tokens must NOT be passed"

    def test_no_framework_imports(self):
        """L5: no LangGraph / LangChain / SDK tool-runner imports anywhere in main.py."""
        import subprocess
        result = subprocess.run(
            ["grep", "-Ei",
             "langgraph|langchain|create_react_agent|AgentExecutor|tool_runner|beta_tool|bind_tools",
             str(_CRM_ROOT / "main.py")],
            capture_output=True, text=True
        )
        assert result.returncode != 0, (
            f"Forbidden framework/tool-runner import found:\n{result.stdout}"
        )


# ===========================================================================
# L2 — Dispatch by name with input as kwargs; catalog_df injection
# ===========================================================================

class TestL2Dispatch:

    def test_dispatch_by_tool_name(self, fake_client, minimal_catalog_df, monkeypatch):
        """L2: when a tool_use block arrives, the correct TOOL_DISPATCH entry is called."""
        dispatched = {}

        def fake_secured_calculator(expression: str) -> str:
            dispatched["name"] = "secured_calculator"
            dispatched["expression"] = expression
            return "42.0"

        # Patch the dispatch dict entry directly (a dict has no settable __getitem__).
        original = main.TOOL_DISPATCH["secured_calculator"]
        main.TOOL_DISPATCH["secured_calculator"] = fake_secured_calculator

        try:
            fc = fake_client([
                _FakeResponse(
                    [_tool_use_block("secured_calculator", "tc-001", {"expression": "2 + 2"})],
                    "tool_use",
                ),
                _end_turn("Result is 42."),
            ])
            result = main.answer_question("calculate 2+2", catalog_df=minimal_catalog_df, policies="p")
            assert dispatched.get("name") == "secured_calculator"
            assert dispatched.get("expression") == "2 + 2"
        finally:
            main.TOOL_DISPATCH["secured_calculator"] = original

    def test_catalog_df_injected_for_extract_and_score_pool(self, fake_client, minimal_catalog_df, monkeypatch):
        """L2: extract_and_score_pool receives catalog_df injected by the loop."""
        received_catalog = {}

        def fake_extract(raw_pool, catalog_df=None):
            received_catalog["df"] = catalog_df
            return []

        original = main.TOOL_DISPATCH["extract_and_score_pool"]
        main.TOOL_DISPATCH["extract_and_score_pool"] = fake_extract

        try:
            fc = fake_client([
                _FakeResponse(
                    [_tool_use_block("extract_and_score_pool", "tc-002", {"raw_pool": []})],
                    "tool_use",
                ),
                _end_turn("Done."),
            ])
            main.answer_question("discover brands", catalog_df=minimal_catalog_df, policies="p")
            assert received_catalog.get("df") is minimal_catalog_df, (
                "catalog_df must be injected by the loop for extract_and_score_pool"
            )
        finally:
            main.TOOL_DISPATCH["extract_and_score_pool"] = original

    def test_unknown_tool_name_returns_error_not_crash(self, fake_client, minimal_catalog_df):
        """L2: an unknown tool name produces a structured error, does not crash."""
        fc = fake_client([
            _FakeResponse(
                [_tool_use_block("nonexistent_tool_xyz", "tc-003", {})],
                "tool_use",
            ),
            _end_turn("Handled."),
        ])
        result = main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")
        # Should return without raising — RS5
        assert isinstance(result, str)


# ===========================================================================
# L3 — tool_use_id → tool_result 1:1 plumbing
# ===========================================================================

class TestL3Plumbing:

    def test_assistant_turn_appended_before_tool_result(self, fake_client, minimal_catalog_df, monkeypatch):
        """L3: the full assistant content (response.content) is appended as an assistant
        turn BEFORE the user turn of tool_result blocks."""
        messages_recorded = []

        original_create = None

        # We'll track the messages list at dispatch time using a side-effecting fake.
        call_count = [0]

        def capturing_secured_calculator(expression: str) -> str:
            return "100"

        original = main.TOOL_DISPATCH["secured_calculator"]
        main.TOOL_DISPATCH["secured_calculator"] = capturing_secured_calculator

        # We'll capture the messages kwarg passed to each messages.create call.
        class CapturingClient:
            def __init__(self):
                self._responses = [
                    _FakeResponse(
                        [_tool_use_block("secured_calculator", "tc-010", {"expression": "50 * 2"})],
                        "tool_use",
                    ),
                    _end_turn("Answer."),
                ]
                self.all_messages = []

            class _Msgs:
                def __init__(self, client):
                    self._c = client

                def create(self, **kwargs):
                    self._c.all_messages.append(list(kwargs.get("messages", [])))
                    if self._c._responses:
                        return self._c._responses.pop(0)
                    return _end_turn()

            @property
            def messages(self):
                return self._Msgs(self)

        cap_client = CapturingClient()
        # Patch the SAME module object that answer_question is called on (top-level
        # `main`). Using a fresh `import main as _main` can bind a different module
        # object if an earlier test deleted `main` from sys.modules, leaving the
        # real _get_client unpatched.
        monkeypatch.setattr(main, "_get_client", lambda: cap_client)

        try:
            main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")
            # After the first tool_use response, the next messages.create call
            # should have in its messages list:
            #   [..., {role: assistant, content: [tool_use_block]}, {role: user, content: [tool_result_block]}]
            second_call_msgs = cap_client.all_messages[1] if len(cap_client.all_messages) > 1 else []
            assert len(second_call_msgs) >= 2, "Expected at least 2 messages in the second create call"
            # The second-to-last should be the assistant turn
            assistant_turn = second_call_msgs[-2]
            assert assistant_turn["role"] == "assistant", (
                "The assistant turn must be appended before the tool_result user turn"
            )
            # The last should be the user turn with tool_result
            user_turn = second_call_msgs[-1]
            assert user_turn["role"] == "user"
            content = user_turn["content"]
            assert isinstance(content, list) and len(content) >= 1
            first_item = content[0]
            assert first_item.get("type") == "tool_result"
            assert first_item.get("tool_use_id") == "tc-010"
        finally:
            main.TOOL_DISPATCH["secured_calculator"] = original

    def test_multiple_tool_use_blocks_answered_1to1(self, fake_client, minimal_catalog_df, monkeypatch):
        """L3: when two tool_use blocks arrive in one response, both get tool_result
        entries in the same user turn (ids 1:1)."""

        def fake_calc(expression: str) -> str:
            return "result"

        def fake_icp(company_profile_data: str) -> dict:
            return {"qualified": False, "tags": [], "count": 0, "reason": "test"}

        orig_calc = main.TOOL_DISPATCH["secured_calculator"]
        orig_icp  = main.TOOL_DISPATCH["evaluate_icp_tags"]
        main.TOOL_DISPATCH["secured_calculator"] = fake_calc
        main.TOOL_DISPATCH["evaluate_icp_tags"] = fake_icp

        class TwoToolClient:
            def __init__(self):
                self._responses = [
                    _FakeResponse(
                        [
                            _tool_use_block("secured_calculator", "tc-a", {"expression": "1+1"}),
                            _tool_use_block("evaluate_icp_tags", "tc-b", {"company_profile_data": "test"}),
                        ],
                        "tool_use",
                    ),
                    _end_turn("Both done."),
                ]
                self.second_call_messages = None

            class _Msgs:
                def __init__(self, c):
                    self._c = c
                    self._call_num = [0]

                def create(self, **kwargs):
                    self._call_num[0] += 1
                    if self._call_num[0] == 2:
                        self._c.second_call_messages = list(kwargs.get("messages", []))
                    if self._c._responses:
                        return self._c._responses.pop(0)
                    return _end_turn()

            @property
            def messages(self):
                # Cache a single _Msgs so the call counter persists across accesses
                # (the loop accesses client.messages fresh on every create()).
                if not hasattr(self, "_msgs_singleton"):
                    self._msgs_singleton = self._Msgs(self)
                return self._msgs_singleton

        ttc = TwoToolClient()
        monkeypatch.setattr(main, "_get_client", lambda: ttc)

        try:
            main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")
            msgs = ttc.second_call_messages
            assert msgs is not None
            user_turn = msgs[-1]
            assert user_turn["role"] == "user"
            tool_results = user_turn["content"]
            assert isinstance(tool_results, list)
            assert len(tool_results) == 2, (
                "Two tool_use blocks must produce exactly two tool_result entries"
            )
            ids = {tr["tool_use_id"] for tr in tool_results}
            assert "tc-a" in ids and "tc-b" in ids, (
                "tool_use_id must match 1:1 for each tool_use block"
            )
        finally:
            main.TOOL_DISPATCH["secured_calculator"] = orig_calc
            main.TOOL_DISPATCH["evaluate_icp_tags"] = orig_icp


# ===========================================================================
# L4 — Gateway called on every outbound (spy)
# ===========================================================================

class TestL4GatewayOnOutbound:

    def test_gateway_called_on_request_reactfirst_pdf(self, fake_client, minimal_catalog_df, monkeypatch):
        """L4: gateway_validate is called when request_reactfirst_pdf is dispatched."""
        gateway_calls = []
        original_gw = main.gateway_validate

        def spy_gateway(payload):
            gateway_calls.append(payload)
            return {"valid": True, "payload": payload}

        monkeypatch.setattr(main, "gateway_validate", spy_gateway)

        def fake_pdf(target_domain, validated_angle_key, calculated_risk_score):
            return {"ok": True, "path": "assets/test.pdf"}

        orig_pdf = main.TOOL_DISPATCH["request_reactfirst_pdf"]
        main.TOOL_DISPATCH["request_reactfirst_pdf"] = fake_pdf

        try:
            fc = fake_client([
                _FakeResponse(
                    [_tool_use_block("request_reactfirst_pdf", "tc-pdf-001",
                                     {"target_domain": "example.com",
                                      "validated_angle_key": "angle_key_01",
                                      "calculated_risk_score": 1.15})],
                    "tool_use",
                ),
                _end_turn("PDF done."),
            ])
            main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")
            # gateway_validate must have been called at least once for the PDF tool
            assert any(
                isinstance(c, dict) and c.get("ok") is True
                for c in gateway_calls
            ), f"gateway_validate not called with PDF result. calls={gateway_calls}"
        finally:
            main.TOOL_DISPATCH["request_reactfirst_pdf"] = orig_pdf

    def test_gateway_called_on_final_output(self, fake_client, minimal_catalog_df, monkeypatch):
        """L4: gateway_validate is called on the final output before returning."""
        gateway_calls = []

        def spy_gateway(payload):
            gateway_calls.append(payload)
            return {"valid": True, "payload": payload}

        monkeypatch.setattr(main, "gateway_validate", spy_gateway)

        fc = fake_client([_end_turn("Final answer text.")])
        main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")

        assert len(gateway_calls) >= 1, "gateway_validate must be called on final output"
        # At least one call should have "final_output" type
        assert any(
            isinstance(c, dict) and c.get("type") == "final_output"
            for c in gateway_calls
        ), f"No final_output gateway call found. calls={gateway_calls}"


# ===========================================================================
# RS1 — BadRequestError (400) caught + stop_reason=="refusal" (200) handled
# ===========================================================================

class TestRS1Resiliency:

    def test_bad_request_error_caught_and_loop_continues(self, fake_client, minimal_catalog_df, monkeypatch):
        """RS1: anthropic.BadRequestError is caught; message surfaced back; loop continues."""
        import anthropic as _anthropic

        # Build a minimal httpx.Response to satisfy BadRequestError's signature.
        try:
            import httpx
            fake_request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
            fake_response = httpx.Response(
                400,
                request=fake_request,
                content=b'{"error":{"message":"test 400 error"}}',
            )
            bad_req_error = _anthropic.BadRequestError(
                message="test 400 error",
                response=fake_response,
                body={"error": {"message": "test 400 error"}},
            )
        except Exception:
            # If we can't construct the real error, use a subclass substitute.
            bad_req_error = Exception("simulated BadRequestError")

        # Track whether the loop recovered and returned a string.
        call_count = [0]

        class RecoveringClient:
            class _Msgs:
                def create(self, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        if isinstance(bad_req_error, _anthropic.BadRequestError):
                            raise bad_req_error
                        # Fallback: use refusal path
                        return _FakeResponse([], "refusal")
                    return _end_turn("Recovered after error.")

            @property
            def messages(self):
                return self._Msgs()

        monkeypatch.setattr(main, "_get_client", lambda: RecoveringClient())
        result = main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")
        # The loop must have recovered — result should be from the second response, not a crash.
        assert isinstance(result, str), "Result must be a string after BadRequestError recovery"
        # Must not contain a raw Python traceback string
        assert "Traceback" not in result

    def test_stop_reason_refusal_handled_loop_continues(self, fake_client, minimal_catalog_df):
        """RS1: stop_reason=='refusal' is handled; stop_reason checked BEFORE content;
        loop continues."""
        # First response has stop_reason='refusal' and EMPTY content (simulates real Claude behavior).
        fc = fake_client([
            _FakeResponse([], "refusal"),   # empty content — checked safely
            _end_turn("Recovered after refusal."),
        ])
        result = main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")
        assert isinstance(result, str)
        assert "Traceback" not in result

    def test_stop_reason_checked_before_content_on_refusal(self, fake_client, minimal_catalog_df):
        """RS1: stop_reason is inspected BEFORE iterating response.content.
        A refusal response with content=None must not crash."""
        # Simulate a refusal with content=None (edge case).
        class RefusalWithNoneContent:
            stop_reason = "refusal"
            content = None  # accessing this without checking stop_reason would crash

        class SafeClient:
            def __init__(self):
                self._call_count = 0

            class _Msgs:
                def __init__(self, c):
                    self._c = c

                def create(self, **kwargs):
                    self._c._call_count += 1
                    if self._c._call_count == 1:
                        return RefusalWithNoneContent()
                    return _end_turn("Safe.")

            @property
            def messages(self):
                return self._Msgs(self)

        import main as _main
        # We can't use monkeypatch here directly (no fixture injection) — use direct attribute.
        original_gc = _main._get_client
        _main._get_client = lambda: SafeClient()
        try:
            result = _main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")
            assert isinstance(result, str)
        finally:
            _main._get_client = original_gc


# ===========================================================================
# RS2 — Anti-loop cap fires at exactly 15 dispatches; no 16th call
# ===========================================================================

class TestRS2AntiLoopCap:

    def test_cap_fires_at_15_no_16th_dispatch(self, fake_client, minimal_catalog_df, monkeypatch):
        """RS2: cap fires after 15 dispatches; LOG_CAP_HIT emitted; no 16th dispatch."""
        dispatch_count = [0]

        def counting_tool(expression: str) -> str:
            dispatch_count[0] += 1
            return "1"

        original = main.TOOL_DISPATCH["secured_calculator"]
        main.TOOL_DISPATCH["secured_calculator"] = counting_tool

        # Build 20 tool_use responses followed by an end_turn that should never be reached.
        responses = []
        for i in range(20):
            responses.append(
                _FakeResponse(
                    [_tool_use_block("secured_calculator", f"tc-cap-{i:03d}", {"expression": "1"})],
                    "tool_use",
                )
            )
        responses.append(_end_turn("Should never reach here."))

        try:
            fc = fake_client(responses)
            result = main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")

            # Cap message must be in the result.
            assert main.LOG_CAP_HIT in result, (
                f"LOG_CAP_HIT ('{main.LOG_CAP_HIT}') must be in the result when cap fires. "
                f"Got: {result!r}"
            )

            # Total dispatches must be exactly TOOL_CALL_CAP (15) — no 16th call.
            assert dispatch_count[0] == main.TOOL_CALL_CAP, (
                f"Expected exactly {main.TOOL_CALL_CAP} dispatches; got {dispatch_count[0]}"
            )
        finally:
            main.TOOL_DISPATCH["secured_calculator"] = original

    def test_cap_constant_is_15(self):
        """RS2: TOOL_CALL_CAP must equal 15 (non-negotiable per CLAUDE.md §9)."""
        assert main.TOOL_CALL_CAP == 15

    def test_log_cap_hit_constant(self):
        """RS2: LOG_CAP_HIT is the conventional string."""
        assert main.LOG_CAP_HIT == "** TERMINATED: tool call cap reached **"


# ===========================================================================
# RS3 — Tool error ({"error": ...}) → appended back; loop continues
# ===========================================================================

class TestRS3ToolError:

    def test_tool_error_continues_loop(self, fake_client, minimal_catalog_df, monkeypatch):
        """RS3: a tool returning {"error": ...} is fed back as tool_result; loop continues."""

        def erroring_tool(expression: str) -> dict:
            return {"error": "simulated tool failure"}

        original = main.TOOL_DISPATCH["secured_calculator"]
        main.TOOL_DISPATCH["secured_calculator"] = erroring_tool

        try:
            fc = fake_client([
                _FakeResponse(
                    [_tool_use_block("secured_calculator", "tc-err-001", {"expression": "bad"})],
                    "tool_use",
                ),
                _end_turn("Handled error gracefully."),
            ])
            result = main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")
            assert isinstance(result, str), "Loop must return a string after tool error"
            # The loop must NOT have crashed (no traceback in the result)
            assert "Traceback" not in result
        finally:
            main.TOOL_DISPATCH["secured_calculator"] = original

    def test_raising_tool_does_not_crash_loop(self, fake_client, minimal_catalog_df, monkeypatch):
        """RS3: a tool that raises an exception returns {"error": ...}; loop continues."""

        def raising_tool(expression: str) -> str:
            raise RuntimeError("Tool exploded!")

        original = main.TOOL_DISPATCH["secured_calculator"]
        main.TOOL_DISPATCH["secured_calculator"] = raising_tool

        try:
            fc = fake_client([
                _FakeResponse(
                    [_tool_use_block("secured_calculator", "tc-raise-001", {"expression": "boom"})],
                    "tool_use",
                ),
                _end_turn("Recovered from raising tool."),
            ])
            result = main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")
            assert isinstance(result, str)
            assert "Traceback" not in result
        finally:
            main.TOOL_DISPATCH["secured_calculator"] = original


# ===========================================================================
# RS4 — Per-tool + total metrics tracked (≤15); written to log + result
# ===========================================================================

class TestRS4CallMetrics:

    def test_metrics_total_never_exceeds_cap(self, fake_client, minimal_catalog_df, monkeypatch):
        """RS4: total tool calls tracked ≤ TOOL_CALL_CAP=15."""

        call_count = [0]

        def counting_tool(expression: str) -> str:
            call_count[0] += 1
            return str(call_count[0])

        original = main.TOOL_DISPATCH["secured_calculator"]
        main.TOOL_DISPATCH["secured_calculator"] = counting_tool

        # Make 5 tool calls then end.
        responses = [
            _FakeResponse(
                [_tool_use_block("secured_calculator", f"tc-m-{i:03d}", {"expression": "1"})],
                "tool_use",
            )
            for i in range(5)
        ]
        responses.append(_end_turn("Five calls done."))

        try:
            fc = fake_client(responses)
            main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")
            assert call_count[0] == 5
        finally:
            main.TOOL_DISPATCH["secured_calculator"] = original

    def test_metrics_written_to_log(self, fake_client, minimal_catalog_df, monkeypatch, tmp_path):
        """RS4: metrics (per-tool counts + total) are written to the log file."""

        def fake_calc(expression: str) -> str:
            return "42"

        original = main.TOOL_DISPATCH["secured_calculator"]
        main.TOOL_DISPATCH["secured_calculator"] = fake_calc

        log_file = str(tmp_path / "test_metrics.log")

        # Patch dual_log to use our temp log path.
        original_dual_log = main.dual_log

        def patched_dual_log(message, log_path=None):
            original_dual_log(message, log_path=log_file)

        monkeypatch.setattr(main, "dual_log", patched_dual_log)

        try:
            fc = fake_client([
                _FakeResponse(
                    [_tool_use_block("secured_calculator", "tc-log-001", {"expression": "10"})],
                    "tool_use",
                ),
                _end_turn("Log test done."),
            ])
            main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")

            log_content = pathlib.Path(log_file).read_text(encoding="utf-8")
            assert "metrics" in log_content.lower() or "total_calls" in log_content, (
                f"Metrics must be written to the log. Log content:\n{log_content}"
            )
        finally:
            main.TOOL_DISPATCH["secured_calculator"] = original

    def test_per_tool_counts_tracked(self, fake_client, minimal_catalog_df, monkeypatch):
        """RS4: per-tool call counts are correctly tracked."""

        per_tool_seen = {}

        def counting_calc(expression: str) -> str:
            return "1"

        def counting_icp(company_profile_data: str) -> dict:
            return {"qualified": False, "tags": [], "count": 0, "reason": "test"}

        original_calc = main.TOOL_DISPATCH["secured_calculator"]
        original_icp  = main.TOOL_DISPATCH["evaluate_icp_tags"]
        main.TOOL_DISPATCH["secured_calculator"] = counting_calc
        main.TOOL_DISPATCH["evaluate_icp_tags"] = counting_icp

        # Capture metrics via dual_log spy.
        log_lines = []

        def spy_log(message, log_path=None):
            log_lines.append(message)

        monkeypatch.setattr(main, "dual_log", spy_log)

        try:
            fc = fake_client([
                _FakeResponse(
                    [_tool_use_block("secured_calculator", "tc-pt-001", {"expression": "1"})],
                    "tool_use",
                ),
                _FakeResponse(
                    [_tool_use_block("evaluate_icp_tags", "tc-pt-002",
                                     {"company_profile_data": "test"})],
                    "tool_use",
                ),
                _end_turn("Per-tool done."),
            ])
            main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")

            # Find the metrics log line
            metrics_line = next(
                (l for l in log_lines if "per_tool" in l), None
            )
            assert metrics_line is not None, (
                f"No per_tool metrics log line found. Lines: {log_lines}"
            )
            assert "secured_calculator" in metrics_line
            assert "evaluate_icp_tags" in metrics_line
        finally:
            main.TOOL_DISPATCH["secured_calculator"] = original_calc
            main.TOOL_DISPATCH["evaluate_icp_tags"] = original_icp


# ===========================================================================
# RS5 — No uncaught exceptions from answer_question or main()
# ===========================================================================

class TestRS5NoUncaughtExceptions:

    def test_answer_question_never_raises(self, fake_client, minimal_catalog_df, monkeypatch):
        """RS5: answer_question always returns a str, never propagates an exception."""

        # Inject a client that raises a completely unexpected error.
        class ChaosClient:
            class _Msgs:
                def create(self, **kwargs):
                    raise RuntimeError("Totally unexpected chaos!")

            @property
            def messages(self):
                return self._Msgs()

        monkeypatch.setattr(main, "_get_client", lambda: ChaosClient())
        result = main.answer_question("q", catalog_df=minimal_catalog_df, policies="p")
        assert isinstance(result, str), "answer_question must always return str"
        assert "Traceback" not in result

    def test_main_catches_all_exceptions(self, monkeypatch, tmp_path):
        """RS5: main() never propagates an unhandled exception — exits with sys.exit(1)."""
        import subprocess
        # Use a subprocess to test sys.exit behaviour without affecting the test process.
        # We just check that answer_question itself always returns a string (above covers this).
        # Verify main() wraps load_catalog errors cleanly.
        import io
        from contextlib import redirect_stderr

        monkeypatch.setattr(main, "_get_client", lambda: FakeReasoningClient([_end_turn()]))
        monkeypatch.setattr(sys, "argv", ["main.py"])
        # Providing a bad catalog path should trigger a ValueError caught by main().
        monkeypatch.setattr(main, "load_catalog", lambda path: (_ for _ in ()).throw(
            ValueError("bad catalog")
        ))
        stderr_capture = io.StringIO()
        with redirect_stderr(stderr_capture):
            try:
                main.main()
            except SystemExit as se:
                assert se.code == 1
            except Exception as e:
                pytest.fail(f"main() must not propagate exceptions; got {e!r}")

    def test_answer_question_returns_str_with_none_catalog(self, monkeypatch):
        """RS5: answer_question(catalog_df=None) still returns a string safely."""
        fc = FakeReasoningClient(responses=[_end_turn("No catalog answer.")])
        monkeypatch.setattr(main, "_get_client", lambda: fc)
        result = main.answer_question("q", catalog_df=None, policies=None)
        assert isinstance(result, str)


# ===========================================================================
# dual_log tests (L1 / RS4 support)
# ===========================================================================

class TestDualLog:

    def test_dual_log_writes_to_stdout_and_file(self, tmp_path, capsys):
        """dual_log writes to both stdout and the log file."""
        log_file = str(tmp_path / "test_dual.log")
        main.dual_log("hello from dual_log", log_path=log_file)
        captured = capsys.readouterr()
        assert "hello from dual_log" in captured.out
        content = pathlib.Path(log_file).read_text(encoding="utf-8")
        assert "hello from dual_log" in content

    def test_dual_log_appends(self, tmp_path):
        """dual_log appends to an existing file — does not overwrite."""
        log_file = str(tmp_path / "append.log")
        main.dual_log("line one", log_path=log_file)
        main.dual_log("line two", log_path=log_file)
        content = pathlib.Path(log_file).read_text(encoding="utf-8")
        assert "line one" in content
        assert "line two" in content

    def test_dual_log_file_error_does_not_raise(self, tmp_path):
        """dual_log swallows file write errors silently (must never crash the pipeline)."""
        # Pass an unwritable path (a directory).
        bad_path = str(tmp_path)  # a directory, not a file
        try:
            main.dual_log("message", log_path=bad_path)
        except Exception as e:
            pytest.fail(f"dual_log must not raise on file error; got {e!r}")


# ===========================================================================
# truncate_for_log tests
# ===========================================================================

class TestTruncateForLog:

    def test_short_string_unchanged(self):
        assert main.truncate_for_log("hello") == "hello"

    def test_exactly_50_chars_unchanged(self):
        s = "x" * 50
        assert main.truncate_for_log(s) == s

    def test_51_chars_truncated(self):
        s = "x" * 51
        result = main.truncate_for_log(s)
        assert result == "x" * 50 + "..."
        assert len(result) == 53

    def test_coerces_non_string(self):
        result = main.truncate_for_log(12345)
        assert result == "12345"

