# 问题：VAE 编码极慢（单 batch 约 8 分钟）

**TL;DR**：VAE 被 `offload_device=cpu` 丢到 CPU 上算，12GB 卡叠加 1024×1024 分块后灾难性降速。（源自 `seedvr2-local-deploy`，2026-11-19 并入）

- 现象：日志 `Encoding batch N/29` 每次间隔 5~8 分钟，UI 进度条停在 0%。
- 根因：`SeedVR2LoadVAEModel` 的 offload device 设成了 CPU。
- 解决：VAE 的 `offload_device` 改 `cuda:0`，让编码上 GPU。
- 预防：慢时看任务管理器——GPU 占用低且 CPU 占用高 = offload 设错了。