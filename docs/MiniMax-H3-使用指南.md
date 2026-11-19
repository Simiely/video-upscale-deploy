# MiniMax H3 本地部署方案（RTX 4070 Super 12G / RTX 4070 Ti Super 16G）

> 整合自：Comfy-Org 文件清单、comfyui-wiki 社区量化汇总、hub.minimax.io/h3 官方 FAQ、smeltcore 4070 SUPER 实测配方、
> jxxy 官方整合仓库导航，以及两个 B 站教程视频（要点与逐字稿见 `MiniMax-H3-参考/`）。
> 所有体积/耗时均为 2026-08~09 的公开口径，社区每周都在动 —— **动手前以仓库 README 的当前数值为准**。

---

## 0. 一页结论

| | RTX 4070 Super 12G | RTX 4070 Ti Super 16G |
|---|---|---|
| 定位 | **能跑，但属于"实验环境"**：每步至少要 8.7 GiB 的 transformer 走 PCIe 流式 | **本地这一档的入门生产位** |
| 首推路线 | **路线 B**：剪枝 INT8 + NVFP4 文本编码器（免额外节点包） | **画质优先 → 路线 B**；**速度优先 → 路线 C** |
| 备选 | 路线 A（GGUF Q4，省显存但要装额外加载器） | 同左 |
| 首次参数 | 864×480（0.4 MP）／124 帧（5 秒）／20 步 | 0.4–0.5 MP；配 Turbo 8 步可摸 768p 短边 |
| 预期耗时 | 6–10 分钟/条（32 GB 内存）；16 GB 内存会掉到 20–29 分钟 | 2–7 分钟/条 |
| 硬门槛 | **32 GB 内存起 + NVMe 45 GB 空闲 + CUDA 13** | 64 GB 内存更顺 |

**三件必须先接受的事：**
1. **本地永远只有 768p**（短边 768，最大 1344×768）。2K 模块 `H3-Regenerate-2K` 没开源，只能走官方 API。
2. **许可排除美/欧/英/韩**，条款还覆盖输出物与衍生模型（国内自用没问题；年营收 ≥2000 万美元的组织需另行授权）。
3. **瓶颈常在主机不在显卡**：内存不足时权重每步都从硬盘重新读，12G 卡会从 6 分钟变 25 分钟。

---

## 1. 三条路线怎么选

| | 路线 A｜GGUF Q4 | 路线 B｜剪枝 INT8 + NVFP4 编码器 | 路线 C｜INT4 / mixed INT4-INT8 |
|---|---|---|---|
| 扩散模型 | `MiniMax-H3-FL2VA-Q4_K_M.gguf`（剪枝版 10.6 GiB） | `minimax_h3_fl2va_pruned_int8_convrot`（19.53 GiB） | `pruned_int4_convrot`（11.3 GB）或 `mixed_int4_int8`（15.5 GB） |
| 文本编码器 | GGUF Q2_K（7.9 GB） | NVFP4 AWQ（14.61 GiB） | INT4 convrot（15.0 GB） |
| 前置依赖 | **要装较新的 ComfyUI-GGUF**（8 月初原生加载器还不认 H3） | 无，官方模板直接用 | 无 |
| 显存占用 | 最低 | 最高（靠卸载） | 居中 |
| 画质 | 中（Q4 平衡档，Q2/Q3 掉运动连贯性） | **最好** | 明显下降（视频 UP 自己也承认） |
| 取向 | 省显存 / 折腾 | 画质 | 速度 / 少卸载 |
| 选它的情况 | 12G 卡、内存只有 32G、愿意装节点包 | 16G 卡 + 64G 内存；12G 卡 + 32G 内存 + NVMe | 16G 卡想要更少等待 |

**决策树：**
```
要 2K？── 是 ──► 别搞本地，走官方 API（2K 约 $0.14/秒）
        └ 否
内存 < 32 GB？── 是 ──► 先加内存，别开始（12G 卡尤其）
16 GB 显存？── 是 ──► 画质优先：路线 B ＋ Turbo 8 步
                 └ 速度优先/嫌慢：路线 C
12 GB 显存？── 是 ──► 路线 B（内存 ≥32G）或路线 A（内存吃紧）
```

