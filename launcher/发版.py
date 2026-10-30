# -*- coding: utf-8 -*-
"""发版一条命令：打包 exe → 出整包 zip → 建 tag → 建 Release → 传资产。

为什么要有它（2026-10-30 手工发 v1.12.0 时的实录）：
    那一次是 6 步手工操作，踩了 3 个坑 ——
      ① `POST /releases` 带 `target_commitish=<短 SHA>` 报 422 `tag_name is not a valid tag`，
         必须先 `POST /git/refs` 把 tag 建出来（且要 40 位完整 SHA）；
      ② PyInstaller 单文件是「引导进程 + 子进程」两段，冒烟时按父 PID 找窗口永远找不到；
      ③ `TCL_LIBRARY` 必须在**当前环境**里显式覆盖（父进程若留着别的 PyInstaller 程序的
         同名变量，打出来的 exe 一启动就 `No module named 'tkinter'`，而构建照样 exit 0）。
    这三条现在都固化进本脚本，另加一道「体积 + TOC」断言防假发版。

用法：
    set GH_TOKEN=ghp_xxx
    python 发版.py --version v1.13.0 --launcher v1.6.0            # 真发
    python 发版.py --version v1.13.0 --launcher v1.6.0 --dry-run  # 只打包出 zip，不碰 GitHub
    python 发版.py ... --skip-build                               # 复用 dist 里已有的 exe
"""
import argparse
import io
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEPLOY_ROOT = os.path.dirname(HERE)
SPEC = "VideoLauncher.spec"
EXE_NAME = "ComfyUI启动器.exe"
MIN_EXE_BYTES = 12 * 1024 * 1024        # 正常 ~13.3 MB；无 tkinter 的坏包约 10.19 MB
DIST = os.path.join(HERE, "dist")
BUILD_LOG = os.path.join(HERE, "build", "发版构建.log")
TCL_REL = os.path.join("tcl", "tcl8.6")
TK_REL = os.path.join("tcl", "tk8.6")


# ---------------------------------------------------------------- 小工具
def run(cmd, cwd=None, env=None, timeout=900, check=True):
    print("  $ %s" % " ".join(cmd if isinstance(cmd, list) else [cmd]))
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if check and r.returncode != 0:
        tail = (r.stdout or "")[-800:] + (r.stderr or "")[-800:]
        raise SystemExit("命令失败（rc=%s）：\n%s" % (r.returncode, tail))
    return r


def git(*args, check=True):
    return run(["git"] + list(args), cwd=DEPLOY_ROOT, check=check)


def app_ver():
    with io.open(os.path.join(HERE, "视频方案启动器.py"), encoding="utf-8") as fh:
        m = re.search(r'^APP_VER = "(v[\d.]+)"', fh.read(), re.M)
    return m.group(1) if m else ""


def remote_repo():
    """从 origin URL 解出 owner/repo（SSH 与 HTTPS 两种写法都吃）。"""
    url = git("remote", "get-url", "origin").stdout.strip()
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    if not m:
        raise SystemExit("无法从 remote 解析 owner/repo：%s" % url)
    return m.group(1)


def changelog_section(md_path, version):
    """取 CHANGELOG 里某个版本号到下一个版本号之间的正文（发版说明直接复用，不手抄）。"""
    with io.open(md_path, encoding="utf-8") as fh:
        text = fh.read()
    pat = re.compile(r"^## %s\b.*?$(.*?)(?=^## |\Z)" % re.escape(version), re.M | re.S)
    m = pat.search(text)
    return m.group(1).strip() if m else ""


def remote_head():
    """远端 main 的 sha，取不到返回 ""。

    优先走 API（有 GH_TOKEN 时）：这台机器 git 直连 GitHub 时通时断，走代理还会 502，
    `git ls-remote` 经常直接失败 —— 而"HEAD 是否已推送"恰恰是发版前最该拦的一项。
    API 在发布时本来就要用，顺带把这项检查做可靠。
    """
    try:
        repo = remote_repo()
    except SystemExit:
        return ""
    if os.environ.get("GH_TOKEN"):
        try:
            return api("GET", "/repos/%s/commits/main" % repo, tries=2).get("sha", "")
        except SystemExit as exc:                  # API 也不通：退回 git，再不行就放行
            print("  [注意] API 查远端失败：%s" % str(exc)[:80])
    ls = run(["git", "-c", "credential.helper=", "-c", "http.proxy=", "-c", "https.proxy=",
              "ls-remote", "origin", "main"], cwd=DEPLOY_ROOT, check=False)
    return (ls.stdout or "").split("\t")[0].strip()


