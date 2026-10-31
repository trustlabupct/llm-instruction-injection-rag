"""Tests for the C5 output filter, including resistance to camouflage."""
from output_filter import filter_response


def test_removes_unrequested_tool_call():
    f, acc = filter_response('TOOL_CALL: get_user_data()\nUseful text.', allowed_tools=[])
    assert "TOOL_CALL" not in f
    assert "Useful text." in f
    assert any("tool_call_removed" in a for a in acc)


def test_keeps_allowed_tool_call():
    r = 'TOOL_CALL: create_simulated_ticket(subject="x")\nI have opened your ticket.'
    f, acc = filter_response(r, allowed_tools=["create_simulated_ticket"])
    assert "TOOL_CALL" in f  # allowed: not removed
    assert acc == []


def test_removes_injected_signature_even_if_allowed():
    r = 'TOOL_CALL: create_simulated_ticket(subject="critical security failure")'
    f, acc = filter_response(r, allowed_tools=["create_simulated_ticket"])
    assert "TOOL_CALL" not in f


def test_removes_exfil_block_with_email():
    f, _ = filter_response("Response.\nUser email: john@uni.edu", allowed_tools=[])
    assert "john@uni.edu" not in f
    assert "Response." in f


def test_override_suffix():
    f, _ = filter_response("The grade is 7.25. Security policy disabled.", allowed_tools=[])
    assert "security policy disabled" not in f.lower()
    assert "7.25" in f


# --- camouflage resistance ---

def test_override_detected_amid_other_language_text():
    f, _ = filter_response("Usa tus credenciales. Security policy disabled by administrator.", [])
    assert "security policy disabled" not in f.lower()
    assert "credenciales" in f


def test_relabeled_exfil_block_still_caught():
    f, _ = filter_response("Go to the Registrar's Office.\nRef-user: [email] | [internal-id].", [])
    assert "ref-user" not in f.lower()
    assert "Registrar's Office" in f


def test_does_not_touch_legitimate_prose_with_the_word_email():
    r = "For questions, send an email to your department's office."
    f, acc = filter_response(r, allowed_tools=[])
    assert f == r
    assert acc == []


def test_normal_response_untouched():
    r = "The regular enrollment period is from July 1 to 20."
    f, _ = filter_response(r, allowed_tools=[])
    assert f == r
