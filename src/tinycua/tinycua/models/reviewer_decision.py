"""ReviewerRetryState dataclass for tracking retry failure count.

Separates retry tracking from task models; the loop owns this as
execution state. Distinct from NodeRetryPolicy.max_attempts which
controls node-level LLM call retries.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReviewerRetryState:
    """Tracks retry failure count across reviewer decisions.

    Attributes:
        retry_count: Number of consecutive retries without acceptance.
        threshold: Maximum retries before escalation. Default: 5.
    """

    retry_count: int = 0
    threshold: int = 5

    def increment(self) -> int:
        """Increment the retry counter.

        Returns:
            The new retry count after increment.
        """
        self.retry_count += 1
        return self.retry_count

    def reset(self) -> None:
        """Reset the retry counter to 0.

        Called when a task is accepted to start fresh.
        """
        self.retry_count = 0

    def is_threshold_reached(self) -> bool:
        """Check if the retry threshold has been reached.

        Returns:
            True if retry_count >= threshold, False otherwise.
        """
        return self.retry_count >= self.threshold

    def can_retry(self) -> bool:
        """Check if another retry is allowed.

        Returns:
            True if retry_count < threshold, False otherwise.
        """
        return self.retry_count < self.threshold
