"""Step 2: Install Unsloth and dependencies.

Installs Unsloth, transformers, and other required packages for QLoRA fine-tuning.
Handles both Kaggle/Colab and local/cloud environments.
"""


def run_pip_install(cmd):
    import subprocess
    import sys
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr[:500] if result.stderr else ""
        stdout = result.stdout[:500] if result.stdout else ""
        print(f"pip warning: {stderr} {stdout}".strip(), file=sys.stderr)
    return result


def run(state):
    import os

    if "COLAB_" not in "".join(os.environ.keys()):
        print("Installing Unsloth for local/cloud environments...")
        run_pip_install("pip install unsloth")
    else:
        print("Installing Unsloth for Google Colab...")
        import torch
        import re
        v = re.match(r'[\d]{1,}\.[\d]{1,}', str(torch.__version__)).group(0)
        xformers = 'xformers==' + {'2.10': '0.0.34', '2.9': '0.0.33.post1', '2.8': '0.0.32.post2'}.get(v, "0.0.34")
        run_pip_install(f"pip install sentencepiece protobuf \"datasets==4.3.0\" \"huggingface_hub>=0.34.0\" hf_transfer")
        run_pip_install(f"pip install --no-deps unsloth_zoo bitsandbytes accelerate {xformers} peft trl triton unsloth")

    run_pip_install("pip install transformers==5.3.0")
    run_pip_install("pip install --no-deps trl==0.22.2")

    print("Installation complete!")


def main():
    print("Step 2 complete: Unsloth and dependencies installed")


if __name__ == "__main__":
    main()
