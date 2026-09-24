# CHANGELOG

本项目按「版本 = 可执行方案的可用快照」记录，每次改动追加一节。

---

## v1.1.0 · 2026-09-24

方案一 Video2X 本机部署验证通过（RTX 4070 SUPER），修复部署中发现的问题，并补充实测性能数据。

### 修复

- `01-Video2X/安装Video2X.ps1`：GitHub API 调用加 token 认证，避免匿名限流导致安装失败
- `01-Video2X/批量放大.ps1`：参数名 `-Input` 改为 `-InputPath`（`$Input` 是 PowerShell 自动变量，会导致绑定失败）
- `01-Video2X/批量放大.ps1`：成功判断从「退出码 0」改为「输出文件存在且 > 0」——Video2X 6.4.0 Windows 版 Vulkan 清理阶段偶发非 0 退出，但文件实际正常

### 新增

- `docs/使用指南.md`：补充 RTX 4070 SUPER 实测性能表（Real-CUGAN / Real-ESRGAN / Anime4K / RIFE 四项速度与耗时估算）

### 验证结果（RTX 4070 SUPER 12G）

- Video2X 6.4.0 安装正常，Vulkan 正确识别 RTX 4070 SUPER
- Real-CUGAN 2x：~33 FPS（360p → 720p）
- Real-ESRGAN 4x：~27 FPS（360p → 1440p）
- Anime4K 2x：~100 FPS（360p → 720p）
- RIFE 2x 补帧：~298 FPS（30fps → 60fps）
- 批量脚本：跳过已完成、参数前置校验、目录批量处理全部正常

---

## v1.0.0 · 2026-09-24

首个可用版本。三套方案（Video2X / FlashVSR / SeedVR2）的安装与批量放大脚本全部落地，并逐条对照官方源码核对完毕。

### 新增

- `检查环境.ps1`：显卡 / 驱动 / git / Python / ffmpeg / 磁盘体检，并给出这台机器该走哪条路（只读，不改任何东西）
- `common.ps1`：路径配置、ComfyUI 节点安装、HF 镜像下载、模型文件校验、ComfyUI HTTP API 封装
- `00-ComfyUI底座/`：ComfyUI + CUDA 版 PyTorch + ComfyUI-Manager 的安装与启动
- `01-Video2X/`：便携版安装 + 批量放大（Real-CUGAN / Real-ESRGAN / Anime4K / RIFE）
- `02-FlashVSR/`：节点与权重安装 + 走 ComfyUI HTTP API 的批量放大
- `03-SeedVR2/`：节点与按档位权重安装 + 走节点自带 CLI 的批量放大
- `docs/使用指南.md`：完整部署手册（执行顺序、每步作用、参数说明、图形界面连线表、常见问题）

### 修正

相对初稿改正 23 处错误，逐条依据见 [docs/使用指南.md](docs/使用指南.md) 的「本次修订记录」。要点：

- SeedVR2 档位命名两套对不上 → 统一为 `12g / 16g / 24g`
- SeedVR2 7B FP8 权重名与所属仓库写错 → 按节点 `MODEL_REGISTRY` 更正为 `_mixed_block35_fp16`（`AInVFX` 仓库）
- SeedVR2 批量脚本传了不存在的 `--allow_vram_overflow` → 移除（上游 README 超前于代码）
- SeedVR2 批量脚本新增显式 `--model_dir`，产物识别改为按时间戳
- FlashVSR：给 NVENC 传 `crf` 改为 `bitrate` + `megabit`；冒烟测试改用 `--quick-test-for-ci`；补 `posi_prompt.pth` 校验
- Video2X：删除不存在的 `realesr-generalv3`；`--list-gpus` 改为 `--list-devices`；补三张模型白名单与缩放倍数校验
- 文档：体积口径统一为 1 GB = 10⁹ 字节；FlashVSR 速度按官方论文口径更正；节点显示名按源码校正
- `检查环境.ps1`：16G 档位建议与手册对齐；Video2X 体积由「3 GB」更正为约 0.2 GB；多卡提速表述与手册统一

### 已核对确认的关键事实

以下结论逐字比对过官方源码，**不要凭印象改回去**（完整清单见手册「本轮已复核确认无误的关键点」）：

- Video2X 全部命令行开关、模型白名单、Anime4K 着色器名 —— 对齐 6.4.0 的 `argparse.cpp` / `validators.cpp`
- FlashVSR 节点 `class_type`、输入名、取值域 —— 对齐节点 `nodes.py`
- VideoHelperSuite 的 `Load Video (Path)` 输出顺序与各视频格式的编码字段 —— 对齐节点源码与 `video_formats/*.json`
- SeedVR2 CLI 的 24 个参数、取值范围、互斥依赖 —— 对齐 `inference_cli.py` 的 `add_argument` 全表
- SeedVR2 七个权重文件名与各自所属仓库 —— 对齐 `src/utils/model_registry.py`