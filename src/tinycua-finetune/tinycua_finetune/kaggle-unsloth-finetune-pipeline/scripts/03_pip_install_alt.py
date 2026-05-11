"""Step 3: Alternative pip installation method (commented out).

This script is an alternative pip install approach that uses os.popen
instead of magic commands. Currently commented out - use 02_install_unsloth.py instead.

This is kept for reference if the primary installation method fails.
"""

# import os
# import re
# import sys
#
#
# def run_pip_install(cmd):
#     """Run pip install with error capture"""
#     result = os.popen(cmd + " 2>&1").read()
#     if result and ("error" in result.lower() or "exception" in result.lower() or "failed" in result.lower()):
#         print(f"pip warning: {result[:500]}", file=sys.stderr)
#     return result
#
# if "COLAB_" not in "".join(os.environ.keys()):
#     run_pip_install("pip install unsloth")
# else:
#     import torch
#     v = re.match(r'[\d]{1,}\.[\d]{1,}', str(torch.__version__)).group(0)
#     xformers = 'xformers==' + {'2.10': '0.0.34', '2.9': '0.0.33.post1', '2.8': '0.0.32.post2'}.get(v, "0.0.34")
#     run_pip_install(f"pip install sentencepiece protobuf \"datasets==4.3.0\" \"huggingface_hub>=0.34.0\" hf_transfer")
#     run_pip_install(f"pip install --no-deps unsloth_zoo bitsandbytes accelerate {xformers} peft trl triton unsloth")
#
# run_pip_install("pip install transformers==5.3.0")
# run_pip_install("pip install --no-deps trl==0.22.2")


def main():
    print("Step 3: Alternative pip install (skipped - using step 2)")


if __name__ == "__main__":
    main()