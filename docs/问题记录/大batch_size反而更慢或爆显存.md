# 问题：大 batch_size 反而更慢 / 爆显存

**TL;DR**：SeedVR2 的消耗主力是 **VAE 解码分块**，不是模型大小或分辨率；小 batch 才高效。（源自 `seedvr2-local-deploy`）

- 现象：845 帧、batch 33 时全程预计达数小时量级。
- 根因：参考 `ai-upscaler-benchmark`（2026-06）实测：1080p 下 batch=9 已约 0.11 fps，更大/更高分辨率直接 OOM。[benchmark](https://github.com/ismael-joffroy-chandoutis/ai-upscaler-benchmark/blob/main/docs/video-upscalers.md)
- 解决：`batch_size` 降到 9（或 5）；保留 VAE tiling + `blocks_to_swap`。
- 预防：长视频优先小 batch + tiling，别贪大 batch。