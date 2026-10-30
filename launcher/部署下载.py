# -*- coding: utf-8 -*-
"""部署件探测 + 联网下载（v1.5.0 从 运行时.py 切出）。

为什么单独成模块：AGENTS 的硬约定是「单文件逻辑行超过 1000 就拆」，而 运行时.py
在 v1.2.23 起一路堆到 1188 行 —— 其中**一半是联网与部署**（清单探测 / ModelScope
分段并行 / GitHub 镜像回退 / ffmpeg 内置安装），跟"界面无关的运行时支撑"其实是两件事。

依赖单向：`视频方案启动器.py` → `部署下载.py` → `运行时.py`（只借 NO_WINDOW 与
human_size 两个基础件）。本模块不 import ui_kit、不建控件。

代理策略（v1.5.0，2026-10-30 实测后定）：**按源分治** —— ModelScope 直连
（8 段直连 98 MB/s，经 Clash 只有 3.3 MB/s），hf-mirror / GitHub 才走探测到的代理。
`HF_PROXY=http://…` 对两个源都生效，`=none` 全部直连。
"""
import hashlib
import os
import shutil
import socket
import subprocess
import tempfile
import time
import zipfile

import 部署清单 as dl
from 运行时 import NO_WINDOW, human_size, workflows_dir


# ================================================================ 缺失部署清单
def deploy_inventory(cfg):
    """探测 部署清单.DEPLOY_ITEMS 的每一项，返回探测结果。

    返回：list of (key, 名称, 状态, 说明, 期望大小, 实际大小, 脚本)
      状态 ∈ {"就绪", "缺失", "不完整"}
        · 就绪       ：root 下 check 文件全部存在，且（若有期望大小）大小达标
        · 不完整     ：某文件/目录实测大小 < 期望（"下了一半"），或 check 不全但有残件
        · 缺失       ：根未配置/不存在，或 check 文件/目录全不存在

    v1.2.27：多返回一个「实际大小」（`path_size`）。
    以前只有权重文件写了 expect，于是目录型条目（custom_nodes/*、models/FlashVSR-v1.1…）
    在界面上全是「-」—— 用户看到的是一列半空的大小列。现在无论文件还是目录，
    都按磁盘真实占用显示（目录递归合计）。
    """
    rows = []
    for it in dl.DEPLOY_ITEMS:
        root = _resolve_deploy_root(cfg, it.get("root", "comfy_dir"))
        # 判定清单：多数项写死在 部署清单 里；「工作流目录」留空 = 以部署仓库 workflows/
        # 实际有哪些 json 为准（动态），这样上游加工作流不用改代码。
        # 文件名要带 WORKFLOW_PREFIX —— 「恢复」铺的就是带前缀的名字（防与画布原件撞名）。
        checks = list(it["check"])
        if not checks and it.get("restore") == "workflows":
            checks = ["user/default/workflows/" + WORKFLOW_PREFIX + fn for fn in workflow_files(cfg)]
        if not checks:
            rows.append((it["key"], it["name"], "缺失",
                         "部署仓库里没找到 workflows 目录，无法判定", None, 0, it["script"]))
            continue
        # expect 支持三种写法：None / 整数 / 与 check 等长的元组（H3 双 VAE 两文件大小不同）
        expect_list = dl.expects_of(it) if it["check"] else [None] * len(checks)
        total_expect = sum(x for x in expect_list if x) or None
        if not root or not os.path.isdir(root):
            rows.append((it["key"], it["name"], "缺失",
                         "根目录未配置/不存在：" + str(root or it.get("root", "")),
                         total_expect, 0, it["script"]))
            continue
        missing, partial, actual = [], False, 0
        for rel, exp in zip(checks, expect_list):
            p = os.path.join(root, rel)
            if not os.path.exists(p):
                missing.append(rel)
                continue
            sz = path_size(p)
            actual += sz
            if exp and sz < exp:
                partial = True
        if missing:
            note = "缺：" + "、".join(missing)
            if partial:
                note += "；且部分文件大小不足（可能下了一半）"
            status = "不完整" if partial else "缺失"
        elif partial:
            status = "不完整"
            note = "文件存在但大小不足（可能下了一半）"
        else:
            status = "就绪"
            note = ""
        rows.append((it["key"], it["name"], status, note, total_expect, actual, it["script"]))
    return rows


