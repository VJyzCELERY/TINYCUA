import os
import re
import subprocess
import sys


def install_dependencies():
    import torch

    if "COLAB_" in "".join(os.environ.keys()):
        v = re.match(r"[\d]{1,}\.[\d]{1,}", str(torch.__version__)).group(0)
        xformers = "xformers==" + {"2.10": "0.0.34", "2.9": "0.0.33.post1", "2.8": "0.0.32.post2"}.get(v, "0.0.34")
        packages = [
            "sentencepiece", "protobuf",
            "datasets==4.3.0", "huggingface_hub>=0.34.0", "hf_transfer",
            "unsloth_zoo", "bitsandbytes", "accelerate", xformers,
            "peft", "trl", "triton", "unsloth",
        ]
    else:
        packages = ["unsloth"]

    packages += ["transformers>=5.3.0", "trl>=0.22.2"]

    for pkg in packages:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pkg, "-q"],
            stdout=subdone.DEVNULL, stderr=subdone.DEVNULL,
        )
