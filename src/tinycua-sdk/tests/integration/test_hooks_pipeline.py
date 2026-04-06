# Integration tests for Hooks Pipeline


from tinycua_sdk.middleware.hooks import (
    Hook,
    HookContext,
    HookResult,
    HookRegistry,
)


class LoggingHook(Hook):
    """Hook that logs tool calls."""

    def pre_call(self, context: HookContext) -> HookResult:
        print(f"LOG: Calling tool {context.tool_name}")
        return HookResult(modified=False)

    def post_call(self, context: HookContext, result: str) -> HookResult:
        print(f"LOG: Tool {context.tool_name} returned: {result}")
        return HookResult(modified=False)


class ParameterModifyingHook(Hook):
    """Hook that modifies tool parameters."""

    def pre_call(self, context: HookContext) -> HookResult:
        modified_params = dict(context.parameters)
        modified_params["_modified_by_hook"] = True
        return HookResult(modified=True, parameters=modified_params)


class ResultModifyingHook(Hook):
    """Hook that modifies tool result."""

    def post_call(self, context: HookContext, result: str) -> HookResult:
        return HookResult(modified=True, result=f"MODIFIED: {result}")


class TestHooksPipeline:
    """Integration tests for hooks pipeline."""

    def test_pre_hook_modifies_parameters(self):
        """Test pre-hook can modify tool parameters."""
        registry = HookRegistry()
        registry.register_pre_hook(ParameterModifyingHook(), priority=100)

        context = HookContext(
            tool_name="test_tool",
            parameters={"original_param": "value"},
        )

        result = registry.execute_pre_hooks(context)

        assert result.parameters["original_param"] == "value"
        assert result.parameters["_modified_by_hook"] is True

    def test_post_hook_modifies_result(self):
        """Test post-hook can modify tool result."""
        registry = HookRegistry()
        registry.register_post_hook(ResultModifyingHook(), priority=100)

        context = HookContext(tool_name="test_tool", parameters={})
        result = registry.execute_post_hooks(context, "original result")

        assert result == "MODIFIED: original result"

    def test_full_pipeline_pre_hook_tool_post_hook(self):
        """Test full pipeline: pre-hook -> tool -> post-hook."""
        registry = HookRegistry()
        registry.register_pre_hook(LoggingHook(), priority=50)
        registry.register_pre_hook(ParameterModifyingHook(), priority=100)
        registry.register_post_hook(ResultModifyingHook(), priority=100)
        registry.register_post_hook(LoggingHook(), priority=50)

        # Pre-hook phase
        context = HookContext(
            tool_name="test_tool",
            parameters={"original": "value"},
        )

        modified_context = registry.execute_pre_hooks(context)

        # Tool execution (simulated)
        tool_result = "tool execution result"

        # Post-hook phase
        final_result = registry.execute_post_hooks(modified_context, tool_result)

        # Verify modifications
        assert modified_context.parameters["_modified_by_hook"] is True
        assert "MODIFIED:" in final_result

    def test_hooks_execute_in_priority_order(self):
        """Test hooks execute in priority order."""
        execution_order = []

        class OrderHook(Hook):
            def __init__(self, name: str, priority: int):
                self.name = name
                self.priority = priority

            def pre_call(self, context: HookContext) -> HookResult:
                execution_order.append(self.name)
                return HookResult(modified=False)

        registry = HookRegistry()
        registry.register_pre_hook(OrderHook("first", priority=100), priority=100)
        registry.register_pre_hook(OrderHook("second", priority=50), priority=50)
        registry.register_pre_hook(OrderHook("third", priority=200), priority=200)

        context = HookContext(tool_name="test", parameters={})
        registry.execute_pre_hooks(context)

        # Should execute in order: second, first, third
        assert execution_order == ["second", "first", "third"]

    def test_multiple_hooks_chaining(self):
        """Test multiple hooks can chain modifications."""
        registry = HookRegistry()

        # Add multiple parameter-modifying hooks
        for i in range(3):
            hook = ParameterModifyingHook()
            registry.register_pre_hook(hook, priority=100 + i)

        context = HookContext(
            tool_name="test_tool",
            parameters={"original": "value"},
        )

        result = registry.execute_pre_hooks(context)

        # Each hook should have modified the parameters
        assert result.parameters["_modified_by_hook"] is True