def path_size(p):
    """文件 → 自身字节数；目录 → 递归合计；不存在 → 0。

    走 os.scandir 而不是 os.walk + getsize：实测 ComfyUI-Manager（14.8 MB / 上千文件）
    只要 36 ms，15 项全量探测不到 100 ms，主线程直接算不会卡。
    """
    try:
        if os.path.isfile(p):
            return os.path.getsize(p)
        if not os.path.isdir(p):
            return 0
    except OSError:
        return 0
    total = 0
    stack = [p]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as entries:
                for e in entries:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total


# 「恢复」铺进 ComfyUI 工作流目录的文件名前缀。
# 为什么必须加（2026-10-30 实测）：那个目录里的同名文件是**画布原件**（UI 格式，
# 如 MiniMax-H3-图生视频I2V.json 有 69 KB），仓库里是**API 图**（同名、只有 6.9 KB）。
# 不加前缀的话，目录被清空后点一次「恢复」，API 图就会顶替画布原件的名字 ——
# 之后「加载到画布」打开的是一张空图，而且没有任何报错。
WORKFLOW_PREFIX = "[API] "

# 这些子目录里的 json 是残次品/重叠档（见根 .gitignore），仓库不留、也不铺进 ComfyUI
SKIP_WORKFLOW_DIRS = ("_弃用-工作流",)


def workflow_files(cfg):
    """部署仓库 `workflows/` 下所有 json 的**文件名**（扁平，不带前缀）。

    为什么扁平：启动器扫工作流目录只看顶层（`scan_workflows` 用 `os.listdir`），
    而仓库里是按 FlashVSR / SeedVR2 / MiniMax 分子目录存的 —— 铺的时候必须压平。
    """
    src = os.path.join(str((cfg or {}).get("deploy_root", "") or ""), "workflows")
    out = []
    for dirpath, dirnames, files in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in SKIP_WORKFLOW_DIRS]
        for fn in files:
            if fn.lower().endswith(".json"):
                out.append(fn)
    return sorted(set(out))


def restore_workflows(cfg):
    """把部署仓库 workflows/ 下的 json 铺进 ComfyUI 的工作流目录（幂等：已存在就跳过）。

    文件名加 `WORKFLOW_PREFIX`：目录里的同名文件可能是画布原件（UI 格式），
    绝不能被仓库的 API 图顶替（见 WORKFLOW_PREFIX 的注释）。
    返回 (复制数, 跳过数, 说明)。目录不存在会自动建 —— 这正是「工作流目录缺失」时的修复动作。
    """
    dep_root = str((cfg or {}).get("deploy_root", "") or "")
    src = os.path.join(dep_root, "workflows")
    if not os.path.isdir(src):
        return 0, 0, "部署仓库里没有 workflows 目录：%s" % src
    dst = workflows_dir(cfg)
    if not dst:
        return 0, 0, "comfy_dir 没配置，无法定位工作流目录"
    os.makedirs(dst, exist_ok=True)
    copied = skipped = 0
    for dirpath, dirnames, files in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in SKIP_WORKFLOW_DIRS]
        for fn in files:
            if not fn.lower().endswith(".json"):
                continue
            target = os.path.join(dst, WORKFLOW_PREFIX + fn)
            if os.path.exists(target):
                skipped += 1
                continue
            try:
                shutil.copy2(os.path.join(dirpath, fn), target)
                copied += 1
            except OSError as exc:
                return copied, skipped, "复制失败：%s（%s）" % (fn, exc)
    return copied, skipped, "工作流目录：%s" % dst


def _resolve_deploy_root(cfg, root):
    """把 部署清单 的 root 字段解析成实际目录。

    root 可能是：配置键名（"comfy_dir"/"ffmpeg_dir"，取 cfg 值）或绝对路径（如 Video2X 的 C:\\AI\\Video2X）。
    """
    if not root:
        return ""
    if os.path.isabs(root):
        return root
    val = cfg.get(root, "")
    return str(val) if val else ""




