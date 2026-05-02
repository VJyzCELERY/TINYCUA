"""Target 9.2: Verify from tinycua_sdk import * only exports v2 public API."""

from tinycua_sdk import *


expected = {
    "Agent",
    "LanguageModel",
    "Tool",
    "tool",
    "Skill",
    "SkillRegistry",
    "BaseLoop",
    "ApprovalWorkflow",
}

imported = {x for x in dir() if not x.startswith("_")}
assert imported == expected, f"Mismatch: extra={imported - expected}, missing={expected - imported}"
print("PASS")
