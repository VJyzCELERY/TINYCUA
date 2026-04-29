# Stage 06 — Design: Remove Modeling

## Overview

Delete the `modeling/` package. User modeling, profiling, and personality analysis are consumer concerns.

## Design Decisions

### Why Delete Modeling?

1. **Stateful by definition**: User profiles, preferences, and personality models are persistent data about users.
2. **Privacy-sensitive**: User profiling involves PII and requires careful handling that the SDK should not dictate.
3. **Consumer owns user data**: The consumer (backend application) manages user accounts, preferences, and profiles.
4. **Not required for agent execution**: An agent can run perfectly without knowing the user's personality or communication style.

### What Replaces Modeling?

Nothing in the SDK. The consumer:
- Defines its own user profile schema
- Stores user data in its own database
- Injects user preferences into `Agent` via `instructions` or `system_prompt`

## Files to Delete

| File | Reason |
|------|--------|
| `modeling/__init__.py` | Package init |
| `modeling/user.py` | UserModel, UserPreference, UserGoal — consumer concern |
| `modeling/profiler.py` | CommunicationProfiler — consumer concern |
| `modeling/personality.py` | Personality — consumer concern |

## Impact Analysis

### Files that reference modeling

```bash
grep -r "from tinycua_sdk.modeling" src/tinycua-sdk/tinycua_sdk/
grep -r "import tinycua_sdk.modeling" src/tinycua-sdk/tinycua_sdk/
```

### Expected impact

Modeling is typically self-contained. The only impact is if `Agent` or `cli/` imports from `modeling/`. CLI will be deleted in Stage 07 anyway.

## Consumer Migration Guide

### Before (SDK provides modeling)
```python
from tinycua_sdk import Agent, UserModel, Personality

user = UserModel.load("user-123")
personality = Personality.analyze(user.conversations)
agent = Agent(personality=personality)
```

### After (Consumer provides modeling)
```python
from tinycua_sdk import Agent, LLMModel

# Consumer's own user modeling
class UserProfile:
    def __init__(self, user_id):
        self.user_id = user_id
        self.preferences = db.load_preferences(user_id)

profile = UserProfile("user-123")
system = f"User prefers {profile.preferences['style']} responses."
agent = Agent(llm_model=LLMModel(system_prompt=system))
```

## Acceptance Criteria

- [ ] `modeling/` package is deleted entirely.
- [ ] No references to `UserModel`, `Personality`, or `CommunicationProfiler` in SDK code.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02.
- **Blocks**: None (can proceed in parallel with Stages 03–05, 07).