# ================================================================ 模型文件补下（P1/P2）
# 源优先级（2026-10-26 实测，同一文件 vae/minimax_h3_video_vae_int8_convrot.safetensors）：
#   · ModelScope 单连接 **15.4 MB/s**（国内 CDN）
#   · hf-mirror 单连接 **0.47 MB/s**，8 连接并行才 2.1 MB/s
#   · 本地 Clash 代理直连 huggingface 更差（0.56 MB/s / 4 连接 0.76 MB/s）
# 两家同一个模型的文件**字节数完全一致**（20970379616 / 1956193000 / 15687142551 /
# 605254808 / 2811065184 逐项核对过），所以可以按"先 ModelScope、失败再 hf-mirror"来下。
HF_ENDPOINT = (os.environ.get("HF_ENDPOINT") or "https://hf-mirror.com").rstrip("/")
MS_ENDPOINT = (os.environ.get("MS_ENDPOINT") or "https://modelscope.cn").rstrip("/")


def _curl_exe():
    """curl.exe 从 Win10 1803 起内置在 System32（curl.se 官方史已核）；优先用绝对路径。"""
    p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "curl.exe")
    return p if os.path.isfile(p) else "curl.exe"


# ---------------------------------------------------------------- 代理自动探测（P1）
# 本机实测（common.ps1 注释，2026-09-24）：hf-mirror 直连 0.04 MB/s、走 Clash 3.07 MB/s（差 75 倍）。
# common.ps1 的 Get-HfProxy 依次试 7890 / 7891 / 10809 / 1080；这里同口径移植到 Python。
# 约定：HF_PROXY=none 强制直连，HF_PROXY=http://... 显式指定，未设置时自动探测。
PROXY_CANDIDATES = (
    ("127.0.0.1", 7890, "Clash"),
    ("127.0.0.1", 7891, "Clash 混合端口"),
    ("127.0.0.1", 10809, "v2rayN"),
    ("127.0.0.1", 1080, "SOCKS/通用"),
)


def detect_proxy(timeout=0.35):
    """探测本机常见代理端口，返回 (代理 URL, 名字)；都没有返回 ("", "")。"""
    for host, port, name in PROXY_CANDIDATES:
        try:
            with socket.create_connection((host, port), timeout):
                return "http://%s:%d" % (host, port), name
        except OSError:
            continue
    return "", ""


def effective_proxy():
    """下载用代理：HF_PROXY 显式优先，`none` = 强制直连，未设置则自动探测。

    只用于**外网下载**。探测 ComfyUI（127.0.0.1:8188）仍必须绕代理
    （Clash 会把本地地址也代理掉并返回 502），别把这里的结果用到 http_json 上。
    """
    env = (os.environ.get("HF_PROXY") or "").strip()
    if env.lower() == "none":
        return ""
    if env:
        return env
    return detect_proxy()[0]


# 国内 CDN：绕代理只会更慢，必须直连。其余源（hf-mirror / GitHub）反过来靠代理续命。
DIRECT_SOURCES = ("ModelScope",)


def proxy_for(source):
    """按下载源决定代理地址：国内 CDN 直连，其余源用探测到的代理。

    为什么要分治（2026-10-30 实测，同一 H3 扩散模型）：
      · ModelScope **8 段直连 98.4 MB/s**，经 Clash **只有 3.3 MB/s** —— 差 30 倍，
        20 GB 会从 3 分钟变成 1.7 小时；
      · hf-mirror 相反：直连 0.04~0.43 MB/s 还假死，走代理 3.07 MB/s。
    `HF_PROXY=http://…` 显式指定时对所有源生效（用户说了算），`none` 全部直连。
    """
    env = (os.environ.get("HF_PROXY") or "").strip()
    if env.lower() == "none":
        return ""
    if env:
        return env
    if source in DIRECT_SOURCES:
        return ""
    return detect_proxy()[0]


