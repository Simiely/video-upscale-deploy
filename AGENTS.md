# AGENTS.md · 项目规则

> 📌 **文档基线**：2026-09-24（commit `3a80057`）v1.1.0 Video2X 本机部署验证通过
> **更新文档/代码后，请更新此行**（日期 + 新 commit hash），并在 CHANGELOG 追加版本

只写代码里看不出的信息。细节见 [DEVELOPMENT.md](DEVELOPMENT.md) 与 [docs/使用指南.md](docs/使用指南.md)。

## 技术栈

| 组件 | 版本 / 来源 |
|---|---|
| 脚本运行环境 | Windows PowerShell **5.1**（不是 PowerShell 7，别用 `??`、`&&` 等新语法） |
| 基础 Python | 3.12 / 3.13，自动探测（`common.ps1` 的 `Get-BasePython`） |
| PyTorch | CUDA 版，按 cu130 → cu128 → cu126 依次尝试，验证 `torch.cuda.is_available()` |
| ComfyUI | `comfyanonymous/ComfyUI`（跟随 main），装进 `C:\AI\ComfyUI\.venv` |
| ComfyUI-Manager | `ltdrdata/ComfyUI-Manager` |
| 视频读写节点 | `Kosinkadink/ComfyUI-VideoHelperSuite` |
| 方案二节点 | `lihaoyun6/ComfyUI-FlashVSR_Ultra_Fast` |
| 方案二权重 | HF `JunhaoZhuang/FlashVSR-v1.1`（4 个主要文件约 6.95 GB，落到 `models\FlashVSR-v1.1`） |
| 方案三节点 | `numz/ComfyUI-SeedVR2_VideoUpscaler`（**v2.5.24**，自带 `inference_cli.py`） |
| 方案三权重 | HF `numz/SeedVR2_comfyUI` + `AInVFX/SeedVR2_comfyUI` |
| 方案一 | `k4yt3x/video2x` **6.4.0** Windows 便携版（C++/Vulkan，不依赖 Python/CUDA） |
| HF 下载源 | 默认 `hf-mirror.com`，可用环境变量 `HF_ENDPOINT` 覆盖 |

目标显卡：RTX 4070 Super 12G / 4070 Ti Super 16G / RTX 4090 24G

## 关键坑（改动前必读）

- **中文脚本必须存成 UTF-8 with BOM**：PowerShell 5.1 对无 BOM 文件按 ANSI 解码，中文被误读会让脚本解析直接失败。改完 `.ps1` 必须确认 BOM 还在。
- **SeedVR2 的 `--allow_vram_overflow` 不存在**：上游 README 列了它，但 v2.5.24 的 `inference_cli.py` 没实现，`parse_args()` 会以 `unrecognized arguments` 退出。**别照 README 加回来。**
- **SeedVR2 权重分两个仓库**：`seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors` 和全部 GGUF 在 `AInVFX/SeedVR2_comfyUI`，其余 safetensors 在 `numz/SeedVR2_comfyUI`。下错仓库直接 404。
- **`--dit_model` 只认注册表里的名字**：候选项 = 节点 `src/utils/model_registry.py` 的 `MODEL_REGISTRY` ∪ 磁盘已有文件。名字写错，ComfyUI 下拉框里就选不到。
- **FlashVSR 需要 `posi_prompt.pth`**：它不在 HF 权重里，随节点仓库提交，由 `nodes.py` 从节点目录加载。必须完整 clone，不能用手工 zip。
- **NVENC 格式没有 `crf`**：VideoHelperSuite 里 `nvenc_*` 用 `bitrate` + `megabit`，`h264/h265-mp4` 用 `crf`。传错会被静默忽略，输出质量不受控。
- **批量脚本的输入参数叫 `-InputPath`，不能叫 `-Input`**：`$Input` 会撞 PowerShell 自动变量 `$input`，`Get-VideoFiles -Path $Input` 拿到空串后报 `Cannot bind argument to parameter 'Path' because it is an empty string`。三个批量脚本统一用 `-InputPath`，改脚本/文档时别改回去。
- **12G 卡跑 FlashVSR 必须开分块**：`tiled_dit` / `tiled_vae` 关掉任意一个都会 OOM（实测节点申请 19.02 GiB，而 12G 卡上限 11.99 GiB）。这两个开关只对 24G 卡有意义。
- **FlashVSR 权重目录布局是写死的**：节点 `nodes.py` 用 `model_path = models_dir / model`，所以必须落在 `models\FlashVSR-v1.1`，不能套一层 `models\FlashVSR\FlashVSR-v1.1`。
- **hf-mirror 拉大文件要关 xet**：设 `HF_HUB_DISABLE_XET=1` 并降为单线程续传，否则 5 GB 级文件会反复中断，还会留下巨型 `.incomplete` 残留。

## 约定

- 脚本与文档全中文；输出信息用 `[完成]` / `[注意]` 前缀，不用 emoji
- 路径一律从 `common.ps1` 顶部的 `UPSCALE_ROOT` / `UPSCALE_IO` 派生，脚本内不写死绝对路径
- 参数合法性检查放在脚本**最前面**，非法值提前 `throw`，不跑到一半才失败
- 改 `-Profile` 档位名要同步四处：`03-SeedVR2\安装SeedVR2.ps1`、`03-SeedVR2\批量放大.ps1`、`检查环境.ps1`、`docs/使用指南.md`
- 体积统一按 1 GB = 10⁹ 字节（HuggingFace 口径），并注明与 Windows 显示值（GiB）的差异

## 常用命令

```powershell
# 环境体检（只读）
powershell -ExecutionPolicy Bypass -File .\检查环境.ps1

# 改完脚本必跑：语法校验 + BOM 检查
Get-ChildItem -Recurse -Filter *.ps1 | ForEach-Object {
  $e = $null
  [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$null, [ref]$e)
  $b = [IO.File]::ReadAllBytes($_.FullName)
  $bom = ($b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)
  "{0,-24} {1} BOM={2}" -f $_.Name, $(if ($e.Count) { "FAIL: $($e[0].Message)" } else { "OK" }), $bom
}

# 启动 ComfyUI（方案二、三的图形界面都从这里进）
powershell -File .\00-ComfyUI底座\启动ComfyUI.ps1

# 查 SeedVR2 CLI 支持哪些参数（改批量脚本前先跑这个）
& C:\AI\ComfyUI\.venv\Scripts\python.exe C:\AI\ComfyUI\custom_nodes\seedvr2_videoupscaler\inference_cli.py --help
```

## 详细规则（按需 @引用）

- 完整部署手册与修订记录：@docs/使用指南.md
- 架构说明与关键问题记录：@DEVELOPMENT.md
- 版本变更：@CHANGELOG.md