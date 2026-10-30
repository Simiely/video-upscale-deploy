# AGENTS.md · 项目规则

> 📌 **文档基线**：2026-10-30 **v1.13.2**（commit hash `951416f`）（修「恢复」撞名毁画布原件的隐患〔`[API] ` 前缀 + 判定同步 + 跳过 `_弃用-工作流/`〕；`log_to_file` 默认开 + 7 天清理；`verify_deploy.py` 瘦身；根 CHANGELOG 与 AGENTS 基线去重，旧条目入 `docs/版本历史.md`） · 2026-10-30 **v1.13.1**（commit hash `2ab1e58`）（工程侧：`发版.py` 打包前强制跑两套用例（55 + 17，无 tkinter）；`tools/check_text.py` 查 `.ps1` BOM/行尾；`launcher/tests/manual/` 收编两个手开窗口的冒烟脚本；`config_drift_lines` 提示 `common.ps1` 与启动器 CONFIG 的路径不一致） · 2026-10-30 **v1.13.0**（commit hash `0eccdd2`）（工程收口：加 `.gitattributes` 统一行尾；`launcher/tests/` 46 个纯函数用例；`launcher/发版.py` 一条命令发版；`verify_deploy --real/--remote` 真机盘点 + 远端对账；`部署清单` 新增 `hf_path` 覆盖字段）· 2026-10-27 **v1.11.0**（commit hash `f59a486`）（新增方案四 `04-VisualEnhancer/`〔VEHelper v1.5.0：7 模块重构 + 精简 GPU/磁盘/端口展示〕；发版合并未单独发版的 v1.10.1）· 2026-10-27 **v1.10.1**（commit hash `564425f`）（启动器 v1.4.0：磁盘预检 / ffmpeg 一键装 / torch·CUDA 自检 / 代理自动探测 / 项内进度 / GitHub 镜像回退；`common.ps1` 新增 `Invoke-GhAsset`，`01-Video2X/安装Video2X.ps1` 改走镜像回退）· 2026-10-27 **v1.10.0**（commit hash `4292ab0`）（启动器改名「ComfyUI 启动器」〔启动器 v1.3.0，exe 产物 `ComfyUI启动器.exe`〕+ Releases 补发：`ComfyUI-Launcher-v1.3.0.exe` / `video-upscale-deploy-v1.10.0.zip`）· 2026-10-26 **v1.9.2**（发版快照：Releases 附 `VideoLauncher-v1.2.22.exe` 与整包 zip；含启动器 v1.2.21/22 全部修复）(commit `c4cd9ad`) · 2026-10-26 **v1.2.21**（图生视频首帧不生效：提示词按 MiniMax 官方 I2VA 结构补对齐句 + 三字段、启动器加提示词入口、`mm_i2v` 改指专用画布原件、`115` 接回宽高）(commit `5a7f3c8`) · 2026-10-14 **v1.9.1**（ComfyUI 输出根统一到 `$OUTPUT_DIR`：`02-FlashVSR/批量放大.ps1` 不再写死 `$COMFY_DIR\output`、`-AutoStart` 补传 `--output-directory`；配套启动器 v1.2.20）· 2026-10-14 **v1.9.0**（两个仓库合并：`video-launcher` 用 git subtree 并入 `launcher/` 子目录〔完整提交历史保留〕 + 启动器 `deploy_root` 自动定位）(commit `732f858`) · ……（v1.10.1 及更早的条目见 docs/版本历史.md）
> **更新文档/代码后，请更新此行**（日期 + 新 commit hash），并在 CHANGELOG 追加版本

只写代码里看不出的信息。细节见 [DEVELOPMENT.md](DEVELOPMENT.md) 与 [docs/使用指南.md](docs/使用指南.md)。

## 仓库结构（v1.9.0 起）

本仓库 = **部署包（根目录）+ 图形启动器（`launcher/`）+ 方案四视觉增强启动器（`04-VisualEnhancer/`）**。
`launcher/` 是 v1.9.0 从独立的 `video-launcher` 仓库用 **`git subtree`** 并入的 ——
**完整提交历史都在这一棵历史里**（`git log --oneline -- launcher/` 可查），不是搬文件压平。

| 区域 | 内容 | 语言 | 什么时候动 |
|---|---|---|---|
| 根：`00-ComfyUI底座/` ~ `03-SeedVR2/`、`common.ps1`、`检查环境.ps1` | 装环境、批量放大 | PowerShell 5.1 | 换引擎版本、调参数 |
| `workflows/` | 11 份工作流图（API 扁平表格式） | JSON | 换模型、调档位 |
| `launcher/` | 桌面启动器（界面 + 调度） | Python 3.12+ / tkinter | 改界面、改调度逻辑 |
| `04-VisualEnhancer/` | 方案四：Merserk Visual Enhancer 下载/安装/启动器（非 ComfyUI） | Python 3.12+ / tkinter + sv-ttk | 改下载链路、界面、打包 |

