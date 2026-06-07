"""Unit tests for MandatoryPassthrough and classification models."""

from __future__ import annotations

from tinycua.models.classification import (
    PASSTHROUGH,
    UNCERTAIN,
    WORKER,
    MandatoryPassthrough,
    QueryAnalystResponse,
)


def test_mandatory_passthrough_creation():
    """MandatoryPassthrough can be created with required fields."""
    # Arrange & Act
    mandatory = MandatoryPassthrough(
        target_node_id="response",
        target_session_id="session123",
        reason="continuation",
        payload=None,
    )

    # Assert
    assert mandatory.target_node_id == "response"
    assert mandatory.target_session_id == "session123"
    assert mandatory.reason == "continuation"
    assert mandatory.payload is None
    assert mandatory.allow_query_analyst_restart is True


def test_mandatory_passthrough_stale_guard():
    """MandatoryPassthrough has stale guard via allow_query_analyst_restart."""
    # Arrange & Act
    mandatory = MandatoryPassthrough(
        target_node_id="response",
        target_session_id="session123",
        reason="continuation",
        payload=None,
        allow_query_analyst_restart=False,
    )

    # Assert
    assert mandatory.allow_query_analyst_restart is False


def test_classification_constants():
    """Classification constants are defined correctly."""
    # Assert
    assert PASSTHROUGH == "passthrough"
    assert WORKER == "worker"
    assert UNCERTAIN == "uncertain"


def test_query_analyst_response_creation():
    """QueryAnalystResponse can be created with fields."""
    # Arrange & Act
    response = QueryAnalystResponse(
        user_query="Help me write a script",
        classification="worker",
        rationale="User needs active work",
    )

    # Assert
    assert response.user_query == "Help me write a script"
    assert response.classification == "worker"
    assert response.rationale == "User needs active work"


def test_query_analyst_response_defaults():
    """QueryAnalystResponse has correct defaults."""
    # Arrange & Act
    response = QueryAnalystResponse()

    # Assert
    assert response.user_query == ""
    assert response.classification == UNCERTAIN
    assert response.rationale is None
