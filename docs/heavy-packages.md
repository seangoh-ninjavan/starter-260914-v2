# Heavy Python packages

The build has a disk ceiling. `torch` — often pulled in by `sentence-transformers` or
`transformers` — defaults to the CUDA build and drags in ~6 GB of NVIDIA wheels that don't
fit, and the cluster has no GPUs anyway. Pin CPU-only:

```
--index-url https://download.pytorch.org/whl/cpu
torch
```
