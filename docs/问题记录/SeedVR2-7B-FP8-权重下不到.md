# 问题：SeedVR2 的 7B FP8 权重下不到

**TL;DR**：`seedvr2_ema_7b_fp8_e4m3fn.safetensors` 不在节点注册表里；注册表内的 7B FP8 是 `_mixed_block35_fp16` 变体，且只在 `AInVFX` 仓库。

- 问题：按直觉写的文件名，在 ComfyUI 的 `--dit_model` 下拉框里根本选不到
- 根因：`--dit_model` 的候选项 = 节点 `src/utils/model_registry.py` 的 `MODEL_REGISTRY` ∪ 磁盘已有文件。名字必须与注册表一致，且不同变体散落在两个 HF 仓库
- 解决：脚本改按注册表内的 `seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors` 下载，并把它归到 `AInVFX/SeedVR2_comfyUI`
- 预防：**改权重文件名前先读 `model_registry.py`**，不要凭文件名推断