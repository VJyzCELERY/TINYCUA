# SDK Specs Index

This folder contains specifications for the TINYCUA SDK.

## Contents

1. **[spec.md](spec.md)** - Main SDK specification
   - Core features overview
   - Architecture
   - Status tracker
   - Requirements

### Feature Specifications

2. **[tool-streaming/](tool-streaming/)** - Streaming tool execution
   - [spec.md](tool-streaming/spec.md) - Requirements and API
   - [design.md](tool-streaming/design.md) - Implementation details

3. **[session/](session/)** - Session & memory tools
   - [spec.md](session/spec.md) - Requirements
   - [design.md](session/design.md) - Implementation

4. **[remote-runner/](remote-runner/)** - Remote Runner SDK
   - [spec.md](remote-runner/spec.md) - Requirements
   - [design.md](remote-runner/design.md) - Implementation

5. **[remote-backend/](remote-backend/)** - Remote Backend SDK
   - [spec.md](remote-backend/spec.md) - Requirements
   - [design.md](remote-backend/design.md) - Implementation

6. **[agent-hierarchy/](agent-hierarchy/)** - Agent Hierarchy
   - [spec.md](agent-hierarchy/spec.md) - Requirements
   - [design.md](agent-hierarchy/design.md) - Implementation

## Related Specifications

### Backend (for reference)
- **[session-context](../../tinycua-backend/specs/session-context/spec.md)** - Backend session management with embeddings, compaction, memory depth

### Design Documents
- **[agent-tool-abstraction](agent-tool-abstraction/)** - Original agent/tool design (reference)

---

## Quick Links

| Feature | Spec Location |
|---------|---------------|
| Tool streaming | [tool-streaming/spec.md](tool-streaming/spec.md) |
| Memory tools | [session/spec.md](session/spec.md) |
| Agent hierarchy | [agent-hierarchy/spec.md](agent-hierarchy/spec.md) |
| Remote Runner | [remote-runner/spec.md](remote-runner/spec.md) |
| Remote Backend | [remote-backend/spec.md](remote-backend/spec.md) |

---

## Status Legend

- ✅ Complete
- ⏳ In Progress / Pending
- ❌ Not Started