# ---------------------------------------------------------------- 1. 前置检查
def preflight(args):
    print("[1/6] 前置检查")
    status = git("status", "--porcelain").stdout.strip()
    if status:
        raise SystemExit("工作区不干净，先提交：\n%s" % status)
    head = git("rev-parse", "HEAD").stdout.strip()
    local = app_ver()
    print("  HEAD=%s  APP_VER=%s" % (head[:12], local))
    if local != args.launcher:
        raise SystemExit("APP_VER (%s) 与 --launcher (%s) 不一致：先改 视频方案启动器.py 再发版"
                         % (local, args.launcher))
    remote_sha = remote_head()
    if remote_sha and remote_sha != head:
        msg = "本地 HEAD 与远端不一致（远端 %s）：先 push 再发版" % remote_sha[:12]
        if args.dry_run:
            print("  [dry-run 放行] " + msg)
        else:
            raise SystemExit(msg)
    elif remote_sha:
        print("  远端 main 已同步")
    else:
        print("  [注意] 读不到远端（ls-remote 失败），继续")
    return head


# ---------------------------------------------------------------- 2. 用例（发版前必过）
# 为什么放在发版流程里而不是靠 CI：这个仓库没有 CI（GitHub 要求 workflow 文件的 PAT 带
# `workflow` scope，手上的 token 只有 `repo`），而"改完记得跑用例"是纯记忆。
# 两套用例都不依赖 tkinter，任何 python 3.12+ 都能跑，成本 0.6 秒。
SUITES = (
    ("启动器", HERE, "tests"),
    ("VEHelper", os.path.join(DEPLOY_ROOT, "04-VisualEnhancer"), "tests"),
)


def run_tests(args):
    if args.skip_tests:
        print("[2/6] 用例：跳过（--skip-tests）")
        return
    print("[2/6] 用例（发版前必过）")
    for name, cwd, start in SUITES:
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", start],
                           cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        tail = [ln for ln in (r.stderr or "").strip().splitlines() if ln.strip()][-2:]
        print("  %-8s %s" % (name, " / ".join(tail) or "(无输出)"))
        if r.returncode != 0:
            raise SystemExit("用例失败，中止发版：%s\n%s" % (name, (r.stderr or "")[-800:]))


# ---------------------------------------------------------------- 3. 打包
def build(args):
    exe = os.path.join(DIST, EXE_NAME)
    if args.skip_build:
        print("[3/6] 打包：跳过（--skip-build），复用 %s" % exe)
    else:
        print("[3/6] 打包 exe")
        run(["taskkill", "/F", "/IM", EXE_NAME], check=False)      # 运行中的 exe 会锁 dist
        env = dict(os.environ)
        # 必须**强制覆盖**：父进程可能是别的 PyInstaller 程序，留着它自己的 TCL_LIBRARY，
        # 打出来的 exe 会缺 tkinter（体积掉到 10.19 MB，构建却 exit 0）。
        env["TCL_LIBRARY"] = os.path.join(sys.base_prefix, TCL_REL)
        env["TK_LIBRARY"] = os.path.join(sys.base_prefix, TK_REL)
        os.makedirs(os.path.dirname(BUILD_LOG), exist_ok=True)
        r = subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", SPEC],
                           cwd=HERE, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
        with io.open(BUILD_LOG, "w", encoding="utf-8") as fh:
            fh.write((r.stdout or "") + "\n" + (r.stderr or ""))
        if r.returncode != 0:
            raise SystemExit("打包失败，详见 %s" % BUILD_LOG)
    size = os.path.getsize(exe) if os.path.exists(exe) else 0
    print("  产物 %s  %.2f MB" % (EXE_NAME, size / 1e6))
    if size < MIN_EXE_BYTES:
        raise SystemExit("体积只有 %.2f MB（正常约 13.3 MB）—— 很可能打出了没有 tkinter 的坏包，"
                         "检查 TCL_LIBRARY / TK_LIBRARY" % (size / 1e6))
    if not args.skip_build:
        log = io.open(BUILD_LOG, encoding="utf-8").read()
        if "pyi_rth__tkinter" not in log:
            raise SystemExit("构建日志里没有 pyi_rth__tkinter —— tkinter 很可能被排除，别发这个包")
    print("  tkinter 检查通过（体积 + pyi_rth__tkinter 双判据）")
    return exe, size


