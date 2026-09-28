# workflows · 图形界面工作流

> 拖进 ComfyUI 网页即用：节点、连线、参数全部自动还原，不用手动搭图。
> 这些文件是**配置**不是脚本，配合 `00-ComfyUI底座\启动ComfyUI.ps1` 使用。

---

## 怎么用（三步）

```powershell
# 1. 起服务（会自动开浏览器）
powershell -ExecutionPolicy Bypass -File .\00-ComfyUI底座\启动ComfyUI.ps1
```

2. 打开 <http://127.0.0.1:8188>
3. **把本目录下的 `.json` 直接拖进网页** → 节点自动铺开 → 改素材路径 → 点 Run

**跑完记得 Ctrl+S 保存**，存进 ComfyUI 侧边栏的 Workflows 列表，以后点一下就打开。

---

## 清单

| 文件 | 对应方案 | 档位 | 适用素材 |
|---|---|---|---|
| [FlashVSR/FlashVSR-12G-有声素材.json](FlashVSR/FlashVSR-12G-有声素材.json) | 方案二 | `tiny-long` / 2× | **有音轨**的素材，产物带原声 |
| [FlashVSR/FlashVSR-12G-无音轨素材.json](FlashVSR/FlashVSR-12G-无音轨素材.json) | 方案二 | `tiny-long` / 2× | **无音轨**的素材（断开了音频连线）|
| [SeedVR2/SeedVR2-12G-1080p.json](SeedVR2/SeedVR2-12G-1080p.json) | 方案三 | 3B FP8 / 短边 1080 | 关键镜头、成片交付 |

三个文件都按 **RTX 4070 SUPER 12G** 调好参数。16G / 24G 卡要改见下面「档位换算」。

---

## 为什么不给 UI 格式，只给这种 JSON

ComfyUI 前端源码（`comfyui_frontend_package/static/assets/settingStore-*.js`）里有这段判定：

```js
function isApiJson(e){ return De(e) && Object.values(e).every(e => e.class_type) }
function getDataFromJSON(e){
  ...
  if (isApiJson(e)) { t({prompt: e}); return }   // ← API 格式：自动还原成节点图
  t({workflow: e})
}
```

**只要 JSON 里每个节点都带 `class_type`，前端就认它是工作流并自动布局。** 这是本目录所有文件采用这种写法的原因。

相比之下，手写「UI 格式」要维护 `widgets_values` 数组的**严格顺序**，还要处理 `format` 下拉框联动出来的动态参数（选 `h264-mp4` 多出 `crf`，选 `nvenc_*` 变成 `bitrate` + `megabit`）——**写错不会报错，只会静默用默认值**，比手动连线更难发现。

---

## ⚠️ 两个 FlashVSR 版本别选错

`VHS_LoadVideoPath` 的 `audio` 输出是**惰性对象**，只有被下游引用时才会去提取（`videohelpersuite/utils.py` 的 `get_audio()`）。**源文件没有音频流时，ffmpeg 会报 `Output file does not contain any stream`，VHS 直接把 stderr 包成 Exception 抛出——它不做「无音轨」降级判断。**

| 你的素材 | 用哪个 | 产物 |
|---|---|---|
| 有 audio 流 | `FlashVSR-12G-有声素材.json` | 画面 + 原音轨 |
| 没有 audio 流 | `FlashVSR-12G-无音轨素材.json` | 只有画面（源本来就没声音，无损失）|

**选错的症状**：任务在**第一个节点**就 error，信息形如

```
VHS failed to extract audio from <你的文件>:
Output #0, f32le, to 'pipe:':
[out#0/f32le] Output file does not contain any stream
```

**先用 ffprobe 判断素材有没有音轨**：

```powershell
ffprobe -v error -show_entries stream=codec_type -of csv=p=0 "素材.mp4"
# 出现 audio 才算有音轨；只输出 video 就是无音轨
```

---

## 参数怎么改（页面里点）

### FlashVSR

| 参数 | 位置 | 说明 |
|---|---|---|
| `video` | Load Video (Path) | **完整路径**，如 `E:\VideoUpscale\input\a.mp4` |
| `frame_load_cap` | Load Video (Path) | `0` = 整片 |
| `model` | FlashVSR Ultra-Fast | 保持 `FlashVSR-v1.1` |
| `mode` | FlashVSR Ultra-Fast | 12G 用 `tiny-long`（16G 可试 `tiny`，24G 可 `full`）|
| `scale` | FlashVSR Ultra-Fast | **只能 2 / 3 / 4**，输出 = 输入 × scale |
| `tiled_vae` `tiled_dit` | FlashVSR Ultra-Fast | **12G 必须都开着**，关任一个就 OOM |
| `crf` | Video Combine | 质量，**建议 17**（见下）|

**输出分辨率 = 输入 × scale**（FlashVSR 没有「指定分辨率」参数）：

| 输入 | scale 2 | scale 3 | scale 4 |
|---|---|---|---|
| 1280×720 | 2560×1440 | 3840×2160（4K）| 5120×2880 |
| 1920×1080 | 3840×2160（4K）| 5760×3240 | — |
| 2048×1152 | 4096×2304 | 6144×3456 | — |
| 2560×1440 | 5120×2880 | — | — |

