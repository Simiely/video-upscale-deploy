# CHANGELOG

本项目按「版本 = 可执行方案的可用快照」记录，每次改动追加一节。

---

## v1.5.0 · 2026-09-24

方案三 SeedVR2 本机部署跑通（RTX 4070 SUPER 12G）。这一版修的问题全部是**只有真跑一遍才会暴露**的——
前两轮是读源码核对，这次是端到端实跑，暴露了 5 处错误，其中 2 处是硬 bug。

### 修复

- **硬 bug：`Test-FfmpegX265` 函数不存在**。`03-SeedVR2/批量放大.ps1` 调用了它，但 `common.ps1`
  里从未定义，一加 `-TenBit` 就报「无法将"Test-FfmpegX265"项识别为 cmdlet」。已改为
  `Resolve-FfmpegTool -NeedX265`。
- **硬 bug：探测出完整版 ffmpeg 路径并不能让 CLI 用上它**。`inference_cli.py` 里写死了裸命令
  （校验用 `shutil.which("ffmpeg")`、编码用 `subprocess.Popen(['ffmpeg', ...])`），只认 PATH。
  新增 `Enable-FfmpegOnPath`，把完整版目录插到当前进程 PATH 最前面，子进程才会拿到对的那个。
  本机 PATH 第一个是 TRAE 自带的 `--disable-everything` 精简版（无 rawvideo、无 libx265），
  不改 PATH 必崩（`Unknown input format: 'rawvideo'`）。
- **音轨丢失**：SeedVR2 的 CLI 完全不处理音频（`add_argument` 全表里没有任何音频项），
  输出天然无音轨。新增 `Restore-AudioTrack`（ffmpeg `-c:v copy -c:a copy` 流拷贝），
  单文件模式与目录模式都会在收尾时回接源音轨。
- `安装SeedVR2.ps1` / `检查环境.ps1`：ffmpeg 判断从 `Test-Cmd 'ffmpeg'`（会被精简版误判为可用）
  改为 `Resolve-FfmpegTool` 按能力探测，并区分「完整版 / 无 libx265 / 没有」三档提示。
- **目录模式产物命名不一致 + 重复计算**：SeedVR2 目录模式沿用输入文件名（无后缀），与方案一（`_2x`）、
  方案二（`_4x_flashvsr`）不一致；若「输入目录 == 输出目录」还会直接覆盖源文件。
  已统一改为 `<原名>_<分辨率>p_seedvr2.mp4`，并加 `-Overwrite` 保护。
  另外把「输出是否已存在」的检查**提前到开跑前**——原来放在 CLI 跑完之后，等于每次都白算一遍
  （实测：已有产物时从 3 分 36 秒降到 1.7 秒秒退）。
- **README 与两处安装脚本的提示行残留 `-Input`**：v1.4.0 只改了脚本参数名，漏改这些文案，
  照抄会报「找不到参数 `-Input`」。全部改为 `-InputPath`。
- 文档常见问题第 4 条原写「SeedVR2 的 CLI 会自动保留音轨」——**完全错误**，已更正。
- **图形界面小节写「搜 `SeedVR2` 能看到全部 4 个节点」**：实测是 **9 个**。该节点走 ComfyUI 新版
  `comfy_entrypoint` 扩展接口注册，`__init__.py` 里没有 `NODE_CLASS_MAPPINGS`，所以光看源码
  grep 不到——只有起一次服务查 `/object_info` 才能确认。
- **未提示下拉框选型陷阱**：`SeedVR2 (Down)Load DiT Model` 的下拉框会列出注册表里全部 10 个
  DiT 模型（含 7B 与 GGUF），与文件是否在本地无关。12G 卡误选 7B 会先自动拉十几 GB 再 OOM，
  已在手册该小节加粗提示「保持默认」。

### 新增

