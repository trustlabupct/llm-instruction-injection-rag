"""Tests for parsing and executing the simulated tools."""
import mock_tools


def test_parse_call_with_kwargs():
    calls = mock_tools.parse_tool_calls('TOOL_CALL: create_simulated_ticket(subject="a", description="b")')
    assert calls == [("create_simulated_ticket", {"subject": "a", "description": "b"})]


def test_parse_positional_call():
    calls = mock_tools.parse_tool_calls('TOOL_CALL: create_simulated_ticket("hello", "world")')
    assert calls == [("create_simulated_ticket", {"subject": "hello", "description": "world"})]


def test_parse_get_user_data_without_args():
    calls = mock_tools.parse_tool_calls("TOOL_CALL: get_user_data()")
    assert calls == [("get_user_data", {})]


def test_parse_several_calls():
    txt = ('TOOL_CALL: get_user_data(user_id="x")\n'
           'some text in between\n'
           'TOOL_CALL: search_document(query="y")')
    calls = mock_tools.parse_tool_calls(txt)
    assert [c[0] for c in calls] == ["get_user_data", "search_document"]


def test_parse_text_without_calls():
    assert mock_tools.parse_tool_calls("a normal response without tools") == []


def test_execute_no_real_effect_and_canary():
    r = mock_tools.execute("get_user_data", {"user_id": "demo"})
    assert r["internal_notes"] == "Simulated information, not disclosable"
    assert "@" in r["email"]


def test_execute_unknown_tool():
    r = mock_tools.execute("nonexistent_tool", {})
    assert "error" in r
