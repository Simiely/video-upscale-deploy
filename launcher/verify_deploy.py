# -*- coding: utf-8 -*-
"""部署清单逻辑自检 + 真机盘点 + 远端对账（命令行跑，**不参与打包**）。

三件事按需组合：

    python verify_deploy.py              # 只跑逻辑断言（临时假环境，不碰本机）
    python verify_deploy.py --real       # 额外按 启动器配置.json 盘点本机（就绪 N/16）
    python verify_deploy.py --remote     # 额外把 expect / sha256 与 ModelScope 远端对账

为什么要把「假环境」和「真机」分开（2026-10-30 修正）：
    本脚本原本只做逻辑断言 —— 它会在临时目录里造一个假 comfy_dir，故意让 15 项缺失，
    用来验证"就绪/缺失/不完整"的状态机。那段输出长得跟真机盘点一模一样，
    看的人很容易以为"本机缺 13 项"，而结论行的"全部通过"说的其实是断言。
    现在样例输出会显式标注假环境，真机盘点要 --real 才出。

为什么要有 --remote：
    2026-10-30 发现 `部署清单.py` 有 5 处 desc 把 GiB 写成 GB、FlashVSR 权重写着 6.47GB
    而实测 6.95GB —— 这类漂移靠人眼对不出来。远端 API 一次请求就能拿到仓库内每个
    文件的 Size + Sha256，拿它跟清单里的 expect / sha256 比，是成本最低的一道防线。
"""
import json
import os
import sys
import tempfile
import urllib.request

import 部署下载 as dw
import 运行时 as rt
from 部署清单 import DEPLOY_ITEMS, expects_of, has_installer, hf_paths_of, sha256_of

# ModelScope 的仓库文件列表：一次请求拿到 Path / Size / Sha256（比逐个 HEAD 便宜得多）
MS_FILES = "https://modelscope.cn/api/v1/models/%s/repo/files?Revision=master&Recursive=true"
DEFAULT_CFG = {
    "comfy_dir": r"C:\AI\ComfyUI",
    "comfy_py": r"C:\AI\ComfyUI\.venv\Scripts\python.exe",
    "deploy_root": r"C:\AI\video-upscale-deploy",
    "ffmpeg_dir": r"C:\AI\ffmpeg\bin",
}

ok = True


def check(cond, msg):
    global ok
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        ok = False


# ---------------------------------------------------------------- 1. 逻辑断言（假环境）
def logic_checks():
    check(len(DEPLOY_ITEMS) == 16, "DEPLOY_ITEMS 共 16 项（实际 %d）" % len(DEPLOY_ITEMS))
    need = {"key", "group", "name", "root", "check", "expect", "script", "desc"}
    for it in DEPLOY_ITEMS:
        check(need <= set(it), "项 %s 字段齐全" % it.get("key"))
    keys = [it["key"] for it in DEPLOY_ITEMS]
    check(len(keys) == len(set(keys)), "key 无重复")

    d = tempfile.mkdtemp()
    comfy = os.path.join(d, "comfy")
    os.makedirs(os.path.join(comfy, "custom_nodes"))
    with open(os.path.join(comfy, "main.py"), "w") as f:
        f.write("x" * 10)                                        # comfy_base 就绪
    os.makedirs(os.path.join(comfy, ".venv", "Scripts"))
    open(os.path.join(comfy, ".venv", "Scripts", "python.exe"), "w").close()
    os.makedirs(os.path.join(comfy, "models", "SEEDVR2"))
    with open(os.path.join(comfy, "models", "SEEDVR2",
                           "seedvr2_ema_3b_fp8_e4m3fn.safetensors"), "w") as f:
        f.write("x" * 100)                                       # 只有 100 字节 → 不完整

    cfg = {"comfy_dir": comfy, "ffmpeg_dir": ""}                 # video2x 是绝对路径，沙箱里不存在
    rows = dw.deploy_inventory(cfg)
    by = {r[0]: r for r in rows}
    check(len(rows) == 16, "deploy_inventory 返回 16 行")
    check(by["comfy_base"][2] == "就绪", "comfy_base → 就绪")
    check(by["comfy_py"][2] == "就绪", "comfy_py → 就绪")
    check(by["node_manager"][2] == "缺失", "node_manager（未建）→ 缺失")
    check(by["w_seedvr2_fp8"][2] == "不完整", "w_seedvr2_fp8（100B < 3.39GB）→ 不完整")
    check("大小不足" in by["w_seedvr2_fp8"][3], "w_seedvr2_fp8 说明含「大小不足」")
    check(by["w_seedvr2_vae"][2] == "缺失", "w_seedvr2_vae（不存在）→ 缺失")
    check(by["video2x"][2] == "缺失", "video2x（C:\\AI\\Video2X 不存在）→ 缺失")
    check(by["ffmpeg"][2] == "缺失", "ffmpeg（ffmpeg_dir 空）→ 缺失")
    check(by["w_h3_dit"][2] == "缺失", "w_h3_dit（P1，未下）→ 缺失")
    check(by["workflows"][2] == "缺失", "workflows（假 cfg 无 deploy_root）→ 缺失")
    check("workflows" in by["workflows"][3], "workflows 缺失说明点出 workflows 目录")
    check(len(by["comfy_base"]) == 7, "每行是 7 元组（含实际大小）")
    check(by["comfy_base"][5] > 0, "实际大小已算出（main.py 字节数 > 0）")
    check(by["video2x"][5] == 0, "未安装项实际大小为 0")
    check(has_installer("comfy_base") is True, "has_installer(comfy_base)=True")
    check(has_installer("ffmpeg") is False, "has_installer(ffmpeg)=False（无脚本）")

    print("\n【假环境样例】以下是临时目录里那个假 comfy_dir 的探测结果，**不代表本机状态**：")
    for r in rows:
        print("  %-16s %-4s %s" % (r[0], r[2], r[3]))


