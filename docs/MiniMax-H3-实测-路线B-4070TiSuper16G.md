# 实测记录 · 路线 B · RTX 4070 Ti SUPER 16G

> 2026-09-30 实测。单机单次跑通，数字是**这台机器、这套配置**的实测值，不是普适结论。
> 社区口径会失效，用前先核当前仓库版本。

---

## 一、实测环境

| 项 | 值 |
|---|---|
| GPU | RTX 4070 Ti SUPER 16G（驱动 616.92） |
| 系统内存 | 64 GB（63.76 GiB） |
| CPU | i7-14700F |
| 系统 | Windows |
| ComfyUI | **0.37.0**（`comfy-kitchen 0.2.35` 已装 ⇒ int8 快速路径**未被静默关闭**） |
| PyTorch | **2.14.0+cu130**（CUDA 13 主版本 ✅） |
| Python | 3.12.13 |
| 权重 | 路线 B 四件套：剪枝 INT8 扩散模型（19.53 GiB）+ NVFP4 AWQ 文本编码器（14.61 GiB）+ 视频 VAE fp16（4.85 GiB）+ 音频 VAE fp32（0.56 GiB） |
| 启动参数 | `--disable-pinned-memory --disable-async-offload --reserve-vram 1` |

## 二、实测配置与结果

**任务**：纯文生视频（t2va），`864×480 / 124 帧（≈5 秒）/ 20 步`，固定种子。

| 指标 | 实测值 |
|---|---|
| **单条总耗时** | **3 分 13 秒**（193.3 s，ComfyUI 自计时；含文本编码 + 20 步采样 + 双 VAE 解码） |
| 其中采样 | 20 步 × ~7.6 s/it ≈ **2 分 31 秒**（首步 13.4 s 含模型初始化） |
| **显存峰值** | **15.2 / 16 GiB** —— 非常紧，几乎没有余量 |
| **系统内存峰值** | **22.7 GiB** |
| 产物 | `h264 / 864×480 / 124 帧 / 24fps` + **`aac 32 kHz 双声道`**，时长 5.167 s（= 124/24，精确吻合） |

## 三、与社区口径的对照（这是本文档最有价值的部分）

| 社区说法 | 本机实测 | 结论 |
|---|---|---|
| 16G 卡「2–7 分钟/条」 | **3 分 13 秒** | ✅ 落在区间内，且偏快 |
| 「编码器加载后约 24 GiB、transformer 后约 45.6 GiB 会**同时驻留系统内存**」（32 GB 内存会出事） | **峰值只用 22.7 GiB** | ⚠️ **该口径在 ComfyUI 0.37 上已不成立**：新版对权重做 dynamic VRAM loading / 分段暂存，不再整份常驻；再加上 `--disable-pinned-memory`。⇒ **「32 GB 内存是下限」的判断偏保守了，值得重测** |
| NVFP4 在 30/40 系（Ada）上只能走模拟路径 | 启动日志明示 `Native ops: ... int8_tensorwise, emulated ops: nvfp4, mxfp8` | ✅ 得到实证：NVFP4 确实是 **emulated** |
| 缺 cu130 / `comfy_kitchen` 导入失败会**静默**降速 3 倍 | 两者均正常（cu130 + comfy-kitchen 0.2.35），7.6 s/it | ✅ 无静默降级 |

## 四、无头（Headless）运行要点 —— 模板不能直接用

官方模板用的是**新版 Subgraph 格式**（一个节点里包着一整个子图），而 ComfyUI 的
`/prompt` 接口**只吃 API 格式**（扁平的 `node_id → {class_type, inputs}`）。要走 HTTP API
无头跑，必须把模板 `definitions.subgraphs[0]` 手工展开。

展开 t2va 得到的最小链路（14 节点）：

```
UNETLoader ─┬─ BasicScheduler(simple, 20步) ─┐
            ├─ BasicGuider ──────────────────┼─ SamplerCustomAdvanced ─┬─ VAEDecode ────┐
CLIPLoader(type=minimax) ─ MiniMaxH3ImageToVideo ─(conditioning + AV latent) │                ├─ CreateVideo(fps=24) ─ SaveVideo
RandomNoise(seed) / KSamplerSelect(res_multistep) ───────────────────────────┘─ VAEDecodeAudio ┘
```

**逐条实测确认的关键点**：

1. `MiniMaxH3ImageToVideo` **不接 `first_frame` / `last_frame` 就是纯文生视频**。
   prompt 在节点内部走 clip 编码，**不需要**单独的 `CLIPTextEncode`；该节点同时输出
   `positive`（conditioning）和 `LATENT`，后者直接接 `SamplerCustomAdvanced.latent_image`。
2. `SamplerCustomAdvanced` 的 **slot 0 同时**喂 `VAEDecode` 和 `VAEDecodeAudio` ——
   H3 的音视频是一个 NestedTensor 打包 latent，两个解码节点各自取自己的流。
3. 模板里的 turbo LoRA 分支默认是**关**的（`ComfySwitchNode switch=False` → 直通 UNETLoader），
   所以不装 LoRA 就用非 turbo 的 20 步。
4. `MiniMaxH3SigmaShift` 在模板里**没有出现** —— shift 由模型默认的 `model_sampling` 自带，不用接。
5. `length` 会被吸附到 **17k+5 帧网格**（124 ✅，因为 124 % 17 == 5；48 会被改成 56）。
6. ⚠️ **模板默认的视频 VAE 是 `minimax_h3_video_vae_int8_convrot.safetensors`**；
   Comfy-Org 同仓也发 **fp16** 版。两者可以互换（本机只有 fp16，直接替换，跑通无异常）。
7. 显存峰值 15.2/16 GiB ⇒ **16G 卡跑这个配置已贴近上限**，别同时开别的吃显存的程序。

## 五、复现要点

- 启动 ComfyUI：`python main.py --disable-pinned-memory --disable-async-offload --reserve-vram 1`
- 提交：`POST /prompt`，body 为 `{"prompt": <API格式工作流>, "client_id": "<任意>"}`，拿回 `prompt_id`
- 轮询：`GET /history/{prompt_id}`，出现该键即结束；`status.status_str == "success"` 判定成败
- 产物路径在 `history.outputs.<SaveVideo节点id>.images[0]` 的 `filename` + `subfolder`
- 验收：用 ffprobe 确认 `codec_name=h264`、帧数与 `length` 一致、**有 `aac` 音轨**（没音轨 = 音频 VAE 那条支路没接对）

---

*本文档为单机实测记录；数据受 ComfyUI / PyTorch 版本影响，升级后建议重测。*
