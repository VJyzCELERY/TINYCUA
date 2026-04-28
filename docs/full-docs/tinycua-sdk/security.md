# Security Documentation

The `security/` package provides permission checking and approval workflows for tool execution.

**Package path:** `tinycua_sdk/security/`

---

## permissions.py - Permission System

### Purpose

Provides a permission system for tool execution with three security levels: SAFE, WARNING, and DANGEROUS.

### PermissionLevel Enum

```python
class PermissionLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGEROUS = "dangerous"
```

**Levels explained:**
- **SAFE**: Tools that only read data or perform non-destructive operations (e.g., `calculator`, `web_search`)
- **WARNING**: Tools that can modify state but are generally safe (e.g., `file_read`, `file_write`)
- **DANGEROUS**: Tools that can cause significant harm and require explicit approval (e.g., `shell_execute`, `delete_file`)

### ToolPermission Dataclass

```python
@dataclass
class ToolPermission:
    name: str
    level: PermissionLevel
    requires_approval: bool = False
```

### PermissionSystem

```python
class PermissionSystem:
    def __init__(self):
        self._permissions: dict[str, ToolPermission] = {}
        self._setup_default_permissions()
```

**Singleton-like behavior:** The class is instantiated fresh each time `AgentExecutor.check_tool_permission()` is called. No global singleton is maintained.

### Default Permissions

```python
def _setup_default_permissions(self):
    self.register("calculator", PermissionLevel.SAFE)
    self.register("web_search", PermissionLevel.SAFE)
    self.register("file_read", PermissionLevel.WARNING)
    self.register("file_write", PermissionLevel.WARNING)
    self.register("shell_execute", PermissionLevel.DANGEROUS, requires_approval=True)
    self.register("delete_file", PermissionLevel.DANGEROUS, requires_approval=True)
    self.register("network_request", PermissionLevel.WARNING)
    self.register("get_weather", PermissionLevel.SAFE)
    self.register("search_code", PermissionLevel.SAFE)
    self.register("list_directory", PermissionLevel.WARNING)
    self.register("read_file", PermissionLevel.WARNING)
    self.register("write_file", PermissionLevel.WARNING)
    self.register("delete_file", PermissionLevel.DANGEROUS, requires_approval=True)
    self.register("execute_command", PermissionLevel.DANGEROUS, requires_approval=True)
    self.register("http_request", PermissionLevel.WARNING)
    self.register("send_email", PermissionLevel.DANGEROUS, requires_approval=True)
    self.register("access_database", PermissionLevel.DANGEROUS, requires_approval=True)
    self.register("manage_memory", PermissionLevel.SAFE)
    self.register("store_data", PermissionLevel.WARNING)
    self.register("retrieve_data", PermissionLevel.SAFE)
    self.register("delegate_to", PermissionLevel.WARNING)
```

**Default tool registry:** Hardcoded list of common tools with their security levels. Note: `delete_file` is registered twice (second registration overwrites the first).

**Why hardcoded defaults?** Provides out-of-the-box security without requiring users to configure permissions. Users can override via `register()`.

### Permission Checking

```python
def check_permission(self, tool_name: str) -> bool:
    permission = self._permissions.get(tool_name)
    if not permission:
        _security_logger.debug("Tool %s not registered, allowing by default", tool_name)
        return True
    
    allowed = permission.level == PermissionLevel.SAFE
    
    if allowed:
        _security_logger.debug("Permission granted for tool: %s", tool_name)
    else:
        _security_logger.warning("Permission denied for tool: %s (level=%s)", tool_name, permission.level.value)
    
    return allowed
```

**Default policy:** Unknown tools are allowed by default (`return True`). This prevents breaking custom tools but means unregistered tools bypass the permission system.

**Why allow unknown tools?** The SDK supports dynamic tool creation. Requiring pre-registration would break the `@tool` decorator workflow.

### Approval Checking

```python
def requires_approval(self, tool_name: str) -> bool:
    permission = self._permissions.get(tool_name)
    if not permission:
        return False
    
    if permission.requires_approval:
        _security_logger.info("Approval required for tool: %s", tool_name)
    
    return permission.requires_approval if permission else False
```

Returns `True` only for tools explicitly marked with `requires_approval=True`.

### Registration

```python
def register(self, tool_name: str, level: PermissionLevel, requires_approval: bool = False):
    self._permissions[tool_name] = ToolPermission(
        name=tool_name,
        level=level,
        requires_approval=requires_approval,
    )
    _security_logger.info("Registered tool: %s (level=%s, requires_approval=%s)", tool_name, level.value, requires_approval)
```

Dynamic registration for custom tools. Logs all registrations for audit trails.

---

## approval.py - Approval Workflow

### Purpose

Manages approval requests for dangerous tool operations.

### ApprovalRequest Dataclass

```python
@dataclass
class ApprovalRequest:
    id: str
    tool_name: str
    arguments: dict
    requested_at: datetime
    status: str  # "pending", "approved", "denied"
```

### ApprovalWorkflow

```python
class ApprovalWorkflow:
    def __init__(self, timeout: int = 60):
        self._requests: dict[str, ApprovalRequest] = {}
        self._timeout = timeout
```

**In-memory storage:** Uses a dict for request tracking. Not persistent - requests are lost on process restart.

### Requesting Approval

```python
def request_approval(self, tool_name: str, arguments: dict) -> str:
    request_id = str(uuid.uuid4())
    request = ApprovalRequest(
        id=request_id,
        tool_name=tool_name,
        arguments=arguments,
        requested_at=datetime.now(),
        status="pending",
    )
    self._requests[request_id] = request
    return request_id
```

Creates a pending approval request and returns a tracking ID.

### Approving/Denying

```python
def approve(self, request_id: str) -> bool:
    request = self._requests.get(request_id)
    if not request:
        return False
    request.status = "approved"
    return True

def deny(self, request_id: str) -> bool:
    request = self._requests.get(request_id)
    if not request:
        return False
    request.status = "denied"
    return True
```

Simple state transitions. Returns `False` if request ID not found.

### Querying

```python
def get_status(self, request_id: str) -> Optional[str]
def get_request(self, request_id: str) -> Optional[ApprovalRequest]
def list_pending_requests(self) -> list[ApprovalRequest]
```

---

## Inter-Module Data Flow

### Permission Check Flow
```
Tool execution requested
  → AgentExecutor.check_tool_permission(tool_name)
    → PermissionSystem()
      → _setup_default_permissions()
      → check_permission(tool_name)
        → If SAFE: return True
        → If WARNING/DANGEROUS: return False
  → If denied: return error dict
```

### Approval Flow
```
DANGEROUS tool execution requested
  → AgentExecutor.check_tool_approval_required(tool_name)
    → PermissionSystem.requires_approval()
      → Return True
  → (In production, would call ApprovalWorkflow)
    → request_approval(tool_name, arguments)
      → Create ApprovalRequest
      → Return request_id
    → Wait for approve(request_id) or deny(request_id)
```
