"""提示词装配：把用户写的描述整理成 MiniMax H3 官方要求的 I2VA 结构。

为什么单独一个模块（v1.2.21）：对齐句与三字段的写法是**官方规范**，不是实现细节
—— 逐字取自 MiniMax 官方仓库 `skills/h3-prompt-writing/references/base-en.txt` §2.1，
改一个词就可能让首帧失效。放在独立文件里，改动一目了然，也免得 `运行时.py`
越过 1000 行的拆分阈值（仓库约定见 AGENTS.md「模块拆分按阈值」）。

只做字符串加工：不碰网络、不碰磁盘、不 import 项目内其它模块（单向依赖）。
"""

# MiniMax H3 图生视频（I2VA）的官方对齐句 —— 逐字取自 MiniMax 官方仓库
# skills/h3-prompt-writing/references/base-en.txt §2.1，原文写明「I2VA always uses」，
# 且必须是整段提示词的第一行，后面空一行再接三个核心字段。
I2V_ALIGN = ("For the target video, at 0.00 seconds into the target video, "
             "<Picture 1> (from [Shot 1]) is fully referenced.")

# 官方要求的三字段（顺序固定，见同一份指南 §2.2）
MM_FIELDS = ("integrated_multimodal_description:",
             "overall_soundscape:",
             "non_diegetic_music:")

MM_SOUND_FALLBACK = "Natural ambience and physical movement sounds matching the scene."

# 界面上的默认提示词：刻意只写"怎么动 + 保持不变"，因为首帧的内容由 <Picture 1> 决定，
# 官方指南 §3.1 明确要求「先立住图里的风格/主体/构图/场景，再写后续动作」。
MM_PROMPT_DEFAULT = (
    "integrated_multimodal_description: [Shot 1] Live-action, cinematic, the scene shown in "
    "<Picture 1> is kept exactly as framed: same subjects, same composition, same lighting "
    "and colour, matching the position and framing established by <Picture 1>. The camera "
    "pushes in with small amplitude at slow speed as the air and light move gently through "
    "the frame and the subjects make one small, natural motion. Toward the end of the shot "
    "the layout, horizon and spatial relationships remain identical to <Picture 1>.\n"
    "overall_soundscape: " + MM_SOUND_FALLBACK + "\n"
    "non_diegetic_music: N/A")


def _fill_missing_fields(body):
    """补齐缺的核心字段：声场缺了给一句中性描述，配乐缺了给 N/A（= 不要配乐）。"""
    text = body.strip()
    if "overall_soundscape:" not in text:
        text += "\noverall_soundscape: " + MM_SOUND_FALLBACK
    if "non_diegetic_music:" not in text:
        text += "\nnon_diegetic_music: N/A"
    return text


def build_i2v_prompt(text):
    """把用户写的提示词整理成官方 I2VA 结构：对齐句 → 空行 → 三个核心字段。

    用户通常只写"画面里发生什么"，对齐句和缺失字段由这里补齐；已经手写过对齐句或
    三字段的，只做换行规范、内容不动（不覆盖人家的排版）。
    """
    body = str(text or "").replace("\r\n", "\n").strip()
    if not body:
        return ""
    lines = body.split("\n")
    if lines[0].strip().lower().startswith("for the target video"):
        # 自己写了对齐句：只补缺失的字段、规范空行，不动正文
        rest = _fill_missing_fields("\n".join(lines[1:]).strip())
        return lines[0].strip() + ("\n\n" + rest if rest else "")
    if any(f in body for f in MM_FIELDS):
        body = _fill_missing_fields(body)
    else:
        # 纯描述：整段当画面描述，压成一行（多行会被模型当成额外的分镜）
        body = _fill_missing_fields(
            "integrated_multimodal_description: [Shot 1] " + " ".join(
                ln.strip() for ln in body.split("\n") if ln.strip()))
    return I2V_ALIGN + "\n\n" + body


def apply_prompt(api, text, default_text=""):
    """把提示词写进 MiniMax H3 节点。返回改动的节点数（0 = 图里没有该节点）。

    图里接了 first_frame 就按官方 I2VA 结构整理；没接（纯文生视频）不加对齐句 ——
    那是图生视频专用的指令。文生视频只在用户**改过**默认值时才覆盖，
    否则保留图里原有的提示词（避免默认文案顶掉别人调好的 T2V 提示词）。
    """
    tgt = [nd for nd in api.values()
           if isinstance(nd, dict) and nd.get("class_type") == "MiniMaxH3ImageToVideo"]
    if not tgt:
        return 0
    raw = str(text or "").strip()
    if not raw:
        return 0
    changed = 0
    for nd in tgt:
        inputs = nd.setdefault("inputs", {})
        if "first_frame" in inputs:
            inputs["prompt"] = build_i2v_prompt(raw)
            changed += 1
        elif default_text and raw == str(default_text).strip():
            continue          # 文生视频 + 没动过默认值 → 保留原提示词
        else:
            inputs["prompt"] = raw
            changed += 1
    return changed