def proxy_hint():
    """启动日志用的一句话：代理是谁 / 没探测到。"""
    env = (os.environ.get("HF_PROXY") or "").strip()
    if env.lower() == "none":
        return "（HF_PROXY=none，强制全部直连）"
    if env:
        return "（HF_PROXY 指定，所有源都走它）"
    url, name = detect_proxy()
    if url:
        return "（自动探测：%s %s；ModelScope 仍直连）" % (name, url)
    return "（未探测到代理，全部直连）"


def hf_sources(repo, path):
    """按优先级给候选源：[(名字, url), ...]。

    `HF_SOURCE=ms|hf` 可强制走某一家（排查用）。
    """
    quoted = _url_quote(path)
    ms = "%s/api/v1/models/%s/repo?Revision=master&FilePath=%s" % (MS_ENDPOINT, repo, quoted)
    hf = "%s/%s/resolve/main/%s" % (HF_ENDPOINT, repo, quoted)
    force = (os.environ.get("HF_SOURCE") or "auto").strip().lower()
    if force == "ms":
        return [("ModelScope", ms)]
    if force == "hf":
        return [("hf-mirror", hf)]
    return [("ModelScope", ms), ("hf-mirror", hf)]


def _probe_total(url, timeout=12, proxy=""):
    """取文件总字节数：Range 0-0 读 Content-Range 的尾部。失败返回 0。

    不用 `curl -w`（本机实测带 `-w` 会假失败：exit 43 + http_code 000），只看响应头。
    探测也要跟着源的代理策略走：hf-mirror 直连可能十几秒都读不出响应头（见 proxy_for）。
    """
    cmd = [_curl_exe(), "-sL", "--fail", "-r", "0-0", "-D", "-",
           "--max-time", str(timeout), "-o", os.devnull]
    if proxy and proxy.lower() != "none":
        cmd += ["-x", proxy]
    cmd.append(url)
    try:
        r = subprocess.run(cmd,
                           capture_output=True, text=True, errors="replace",
                           creationflags=NO_WINDOW)
    except Exception:
        return 0
    total = 0
    for line in (r.stdout or "").splitlines():
        low = line.lower()
        if low.startswith("content-range:") and "/" in low:
            tail = low.rsplit("/", 1)[-1].strip()
            if tail.isdigit():
                total = int(tail)      # 多级重定向时取最后一个
    return total


