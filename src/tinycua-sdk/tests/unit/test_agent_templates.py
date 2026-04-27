"""Unit tests for agent templates module."""

import pytest

from tinycua_sdk.agent.templates import (
    get_template,
    list_templates,
    template_exists,
    validate_template,
    apply_template_overrides,
)


class TestGetTemplate:
    """Tests for get_template function."""

    def test_get_coder_template(self):
        """get_template('coder') returns correct template."""
        template = get_template("coder")
        assert template["name"] == "coder"
        assert "system_prompt" in template
        assert "model" in template

    def test_get_researcher_template(self):
        """get_template('researcher') returns correct template."""
        template = get_template("researcher")
        assert template["name"] == "researcher"
        assert "system_prompt" in template
        assert "model" in template

    def test_get_assistant_template(self):
        """get_template('assistant') returns correct template."""
        template = get_template("assistant")
        assert template["name"] == "assistant"
        assert "system_prompt" in template
        assert "model" in template

    def test_get_template_invalid_name(self):
        """get_template('invalid') raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_template("invalid")
        assert "not found" in str(exc_info.value)

    def test_get_template_case_insensitive(self):
        """get_template is case-insensitive."""
        template = get_template("CODER")
        assert template["name"] == "coder"
        template = get_template("Researcher")
        assert template["name"] == "researcher"


class TestListTemplates:
    """Tests for list_templates function."""

    def test_list_templates(self):
        """list_templates() returns all 3 templates."""
        templates = list_templates()
        assert len(templates) == 3
        assert "assistant" in templates
        assert "coder" in templates
        assert "researcher" in templates


class TestTemplateExists:
    """Tests for template_exists function."""

    def test_template_exists_true(self):
        """template_exists('coder') returns True."""
        assert template_exists("coder") is True

    def test_template_exists_false(self):
        """template_exists('invalid') returns False."""
        assert template_exists("invalid") is False

    def test_template_exists_case_insensitive(self):
        """template_exists is case-insensitive."""
        assert template_exists("CODER") is True
        assert template_exists("Researcher") is True


class TestValidateTemplate:
    """Tests for validate_template function."""

    def test_validate_template_valid(self):
        """validate_template(valid_template) does not raise."""
        valid_template = {"name": "test", "system_prompt": "You are a test."}
        # Should not raise
        validate_template(valid_template)

    def test_validate_template_missing_name(self):
        """validate_template with missing name raises ValueError."""
        invalid_template = {"system_prompt": "You are a test."}
        with pytest.raises(ValueError) as exc_info:
            validate_template(invalid_template)
        assert "required field" in str(exc_info.value)

    def test_validate_template_missing_system_prompt(self):
        """validate_template with missing system_prompt raises ValueError."""
        invalid_template = {"name": "test"}
        with pytest.raises(ValueError) as exc_info:
            validate_template(invalid_template)
        assert "required field" in str(exc_info.value)


class TestApplyTemplateOverrides:
    """Tests for apply_template_overrides function."""

    def test_apply_overrides_model(self):
        """Overriding model works correctly."""
        template = get_template("coder")
        result = apply_template_overrides(template, {"model": "gpt-4o"})
        assert result["model"] == "gpt-4o"

    def test_apply_overrides_nested_policy(self):
        """Nested policy override works."""
        template = get_template("coder")
        result = apply_template_overrides(
            template, {"policy": {"temperature": 0.3}}
        )
        assert result["policy"]["temperature"] == 0.3
        # Original values preserved
        assert result["policy"]["max_tool_calls"] == 15

    def test_apply_overrides_none(self):
        """No overrides returns copy of template."""
        template = get_template("coder")
        result = apply_template_overrides(template, None)
        assert result == template
        # Should be a copy, not the same object
        assert result is not template

    def test_apply_overrides_invalid_key(self):
        """Invalid override key raises ValueError."""
        template = get_template("coder")
        with pytest.raises(ValueError) as exc_info:
            apply_template_overrides(template, {"invalid_key": "value"})
        assert "Invalid override keys" in str(exc_info.value)

    def test_apply_overrides_validates_keys(self):
        """Override key validation works."""
        template = get_template("coder")
        with pytest.raises(ValueError) as exc_info:
            apply_template_overrides(
                template, {"invalid_key": "value", "another_invalid": 123}
            )
        assert "Invalid override keys" in str(exc_info.value)

    def test_apply_overrides_tools(self):
        """Overriding tools works."""
        template = get_template("coder")
        result = apply_template_overrides(template, {"tools": ["custom_tool"]})
        assert result["tools"] == ["custom_tool"]

    def test_apply_overrides_skills(self):
        """Overriding skills works."""
        template = get_template("coder")
        result = apply_template_overrides(
            template, {"skills": ["skill1", "skill2"]}
        )
        assert result["skills"] == ["skill1", "skill2"]

    def test_apply_overrides_loop_dict(self):
        """Overriding loop with dict works."""
        template = get_template("coder")
        result = apply_template_overrides(
            template, {"loop": {"type": "react", "max_iterations": 10}}
        )
        assert result["loop"]["type"] == "react"
        assert result["loop"]["max_iterations"] == 10

    def test_apply_overrides_loop_string(self):
        """Overriding loop with string works."""
        template = get_template("coder")
        result = apply_template_overrides(template, {"loop": "react"})
        assert result["loop"] == "react"

    def test_apply_overrides_provider(self):
        """Overriding provider works."""
        template = get_template("coder")
        result = apply_template_overrides(template, {"provider": "ollama"})
        assert result["provider"] == "ollama"

    def test_apply_overrides_system_prompt(self):
        """Overriding system_prompt works."""
        template = get_template("coder")
        result = apply_template_overrides(
            template, {"system_prompt": "Custom prompt."}
        )
        assert result["system_prompt"] == "Custom prompt."

    def test_apply_overrides_multiple(self):
        """Multiple overrides work together."""
        template = get_template("coder")
        result = apply_template_overrides(
            template, {"model": "gpt-4o", "provider": "ollama"}
        )
        assert result["model"] == "gpt-4o"
        assert result["provider"] == "ollama"
