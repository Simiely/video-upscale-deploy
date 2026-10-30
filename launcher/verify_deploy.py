# -*- coding: utf-8 -*-
"""部署清单体检：本机盘点（默认）+ 远端对账（--remote）。命令行跑，**不参与打包**。

    python verify_deploy.py             # 本机盘点：就绪 N/16 + 逐项状态
    python verify_deploy.py --remote    # 额外把 expect / sha256 与 ModelScope 远端对账

逻辑断言（三态状态机、元组归一、`hf_paths_of` 覆盖等）已迁到
`launcher/tests/test_deploy.py`（`python -m unittest discover -s tests`）——
2026-10-30 起两边不再重复维护，这里只做**针对本机**的活。

为什么要有 --remote：
    2026-10-30 发现 `部署清单.py` 有 5 处 desc 把 GiB 写成 GB、FlashVSR 权重写着 6.47GB
    而实测 6.95GB —— 这类漂移靠人眼对不出来。远端 API 一次请求就能拿到仓库内每个
    文件的 Size + Sha256，拿它跟清单里的 expect / sha256 比，是成本最低的一道防线
    （第一次跑就抓出过 SeedVR2 的 hf 路径映射错误）。
"""
import json
import os
import sys
import urllib.request

import 部署下载 as dw
import 运行时 as rt
from 部署清单 import DEPLOY_ITEMS, expects_of, hf_paths_of, sha256_of

# ModelScope 的仓库文件列表：一次请求拿到 Path / Size / Sha256（比逐个 HEAD 便宜得多）
MS_FILES = "https://modelscope.cn/api/v1/models/%s/repo/files?Revision=master&Recursive=true"
DEFAULT_CFG = {
    "comfy_dir": r"C:\AI\ComfyUI",
    "comfy_py": r"C:\AI\ComfyUI\.venv\Scripts\python.exe",
    "deploy_root": r"C:\AI\video-upscale-deploy",
    "ffmpeg_dir": r"C:\AI\ffmpeg\bin",
}


def real_cfg():
    """启动器同款配置：内置默认 → 程序同目录的 启动器配置.json 覆盖。"""
    cfg = dict(DEFAULT_CFG)
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "启动器配置.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as fh:
                cfg.update(json.load(fh))
            print("（配置来源：%s）" % p)
        except Exception as exc:                     # 配置坏了就退回默认值，别阻塞体检
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
    return not todo


def ms_repo_files(repo, cache):
    """{仓库内路径: (字节数, sha256)}；一次请求拿全仓，失败返回 {}。"""
    if repo in cache:
        return cache[repo]
    req = urllib.request.Request(MS_FILES % repo, headers={"User-Agent": "verify-deploy"})
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # ModelScope 国内直连
    try:
        data = json.loads(op.open(req, timeout=40).read())
        files = {f["Path"]: (int(f.get("Size") or 0), (f.get("Sha256") or "").lower())
                 for f in data.get("Data", {}).get("Files", [])
                 if f.get("Type") == "blob"}
    except Exception as exc:                    # 网络问题不该让整份体检判死
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
    return drift == 0


def main():
    remote = "--remote" in sys.argv
    ok = real_report(real_cfg())
    if remote:
        print("\n== 远端对账（ModelScope 文件列表）")
        ok = remote_check() and ok
    print("\n结果：", "全部通过" if ok else "有不就绪项 / 漂移")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