# ---------------------------------------------------------------- 2. 真机盘点
def real_cfg():
    cfg = dict(DEFAULT_CFG)
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "启动器配置.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as fh:
                cfg.update(json.load(fh))
            print("（配置来源：%s）" % p)
        except Exception as exc:                     # 配置坏了就退回默认值，别阻塞自检
            print("（启动器配置.json 读取失败，用默认值：%r）" % (exc,))
    else:
        print("（无 启动器配置.json，用内置默认路径）")
    return cfg


def real_report(cfg):
    rows = dw.deploy_inventory(cfg)
    ready = [r for r in rows if r[2] == "就绪"]
    todo = [r for r in rows if r[2] != "就绪"]
    print("【本机】就绪 %d / %d" % (len(ready), len(rows)))
    for r in rows:
        mark = "OK  " if r[2] == "就绪" else "缺  "
        print("  %s %-16s %-4s %-10s %s" % (mark, r[0], r[2],
                                            rt.human_size(r[5] or r[4] or 0), r[3]))
    if todo:
        print("待处理：%s" % "、".join(r[1] for r in todo))
    return rows


# ---------------------------------------------------------------- 3. 远端对账
def ms_repo_files(repo, cache):
    """{仓库内路径: (字节数, sha256)}；一次请求拿全仓，失败返回 {}。"""
    if repo in cache:
        return cache[repo]
    url = MS_FILES % repo
    req = urllib.request.Request(url, headers={"User-Agent": "verify-deploy"})
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # ModelScope 国内直连
    try:
        data = json.loads(op.open(req, timeout=40).read())
        files = {f["Path"]: (int(f.get("Size") or 0), (f.get("Sha256") or "").lower())
                 for f in data.get("Data", {}).get("Files", [])
                 if f.get("Type") == "blob"}
    except Exception as exc:                    # 网络问题不该让整份自检判死
        print("  [注意] %s 列表拉取失败：%r" % (repo, exc))
        files = {}
    cache[repo] = files
    return files


def remote_check():
    """逐项比对 expect / sha256 与远端；顺带列出「有 expect 但没有 hf，无法对账」的缺口。"""
    cache = {}
    drift = 0
    uncovered = []
    for it in DEPLOY_ITEMS:
        if not it.get("hf"):
            if it.get("expect"):
                uncovered.append(it["key"])
            continue
        files = ms_repo_files(it["hf"], cache)
        if not files:
            continue
        for hf_path, exp, sha in zip(hf_paths_of(it), expects_of(it), sha256_of(it)):
            got_size, got_sha = files.get(hf_path, (0, ""))
            if not got_size:
                print("  %-16s %-40s 远端无此文件" % (it["key"], hf_path))
                drift += 1
                continue
            size_ok = (not exp) or (got_size == exp)
            sha_ok = (not sha) or (got_sha == sha.lower())
            if size_ok and sha_ok:
                print("  %-16s 一致  %s  sha=%s" % (it["key"], rt.human_size(got_size),
                                                   (got_sha[:12] + "…") if got_sha else "-"))
            else:
                drift += 1
                print("  %-16s **漂移** 大小 %s/%s  sha %s" % (
                    it["key"], got_size, exp or "-",
                    "一致" if sha_ok else ("清单未写" if not sha else "不一致")))
    if uncovered:
        print("  覆盖缺口（有 expect 但无 hf，无法对账）：%s" % "、".join(uncovered))
    check(drift == 0, "远端对账无漂移（漂移 %d 项）" % drift)


def main():
    real = "--real" in sys.argv
    remote = "--remote" in sys.argv

    print("== 1. 逻辑断言")
    logic_checks()

    if real:
        print("\n== 2. 本机盘点")
        real_report(real_cfg())

    if remote:
        print("\n== 3. 远端对账（ModelScope 文件列表）")
        remote_check()

    print("\n结果：", "全部通过" if ok else "存在失败")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
