# 问题记录索引

> 从 `DEVELOPMENT.md` 拆出（规范 2.1.4：`DEVELOPMENT.md` > 200 行）。
> 项目概览见 [../../DEVELOPMENT.md](../../DEVELOPMENT.md)，架构见 [../架构.md](../架构.md)。

| 问题 | TL;DR |
|---|---|
| [PowerShell 5.1 把中文脚本读成乱码](PowerShell-5.1-把中文脚本读成乱码.md) | `.ps1` 无 BOM 时 PS 5.1 按 ANSI 解码，每奇数个连续汉字多出半字节、吞掉紧随其后的字符：吞引号报语法错误，吞换行则静默合并两行。 |
| [安装脚本与批量脚本的档位名对不上](安装脚本与批量脚本档位名对不上.md) | 安装用 `-Profile 3b-fp8`、批量用 `-Profile 12g`，按手册装完就跑不起来。 |
| [SeedVR2 的 7B FP8 权重下不到](SeedVR2-7B-FP8-权重下不到.md) | `seedvr2_ema_7b_fp8_e4m3fn.safetensors` 不在节点注册表里；注册表内的 7B FP8 是 `_mixed_block35_fp16` 变体，且只在 `AInVFX` 仓库。 |
| [上游 README 写了 CLI 参数，代码里却没有](上游README写了CLI参数代码里却没有.md) | `--allow_vram_overflow` 出现在 SeedVR2 仓库 README 的「Performance Optimization」一节，但 v2.5.24 的 `inference_cli.py` 没实现它，传了直接报错退出。 |
| [给 NVENC 编码器传 crf 被静默忽略](NVENC编码器传crf被静默忽略.md) | VideoHelperSuite 的 `nvenc_*` 格式定义里没有 `crf`，用的是 `bitrate` + `megabit`。 |
| [Video2X 的模型名与缩放倍数不是任意组合](Video2X模型名与缩放倍数不是任意组合.md) | 合法模型只有 3+3+14 个；且 `models-pro` 没有 4 倍、`models-nose` 只有 2 倍、`realesrgan-plus` 只有 4 倍。 |
| [Video2X 列设备用了旧版参数名](Video2X列设备用了旧版参数名.md) | 6.4.0 用 `--list-devices` / `-l` 列设备、`--device` / `-d` 选设备；`--list-gpus` 是旧版写法。 |
| [FlashVSR 缺少 posi_prompt.pth 导致节点导入失败](FlashVSR缺posi_prompt导致节点导入失败.md) | 这个文件不在 HuggingFace 权重里，而是随节点仓库提交，由 `nodes.py` 从节点目录自身加载。 |
| [用 import_module 做节点冒烟测试永远失败](用import_module做节点冒烟测试永远失败.md) | `custom_nodes` 下的目录名带连字符且不是 Python 包，`importlib.import_module("custom_nodes.ComfyUI-FlashVSR_Ultra_Fast")` 必然失败，会误导成"安装失败"。 |
| [靠文件名集合判断批量产物会误判](靠文件名集合判断批量产物会误判.md) | 同名文件被覆盖时，新旧文件名集合完全一样，脚本会误判成"没有生成输出"。 |
| [体积口径混用 GiB 与 GB](体积口径混用GiB与GB.md) | 同一份手册里两套口径（1 GiB = 2³⁰ vs 1 GB = 10⁹）却都标成"HuggingFace 实际文件大小"，同一文件出现两个数。 |
| [同一事实在三个文件里写了三个版本](同一事实在三个文件里写了三个版本.md) | `检查环境.ps1` 给 16G 卡的方案三建议是"3B FP8 无 BlockSwap"，而手册和批量脚本的 `-Profile 16g` 是"3B FP16 + BlockSwap 16"。 |
| [SeedVR2 的 ffmpeg 编码后端崩在精简构建上](SeedVR2的ffmpeg编码后端崩在精简构建上.md) | `inference_cli.py` 里写死了裸命令 `ffmpeg`（`shutil.which` 校验 + `subprocess.Popen(['ffmpeg', ...])` 编码），**只认 PATH**。PATH 上第一个往往是精简构建（`--disable-everything`，无 rawvideo、无 libx265），一跑就 `Unknown input format: 'rawvideo'` 崩溃；若换 opencv 后端则写成 MPEG-4 Part 2。 |
| [SeedVR2 输出没有音轨](SeedVR2输出没有音轨.md) | SeedVR2 的 CLI **完全不处理音频**，`add_argument` 全表里没有任何音频项，输出天然只有视频流。手册一度写成"CLI 会自动保留"，是错的。 |
| [只看"跑完了"会漏掉静默降级](只看跑完了会漏掉静默降级.md) | SeedVR2 的 ffmpeg 后端不可用时会**静默退回 opencv**，输出是 MPEG-4 Part 2（`codec_name=mpeg4`），体积比 H.264 大得多，但脚本退出码是 0、日志也报"completed successfully"。 |
| [VAE 编码极慢（单 batch 约 8 分钟）](VAE编码极慢-单batch约8分钟.md) | VAE 被 `offload_device=cpu` 丢到 CPU 上算，12GB 卡叠加 1024×1024 分块后灾难性降速。（源自 `seedvr2-local-deploy`，2026-11-19 并入） |
| [大 batch_size 反而更慢 / 爆显存](大batch_size反而更慢或爆显存.md) | SeedVR2 的消耗主力是 **VAE 解码分块**，不是模型大小或分辨率；小 batch 才高效。（源自 `seedvr2-local-deploy`） |
| [`resolution` 参数填 `"fixed"` 不生效](resolution填fixed不生效.md) | 该字段要整数；填字符串会走默认值、控件显示异常。（源自 `seedvr2-local-deploy`） |
| [每次跑都像第一次一样慢](每次跑都像第一次一样慢.md) | `cache_model=false` 时每次任务结束就卸载模型，下一次重新加载 + 冷启动。（源自 `seedvr2-local-deploy`） |
| [git / curl 不走系统代理，GitHub 直连被重置](git和curl不走系统代理.md) | 本机代理是 `127.0.0.1:7890`，但 `git`/`curl` 默认不读系统代理，git 协议连 GitHub 偶尔直接失败。（源自 `seedvr2-local-deploy`） |