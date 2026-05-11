"""Step 11: Configure Response-Only Training.

Configures the trainer to learn only from assistant responses,
ignoring user prompts in the loss calculation. This focuses learning
on the model's generated outputs.
"""

from unsloth.chat_templates import train_on_responses_only

from state import trainer

INSTRUCTION_MARKER = '<|im_start|>user\n'
RESPONSE_MARKER = '<|im_start|>assistant\n'

trainer = train_on_responses_only(
    trainer,
    instruction_part=INSTRUCTION_MARKER,
    response_part=RESPONSE_MARKER,
)

print("Training configured to learn only from assistant responses")


def main():
    print("Step 11 complete: Response-only training configured")


if __name__ == "__main__":
    main()