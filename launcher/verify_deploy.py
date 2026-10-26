# 验证脚本：仅用于本地校验 部署清单.py + 运行时.deploy_inventory（非仓库运行时依赖）
import os
import sys
import tempfile

import 运行时 as rt
from 部署清单 import DEPLOY_ITEMS, has_installer

ok = True
def check(cond, msg):
    global ok
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        ok = False

# 1) 数据完整性
check(len(DEPLOY_ITEMS) == 16, "DEPLOY_ITEMS 共 16 项（实际 %d）" % len(DEPLOY_ITEMS))
need = {"key", "group", "name", "root", "check", "expect", "script", "desc"}
for it in DEPLOY_ITEMS:
    check(need <= set(it), "项 %s 字段齐全" % it.get("key"))
# 每个 key 唯一
keys = [it["key"] for it in DEPLOY_ITEMS]
check(len(keys) == len(set(keys)), "key 无重复")

# 2) 模拟 inventory（建一个假的 comfy_dir）
d = tempfile.mkdtemp()
comfy = os.path.join(d, "comfy"); os.makedirs(comfy)
os.makedirs(os.path.join(comfy, "custom_nodes"))
with open(os.path.join(comfy, "main.py"), "w") as f:
    f.write("x" * 10)                                        # comfy_base 就绪（10 字节）
os.makedirs(os.path.join(comfy, ".venv", "Scripts"))
open(os.path.join(comfy, ".venv", "Scripts", "python.exe"), "w").close()  # comfy_py 就绪
os.makedirs(os.path.join(comfy, "models", "SEEDVR2"))
# w_seedvr2_fp8：文件存在但只有 100 字节（期望 3.16GB）→ 不完整
with open(os.path.join(comfy, "models", "SEEDVR2", "seedvr2_ema_3b_fp8_e4m3fn.safetensors"), "w") as f:
    f.write("x" * 100)
# w_seedvr2_vae：不存在 → 缺失

cfg = {"comfy_dir": comfy, "ffmpeg_dir": ""}  # video2x 用绝对路径 C:\AI\Video2X（沙箱不存在）
rows = rt.deploy_inventory(cfg)
by = {r[0]: r for r in rows}
check(len(rows) == 16, "deploy_inventory 返回 16 行")
check(by["comfy_base"][2] == "就绪", "comfy_base → 就绪")
check(by["comfy_py"][2] == "就绪", "comfy_py → 就绪")
check(by["node_manager"][2] == "缺失", "node_manager（未建）→ 缺失")
check(by["w_seedvr2_fp8"][2] == "不完整", "w_seedvr2_fp8（100B<3.16GB）→ 不完整")
check("大小不足" in by["w_seedvr2_fp8"][3], "w_seedvr2_fp8 说明含「大小不足」")
check(by["w_seedvr2_vae"][2] == "缺失", "w_seedvr2_vae（不存在）→ 缺失")
check(by["video2x"][2] == "缺失", "video2x（C:\\AI\\Video2X 不存在）→ 缺失")
check(by["ffmpeg"][2] == "缺失", "ffmpeg（ffmpeg_dir 空）→ 缺失")
check(by["w_h3_dit"][2] == "缺失", "w_h3_dit（P1，未下）→ 缺失")
check(by["workflows"][2] == "缺失", "workflows（假 cfg 无 deploy_root）→ 缺失")
check("workflows" in by["workflows"][3], "workflows 缺失说明点出 workflows 目录")
# 元组结构：(key, 名称, 状态, 说明, 期望大小, 实际大小, 脚本)
check(len(by["comfy_base"]) == 7, "每行是 7 元组（含实际大小）")
check(by["comfy_base"][5] > 0, "实际大小已算出（main.py 字节数 > 0）")
check(by["video2x"][5] == 0, "未安装项实际大小为 0")
check(has_installer("comfy_base") is True, "has_installer(comfy_base)=True")
check(has_installer("ffmpeg") is False, "has_installer(ffmpeg)=False（无脚本）")

print("\n探测结果样例：")
for r in rows:
    print("  %-16s %-4s %s" % (r[0], r[2], r[3]))

print("\n结果：", "全部通过 ✅" if ok else "存在失败 ❌")
sys.exit(0 if ok else 1)
