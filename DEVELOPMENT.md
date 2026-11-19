# DEVELOPMENT.md · 项目概览与索引

结构固定三块：**项目概览 → 架构说明（[子页](docs/架构.md)）→ 关键问题与方案（索引表 + 一坑一篇）**。
关键问题一坑一篇，格式与 knowledge-base 完全一致，项目收尾时可直接提炼过去。

---

## 一、项目概览

**目标**：给三张不同显存的 N 卡（12G / 16G / 24G）提供"照做就能跑"的本地视频放大部署方案，覆盖从装环境到批量出片的完整链路。

**设计取舍**：

| 取舍 | 选择 | 理由 |
|---|---|---|
| 交付形态 | 纯 PowerShell 脚本，不做安装器 | 用户双击或粘贴一行命令即可；出问题能直接看脚本，不用反编译 |
| 依赖管理 | 复用 ComfyUI 自带的 `.venv` | 方案二、三都要 ComfyUI，没必要各建一套 Python 环境 |
| 方案一不装 Python | Video2X 用官方便携包 | C++/Vulkan 实现，12G 卡也能跑，且是最快的草稿路线 |
| 参数校验位置 | 全部放脚本最前面 | 批量跑到一半才失败，浪费的是几十分钟而不是几秒 |
| 档位命名 | 按显存 `12g / 16g / 24g` | 用户记的是自己的显卡，不是模型精度组合 |

---

## 二、架构说明
组件职责、`common.ps1` 提供的能力、两条批量通道（脚本 CLI / ComfyUI API）、关键设计决策、
方案四 VEHelper 的分工与线程模型，以及 4070S 12GB 的性能基准，全部在 [docs/架构.md](docs/架构.md)。

## 三、关键问题与方案

一坑一篇，全文在 [`docs/问题记录/`](docs/问题记录/)，索引页见 [docs/问题记录/index.md](docs/问题记录/index.md)；
本表只留标题与 TL;DR，方便扫。

