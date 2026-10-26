# 部署清单 · 缺失检测数据源（纯数据模块，零逻辑，风格对齐 桥接资源.py）
#
# 每项字段：
#   key     唯一键（UI / 回调用）
#   group   归属分组键（见文件末尾 GROUPS；决定卡片放哪一格）
#   name    中文展示名
#   root    判定文件相对的根：配置键名（"comfy_dir" / "ffmpeg_dir"）或绝对路径
#   check   判定文件列表（相对 root；全部存在才算就绪）
#   expect  期望字节数（None = 目录型/不单文件校验；整数 = 每个 check 文件都按它校验；
#           元组 = 与 check 一一对应的逐文件期望值）
#   hf      HF 仓库（"org/repo"）；有它才能「下载」单文件（仓库内路径由 check 去掉 models/ 前缀得到）
#   script  一键安装脚本（相对 deploy_root；"" = 暂无脚本）
#   desc    一句话描述
#
# 数据实测于 2026-10-26，与 docs/交接-缺失下载部署.md §4 一致。
# w_seedvr2_fp8 / w_seedvr2_vae 两项目标大小由 hf-mirror API 于 2026-10-26 复核补全。
# H3 四项的 hf / expect 由 hf-mirror tree API 逐文件实测（字节数取 API 原值，不是"整数 GB 估算"）。
#
# ★ 为什么分组（v1.2.26）：这个工具同时挂着四条工作流（Video2X / FlashVSR / SeedVR2 / MiniMax H3），
#   每条工作流要部署的东西不一样，用户只需要装自己会用的那条。所以按"公共 + 各工作流"组织，
#   组内自洽、组间独立 —— 看起来才知道"这堆东西是给谁用的"。
#
# 注意：权重落点以各安装脚本为准（SeedVR2 装到 models\SEEDVR2，H3 走 ComfyUI 原生目录）。

GROUPS = (
    # (分组键, 卡片标题, 一句话说明)
    ("common", "公共组件", "四条工作流都要用的底座与通用依赖"),
    ("video2x", "Video2X", "方案一 · 独立超分工具（C++/Vulkan，不依赖 ComfyUI/CUDA）"),
    ("flashvsr", "FlashVSR", "方案二 · 快速的视频超分（ComfyUI 节点 + 权重）"),
    ("seedvr2", "SeedVR2", "方案三 · 高质量视频修复/放大（ComfyUI 节点 + 权重）"),
    ("h3", "MiniMax H3", "方案四 · 文生视频 / 图生视频（ComfyUI 原生目录）"),
)