> ⚠️ **改工作流文件名要同步三处**（v1.8.0 那次改名就是这三处）：
> ① `workflows/` 里的文件名 → ② `launcher/运行时.py` 的 `WORKFLOWS` 里六条 `api` 路径
> → ③ ComfyUI `user/default/workflows/` 下的画布原件名（对应 `launcher/桥接资源.py` 的 `WF_UI_SOURCES`）。
> 合并解决了"两个仓库来回同步"，但这三处还在同一仓库的不同位置，改名时别漏。

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
| VEHelper 运行/打包 | Python 3.14.6（本机）+ tkinter + `sv-ttk` 2.6.1；PyInstaller 6.22.3，产物 `VEHelper.exe` |
| 方案四外部程序 | `Merserk/dlss5-visual-enhancer` 桌面版，默认安装到 `D:\Tool\VisualEnhancer`（不入库） |

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
- **SeedVR2 的 ffmpeg 只认 PATH，而且「注入进去」不一定到得了子进程**：`inference_cli.py` 写死了裸命令（校验 `shutil.which("ffmpeg")`、编码 `subprocess.Popen(['ffmpeg', ...])`），`add_argument` 全表**没有** `--ffmpeg_path` 这类参数，**PATH 是唯一杠杆**。`common.ps1` 的 `Enable-FfmpegOnPath` 把完整版目录插到当前进程 PATH 最前，**普通终端里有效**；但**某些宿主（AI agent 的执行环境）创建子进程时会用固定快照重写环境**，注入的目录到不了子进程——表现为日志打印了正确路径、CLI 仍报 `--video_backend ffmpeg requires ffmpeg in PATH`。**处置：把 ffmpeg 放到候选① `<UPSCALE_ROOT>\ffmpeg\bin\` 并写进注册表级【用户级】PATH（改完开新终端）**；`03-SeedVR2\批量放大.ps1` 开跑前会用真实子进程复核一次，拿不到就直接报错，不等到 CLI 崩。
- **别再把 TRAE 自带的 ffmpeg 当成精简构建**：实测 `%APPDATA%\TRAE SOLO CN\...\app\ffmpeg\ffmpeg.exe` 是 **gyan.dev 8.1-full**（rawvideo / libx264 / libx265 齐全，同目录含 `ffprobe.exe`）。早期 `common.ps1` 注释与手册说它是 `--disable-everything` 版本，属**过时误判**，2026-09-30 已更正（详见手册常见问题第 8 条、修订记录第 29 条）。
- **别用 `Test-Cmd 'ffmpeg'` 判断 ffmpeg 可用**：精简构建也在 PATH 上，会被误判为可用。统一用 `Resolve-FfmpegTool`（按 `-demuxers` 找 rawvideo、按 `-encoders` 找 libx265 做能力探测）。
- **SeedVR2 的 CLI 完全不处理音频**：`inference_cli.py` 的 `add_argument` 全表里没有任何音频项，输出天然无音轨。单文件与目录两种模式都由 `批量放大.ps1` 收尾时调 `Restore-AudioTrack` 用 ffmpeg 流拷贝接回（`-c:v copy -c:a copy`）。
- **校验输出要看编码，不能只看「跑完了」**：SeedVR2 在 ffmpeg 后端不可用时会**静默退回 opencv**，写成 MPEG-4 Part 2（`codec_name=mpeg4`，同画质体积大得多）。用 ffprobe 核对 `codec_name` 应为 `h264`、帧数与源一致、有 `aac` 音轨。
- **`VHS_LoadVideoPath` 连了 `audio` 就不能喂无音轨素材**：该节点的 audio 输出是**惰性对象**，被下游引用时才调 `get_audio()`（`videohelpersuite/utils.py`）；源没有 audio 流时 ffmpeg 报 `Output file does not contain any stream`，VHS 把 stderr 包成 Exception **直接抛，不做降级**——任务在 node 1 就 error，信息是 `VHS failed to extract audio from ...`。无音轨素材要么断开这条线（见 `workflows/FlashVSR/FlashVSR-放大2x-无音轨素材.json`），要么先补一条静音轨。用 `ffprobe -v error -show_entries stream=codec_type -of csv=p=0 x.mp4` 判断。
- **ComfyUI 的产物只能落在 output 根目录之内**：`folder_paths.get_save_image_path()` 会校验，绝对路径（跨盘/同盘）与 `..\..` 一律抛 `Saving image outside the output folder is not allowed.`。改落点只能用启动参数 `--output-directory`（`启动ComfyUI.ps1` 已暴露为 `-OutputDirectory`，默认跟随 `common.ps1` 的 `UPSCALE_IO\output`）——**改工作流里的 `filename_prefix` 做不到**。
  - ⚠️ **配套坑（v1.9.1 修）**：既然落点**只**由启动参数决定，那**每一条拉起 ComfyUI 的路径都必须显式传它** —— 漏一条就多一个输出落点。启动器曾漏传，导致画布手动跑的产物落在 `<comfy_dir>\output`，而界面显示的是另一个目录（用户报"输出目录又变了"）。现在三处已统一到 `$OUTPUT_DIR`：`启动ComfyUI.ps1`、启动器 `launcher/`（v1.2.20）、`02-FlashVSR/批量放大.ps1 -AutoStart`（v1.9.1）。**以后新增任何拉起 ComfyUI 的代码点，都要把 `--output-directory` 带上。**
  - ⚠️ **同源坑**：`02-FlashVSR/批量放大.ps1` 取产物靠「提交前后目录差集」，所以它的 `$comfyOutDir` 必须与同一个输出根对齐（v1.9.1 已从写死的 `$COMFY_DIR\output` 改为 `$OUTPUT_DIR`）。两者不一致时脚本会报「跑完了但没找到输出文件」——那是**找错目录**，不是任务失败。
- **别用「倍率」估 FlashVSR 的时间，要按输出分辨率估**：实测 720p→1440p = 3.5 s/帧，720p→2160p（scale 3）= **≈17 s/帧**。面积只涨 2.25 倍，耗时涨约 5 倍（tile 数与单 tile 窗口同时变大），**scale 是超线性的**，按倍率估会严重低估。
- **`/interrupt` 打不断 CUDA 算子**：`POST /interrupt` 返回 200、日志也打印 `Global interrupt`，但队列仍 `running`、GPU 仍 100%（VAE 的 tiled kernel 要等算子返回，可能几分钟）。只能杀进程：`netstat -ano` 找 8188 的 PID → `Stop-Process -Id <pid> -Force`；停完三项核验：端口释放 / 显存回落 / `nvidia-smi --query-compute-apps` 里无 python。
- **`workflows/` 下的 json 故意用 API 格式而非 UI 格式**：前端 `isApiJson(e)` 的判定是「是对象且每个值都带 `class_type`」，满足即自动还原成节点图（源码见 `comfyui_frontend_package/static/assets/settingStore-*.js`）。UI 格式要维护 `widgets_values` 的严格顺序，还要处理 `format` 联动出的动态参数（`h264-mp4` → `crf`；`nvenc_*` → `bitrate` + `megabit`），**写错不会报错、只会静默用默认值**，比手动连线更难查。
- **VEHelper 的版本查询不能换成 REST API**：未认证 GitHub API 只有 60 次/小时，界面每次启动都查很容易打满；现用 `releases.atom` 取 tag + `releases/expanded_assets/<tag>` 取资产名，不受该限额影响。
- **`.parts/plan.json` 必须按 tag / 资产名 / 总字节数三者校验**：只比 tag 会把不同版本的段拼在一起，合并出来是坏包。任一项对不上就整计划重置。
- **不要尝试用程序下 VE 的三个模型**：`Visual-Enhancer/*` 是私有 HF 仓库，匿名请求 401，作者页也没有公开副本，官方 GUI 没有 token 输入口。这三颗只影响「模型加载」，神经渲染 / DLSS SR / RTX VSR 都不需要它们。
- **打包 tkinter 前先清 `TCL_LIBRARY` / `TK_LIBRARY`**：外部 PyInstaller 程序可能把这两个变量留在父进程环境里，PyInstaller 会据此判定「tkinter installation is broken」并把 tkinter 整个排除，exe 启动即报 `No module named 'tkinter'`。构建后确认 TOC 里有 tkinter、构建日志出现 `pyi_rth__tkinter.py`。

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

# 验 ffmpeg 够不够用（rawvideo 必须有；libx265 决定 -TenBit 能否用）
ffmpeg -hide_banner -demuxers  | Select-String rawvideo
ffmpeg -hide_banner -encoders | Select-String libx265

# 验收放大产物：编码应为 h264（mpeg4 = 踩了精简 ffmpeg）、帧数与源一致、有 aac 音轨
ffprobe -v error -show_entries stream=codec_name,width,height,nb_frames -of default=noprint_wrappers=1 "输出.mp4"

# 方案四：跑测试 / 打包（打包前清 TCL_LIBRARY、TK_LIBRARY，见关键坑）
cd .\04-VisualEnhancer
python -m unittest discover -s tests -v
Remove-Item Env:TCL_LIBRARY, Env:TK_LIBRARY -ErrorAction SilentlyContinue
python -m PyInstaller --clean --noconfirm VEHelper.spec
```

## 详细规则（按需 @引用）

- 完整部署手册与修订记录：@docs/使用指南.md
- 架构说明与关键问题记录：@DEVELOPMENT.md
- 版本变更：@CHANGELOG.md

## 启动器（launcher/）

（以下接自 launcher/AGENTS 基线，起点 v1.4.0）