def hf_pull(repo, path, dest_path, expect=None, on_progress=None, sha256=None):
    """补下单个文件，返回 (ok, 最终大小, 说明)。

    实测选型（2026-10-26，同一文件 vs 本地 200M 宽带）：
      · 源：ModelScope 单连接 15 MB/s（峰值 50+）vs hf-mirror 0.43 MB/s —— 差 35 倍，**优先 ModelScope**；
      · 传输：大文件走**分段并行**（`HF_CONNECTIONS`，默认 8）。CDN 单连接会"先快后限速"
        （实测从 50 MB/s 掉到 11 MB/s），多连接能把每段的限速绕开；
      · 断点续传：已有单连接半成品就继续单连接补（不换源、不改分段，避免拼接坏文件）；
        分段下载的续传粒度是"每个 part 文件自己的大小"；
      · 代理：**按源分治**（`proxy_for`）—— ModelScope 直连、其余源才走探测到的代理。
        2026-10-30 实测：同一 20.97 GB 文件，ModelScope 经 Clash 只有 3.3 MB/s，
        直连才有 98 MB/s 量级；`HF_PROXY=…` 显式指定时对两个源都生效。
    """
    path = path.replace("\\", "/")
    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
    if expect and os.path.exists(dest_path) and os.path.getsize(dest_path) >= expect:
        if not sha256:
            return True, os.path.getsize(dest_path), "已存在且大小达标，跳过"
        if _sha256_file(dest_path).lower() == sha256.lower():
            return True, os.path.getsize(dest_path), "已存在且校验通过，跳过"
        _quarantine(dest_path)          # 大小对但校验不过 = 之前拼坏的残件，改名别再续传

    try:
        segments = int(os.environ.get("HF_CONNECTIONS", "8") or 8)
    except ValueError:
        segments = 8

    last = "无可用下载源"
    for name, url in hf_sources(repo, path):
        proxy = proxy_for(name)          # 每个源各有各的代理策略，别拿一个值套到底
        via = ("经代理 %s" % proxy) if proxy else "直连"
        total = _probe_total(url, proxy=proxy)
        if not total:
            last = "%s 探测失败（文件不存在或无响应）" % name
            continue
        if expect and total != expect:
            last = "%s 大小不符：远端 %s ≠ 期望 %s" % (
                name, human_size(total), human_size(expect))
            continue
        if segments > 1 and total > 64 * 1024 * 1024:
            ok, size, msg = _parallel_download(url, dest_path, total, segments,
                                               on_progress, proxy)
        else:
            ok, size, msg = _curl_download(url, dest_path, total, on_progress, proxy)
        if ok:
            if not sha256:
                return True, size, "%s · %s · %s" % (name, msg, via)
            got = _sha256_file(dest_path)
            if got.lower() == sha256.lower():
                return True, size, "%s · %s · sha256 校验通过 · %s" % (name, msg, via)
            _quarantine(dest_path)
            return False, size, "%s · 校验失败（%s… ≠ %s…），已改名 .bad，请重下" % (
                name, got[:12], sha256[:12])
        last = "%s：%s" % (name, msg)
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            return False, os.path.getsize(dest_path), last   # 已有半成品，别换源拼接
        if os.path.isdir(dest_path + ".parts"):
            break                                            # 分段有进度，也别换源
    return False, (os.path.getsize(dest_path) if os.path.exists(dest_path) else 0), last


def _parallel_download(url, dest_path, total, segments, on_progress, proxy=""):
    """分段并行下载：把 [已有字节, total) 切成 N 段，每段一个 curl Range，
    写 `<dest>.parts/partNN`，全部凑齐后顺序追加到目标文件。

    两个关键设计：
      · **续传粒度 = 每个 part 自己的大小**。curl 自带的 `-C -` 偏移是相对整份文件的，
        跟 `-r a-b` 的分段起点冲突，所以这里自己算偏移、用追加写（stdout → ab 文件句柄）。
      · **已有半成品能接着用**：dest 已存在 S 字节时，只对 [S, total) 切段，最后追加即可——
        这样"单连接爬到一半卡住"的文件也能直接转成分段并行收尾。
    """
    part_dir = dest_path + ".parts"
    os.makedirs(part_dir, exist_ok=True)
    base = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
    if base >= total:
        return True, base, "完成 %s（已存在）" % human_size(base)
    span = total - base
    seg = span // segments
    if seg <= 0:
        return False, base, "剩余数据太少，不值得分段"
    plan = []
    for i in range(segments):
        start = base + i * seg
        end = total - 1 if i == segments - 1 else (base + (i + 1) * seg - 1)
        plan.append((start, end, os.path.join(part_dir, "part%02d" % i)))

    def done_bytes():
        n = base
        for _s, _e, p in plan:
            if os.path.exists(p):
                n += min(os.path.getsize(p), _e - _s + 1)
        return n

    procs = []
    for start, end, part in plan:
        got = os.path.getsize(part) if os.path.exists(part) else 0
        seg_len = end - start + 1
        if got >= seg_len:
            continue
        cmd = [_curl_exe(), "-sL", "--fail",
               "--retry", "8", "--retry-delay", "5", "--retry-all-errors",
               "--connect-timeout", "30",
               "-r", "%d-%d" % (start + got, end), url]
        if proxy and proxy.lower() != "none":
            cmd += ["-x", proxy]
        fh = open(part, "ab")
        procs.append((subprocess.Popen(cmd, stdout=fh, stderr=subprocess.PIPE,
                                      creationflags=NO_WINDOW), fh))

    last = -1
    while any(p.poll() is None for p, _f in procs):
        time.sleep(1.0)
        cur = done_bytes()
        if on_progress and cur != last:
            last = cur
            try:
                on_progress(cur, total)
            except Exception:
                pass
    for p, fh in procs:
        try:
            fh.close()
        except Exception:
            pass
    for start, end, part in plan:            # 段大小不对（服务器忽略 Range）就别往下走
        want = end - start + 1
        got = os.path.getsize(part) if os.path.exists(part) else 0
        if got != want:
            return False, done_bytes(), "分段不完整（%s：%d/%d B）" % (
                os.path.basename(part), got, want)

    with open(dest_path, "ab") as out:
        for _s, _e, part in plan:
            with open(part, "rb") as f:
                shutil.copyfileobj(f, out, 1 << 20)
    size = os.path.getsize(dest_path)
    if size != total:
        return False, size, "合并后大小不符：%s / %s" % (human_size(size), human_size(total))
    shutil.rmtree(part_dir, ignore_errors=True)
    return True, size, "分段并行 %d 路 · 完成 %s" % (len(plan), human_size(size))