- `common.ps1`：`Enable-FfmpegOnPath`（把可用 ffmpeg 注入子进程 PATH）
- `common.ps1`：`Get-FFmpegExe` / `Get-FfprobeExe` / `Test-HasAudio` / `Restore-AudioTrack`
- 使用指南新增「RTX 4070 SUPER 12G 实测」小节：分阶段耗时表 + 换算 + 提速建议
- 使用指南常见问题新增第 8 条（ffmpeg 精简构建的识别与处置）、第 9 条（用 ffprobe 自检输出）

### 实测数据（4070 SUPER 12G，`-Profile 12g` = 3B FP8 + BlockSwap 24 + VAE 分块）

源：1280×720 / 48 帧 / 2.0 秒 / h264 + AAC

| 阶段 | 耗时 | 说明 |
|---|---|---|
| VAE 编码（10 批 × 5 帧） | 约 31 s | 3.1 s/批 |
| DiT 扩散（10 批） | 约 40 s | 3.9 s/批，BlockSwap 24/32 |
| VAE 解码（10 批） | 约 130 s | 13 s/批，**全链路最慢** |
| 后处理 + 封装 | 约 8 s | LAB 色彩迁移 |
| **合计** | **209 s** | **约 4.4 s/帧**；脚本端到端 3 分 36 秒 |

- 启动显存余量 10.81 GB / 11.99 GB，全程无 OOM
- 输出校验（单文件模式与目录模式**两条分支**均验证）：
  `h264 High` / 1920×1080 / 48 帧（与源一致）/ AAC 94 帧（与源一致）/ 4.75 MB
- 换算：24fps 素材约 **17.6 小时/10 分钟片**，印证对比表"数小时级"的定位
- 图形界面通路单独验证：ComfyUI 0.37.0 冷启动 `seedvr2_videoupscaler` 导入 1.9 秒无报错，
  9 个节点全部注册；DiT 下拉默认值 = 已下载的 3B FP8（选项共 10 个，见上「未提示下拉框选型陷阱」）
- 复核：目录模式完整重跑一次（218 s 推理 / 0.22 fps，脚本 3 分 46 秒），产物与首次一致

### 技术说明

- **解码比扩散慢三倍多**，与"扩散模型慢在扩散"的直觉相反：VAE 分块 + 逐批 CPU 往返是主因。
  12G 上这是必要代价——关掉 `-TiledVae` 实测直接 OOM。
- 修复前那次"跑通"的输出其实是 `codec_name=mpeg4`（MPEG-4 Part 2），说明走的是 opencv 回退
  路径，ffmpeg 后端从未真正生效。**这也是为什么必须用 ffprobe 校验编码，而不是只看"跑完了"**。
- 清理了 1010 MB 下载残留：早期 `huggingface_hub` 失败留下的 `.cache\huggingface\download\*.incomplete`
  在改用 curl 后已无用途。

---

## v1.4.0 · 2026-09-24

方案二 FlashVSR 本机部署跑通（RTX 4070 SUPER 12G），并修复脚本与文档中的参数名不一致问题。

### 新增

- `02-FlashVSR/workflow_api.json`：可直接 POST 给 ComfyUI `/prompt` 的 API 格式工作流
  （`VHS_LoadVideoPath` → `FlashVSRNode` → `VHS_VideoCombine`，含音轨回接）
- 使用指南新增「RTX 4070 SUPER 12G 实测」小节：速度、显存峰值、分块必要性

### 修复

- **参数名冲突**：`02-FlashVSR/批量放大.ps1` 与 `03-SeedVR2/批量放大.ps1` 的 `-Input`
  与 PowerShell 自动变量 `$input` 冲突，导致 `Get-VideoFiles -Path $Input` 拿到空字符串而报
  `Cannot bind argument to parameter 'Path' because it is an empty string`。
  统一改名为 `-InputPath`（方案一早在 v1.1.0 已改，这两个脚本漏改）。
- **HF 下载函数**：`common.ps1` 的 `Invoke-HfDownload` 用 `python -c` 传多行代码时引号被 shell 吃掉，
  生成 `inc == *`、`inc.split(,)` 这类非法语法。改为写临时 `.py` 文件再执行。
- 使用指南中 9 处 `-Input` 示例同步改为 `-InputPath`。

