# DEVELOPMENT.md · 架构与问题记录

结构固定三块：**项目概览 → 架构说明 → 关键问题与方案**。
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

### 目录与职责

```
common.ps1              # 唯一的配置源 + 工具函数库（不含业务逻辑）
检查环境.ps1             # 只读体检，不产生任何副作用
00-ComfyUI底座/          # 方案二、三共用的运行环境
01-Video2X/ 02-FlashVSR/ 03-SeedVR2/
                        # 每个方案固定两个脚本：安装X.ps1 / 批量放大.ps1
```

分层规则：**`common.ps1` 只放"配置 + 通用能力"，各方案目录只放"这个方案特有的事"**。
新增方案时不需要动 `common.ps1`，除非要加新的通用能力。

### common.ps1 提供的能力

| 函数 | 作用 |
|---|---|
| `New-ProjectDirs` / `Get-VideoFiles` | 目录初始化、按扩展名收集待处理视频 |
| `Show-Gpu` / `Test-Cmd` / `Get-BasePython` | 环境探测（显卡、外部命令、Python 解释器） |
| `Assert-ComfyReady` | 前置断言：底座没装就报错并给出补救命令 |
| `Install-ComfyNode` | 克隆自定义节点 + 装其 `requirements.txt`（已存在则只补依赖） |
| `Invoke-HfDownload` | 走镜像的 `snapshot_download`，支持断点续传与文件通配 |
| `Assert-ModelFiles` | 校验关键权重文件是否齐全，缺哪个列哪个 |
| `Test-ComfyApi` / `Wait-ComfyApi` / `Invoke-ComfyPrompt` | 方案二的批量通道：把 API 格式工作流提交给 ComfyUI 并等结果 |

### 两条批量通道

三套方案里，方案一和方案三走命令行，方案二只能走 HTTP API —— 这是由各自项目形态决定的：

```
方案一 Video2X   批量放大.ps1 → video2x.exe（循环调用，逐文件）
方案二 FlashVSR  批量放大.ps1 → HTTP POST /prompt → 轮询 /history/{id}
方案三 SeedVR2   批量放大.ps1 → inference_cli.py（节点自带，天生为批量设计）
```

方案二之所以走 API：FlashVSR 是 ComfyUI 节点，没有独立 CLI；API 格式工作流
（`{"节点ID": {"class_type": ..., "inputs": {...}}}`）比在网页上点按钮更适合循环几百个视频。

### 关键设计决策

1. **路径集中**：`common.ps1` 顶部两个变量派生全部路径，用户只改这两处
2. **档位映射集中**：`批量放大.ps1` 里用 `switch ($Profile)` 一张表决定模型精度、批大小、BlockSwap 层数
3. **模型下载按仓库分组**：`$want` 哈希表以仓库名为键，避免把 AInVFX 的文件名拿到 numz 去下
4. **产物识别按时间戳**：不比对文件名集合，避免同名覆盖时误判"没找到输出"
5. **镜像可切**：`HF_ENDPOINT` 环境变量优先，默认 `hf-mirror.com`

---

## 三、关键问题与方案

### 问题：PowerShell 5.1 把中文脚本读成乱码

**TL;DR**：`.ps1` 存成 UTF-8 **without** BOM，PowerShell 5.1 按 ANSI 解码，中文变乱码并直接解析失败。

- 问题：含中文注释/字符串的脚本执行时报语法错误，报错位置和实际错误位置对不上
- 根因：PowerShell 5.1 判断文件编码时不看内容只看 BOM；无 BOM 就退回系统 ANSI 代码页
- 解决：把文件另存为 **UTF-8 with BOM**（写入时先写 `EF BB BF` 三字节）
- 预防：改完 `.ps1` 跑一次 BOM 检查（命令见 [AGENTS.md](AGENTS.md)「常用命令」）

### 问题：安装脚本与批量脚本的档位名对不上

