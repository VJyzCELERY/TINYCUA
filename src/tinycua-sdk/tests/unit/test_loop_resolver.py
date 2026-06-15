"""Unit tests for loop_resolver module."""

import pytest

from tinycua_sdk.agent.loop_resolver import (
    analyze_loop_source,
    extract_helper_functions,
)


class TestExtractHelperFunctions:
    """Tests for extract_helper_functions."""

    def test_extract_no_helpers(self):
        """Test source with no helper functions."""
        source = """
class MyLoop(DefaultLoop):
    async def run(self, agent, user_input, **kwargs):
        return await super().run(agent, user_input, **kwargs)
"""
        helpers = extract_helper_functions(source)
        assert helpers == []

    def test_extract_single_helper(self):
        """Test source with one helper function."""
        source = """
def helper_function(x):
    return x * 2

class MyLoop(DefaultLoop):
    async def run(self, agent, user_input, **kwargs):
        result = helper_function(5)
        return await super().run(agent, user_input, **kwargs)
"""
        helpers = extract_helper_functions(source)
        assert len(helpers) == 1
        assert helpers[0]["name"] == "helper_function"
        assert "def helper_function" in helpers[0]["source"]

    def test_extract_multiple_helpers(self):
        """Test source with multiple helper functions."""
        source = """
def helper_a():
    pass

def helper_b(x, y):
    return x + y

class MyLoop(DefaultLoop):
    async def run(self, agent, user_input, **kwargs):
        return await super().run(agent, user_input, **kwargs)
"""
        helpers = extract_helper_functions(source)
        assert len(helpers) == 2
        names = [h["name"] for h in helpers]
        assert "helper_a" in names
        assert "helper_b" in names

    def test_skip_run_method(self):
        """Test that run method is not extracted as helper."""
        source = """
def helper_func():
    pass

class MyLoop(DefaultLoop):
    async def run(self, agent, user_input, **kwargs):
        return await super().run(agent, user_input, **kwargs)
"""
        helpers = extract_helper_functions(source)
        names = [h["name"] for h in helpers]
        assert "run" not in names
        assert "helper_func" in names


class TestAnalyzeLoopSource:
    """Tests for analyze_loop_source."""

    def test_no_external_deps(self):
        """Test source with no external dependencies."""
        source = """
class MyLoop(DefaultLoop):
    async def run(self, agent, user_input, **kwargs):
        return await super().run(agent, user_input, **kwargs)
"""
        deps, helpers = analyze_loop_source(source)
        assert deps == []
        assert helpers == []

    def test_with_external_deps(self):
        """Test source with external dependencies."""
        source = """
import requests
import json

class MyLoop(DefaultLoop):
    async def run(self, agent, user_input, **kwargs):
        response = requests.get("http://example.com")
        return await super().run(agent, user_input, **kwargs)
"""
        deps, helpers = analyze_loop_source(source)
        assert "requests" in deps
        assert "json" not in deps  # stdlib

    def test_with_helpers_and_deps(self):
        """Test source with both helpers and external dependencies."""
        source = """
import pandas

def process_data(data):
    return pandas.DataFrame(data)

class MyLoop(DefaultLoop):
    async def run(self, agent, user_input, **kwargs):
        data = process_data([1, 2, 3])
        return await super().run(agent, user_input, **kwargs)
"""
        deps, helpers = analyze_loop_source(source)
        assert "pandas" in deps
        assert len(helpers) == 1
        assert helpers[0]["name"] == "process_data"
