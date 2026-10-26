# 部署清单 · 缺失检测数据源（纯数据模块，零逻辑，风格对齐 桥接资源.py）
#
# 每项字段：
#   key     唯一键（UI / 回调用）
#   name    中文展示名
#   root    判定文件相对的根：配置键名（"comfy_dir" / "ffmpeg_dir"）或绝对路径
#   check   判定文件列表（相对 root；全部存在才算就绪）
#   expect  期望字节数（None = 目录型/不单文件校验；非 None 时本地 < 期望即判"不完整"）
#   script  一键安装脚本（相对 deploy_root；"" = 暂无脚本，安装按钮置灰）
#   desc    一句话描述
#
# 数据实测于 2026-10-26，与 docs/交接-缺失下载部署.md §4 一致。
# w_seedvr2_fp8 / w_seedvr2_vae 两项目标大小由 hf-mirror API 于 2026-10-26 复核补全
# （seedvr2_ema_3b_fp8_e4m3fn.safetensors = 3.16 GB；ema_vae_fp16.safetensors = 0.47 GB）。
# FlashVSR-v1.1 全仓 8 文件合计 6.47 GB（handover 原写 ≈6.95 GB，已据镜像复核修正）。
#
# 注意：权重落点以各安装脚本为准（SeedVR2 装到 models\SEEDVR2，H3 走 ComfyUI 原生目录）。

DEPLOY_ITEMS = (
    # ---------- ComfyUI 底座 ----------
    dict(key="comfy_base", name="ComfyUI 底座", root="comfy_dir",
         check=("main.py",), expect=None,
         script="00-ComfyUI底座/安装ComfyUI.ps1",
         desc="ComfyUI 主程序（{comfy_dir}）"),
    dict(key="comfy_py", name="ComfyUI Python", root="comfy_dir",
         check=(".venv/Scripts/python.exe",), expect=None,
         script="00-ComfyUI底座/安装ComfyUI.ps1",
         desc="ComfyUI 虚拟环境 Python（{comfy_dir}）"),
    dict(key="node_manager", name="ComfyUI-Manager", root="comfy_dir",
         check=("custom_nodes/ComfyUI-Manager",), expect=None,
         script="00-ComfyUI底座/安装ComfyUI.ps1",
         desc="节点管理器（ltdrdata/ComfyUI-Manager）"),
    dict(key="node_vhs", name="VideoHelperSuite", root="comfy_dir",
         check=("custom_nodes/ComfyUI-VideoHelperSuite",), expect=None,
         script="02-FlashVSR/安装FlashVSR.ps1",
         desc="视频读写节点（Kosinkadink）"),
    dict(key="node_flashvsr", name="FlashVSR 节点", root="comfy_dir",
         check=("custom_nodes/ComfyUI-FlashVSR_Ultra_Fast",), expect=None,
         script="02-FlashVSR/安装FlashVSR.ps1",
         desc="方案二引擎节点（lihaoyun6）"),
    dict(key="node_seedvr2", name="SeedVR2 节点", root="comfy_dir",
         check=("custom_nodes/seedvr2_videoupscaler",), expect=None,
         script="03-SeedVR2/安装SeedVR2.ps1",
         desc="方案三引擎节点（numz，v2.5.24）"),

    # ---------- 方案一：Video2X（独立目录） ----------
    dict(key="video2x", name="Video2X", root=r"C:\AI\Video2X",
         check=("video2x.exe",), expect=None,
         script="01-Video2X/安装Video2X.ps1",
         desc="方案一引擎（k4yt3x/video2x 6.4.0，C++/Vulkan，不依赖 Python/CUDA）"),

    # ---------- 方案二：FlashVSR 权重 ----------
    dict(key="w_flashvsr", name="FlashVSR v1.1 权重", root="comfy_dir",
         check=("models/FlashVSR-v1.1",), expect=None,  # 目录型；全仓 8 文件 ≈ 6.47 GB
         script="02-FlashVSR/安装FlashVSR.ps1",
         desc="JunhaoZhuang/FlashVSR-v1.1（约 6.47 GB）"),

    # ---------- 方案三：SeedVR2 权重（大小已复核） ----------
    dict(key="w_seedvr2_fp8", name="SeedVR2 3B FP8 权重", root="comfy_dir",
         check=("models/SEEDVR2/seedvr2_ema_3b_fp8_e4m3fn.safetensors",),
         expect=3391544696,  # 3.16 GB（hf-mirror 2026-10-26 复核）
         script="03-SeedVR2/安装SeedVR2.ps1",
         desc="numz/SeedVR2_comfyUI · 3.16 GB"),
    dict(key="w_seedvr2_vae", name="SeedVR2 VAE", root="comfy_dir",
         check=("models/SEEDVR2/ema_vae_fp16.safetensors",),
         expect=501324814,  # 0.47 GB（hf-mirror 2026-10-26 复核）
         script="03-SeedVR2/安装SeedVR2.ps1",
         desc="numz/SeedVR2_comfyUI · 0.47 GB"),

    # ---------- 方案一扩展：ffmpeg（P2 才有安装脚本） ----------
    dict(key="ffmpeg", name="ffmpeg", root="ffmpeg_dir",
         check=("ffmpeg.exe",), expect=None,
         script="",  # P2 才补安装脚本；现走 PATH / 候选路径解析
         desc="视频封装/转码（{ffmpeg_dir}）"),

    # ---------- 方案四：MiniMax H3（P1 hf_pull 目标；大小已核对，暂不判定） ----------
    dict(key="w_h3_dit", name="H3 扩散模型", root="comfy_dir",
         check=("models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",),
         expect=None, script="", desc="Comfy-Org/MiniMax-H3 · 20.97 GB（P1）"),
    dict(key="w_h3_te", name="H3 文本编码器", root="comfy_dir",
         check=("models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",),
         expect=None, script="", desc="Comfy-Org/MiniMax-H3 · 15.69 GB（P1）"),
    dict(key="w_h3_vae", name="H3 双 VAE", root="comfy_dir",
         check=("models/vae/minimax_h3_video_vae_int8_convrot.safetensors",
                "models/vae/minimax_h3_audio_vae_fp32.safetensors"),
         expect=None, script="", desc="Comfy-Org/MiniMax-H3 · 2.81 + 0.61 GB（P1）"),
    dict(key="w_h3_lora", name="H3 turbo LoRA", root="comfy_dir",
         check=("models/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",),
         expect=None, script="", desc="lightx2v/Minimax-h3-Turbo · 1.96 GB（P1）"),
)

# 供 UI 快速判断"是否可一键安装"
def has_installer(key):
    for it in DEPLOY_ITEMS:
        if it["key"] == key:
            return bool(it["script"])
    return False