DEPLOY_ITEMS = (
    # ---------- 公共：ComfyUI 底座 ----------
    dict(key="comfy_base", group="common", name="ComfyUI 底座", root="comfy_dir",
         check=("main.py",), expect=None,
         script="00-ComfyUI底座/安装ComfyUI.ps1",
         desc="ComfyUI 主程序（{comfy_dir}）"),
    dict(key="comfy_py", group="common", name="ComfyUI Python", root="comfy_dir",
         check=(".venv/Scripts/python.exe",), expect=None,
         script="00-ComfyUI底座/安装ComfyUI.ps1",
         desc="ComfyUI 虚拟环境 Python（{comfy_dir}）"),
    dict(key="node_manager", group="common", name="ComfyUI-Manager", root="comfy_dir",
         check=("custom_nodes/ComfyUI-Manager",), expect=None,
         script="00-ComfyUI底座/安装ComfyUI.ps1",
         desc="节点管理器（ltdrdata/ComfyUI-Manager）"),
    dict(key="node_vhs", group="common", name="VideoHelperSuite", root="comfy_dir",
         check=("custom_nodes/ComfyUI-VideoHelperSuite",), expect=None,
         script="02-FlashVSR/安装FlashVSR.ps1",   # 顺带装，属于公共视频读写节点
         desc="视频读写节点（Kosinkadink），与 ffmpeg 配合"),
    dict(key="ffmpeg", group="common", name="ffmpeg", root="ffmpeg_dir",
         check=("ffmpeg.exe",), expect=None,
         script="",  # P2 才补安装脚本；现走 PATH / 候选路径解析
         desc="视频封装/转码（{ffmpeg_dir}）"),

    # ---------- 方案一：Video2X（独立目录） ----------
    dict(key="video2x", group="video2x", name="Video2X", root=r"C:\AI\Video2X",
         check=("video2x.exe",), expect=None,
         size_hint="约 190 MB",   # 仅供显示：GitHub release 的 video2x-windows-amd64.zip（6.4.0 = 187.9 MB）
         script="01-Video2X/安装Video2X.ps1",
         desc="方案一引擎（k4yt3x/video2x 6.4.0，C++/Vulkan，不依赖 Python/CUDA）"),

    # ---------- 方案二：FlashVSR ----------
    dict(key="node_flashvsr", group="flashvsr", name="FlashVSR 节点", root="comfy_dir",
         check=("custom_nodes/ComfyUI-FlashVSR_Ultra_Fast",), expect=None,
         script="02-FlashVSR/安装FlashVSR.ps1",
         desc="方案二引擎节点（lihaoyun6）"),
    dict(key="w_flashvsr", group="flashvsr", name="FlashVSR v1.1 权重", root="comfy_dir",
         check=("models/FlashVSR-v1.1",), expect=None,  # 目录型；全仓 8 文件 ≈ 6.47 GB
         script="02-FlashVSR/安装FlashVSR.ps1",
         desc="JunhaoZhuang/FlashVSR-v1.1（约 6.47 GB）"),

    # ---------- 方案三：SeedVR2 ----------
    dict(key="node_seedvr2", group="seedvr2", name="SeedVR2 节点", root="comfy_dir",
         check=("custom_nodes/seedvr2_videoupscaler",), expect=None,
         script="03-SeedVR2/安装SeedVR2.ps1",
         desc="方案三引擎节点（numz，v2.5.24）"),
    dict(key="w_seedvr2_fp8", group="seedvr2", name="SeedVR2 3B FP8 权重", root="comfy_dir",
         check=("models/SEEDVR2/seedvr2_ema_3b_fp8_e4m3fn.safetensors",),
         expect=3391544696,  # 3.16 GB（hf-mirror 2026-10-26 复核）
         script="03-SeedVR2/安装SeedVR2.ps1",
         desc="numz/SeedVR2_comfyUI · 3.16 GB"),
    dict(key="w_seedvr2_vae", group="seedvr2", name="SeedVR2 VAE", root="comfy_dir",
         check=("models/SEEDVR2/ema_vae_fp16.safetensors",),
         expect=501324814,  # 0.47 GB（hf-mirror 2026-10-26 复核）
         script="03-SeedVR2/安装SeedVR2.ps1",
         desc="numz/SeedVR2_comfyUI · 0.47 GB"),

    # ---------- 方案四：MiniMax H3（huggingface 单文件补下） ----------
    dict(key="w_h3_dit", group="h3", name="H3 扩散模型", root="comfy_dir",
         check=("models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",),
         expect=20970379616, hf="Comfy-Org/MiniMax-H3",
         script="", desc="Comfy-Org/MiniMax-H3 · 20.97 GB"),
    dict(key="w_h3_te", group="h3", name="H3 文本编码器", root="comfy_dir",
         check=("models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",),
         expect=15687142551, hf="Comfy-Org/MiniMax-H3",
         script="", desc="Comfy-Org/MiniMax-H3 · 15.69 GB"),
    dict(key="w_h3_vae", group="h3", name="H3 双 VAE", root="comfy_dir",
         check=("models/vae/minimax_h3_video_vae_int8_convrot.safetensors",
                "models/vae/minimax_h3_audio_vae_fp32.safetensors"),
         expect=(2811065184, 605254808),          # 逐文件期望值（与 check 一一对应）
         hf="Comfy-Org/MiniMax-H3", script="",
         desc="Comfy-Org/MiniMax-H3 · 2.62 + 0.56 GB"),
    dict(key="w_h3_lora", group="h3", name="H3 turbo LoRA", root="comfy_dir",
         check=("models/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",),
         expect=1956193000, hf="Comfy-Org/MiniMax-H3",
         script="", desc="MiniMax-H3 · 1.82 GB"),
)


def has_installer(key):
    """供 UI 快速判断"是否可一键安装"。"""
    for it in DEPLOY_ITEMS:
        if it["key"] == key:
            return bool(it["script"])
    return False


def by_key(key):
    """按 key 取条目（UI 点「安装 / 下载」时用来查仓库与文件清单）。"""
    for it in DEPLOY_ITEMS:
        if it["key"] == key:
            return it
    return None


def group_of(key):
    """条目属于哪个分组（UI 卡片分栏用）。"""
    it = by_key(key)
    return it["group"] if it else "common"


def items_of(group):
    """取某一组的全部条目（按 DEPLOY_ITEMS 原顺序）。"""
    return [it for it in DEPLOY_ITEMS if it["group"] == group]


def expects_of(item):
    """把 expect 归一成"与 check 等长"的列表。None/整数/元组三种写法都吃。"""
    n = len(item["check"])
    exp = item.get("expect")
    if isinstance(exp, (list, tuple)):
        vals = list(exp) + [None] * (n - len(exp))
        return vals[:n]
    return [exp] * n


def hf_paths_of(item):
    """check 里的相对路径 → HF 仓库内路径（去掉 ComfyUI 的 models/ 前缀）。"""
    out = []
    for rel in item["check"]:
        rel = rel.replace("\\", "/")
        out.append(rel[len("models/"):] if rel.startswith("models/") else rel)
    return out