def _sha256_file(path):
    """整文件 sha256。20 GB 全量哈希约 1 分钟（本地 NVMe 实测 ~350 MB/s），只在下载完成后跑一次。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _quarantine(path):
    """校验失败的残件改名，别让它被下次"续传"当成正常前缀接着拼。"""
    try:
        os.replace(path, path + ".bad")
    except OSError:
        pass


def _curl_download(url, dest_path, total, on_progress, proxy=""):
    """跑一次 curl 下载（支持续传），每秒回报进度。返回 (ok, 大小, 说明)。"""
    cmd = [_curl_exe(), "-L", "--fail", "-C", "-",
           "--retry", "8", "--retry-delay", "5", "--retry-all-errors",
           "--connect-timeout", "30", "-o", dest_path]
    if proxy and proxy.lower() != "none":
        cmd += ["-x", proxy]
    cmd.append(url)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=NO_WINDOW)
    last = -1
    while proc.poll() is None:
        time.sleep(1.0)
        cur = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
        if on_progress and cur != last:
            last = cur
            try:
                on_progress(cur, total)
            except Exception:
                pass                       # 进度回调坏了不能拖垮下载
    try:
        tail = (proc.stdout.read() or b"").decode("utf-8", "replace").strip()
    except Exception:
        tail = ""
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
    size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
    if proc.returncode != 0:
        return False, size, "curl 退出码 %s：%s" % (proc.returncode, _curl_tail(tail))
    if total and size < total:
        return False, size, "大小不足：%s / %s（再点一次会断点续传）" % (
            human_size(size), human_size(total))
    return True, size, "完成 %s" % human_size(size)


def _curl_tail(tail):
    """curl 把进度条也写在 stderr：去掉 `100 500k ...` 这类行，只留真正的错误。"""
    keep = [ln.strip() for ln in tail.splitlines()
            if ln.strip() and "--:--" not in ln and "%" not in ln]
    return " | ".join(keep[-3:])[:200]


def _url_quote(s):
    from urllib.parse import quote
    return quote(s, safe="/")


# ================================================================ 磁盘空间预检（P2）
def disk_free(path):
    """目标路径所在盘的可用字节；路径还不存在时向上找最近存在的祖先。"""
    p = os.path.abspath(path or ".")
    while p and not os.path.exists(p):
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return 0


def disk_check(cfg, item):
    """安装/下载前的空间预检，返回 (ok, 可用, 需要, 目标根)。

    need 取值优先级：expect 之和（权重类，字节数精确）→ install_bytes（脚本类估算）。
    两样都没有（底座/节点等体积未知）时 need=0，直接放行 —— 不假装知道体积。
    """
    root = _resolve_deploy_root(cfg, item.get("root", "comfy_dir"))
    need = 0
    if item.get("expect"):
        need = sum(x for x in dl.expects_of(item) if x)
    elif item.get("install_bytes"):
        need = int(item["install_bytes"])
    free = disk_free(root)
    return ((free >= need) if need else True), free, need, root


# ================================================================ GitHub 资产下载（P1：镜像回退）
# 国内直连 GitHub releases 常被卡；ghproxy 系镜像对 release 资产有效（handoff §2.3）。
GH_MIRRORS = ("https://ghproxy.net/", "https://gh-proxy.com/")


def gh_mirrors(url):
    """候选下载地址：原始直连 + 两个镜像前缀。"""
    return [url] + [m + url for m in GH_MIRRORS]


def gh_download(url, dest_path, expect=None, on_progress=None):
    """从 GitHub 资产地址下载（curl 续传 + 镜像回退），返回 (ok, 大小, 说明)。

    镜像与直连拿到的是同一份文件，所以某一路断在中途时，下一路能接着 `curl -C -` 续传。
    """
    proxy = effective_proxy()
    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
    last = "无可用下载地址"
    for cand in gh_mirrors(url):
        host = cand.split("/")[2] if "//" in cand else cand
        total = _probe_total(cand) or (expect or 0)
        ok, size, msg = _curl_download(cand, dest_path, total, on_progress, proxy)
        if ok and (not expect or size >= expect):
            return True, size, "%s · %s" % (host, msg)
        last = "%s：%s" % (host, msg)
    size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
    return False, size, last


# ================================================================ ffmpeg 一键装（P2）
# BtbN 的 win64-gpl 构建含 rawvideo + libx264/libx265（SeedVR2 要求的就是能力，不是"有没有 ffmpeg"）。
FFMPEG_ASSET = ("https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/"
                "ffmpeg-master-latest-win64-gpl.zip")


def ffmpeg_capable(exe):
    """能力探测：能读 rawvideo + 能编 libx265。AGENTS 明确不许只看文件是否存在。"""
    def _has(args, needle):
        try:
            r = subprocess.run([exe, "-hide_banner"] + args, capture_output=True, text=True,
                               errors="replace", creationflags=NO_WINDOW, timeout=20)
        except Exception:
            return False
        return needle in (r.stdout or "") + (r.stderr or "")
    return _has(["-demuxers"], "rawvideo") and _has(["-encoders"], "libx265")


def install_ffmpeg(cfg, on_progress=None):
    """下载 BtbN 完整版 ffmpeg 并铺到 ffmpeg_dir，返回 (ok, 说明)。

    只把 exe 放进目标目录，**不改注册表级 PATH** —— PATH 由用户按手册常见问题第 8 条自行添加
    （程序擅自改系统环境变量属于越权，也难回滚）。
    """
    target = str(cfg.get("ffmpeg_dir") or "")
    if not target:
        return False, "ffmpeg 目录未配置"
    exe = os.path.join(target, "ffmpeg.exe")
    if os.path.isfile(exe) and ffmpeg_capable(exe):
        return True, "已存在完整版 ffmpeg，跳过"
    tmp_zip = os.path.join(tempfile.gettempdir(), os.path.basename(FFMPEG_ASSET))
    if os.path.exists(tmp_zip):
        try:
            os.remove(tmp_zip)          # 上次残件可能来自不同镜像，重下更稳
        except OSError:
            pass
    ok, size, msg = gh_download(FFMPEG_ASSET, tmp_zip, on_progress=on_progress)
    if not ok:
        return False, "下载失败：%s" % msg
    try:
        with zipfile.ZipFile(tmp_zip) as z:
            members = [n for n in z.namelist()
                       if n.endswith("/bin/ffmpeg.exe") or n.endswith("/bin/ffprobe.exe")]
            if len(members) < 2:
                return False, "压缩包里没有 bin/ffmpeg.exe + ffprobe.exe"
            os.makedirs(target, exist_ok=True)
            for m in members:
                with z.open(m) as src, open(os.path.join(target, os.path.basename(m)), "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
    except (zipfile.BadZipFile, OSError) as exc:
        return False, "解压失败：%s" % exc
    finally:
        try:
            os.remove(tmp_zip)
        except OSError:
            pass
    if not ffmpeg_capable(exe):
        return False, "已解压但能力探测不过（缺 rawvideo 或 libx265）"
    return True, "已安装到 %s（%s）" % (target, human_size(size))
