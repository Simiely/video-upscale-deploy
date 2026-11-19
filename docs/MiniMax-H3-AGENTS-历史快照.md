> 📦 **历史快照**：原独立仓 `minimax-h3-local-deploy` 的 AGENTS.md，2026-11-19 并入总仓时原样保留，仅作追溯；其中的路径与版本是当时的快照，现行内容见总仓对应文档。

# AGENTS.md · 项目规则

> 📌 **文档基线**：2026-11-18（commit `37bc179`）接入 repo-kit 机器层（link-only / 规范 2.1.4）
> **更新文档/代码后，请更新此行**（日期 + 新 commit hash），并在 CHANGELOG 追加版本

## 技术栈

- 模型：MiniMax H3（Hailuo 3.0），33B 全模态单流 Transformer，音画一次推理同出；本地精度上限 768p 短边
- 推理前端：ComfyUI **≥ 0.30.0**（H3 节点在核心 `comfy_extras/nodes_minimax_h3.py`，非自定义节点）
- 运行时：PyTorch **cu130**（CUDA 13）+ Python 3.10+
- 目标硬件：RTX 4070 Super 12G / RTX 4070 Ti Super 16G；系统内存 32 GB 起（64 GB 顺）
- 量化权重来源：Comfy-Org/MiniMax-H3（官方重打包）与社区仓库（Abiray / Merserk / tsolful 等）

## 关键坑（详情在 DEVELOPMENT.md，一坑一篇）

1. 加载阶段被系统杀掉 → 是**系统内存**不够，不是显存；加 `--disable-pinned-memory`
2. 生成慢约 3 倍且无报错 → 缺 cu130，或 `comfy_kitchen` 导入失败（**静默降级**）
3. 文本编码器用 NVFP4 AWQ（14.61 GiB）；**扩散模型绝不能选 NVFP4**（Blackwell 专属，30/40 系只有模拟）
4. GGUF 需要额外加载器节点包；编码器报 `[5120] vs [4096]` 是被识别成 Qwen3-VL-8B，要 `type=minimax`
5. 权重必须放 NVMe：32 GB 内存时硬盘会进入采样循环，直接决定 6 分钟还是 25 分钟

## 约定

- 全中文文档；文件命名中文为主（`领域-主题`），不带空格
- 体积统一标 GiB/GB **并注明来源**；社区实测一律标时间和来源，不写成定论
- 任何结论必须可核对：写清是官方 FAQ、仓库 README 还是实测
- **新写结论前先查一遍当前仓库/官方页**，不要照抄本仓库存量数字（社区每周在动）
- 隐私红线（公开仓库）：禁止收录凭据、本地绝对路径、个人信息、未公开项目细节
- 边界：不写绕过内容安全机制的配置 / 提示词 / 思路

## 机器层（repo-kit · link-only）

- `schema/taxonomy.json` + `schema/kit.lock.json`（kit `2.9.0` / 规范 `2.1.4` / `link-only`）+ `tools/repo-kit/check_repo.py`
- 校验：`python tools/repo-kit/check_repo.py --root .`；锁哈希：`pwsh tools/update-repo-kit.ps1 -Check`
- 只查**链接与锚点**：全仓 md 豁免 frontmatter（本仓没有 frontmatter 契约）
- `schema/kit.lock.json` **不要手改**，升级只能跑 `tools/update-repo-kit.ps1`

## 常用命令

```bash
# 下载权重（路线 B）
hf download Comfy-Org/MiniMax-H3 \
  diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors \
  text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors \
  vae/minimax_h3_video_vae_fp16.safetensors \
  vae/minimax_h3_audio_vae_fp32.safetensors --local-dir models

# 启动（32 GB 内存必加第一个标志）
python main.py --disable-pinned-memory --disable-async-offload --reserve-vram 1

# 维护四步：CHANGELOG 加版本节 → 本文件基线行更新 → 回填仓库盘点表 → 推送
```