**TL;DR**：安装用 `-Profile 3b-fp8`、批量用 `-Profile 12g`，按手册装完就跑不起来。

- 问题：两套命名各自演进，用户按安装脚本的档位名去跑批量脚本，参数校验直接拒绝
- 根因：档位是"按显卡"还是"按模型精度"命名，早期没定死
- 解决：统一为按显存命名 `12g / 16g / 24g`（批量脚本额外有 `custom` 供手动指定模型）
- 预防：改档位名时同步四处——两个 SeedVR2 脚本、`检查环境.ps1`、`docs/使用指南.md`

### 问题：SeedVR2 的 7B FP8 权重下不到

**TL;DR**：`seedvr2_ema_7b_fp8_e4m3fn.safetensors` 不在节点注册表里；注册表内的 7B FP8 是 `_mixed_block35_fp16` 变体，且只在 `AInVFX` 仓库。

- 问题：按直觉写的文件名，在 ComfyUI 的 `--dit_model` 下拉框里根本选不到
- 根因：`--dit_model` 的候选项 = 节点 `src/utils/model_registry.py` 的 `MODEL_REGISTRY` ∪ 磁盘已有文件。名字必须与注册表一致，且不同变体散落在两个 HF 仓库
- 解决：脚本改按注册表内的 `seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors` 下载，并把它归到 `AInVFX/SeedVR2_comfyUI`
- 预防：**改权重文件名前先读 `model_registry.py`**，不要凭文件名推断

### 问题：上游 README 写了 CLI 参数，代码里却没有

**TL;DR**：`--allow_vram_overflow` 出现在 SeedVR2 仓库 README 的「Performance Optimization」一节，但 v2.5.24 的 `inference_cli.py` 没实现它，传了直接报错退出。

- 问题：照 README 给批量脚本加了 `--allow_vram_overflow`，SeedVR2 启动即以 `unrecognized arguments` 退出
- 根因：上游文档比代码超前。入口用的是 `parser.parse_args()` 且 `allow_abbrev=False`，未知参数不会静默忽略
- 解决：从批量脚本移除该参数
- 预防：**以代码为准，不以文档为准**。改 SeedVR2 参数前先跑 `inference_cli.py --help`（命令见 [AGENTS.md](AGENTS.md)）

### 问题：给 NVENC 编码器传 crf 被静默忽略

**TL;DR**：VideoHelperSuite 的 `nvenc_*` 格式定义里没有 `crf`，用的是 `bitrate` + `megabit`。

- 问题：用显卡编码器出片时设了 `crf`，输出体积和画质完全不受控，也不报错
- 根因：不同编码格式的输入项不同——`h264/h265-mp4` 用 `crf`，`nvenc_*` 用 `bitrate`（配合 `megabit` 布尔位表示 Mbps）
- 解决：批量脚本按格式分派——`-Format` 含 `nvenc` 时填 `bitrate` + `megabit`，否则填 `crf`
- 预防：新增编码格式前先看 `video_formats/<格式>.json` 里的字段定义

### 问题：Video2X 的模型名与缩放倍数不是任意组合

**TL;DR**：合法模型只有 3+3+14 个；且 `models-pro` 没有 4 倍、`models-nose` 只有 2 倍、`realesrgan-plus` 只有 4 倍。

- 问题：示例里用了 `realesr-generalv3` 这个不存在的模型；也默认了"任何模型都能 2/3/4 倍"
- 根因：模型白名单在源码 `validators.cpp` 里，倍数支持范围取决于模型目录里实际有哪些权重文件
- 解决：批量脚本内置三张白名单，并按模型校验 `-Scale` 是否合法，非法值在最前面就报错
- 预防：加新模型前先查 `validators.cpp` 与上游模型目录树，别照文档站（部分页面是旧版写法）

### 问题：Video2X 列设备用了旧版参数名

**TL;DR**：6.4.0 用 `--list-devices` / `-l` 列设备、`--device` / `-d` 选设备；`--list-gpus` 是旧版写法。