> 想要「指定目标分辨率」而不是倍数，那是**方案三 SeedVR2** 的 `resolution` 参数（指定短边像素，自动保持宽高比）。

### SeedVR2

| 参数 | 位置 | 12G 取值 |
|---|---|---|
| `model` | (Down)Load DiT Model | `seedvr2_ema_3b_fp8_e4m3fn.safetensors`（**别选 7B**）|
| `blocks_to_swap` | (Down)Load DiT Model | `24`（3B 上限 32）|
| `swap_io_components` | (Down)Load DiT Model | `true` —— GUI 里这个开关是独立的，**容易漏开** |
| `offload_device` | 两个 Load 节点 | `cpu` |
| `resolution` | Video Upscaler | 短边像素，如 `1080` |
| `batch_size` | Video Upscaler | **必须 4n+1**（1/5/9/13/17/21…），12G 建议 21 |
| `uniform_batch_size` | Video Upscaler | `true` |
| `color_correction` | Video Upscaler | `lab` |

> ⚠️ `SeedVR2 (Down)Load DiT Model` 的下拉框会列出注册表里**全部 10 个** DiT 模型（含 7B 与 GGUF），**与你本地有没有无关**。12G 卡误选 7B 会先自动下载十几 GB 再 OOM，**保持默认即可**。

### 档位换算（16G / 24G）

| 显卡 | FlashVSR `mode` | SeedVR2 档位 |
|---|---|---|
| 4070 Super 12G | `tiny-long` | 3B FP8 + `blocks_to_swap` 24 + VAE 分块 |
| 4070 Ti Super 16G | `tiny` | 3B FP16 + `blocks_to_swap` 16 |
| 4090 24G | `full` | 7B FP8(mixed) + `blocks_to_swap` 0 + torch.compile |

---

## 产物去哪

由 ComfyUI 的 `--output-directory` 决定。`启动ComfyUI.ps1` 默认把它设成 `common.ps1` 里的 `UPSCALE_IO\output`（即 `E:\VideoUpscale\output`），**和命令行脚本的落点一致**。

产物命名看 `Video Combine` 的 `filename_prefix`（默认 `upscaled/flashvsr`）：

```
E:\VideoUpscale\output\upscaled\flashvsr_00001.mp4          ← 只有画面
E:\VideoUpscale\output\upscaled\flashvsr_00001-audio.mp4    ← 带音轨的，一般用这个
```

> ⚠️ 连了音频线时 VHS 会同时写两个文件，**只有带 `-audio` 后缀的含音轨**，别拿错。没连音频线时只写一个。

**想换落点**：改 `启动ComfyUI.ps1 -OutputDirectory "D:\某处"`，或直接改 `common.ps1` 的 `UPSCALE_IO`。
⚠️ ComfyUI 有硬性校验，**产物必须落在 output 根目录之内**，写绝对路径或 `..` 会被拒绝：
`Saving image outside the output folder is not allowed.`

---

## `crf` 该填多少（实测）

`h264-mp4` 格式默认 `crf=19`。实测（4K 素材二次编码对照）：

| crf | 文件大小 | 相对 19 |
|---|---|---|
| 17 | +31.9% | |
| 19 | 基准（VHS 默认）| |
| 23 | −45.6% | |

规律：**crf 每 +2，文件小约 21%；每 +6，约减半**。

**但建议填 17 而不是默认的 19** —— 因为就你那份 4K 任务而言，**编码只占 43 秒 / 总 2506 秒 = 1.7%**。多花几秒编码时间换回花 40 分钟推理出来的细节，这笔账很划算。

| crf | 用途 |
|---|---|
| 15 | 交付母版 / 还要二次剪辑 |
| **17** | **推荐** |
| 19 | 默认值，能用但白瞎了前面的算力 |
| 23 | 预览 / 存草稿 |

另可把 `pix_fmt` 设为 `yuv420p10le`（10bit），缓解渐变区域色带，代价是文件再大一点。

---

## 实测性能（RTX 4070 SUPER 12G）

| 配置 | 输出 | 每帧耗时 | 6 秒 24fps 素材（143 帧）|
|---|---|---|---|
| FlashVSR `tiny-long` scale 2 | 2560×1440 | **3.5 s/帧** | 约 9 分钟 |
| FlashVSR `tiny-long` scale 3 | 3840×2160 | **≈17 s/帧** | **41 分 46 秒**（实测）|

**⚠️ scale 的提升是超线性的**：2 → 3 面积只涨 2.25 倍，耗时涨约 **5 倍**（tile 数量与单 tile 窗口同时变大）。
开跑前按目标输出分辨率估时间，别只看"倍率"。

---

## 相关文档

- 图形界面连线表（想手动搭图时）：[../docs/使用指南.md](../docs/使用指南.md) 第五节
- 命令行批量放大：`../02-FlashVSR\批量放大.ps1`、`../03-SeedVR2\批量放大.ps1`
- 关键坑与约定：[../AGENTS.md](../AGENTS.md)
