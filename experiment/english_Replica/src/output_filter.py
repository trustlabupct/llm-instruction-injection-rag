"""Output filter for configuration C5.

Acts on the RESPONSE after it has already been generated, before returning it to the user.
It is a deterministic mitigation on the output side: it does not depend on the model
obeying instructions.

Removes from the response:
  1. Tool calls with unsolicited consequences or with an injected signature.
  2. User data disclosure blocks, detected by STRUCTURE (a line with an identity word -email,
     identifier, user_id, ref-user, internal_notes...- followed by a value separator), not by
     a fixed tag. This makes it resistant to relabeling of the block (e.g. "Ref-user: ...")
     and to concrete values (email, ID number) or placeholder values ("[email]").
  3. Override orders, in several languages ("security policy disabled", "ignore previous
     instructions"...).

Does not cover context contamination: a semantically plausible false claim cannot be
distinguished by output-level patterns (it would require factual verification).
"""
from __future__ import annotations

import re
import unicodedata

CONSEQUENTIAL_TOOLS = {"get_user_data", "create_simulated_ticket"}
INJECTED_SIGNATURES = [
    "critical security failure", "automatic escalation", "mass reset",
    "internship enrollment", "system-generated request", "complete file",
]

_CALL_RE = re.compile(r"TOOL_CALL:\s*(?:execute\s+)?(\w+)\s*\((.*?)\)", re.DOTALL)
_EMAIL_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.I)
_ID_NUMBER_RE = re.compile(r"\b\d{7,8}[a-z]\b", re.I)

# word indicating an identity datum of the user (basis for structural detection)
_IDENTITY_LABEL = re.compile(
    r"(email|e-?mail|email address|identifier|internal[-_ ]?id|user[_ ]?id|"
    r"ref[-_ ]?user|internal[_ ]?notes|administrative note|traceability|user data|id number)\b"
)
# typical separator of a "label: value" or "a | b" block
_SEPARATOR = re.compile(r"[:=|]")

# override orders
_OVERRIDE = re.compile(
    r"(security policy (?:has been |is )?disabled"
    r"|restrictions?\b.{0,30}(?:lifted|removed|disabled|no longer (?:apply|in effect))"
    r"|ignore (?:all )?(?:previous|prior) instructions"
    r"|disregard (?:all )?(?:previous|prior) instructions"
    r"|system override"
    r"|without (?:any )?restrictions?)",
    re.I,
)


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _is_data_block(line: str, low: str) -> bool:
    """A line is a data disclosure if it exposes a concrete value (email, ID number, internal
    notes) or has the form 'identity-label ... separator ...' (structured block)."""
    if "internal_notes" in low or _EMAIL_RE.search(line) or _ID_NUMBER_RE.search(line):
        return True
    if _IDENTITY_LABEL.search(low) and _SEPARATOR.search(line):
        return True
    return False


def filter_response(response: str, allowed_tools=None):
    """Returns (filtered_response, actions), where actions lists what was removed."""
    allowed = set(allowed_tools or [])
    actions = []
    clean_lines = []

    for line in response.split("\n"):
        low = _norm(line)

        # 1. calls to dangerous or injected tools
        m = _CALL_RE.search(line)
        if m:
            name = m.group(1)
            signature = any(f in low for f in INJECTED_SIGNATURES)
            unrequested_consequential = name in CONSEQUENTIAL_TOOLS and name not in allowed
            if signature or unrequested_consequential:
                actions.append(f"tool_call_removed:{name}")
                continue

        # 2. user data disclosure block (by structure)
        if _is_data_block(line, low):
            actions.append("exfil_line_removed")
            continue

        # 3. override order: the line is truncated from the order onward (it usually appears as a suffix)
        mo = _OVERRIDE.search(line)
        if mo:
            line = line[:mo.start()].rstrip(" .-—:;")
            actions.append("override_removed")
            if not line.strip():
                continue

        clean_lines.append(line)

    filtered = "\n".join(l for l in clean_lines if l.strip())
    if not filtered.strip():
        filtered = ("I cannot display this response: the generated content included unauthorized "
                    "actions or data that the output check has blocked.")
    return filtered, actions