---

## 2. 硬门槛清单（开工前逐项打勾）

| 项 | 要求 | 为什么 |
|---|---|---|
| 系统内存 | **32 GB 起**，64 GB 顺 | 加载阶段文本编码器与 transformer **同时**占系统内存（实测编码器加载后 24 GiB、transformer 加载后 45.6 GiB） |
| 磁盘 | **NVMe 上 45 GB 空闲** | 32 GB 内存时权重缓存不住，**硬盘会进入采样循环** |
| GPU 驱动 | 支持 CUDA 13 的版本 | 见下 |
| Python 环境 | torch **cu130** 版 | cu128 的 PyTorch 会**静默**关掉 int8-convrot 快速路径 —— 不报错，只是慢约 3 倍 |
| ComfyUI | **≥ 0.30.0**（建议 0.30.2 或更新） | H3 节点在核心 `comfy_extras/nodes_minimax_h3.py`，0.30 才有 |
| 许可认知 | 排除美/欧/英/韩 | 别把权重和输出带到这些地区商用 |

---

## 3. 下载清单（照抄即可）

### 路线 B（推荐，两个文件 + 两个 VAE）

```bash
# 在 ComfyUI 根目录执行；路径写 models（不是 ComfyUI/models）
hf download Comfy-Org/MiniMax-H3 \
  diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors \
  text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors \
  vae/minimax_h3_video_vae_fp16.safetensors \
  vae/minimax_h3_audio_vae_fp32.safetensors \
  --local-dir models
```

| 文件 | 体积 | 放哪 |
|---|---|---|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 19.53 GiB | `models/diffusion_models/` |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 14.61 GiB | `models/text_encoders/` |
| `minimax_h3_video_vae_fp16.safetensors` | 4.85 GiB | `models/vae/` |
| `minimax_h3_audio_vae_fp32.safetensors` | 0.56 GiB | `models/vae/` |

三个要点：
- **文本编码器只用 NVFP4 版**（14.61 GiB），不要 int8 版（25.3–27.1 GiB）。它在 Ada（sm_89）上只当**存储格式**用，不请求加速内核，但省 10 GiB 对 12G 卡是决定性的。
- **千万别下 NVFP4 的扩散模型** —— Blackwell 专属，30/40 系上只有模拟，没加速还掉画质。
- **两个 VAE 缺一不可**，缺音频 VAE 的典型症状是"视频正常但没声音"。

### 路线 A（12G 卡内存吃紧时的备选）

- 扩散模型：Abiray/MiniMax-H3-GGUF 或 realrebelai/MiniMax-H3_GGUFs 里的 `FL2VA Q4_K_M`（**按体积挑**：剪枝起点约 10.6 GiB，完整起点约 19.9 GB，两者同名不同物）。
- 文本编码器：同仓库的 `qwen3vl_32b_minimax_h3-Q4_K_M.gguf`（14.6 GB）或 Q2_K（7.9 GB）。
- 额外前置：装较新的 **ComfyUI-GGUF**（提供 `UnetLoaderGGUF`）。若编码器报 `size mismatch [5120] vs [4096]`，说明被识别成 Qwen3-VL-8B，需要把 CLIP Loader 的 Type 设成 `minimax`（H3 专用加载器节点）。
- **命名陷阱**：H3 去噪器隐藏维 2688 不能被 256 整除，标 `Q4_K_M` 的文件内部多半是 Q4_0/Q4_1 —— **按文件体积选，不要按后缀选**。

### 可选组件（想省显存/提质量时）

| 组件 | 收益 |
|---|---|
| fp8mix 视频 VAE（2.60 GiB）+ bf16 音频 VAE（289 MiB） | 比官方 VAE 组合省约 2.5 GiB |
| Ref Patch（148 MiB） | 让 FL2VA 权重部分模拟 Ref2VA，想要参考能力又怕占显存时用 |
| Turbo LoRA / 4 步 Turbo GGUF（配 H3 Turbo Sampler 节点） | 步数 20 → 4/6–8 |

---

