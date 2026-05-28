# Integration tests for Context Pipeline


from tinycua_sdk.context.discovery import ContextDiscovery
from tinycua_sdk.context.compression import ContextCompressor
from tinycua_sdk.context.sanitizer import MessageSanitizer
from tinycua_sdk.context.injection import InjectionDetector
from tinycua_sdk.storage.models import Message
import uuid


class TestContextPipeline:
    """Integration tests for context pipeline."""

    def test_discovery_compression_pipeline(self, tmp_path):
        """Test discovery -> compression pipeline."""
        # Create context files
        (tmp_path / "AGENTS.md").write_text("Test context file")

        # Discovery
        discovery = ContextDiscovery(root_dir=tmp_path)
        contexts = discovery.load_contexts()
        assert len(contexts) > 0

        # Compression with sliding window
        compressor = ContextCompressor()
        messages = [
            Message(
                id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                role="user",
                content=f"Message {i}",
                turn_index=i // 2,
                created_at=None,
            )
            for i in range(20)
        ]

        compressed = compressor.compress(messages, strategy="sliding")
        assert len(compressed) < len(messages)

    def test_sanitization_injection_pipeline(self):
        """Test sanitization -> injection detection pipeline."""
        sanitizer = MessageSanitizer()
        detector = InjectionDetector()

        # Test message with potential injection
        message = {
            "role": "user",
            "content": "Normal message",
        }

        # Sanitize
        sanitized = sanitizer.sanitize_message(message)
        assert sanitized["content"] == "Normal message"

        # Check for injection
        threats = detector.scan_text(sanitized["content"])
        assert len(threats) == 0

    def test_full_pipeline(self, tmp_path):
        """Test full context pipeline: discovery -> compression -> sanitization -> injection."""
        # Create context file with potential injection (but whitelisted)
        (tmp_path / "AGENTS.md").write_text("System instructions for the agent")

        # Discovery
        discovery = ContextDiscovery(root_dir=tmp_path)
        contexts = discovery.load_contexts()
        merged = "\n".join(contexts)

        # Injection detection
        detector = InjectionDetector()
        threats = detector.scan_text(merged)
        # Should not find threats in normal content

        # Sanitization
        sanitizer = MessageSanitizer()
        sanitized = sanitizer.sanitize_system_prompt(merged)
        assert sanitized is not None

        # Compression (with sample messages)
        compressor = ContextCompressor()
        messages = [
            Message(
                id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                role="user",
                content=f"Message {i}",
                turn_index=i,
                created_at=None,
            )
            for i in range(5)
        ]

        compressed = compressor.compress(messages, strategy="sliding")
        assert len(compressed) <= len(messages)