- 问题：安装脚本用 `--list-gpus` 做自检兜底，在 6.4.0 上报未知参数
- 根因：文档站部分页面停留在旧版命令行
- 解决：改用 `--list-devices`，并把该事实写进脚本注释
- 预防：**命令行参数以 tag 对应的 `argparse.cpp` 为准**

### 问题：FlashVSR 缺少 posi_prompt.pth 导致节点导入失败

**TL;DR**：这个文件不在 HuggingFace 权重里，而是随节点仓库提交，由 `nodes.py` 从节点目录自身加载。

- 问题：只下了 HF 权重，节点导入时报找不到 `posi_prompt.pth`
- 根因：权重与"节点自带的提示文件"分属两个来源；用不完整的 zip 包安装会漏掉它
- 解决：安装脚本显式校验该文件存在，缺失时报错并提示重新完整 clone 节点仓库
- 预防：装节点后先确认节点目录里该有的文件都在，再下权重

### 问题：用 import_module 做节点冒烟测试永远失败

**TL;DR**：`custom_nodes` 下的目录名带连字符且不是 Python 包，`importlib.import_module("custom_nodes.ComfyUI-FlashVSR_Ultra_Fast")` 必然失败，会误导成"安装失败"。

- 问题：安装脚本的冒烟测试报导入错误，但节点其实是好的
- 根因：测试方法本身不成立——目录名不是合法标识符
- 解决：改用 ComfyUI 自带的 `main.py --quick-test-for-ci`，它会真实加载全部自定义节点后退出
- 预防：验证"节点能否被 ComfyUI 加载"要用 ComfyUI 自己的加载器，不要绕过去手工 import

### 问题：靠文件名集合判断批量产物会误判

**TL;DR**：同名文件被覆盖时，新旧文件名集合完全一样，脚本会误判成"没有生成输出"。

- 问题：重跑同一批素材，脚本报"没找到输出文件"，但产物其实已经生成
- 根因：产物识别用的是"输出目录文件名集合的差集"，覆盖场景下差集为空
- 解决：改为按"文件修改时间晚于本次启动时刻"识别
- 预防：识别产物优先用时间戳或显式输出路径，不要用集合差集

### 问题：体积口径混用 GiB 与 GB

**TL;DR**：同一份手册里两套口径（1 GiB = 2³⁰ vs 1 GB = 10⁹）却都标成"HuggingFace 实际文件大小"，同一文件出现两个数。

- 问题：用户按手册核对自己磁盘上的文件大小，对不上，怀疑下载不完整
- 根因：HuggingFace 页面按 1 GB = 10⁹ 显示，Windows 资源管理器按 1 GiB = 2³⁰ 显示，两者相差约 7%
- 解决：全部统一为 1 GB = 10⁹ 字节，并在文档里显式注明与 Windows 显示值的差异
- 预防：写体积时标明口径；跨来源数据先统一单位再入表

### 问题：同一事实在三个文件里写了三个版本

**TL;DR**：`检查环境.ps1` 给 16G 卡的方案三建议是"3B FP8 无 BlockSwap"，而手册和批量脚本的 `-Profile 16g` 是"3B FP16 + BlockSwap 16"。

- 问题：用户先跑体检脚本拿到建议，再照手册装，两处说的不是一回事
- 根因：建议文案是手写的，没有单一事实源
- 解决：统一为 `-Profile 16g`（3B FP16 + BlockSwap 16）；24G 同步为 `-Profile 24g`
- 预防：**凡是有"档位/默认值"的地方，都从同一张表派生**；改一处必须 grep 全仓库同名概念

---

## 四、后续可做

- 给三套批量脚本补自动化回归测试（至少覆盖参数校验分支）
- FlashVSR / SeedVR2 的图形界面工作流存成 `.json`，网页里直接导入，不用手拖节点
- 按可用显存动态调整参数，替代当前的固定档位表