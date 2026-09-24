# video-upscale-deploy · 本地视频放大部署包

> 面向 RTX 4070 Super 12G / 4070 Ti Super 16G / RTX 4090 24G 三张显卡的**可执行**本地视频放大方案。
> 全部脚本为 PowerShell，双击或命令行运行即可，不需要写代码。

一套脚本，三种画质与速度的取舍：**日常批量用 Video2X，正式出片用 SeedVR2，FlashVSR 在中间补位。**

---

## 三套方案速览

| | 方案一 Video2X | 方案二 FlashVSR | 方案三 SeedVR2 |
|---|---|---|---|
| 技术路线 | 逐帧超分（Real-CUGAN / Real-ESRGAN）+ 补帧 | 流式扩散超分（Wan2.1 底模） | 一步扩散视频修复（ByteDance） |
| 依赖 | C++/Vulkan 便携包，不装 Python、不用 CUDA | ComfyUI + 自定义节点 | ComfyUI + 自定义节点（自带 CLI） |
| 画质 | 一般，锐化感明显 | 好，时序稳定不闪烁 | 最好，接近"重拍"效果 |
| 速度 | 最快，逐帧线性增长，分钟级 | 扩散类里最快 | 最慢，数小时级 |
| 显存 | 很低（Vulkan 推理，通常 2 GB 以内） | 6–16 GB 可调 | 3B FP8 权重约 3.4 GB 起 |
| 适合场景 | 批量出草稿、番剧、老片快速放大 | 真人短视频、直播切片精修 | 关键镜头、成片交付 |

### 三张卡怎么分配

| 显卡 | 显存 | 推荐主力 | 具体档位 |
|---|---|---|---|
| RTX 4070 Super | 12 GB | 方案一 + 方案二 | 方案二 `-Mode tiny-long`；方案三 `-Profile 12g` |
| RTX 4070 Ti Super | 16 GB | 方案二 + 方案三 | 方案二 `-Mode tiny`；方案三 `-Profile 16g` |
| RTX 4090 | 24 GB | 方案三 | `-Profile 24g`；方案二可开 `-Mode full` 冲画质 |

---

## 环境要求

- Windows 10 / 11
- NVIDIA 显卡 + 较新驱动（方案二、三需要 CUDA，方案一需要 Vulkan）
- git、Python 3.12 或 3.13（方案一不需要）
- 磁盘：程序与模型放 SSD，素材与成品放机械盘，读写特性能对上

## 安装（按这个顺序做）

```powershell
# 0. 环境体检（只读，随时可重跑，不改任何东西）
powershell -ExecutionPolicy Bypass -File .\检查环境.ps1

# 1. 方案一：Video2X（最快见效，不依赖 Python）
powershell -ExecutionPolicy Bypass -File .\01-Video2X\安装Video2X.ps1

# 2. ComfyUI 底座（方案二、三共用，只需装一次）
powershell -ExecutionPolicy Bypass -File .\00-ComfyUI底座\安装ComfyUI.ps1

# 3. 方案二：FlashVSR
powershell -ExecutionPolicy Bypass -File .\02-FlashVSR\安装FlashVSR.ps1

# 4. 方案三：SeedVR2（档位按显卡选：12g / 16g / 24g）
powershell -ExecutionPolicy Bypass -File .\03-SeedVR2\安装SeedVR2.ps1 -Profile 12g
```

## 快速开始

```powershell
# 方案一：通用/真人素材 2 倍，最快
powershell -File .\01-Video2X\批量放大.ps1 -InputPath "E:\VideoUpscale\input" -Scale 2

# 方案二：4090 上 4 倍
powershell -File .\02-FlashVSR\批量放大.ps1 -InputPath "E:\VideoUpscale\input" -Scale 4

# 方案三：按档位批量（直接用节点自带 CLI，不用先开 ComfyUI）
powershell -File .\03-SeedVR2\批量放大.ps1 -InputPath "E:\VideoUpscale\input" -Profile 12g
```

**路径约定**：只改 `common.ps1` 顶部两个变量，所有脚本自动跟着走，不用逐个改。

```
C:\AI\              <- 程序 + 模型（改 UPSCALE_ROOT 可换）
  ComfyUI\          <- 方案二、三共用的底座
  Video2X\          <- 方案一便携包

E:\VideoUpscale\    <- 素材与成品（改 UPSCALE_IO 可换）
  input\            <- 待放大的视频丢这里
  output\           <- 成品出这里
```

---

## 目录结构

```
video-upscale-deploy/
├── README.md               # 本文件：门面 + 快速开始 + 文档索引
├── AGENTS.md               # 给 AI / 未来的你：技术栈版本、关键坑、约定
├── DEVELOPMENT.md          # 架构说明与关键问题记录（一坑一篇）
├── CHANGELOG.md            # 版本变更
├── .gitignore
├── docs/
│   └── 使用指南.md          # 完整部署手册（含逐条修订记录）
├── common.ps1              # 三套方案共用的配置与工具函数
├── 检查环境.ps1             # 环境体检（只读）
├── 00-ComfyUI底座/
│   ├── 安装ComfyUI.ps1
│   └── 启动ComfyUI.ps1
├── 01-Video2X/
│   ├── 安装Video2X.ps1
│   └── 批量放大.ps1
├── 02-FlashVSR/
│   ├── 安装FlashVSR.ps1
│   └── 批量放大.ps1
└── 03-SeedVR2/
    ├── 安装SeedVR2.ps1
    └── 批量放大.ps1
```

## 文档索引

| 文档 | 给谁看 | 内容 |
|---|---|---|
| [docs/使用指南.md](docs/使用指南.md) | 使用者 | 执行顺序、每个步骤的作用、全部参数说明、显卡分配、图形界面连线表、常见问题、修订记录 |
| [AGENTS.md](AGENTS.md) | AI / 未来的你 | 技术栈精确版本、关键坑、约定、常用命令 |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 开发者 | 项目概览、架构说明、关键问题与方案 |
| [CHANGELOG.md](CHANGELOG.md) | 所有人 | 版本变更记录 |

---

## 参考来源

- Video2X：<https://github.com/k4yt3x/video2x>（命令行文档：<https://docs.video2x.org/command-line.html>）
- FlashVSR：原模型 <https://github.com/OpenImagingLab/FlashVSR>，ComfyUI 节点 <https://github.com/lihaoyun6/ComfyUI-FlashVSR_Ultra_Fast>
- SeedVR2：原模型 <https://github.com/ByteDance-Seed/SeedVR>，ComfyUI 节点 <https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler>
- VideoHelperSuite：<https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite>
- 权重仓库：`JunhaoZhuang/FlashVSR-v1.1`、`numz/SeedVR2_comfyUI`、`AInVFX/SeedVR2_comfyUI`

## 说明

- 所有参数名、模型文件名、缩放倍数限制均以各项目**官方源码**为准，核对结果见 [docs/使用指南.md](docs/使用指南.md) 的「本次修订记录」。
- 本仓库只含部署脚本与文档，不含任何模型权重；权重由安装脚本从 HuggingFace 拉取。