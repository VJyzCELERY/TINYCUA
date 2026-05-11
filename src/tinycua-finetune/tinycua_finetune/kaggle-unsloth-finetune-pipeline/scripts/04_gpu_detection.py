"""Step 4: GPU Detection and Configuration.

Detects available GPUs and displays their properties.
Essential for verifying GPU availability before training.
"""

import torch

print("=" * 50)
print("GPU Configuration")
print("=" * 50)

if torch.cuda.is_available():
    num_gpus = torch.cuda.device_count()
    print(f"Number of GPUs: {num_gpus}")
    for i in range(num_gpus):
        gpu_name = torch.cuda.get_device_name(i)
        vram_gb = torch.cuda.get_device_properties(i).total_memory / 1e9
        print(f"GPU {i}: {gpu_name} ({vram_gb:.1f}GB)")
    print("Using CUDA for training")
else:
    print("WARNING: No GPU detected - using CPU (will be very slow)")

print("=" * 50)


def main():
    print("Step 4 complete: GPU configuration detected")


if __name__ == "__main__":
    main()