### 实测数据（4070 SUPER 12G，tiny 模式，tiled_vae/tiled_dit 默认开启）

| 源 | 帧数 | 输出 | 耗时 | 速度 |
|---|---|---|---|---|
| 1280×720（约 6 秒） | 143 | 2560×1440 | 586 s | 4.10 s/帧 |
| 1280×720（2 秒） | 48 | 2560×1440 | 196 s | 4.08 s/帧 |

- 显存峰值约 11.4 GB / 12.3 GB，GPU 利用率 100%
- 帧数、帧率、音轨原样保留
- **关掉 `tiled_dit` 或 `tiled_vae` 必然 OOM**（节点申请 19.02 GiB > 12G 上限 11.99 GiB），
  12G 卡必须保持分块开启；分块会把 720p 输入切成 18 个 256px 空间块逐个推理

### 技术说明

- FlashVSR 权重仓库为 `JunhaoZhuang/FlashVSR-v1.1`，共 8 个文件约 6.5 GB，
  落到 `ComfyUI\models\FlashVSR-v1.1`（节点源码 `nodes.py` 里 `model_path = models_dir / model` 写死这个布局）
- 主模型 `diffusion_pytorch_model_streaming_dmd.safetensors` 约 5.29 GB / 825 个张量，
  校验方式：读 safetensors 头部的 JSON 长度并解析张量表
- hf-mirror 的 xet 传输协议在拉大文件时不稳定，需设 `HF_HUB_DISABLE_XET=1` 并降为单线程续传

---

## v1.3.0 · 2026-09-24

GUI 稳定性修复 + 深色主题。

### 修复

- **核心修复**：GUI 改用 `System.Diagnostics.Process` + cmd 重定向启动 video2x，替代 `Start-Job`（PowerShell 后台任务在 WinForms 事件中状态检测失效）
- **参数拼接**：修复 `crf=` 与数字间被拆成两个参数的 bug（`'crf=' + $Crf` 改成 `"crf=$($Crf)"` 字符串插值）
- **跳过校验**：输出文件小于 10KB 视为损坏，自动删除重新处理，避免 48 字节空文件被误判为已完成
- **完成检测**：Timer 轮询进程 `HasExited`，处理完后正确显示结果并弹框
- **作用域修复**：所有在事件/函数中访问的变量改用 `$script:` 作用域

### 新增

- **深色主题**：VS Code 风格深色界面（背景 `#1e1e1e`，输入框 `#2d2d30`，文字 `#d4d4d4`）
- **实时日志**：video2x 的完整输出实时显示在日志面板，方便排错
- **命令回显**：日志里显示实际执行的 video2x 命令行
- **窗口加高**：680px 高度，底部状态区域不再被裁切

### 技术说明

- 用临时日志文件 + Timer 轮询的方式实现输出回显，避免跨线程操作 UI 控件
- 所有类型构造统一使用 `[Type]::new()` 语法，避开 PowerShell 5.1 `New-Object` 参数解析 bug

---

## v1.2.0 · 2026-09-24

新增 Video2X 图形界面（WinForms），不用记命令行参数，窗口里点几下就能放大。

### 新增

- `01-Video2X/Video2X_GUI.ps1`：原生 Windows 窗口界面
  - 选文件或文件夹作为输入
  - 四种处理器：Real-CUGAN / Real-ESRGAN / Anime4K / RIFE
  - 模型下拉自动联动（换处理器自动刷新模型列表，换模型自动调整可用倍数）
  - CRF 画质滑块（15-28，实时提示"高质量/平衡/体积小"）
  - 显卡选择（自动枚举 Vulkan 设备）
  - 进度条 + 深色日志面板
  - 处理完弹窗提示，可一键打开输出目录
  - 自动跳过已完成、关闭时确认

### 技术说明

- 用 PowerShell WinForms 实现，无需额外安装
- 后台 Job 处理视频，界面不卡死
- 所有构造函数使用 `[Type]::new()` 语法（避开 PowerShell 5.1 `New-Object` 参数解析 bug）

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