## 4. 安装与环境（Windows）

**两条安装路径：**

| 方式 | 适合 | 要点 |
|---|---|---|
| ComfyUI 桌面版 | 想省事 | 自带模板中心，打开 H3 模板会提示缺哪些模型，点「全部下载」即可；**大陆必须开镜像加速**，否则主模型下不动。默认路径 `C:\Users\<用户名>\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models\` |
| 便携版 / venv | 想可控、要装 SageAttention | 手动按上面下载清单拉权重，自己管 torch 版本 |

**环境安装顺序（关键，别搞反）：**
```bash
cd ComfyUI
git fetch --tags && git checkout v0.30.2      # 或更新版本
pip install -r requirements.txt
# 必须最后装 CUDA 13 栈：requirements.txt 里 torch 未固定版本，后装会覆盖并破坏快速路径
pip install --force-reinstall --index-url https://download.pytorch.org/whl/cu130 \
  torch torchvision torchaudio
```

**启动命令：**
```bash
# 32 GB 内存的机器：必加 --disable-pinned-memory
python main.py --disable-pinned-memory

# Windows 且 GPU 同时驱动桌面时（推荐形态）
python main.py --disable-pinned-memory --disable-async-offload --reserve-vram 1

# 装好 SageAttention 之后再加
python main.py --disable-pinned-memory --use-sage-attention
```

**启动日志必须确认三件事：**
1. torch 版本带 `+cu130`；
2. `Native ops:` 行列出 `float8_e4m3fn`，`nvfp4` 在模拟侧（Ada 被正确识别）；
3. **没有** `Enabled pinned memory` 这一行（有就说明标志没生效，加载阶段可能被 OOM kill）。

> 不要一股脑叠加 `--lowvram` / `--cache-none` / `--disable-smart-memory` —— 盲加会更慢，遇到 OOM 再一次加一个。

---

## 5. 首次跑通（最小验证，别一上来做 15 秒参考视频）

1. 启动日志三项检查通过（上一节）。
2. 四个文件放对三个目录，文件名不要改。
3. 用内置模板：`Template Library → Video → MiniMax H3 → T2V`。
4. 参数固定成最小集：**864×480（0.4 MP）／124 帧（5 秒）／20 步／res_multistep + simple**。
5. 提示词写成**一整段"分镜"**（画面 + 动作 + 镜头运动 + 声音一起写，H3 的音画是同一次推理生成的，你不写声音它就自己猜）。
6. 检查成品：有画面、**有立体声**、时长与分辨率正确、改提示词画面确实跟着变。
7. 记录：峰值显存、峰值系统内存、加载耗时、采样耗时、端到端耗时。
8. **第二次只改一个变量**（先动时长，再动分辨率 —— 缩时长比降分辨率更省显存）。

---

## 6. 参数手册

| 参数 | 取值 | 说明 |
|---|---|---|
| 分辨率 | 短边 768 为原生；上限 1344×768（1,032,192 px）；**最小 384p，256p 直接失败** | 必须 32 的倍数 |
| 常用档 | 0.4 MP ≈ 864×480；0.5 MP 起需更多余量 | 工作流里用 Resolution Selector，别手打尺寸 |
| 帧数 | 24 fps，**17k+5 网格**；5 秒 = 124 帧；支持范围 124–362 帧 | 时长靠帧数控制 |
| 步数 | 20 步（原生）；Turbo LoRA：4 步 = 草稿，6–8 步 = 成片 | 4 步容易发虚、音画不同步 |
| 采样器 | `res_multistep` + `simple` | 官方模板默认 |
| CFG | H3 已内置 CFG 蒸馏，按模板默认走 | 花屏/闪烁先查帧数是否超限、CFG 是否过大、尾帧是否与首帧风格冲突 |

---

## 7. 加速（收益通常大于换量化档）

| 组件 | 怎么装 | 效果 |
|---|---|---|
| **Turbo LoRA** | 社区加速 LoRA / 4 步 Turbo GGUF + H3 Turbo Sampler 节点 | 20 步 → 6–8 步；**这是最省时间的一步** |
| **SageAttention** | `pip install sageattention`（PyPI 1.0.6，纯 Triton 可用）；2.x 需源码构建 | 降单步成本。KJNodes 的 H3 节点要求 2.x |
| **KJNodes 低显存节点** | `MiniMax H3 Low VRAM Attention` / `MiniMax H3 Chunk FeedForward` | 降低 self-attention 与前馈层峰值显存，**输出与原模型一致** → 12/16G 卡先试这两个，再考虑降量化 |
| **fp8mix VAE** | 替换官方 VAE | 省约 2.5 GiB |

内存只有 32 GB 时的顺序：**① 关 pinned memory → ② 上 Turbo（先减步数）→ ③ 缩时长 → ④ 降量化档**。

---

## 8. 排错速查

| 现象 | 根因 | 处理 |
|---|---|---|
| 加载时进程被杀 / MemoryError | **系统内存**不足，不是显存 | 确认日志没有 `Enabled pinned memory`；加 `--disable-pinned-memory`；权重放 NVMe。`UNETLoader` 单独报 MemoryError 还要怀疑下载截断（重哈希） |
| 生成异常慢（慢约 3 倍） | 缺 cu130 / `comfy_kitchen` 导入失败 / 权重在机械盘 | 查启动日志；重装 cu130 torch；把权重挪到 NVMe |
| 采样中 `torch.OutOfMemoryError` | 激活值超预算 | 先降时长（124 帧），再降分辨率；参考视频进节点前先缩放 |
| 视频正常但没声音 | 音频 VAE 没加载 | 补 `minimax_h3_audio_vae_fp32` |
| 纯噪点 / 花屏 | VAE 被部分卸载或权重文件损坏 | `--disable-smart-memory --cache-none`；重新核对文件体积/哈希 |
| GGUF 加载报 state_dict mismatch | 编码器被识别成 Qwen3-VL-8B | 用 H3 专用 CLIP Loader，Type = `minimax` |
| 人物远景脸崩 | 模型已知弱点（远景/广角明显，中近景正常） | 换卡没用，改分镜 |
| 采样中途 OOM 但显存看着够 | GGUF/int8 块的显存与主机之间搬运撞车 | 加 `--reserve-vram 1`，别下调 |

---

## 9. 什么时候别搞本地

- **交付物要 2K** → 本地永远只有 768p。要么走官方 API（2K 约 $0.14/秒，国内报道 0.8 元/秒；768p 约 $0.10/秒）。
- **一周出不了几十条** → API 比攒 24G 卡 + 64G 内存便宜。
- **8 GB 显卡** → 能跑，但那是验证环境不是生产环境。
- 判据很简单：**每周重抽上百次，或素材不能出内网** → 本地；否则 → API。

---

## 10. 关于"越狱 / 无审查"路线（边界说明）

社区在流传把官方 Qwen3-VL-32B 文本编码器换成无审查（heretic）版本的做法，改的**只是文本编码器**，
扩散模型、画质、时长上限、显存占用全都不变。相关要点见 `MiniMax-H3-参考/要点与风险-无审查编码器视频.md`。
**我不会为生成违法内容的用途提供配置、提示词或绕审思路**，本方案也不包含这部分。
另外"无版权可自由商用"这个说法只针对生成内容本身的版权主张，**不等于拿到 H3 的开源许可授权**，两件事别混。

---

## 附：仓库内其他文件

| 文件 | 内容 |
|---|---|
| `../README.md` | 门面：结论速览、快速开始、索引 |
| `MiniMax-H3-DEVELOPMENT.md` | 关键问题与方案（一坑一篇，共 7 条） |
| `MiniMax-H3-参考/要点对照-选型视频.md` | 选型视频（AI-PanSir）要点 + 与本文口径的逐条核对 |
| `MiniMax-H3-参考/逐字稿-选型视频-AI-PanSir.md` | 该视频完整口播转写 |
| `MiniMax-H3-参考/要点与风险-无审查编码器视频.md` | 无审查编码器视频的要点、技术真相与风险说明 |
| `MiniMax-H3-参考/逐字稿-无审查编码器视频-零度解说.md` | 该视频完整口播转写 |