# ---------------------------------------------------------------- 3. 整包 zip
def make_zip(args, exe):
    print("[4/6] 生成整包 zip")
    out = os.path.join(DIST, "video-upscale-deploy-%s.zip" % args.version)
    run(["git", "archive", "--format=zip", "-o", out, "HEAD"], cwd=DEPLOY_ROOT)
    with zipfile.ZipFile(out, "a", zipfile.ZIP_DEFLATED) as z:
        z.write(exe, "launcher/" + EXE_NAME)
    print("  %s  %.2f MB" % (os.path.basename(out), os.path.getsize(out) / 1e6))
    return out


# ---------------------------------------------------------------- 4/5. GitHub
def _opener():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                       urllib.request.HTTPSHandler(context=ctx))


def api(method, path, body=None, raw=None, host="api.github.com", tries=4):
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("缺 GH_TOKEN 环境变量（需要 repo scope）")
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request("https://%s%s" % (host, path), data=data, method=method,
                                 headers={"Authorization": "Bearer " + token,
                                          "Accept": "application/vnd.github+json",
                                          "User-Agent": "wb-release",
                                          "Content-Type": "application/octet-stream" if raw is not None
                                          else "application/json"})
    last = None
    for i in range(tries):
        try:
            with _opener().open(req, timeout=180) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:200]
            last = "HTTP %s %s" % (exc.code, detail)
            if exc.code in (401, 403, 404, 422):     # 认证/参数问题，重试没意义
                break
        except Exception as exc:                     # 网络抖动：重试
            last = repr(exc)
        time.sleep(5)
    raise SystemExit("GitHub 调用失败：%s（%s %s）" % (last, method, path))


def publish(args, exe, exe_size, zip_path, head):
    repo = remote_repo()
    exe_asset = "ComfyUI-Launcher-%s.exe" % args.launcher
    zip_asset = os.path.basename(zip_path)

    print("[5/6] 建 tag 与 Release（%s）" % repo)
    if args.dry_run:
        print("  [dry-run] 将建 tag %s @ %s，Release 资产：%s / %s"
              % (args.version, head[:12], exe_asset, zip_asset))
        return
    # ① 先建 tag ref：直接给 /releases 传 target_commitish 短 SHA 会 422，且 tag 必须 40 位
    ref = "refs/tags/%s" % args.version
    got = api("GET", "/repos/%s/git/matching-refs/tags/%s" % (repo, args.version), tries=2)
    if not got:
        api("POST", "/repos/%s/git/refs" % repo, {"ref": ref, "sha": head})
        print("  tag 已建：%s" % args.version)
    else:
        print("  tag 已存在，复用：%s" % args.version)

    # ② Release（不再传 target_commitish）
    body = "## 启动器 %s\n\n%s\n" % (args.launcher, changelog_section(
        os.path.join(HERE, "CHANGELOG.md"), args.launcher) or "（见 CHANGELOG）")
    rel = api("POST", "/repos/%s/releases" % repo, {
        "tag_name": args.version,
        "name": "%s · 启动器 %s" % (args.version, args.launcher),
        "body": body,
    })
    print("  Release: %s" % rel["html_url"])

    print("[6/6] 上传资产")
    for path, name in ((exe, exe_asset), (zip_path, zip_asset)):
        size = os.path.getsize(path)
        print("  %s（%.2f MB）…" % (name, size / 1e6))
        asset = api("POST", "/repos/%s/releases/%s/assets?name=%s" % (repo, rel["id"], name),
                    raw=open(path, "rb").read(), host="uploads.github.com")
        if asset.get("size") != size:
            raise SystemExit("上传大小不符：%s vs %s" % (asset.get("size"), size))
        print("    → %s" % asset["browser_download_url"])
    print("\n完成：%s" % rel["html_url"])


def main():
    ap = argparse.ArgumentParser(description="一条命令发版（打包 + zip + tag + Release + 资产）")
    ap.add_argument("--version", required=True, help="仓库版本，如 v1.13.0")
    ap.add_argument("--launcher", required=True, help="启动器版本（须等于 APP_VER），如 v1.6.0")
    ap.add_argument("--dry-run", action="store_true", help="只打包与出 zip，不碰 GitHub")
    ap.add_argument("--skip-build", action="store_true", help="复用 dist 里已有 exe")
    ap.add_argument("--skip-tests", action="store_true", help="跳过发版前的用例（不建议）")
    args = ap.parse_args()

    head = preflight(args)
    run_tests(args)
    exe, exe_size = build(args)
    zip_path = make_zip(args, exe)
    publish(args, exe, exe_size, zip_path, head)
    return 0


if __name__ == "__main__":
    sys.exit(main())