| 问题 | TL;DR | 全文 |
|---|---|---|
| [PowerShell 5.1 把中文脚本读成乱码](docs/问题记录/PowerShell-5.1-把中文脚本读成乱码.md) | `.ps1` 存成 UTF-8 **without** BOM，PowerShell 5.1 按 ANSI 解码，中文变乱码并直接解析失败。 |
| [安装脚本与批量脚本的档位名对不上](docs/问题记录/安装脚本与批量脚本档位名对不上.md) | 安装用 `-Profile 3b-fp8`、批量用 `-Profile 12g`，按手册装完就跑不起来。 |
| [SeedVR2 的 7B FP8 权重下不到](docs/问题记录/SeedVR2-7B-FP8-权重下不到.md) | `seedvr2_ema_7b_fp8_e4m3fn.safetensors` 不在节点注册表里；注册表内的 7B FP8 是 `_mixed_block35_fp16` 变体，且只在 `AInVFX` 仓库。 |
| [上游 README 写了 CLI 参数，代码里却没有](docs/问题记录/上游README写了CLI参数代码里却没有.md) | `--allow_vram_overflow` 出现在 SeedVR2 仓库 README 的「Performance Optimization」一节，但 v2.5.24 的 `inference_cli.py` 没实现它，传了直接报错退出。 |
| [给 NVENC 编码器传 crf 被静默忽略](docs/问题记录/NVENC编码器传crf被静默忽略.md) | VideoHelperSuite 的 `nvenc_*` 格式定义里没有 `crf`，用的是 `bitrate` + `megabit`。 |
| [Video2X 的模型名与缩放倍数不是任意组合](docs/问题记录/Video2X模型名与缩放倍数不是任意组合.md) | 合法模型只有 3+3+14 个；且 `models-pro` 没有 4 倍、`models-nose` 只有 2 倍、`realesrgan-plus` 只有 4 倍。 |
| [Video2X 列设备用了旧版参数名](docs/问题记录/Video2X列设备用了旧版参数名.md) | 6.4.0 用 `--list-devices` / `-l` 列设备、`--device` / `-d` 选设备；`--list-gpus` 是旧版写法。 |
| [FlashVSR 缺少 posi_prompt.pth 导致节点导入失败](docs/问题记录/FlashVSR缺posi_prompt导致节点导入失败.md) | 这个文件不在 HuggingFace 权重里，而是随节点仓库提交，由 `nodes.py` 从节点目录自身加载。 |
| [用 import_module 做节点冒烟测试永远失败](docs/问题记录/用import_module做节点冒烟测试永远失败.md) | `custom_nodes` 下的目录名带连字符且不是 Python 包，`importlib.import_module("custom_nodes.ComfyUI-FlashVSR_Ultra_Fast")` 必然失败，会误导成"安装失败"。 |
| [靠文件名集合判断批量产物会误判](docs/问题记录/靠文件名集合判断批量产物会误判.md) | 同名文件被覆盖时，新旧文件名集合完全一样，脚本会误判成"没有生成输出"。 |
| [体积口径混用 GiB 与 GB](docs/问题记录/体积口径混用GiB与GB.md) | 同一份手册里两套口径（1 GiB = 2³⁰ vs 1 GB = 10⁹）却都标成"HuggingFace 实际文件大小"，同一文件出现两个数。 |
| [同一事实在三个文件里写了三个版本](docs/问题记录/同一事实在三个文件里写了三个版本.md) | `检查环境.ps1` 给 16G 卡的方案三建议是"3B FP8 无 BlockSwap"，而手册和批量脚本的 `-Profile 16g` 是"3B FP16 + BlockSwap 16"。 |
| [SeedVR2 的 ffmpeg 编码后端崩在精简构建上](docs/问题记录/SeedVR2的ffmpeg编码后端崩在精简构建上.md) | `inference_cli.py` 里写死了裸命令 `ffmpeg`（`shutil.which` 校验 + `subprocess.Popen(['ffmpeg', ...])` 编码），**只认 PATH**。PATH 上第一个往往是精简构建（`--disable-everything`，无 rawvideo、无 libx265），一跑就 `Unknown input format: 'rawvideo'` 崩溃；若换 opencv 后端则写成 MPEG-4 Part 2。 |
| [SeedVR2 输出没有音轨](docs/问题记录/SeedVR2输出没有音轨.md) | SeedVR2 的 CLI **完全不处理音频**，`add_argument` 全表里没有任何音频项，输出天然只有视频流。手册一度写成"CLI 会自动保留"，是错的。 |
| [只看"跑完了"会漏掉静默降级](docs/问题记录/只看跑完了会漏掉静默降级.md) | SeedVR2 的 ffmpeg 后端不可用时会**静默退回 opencv**，输出是 MPEG-4 Part 2（`codec_name=mpeg4`），体积比 H.264 大得多，但脚本退出码是 0、日志也报"completed successfully"。 |
| [VAE 编码极慢（单 batch 约 8 分钟）](docs/问题记录/VAE编码极慢-单batch约8分钟.md) | VAE 被 `offload_device=cpu` 丢到 CPU 上算，12GB 卡叠加 1024×1024 分块后灾难性降速。（源自 `seedvr2-local-deploy`，2026-11-19 并入） |
| [大 batch_size 反而更慢 / 爆显存](docs/问题记录/大batch_size反而更慢或爆显存.md) | SeedVR2 的消耗主力是 **VAE 解码分块**，不是模型大小或分辨率；小 batch 才高效。（源自 `seedvr2-local-deploy`） |
| [`resolution` 参数填 `"fixed"` 不生效](docs/问题记录/resolution填fixed不生效.md) | 该字段要整数；填字符串会走默认值、控件显示异常。（源自 `seedvr2-local-deploy`） |
| [每次跑都像第一次一样慢](docs/问题记录/每次跑都像第一次一样慢.md) | `cache_model=false` 时每次任务结束就卸载模型，下一次重新加载 + 冷启动。（源自 `seedvr2-local-deploy`） |
| [git / curl 不走系统代理，GitHub 直连被重置](docs/问题记录/git和curl不走系统代理.md) | 本机代理是 `127.0.0.1:7890`，但 `git`/`curl` 默认不读系统代理，git 协议连 GitHub 偶尔直接失败。（源自 `seedvr2-local-deploy`） |

---

## 四、后续可做

- 给三套批量脚本补自动化回归测试（至少覆盖参数校验分支）
- 按可用显存动态调整参数，替代当前的固定档位表