# -*- coding: utf-8 -*-
"""下载核心：纯分段计划 / 合并，加上一个薄的 curl 外壳。

纯函数（plan_ranges / done_bytes / merge_parts）不碰网络，可单测；
Downloader 只负责 I/O 与子进程，方便替换实现。
"""
import json
import os
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field

from .errors import DownloadError

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(frozen=True)
class Plan:
    total: int
    base: int
    ranges: list = field(default_factory=list)
    tag: str = ""
    asset: str = ""


def plan_ranges(total, base=0, n=16):
    """把 [base, total) 切成最多 n 段，覆盖完整、无重叠。"""
    if total <= 0:
        raise ValueError("total 必须为正")
    base = max(0, min(base, total))
    if base >= total:
        return []
    span = total - base
    n = max(1, min(n, span))
    seg = (span + n - 1) // n
    ranges = []
    start = base
    while start < total and len(ranges) < n:
        end = min(total - 1, start + seg - 1)
        ranges.append((start, end))
        start = end + 1
    return ranges


def make_plan(total, base, tag, asset, n=16):
    return Plan(total=total, base=base, ranges=plan_ranges(total, base, n),
                tag=tag, asset=asset)


def plan_to_dict(plan):
    return asdict(plan)


def plan_from_dict(data):
    if not isinstance(data, dict):
        return None
    try:
        ranges = [tuple(int(x) for x in pair) for pair in data.get("ranges", [])]
        return Plan(total=int(data["total"]), base=int(data.get("base", 0)),
                    ranges=ranges, tag=str(data.get("tag", "")),
                    asset=str(data.get("asset", "")))
    except (KeyError, TypeError, ValueError):
        return None


def load_plan(path, total, tag, asset):
    try:
        with open(path, "r", encoding="utf-8") as f:
            plan = plan_from_dict(json.load(f))
    except (OSError, ValueError):
        return None
    if (not plan or plan.total != total or plan.tag != tag
            or plan.asset != asset):
        return None
    return plan


def save_plan(path, plan):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan_to_dict(plan), f)


def done_bytes(part_dir, plan):
    n = plan.base
    for i, (start, end) in enumerate(plan.ranges):
        p = os.path.join(part_dir, "part%03d" % i)
        if os.path.exists(p):
            n += min(os.path.getsize(p), end - start + 1)
    return n


def merge_parts(zip_path, part_dir, plan):
    mode = "ab" if plan.base and os.path.exists(zip_path) else "wb"
    with open(zip_path, mode) as out:
        for i, (_start, _end) in enumerate(plan.ranges):
            p = os.path.join(part_dir, "part%03d" % i)
            with open(p, "rb") as f:
                shutil.copyfileobj(f, out, 1 << 20)
    return os.path.getsize(zip_path) == plan.total


class Downloader:
    def __init__(self):
        self._procs = []
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            procs = list(self._procs)
        for proc in procs:
            try:
                proc.terminate()
            except Exception:
                pass

    @staticmethod
    def curl_exe():
        path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                            "System32", "curl.exe")
        return path if os.path.isfile(path) else "curl.exe"

    @staticmethod
    def sources(url):
        return ["https://gh.llkk.cc/" + url, url, "https://ghproxy.net/" + url]

    def probe_total(self, url, proxy=""):
        cmd = [self.curl_exe(), "-sL", "--fail", "-r", "0-0", "-D", "-",
               "-o", os.devnull, "--connect-timeout", "15", "--max-time", "25", url]
        if proxy:
            cmd += ["-x", proxy]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                               creationflags=NO_WINDOW, timeout=30)
        except Exception:
            return 0
        for line in (r.stdout or "").splitlines():
            low = line.lower()
            if low.startswith("content-range:") and "/" in low:
                tail = low.rsplit("/", 1)[-1].strip()
                if tail.isdigit():
                    return int(tail)
        return 0

    def download(self, release, target, proxy="", progress=None,
                 stop_event=None, n=16):
        """下载 release.asset 到 target，返回 zip 路径；支持断点续传。"""
        os.makedirs(target, exist_ok=True)
        zip_path = os.path.join(target, release.asset)
        part_dir = zip_path + ".parts"
        plan_path = os.path.join(part_dir, "plan.json")
        sources = self.sources(release.url)
        total = self.probe_total(sources[0], proxy) or self.probe_total(sources[1], proxy)
        if not total:
            raise DownloadError("无法获取文件大小（镜像与直连都失败）")
        if os.path.exists(zip_path) and os.path.getsize(zip_path) >= total:
            return zip_path

        plan = load_plan(plan_path, total, release.tag, release.asset)
        if plan is not None and plan.base and not os.path.exists(zip_path):
            plan = None
        if plan is None:
            shutil.rmtree(part_dir, ignore_errors=True)
            base = os.path.getsize(zip_path) if os.path.exists(zip_path) else 0
            plan = make_plan(total, base, release.tag, release.asset, n)
            save_plan(plan_path, plan)

        self._run_segments(part_dir, plan, sources, proxy, progress, stop_event)
        if stop_event is not None and stop_event.is_set():
            raise DownloadError("已取消")
        if not merge_parts(zip_path, part_dir, plan):
            raise DownloadError("合并后大小不符，再点一次会续传")
        shutil.rmtree(part_dir, ignore_errors=True)
        return zip_path

    def _run_segments(self, part_dir, plan, sources, proxy, progress, stop_event):
        results = []
        results_lock = threading.Lock()

        def worker(idx, start, end):
            part = os.path.join(part_dir, "part%03d" % idx)
            want = end - start + 1
            for src in sources:
                for _attempt in range(2):
                    if stop_event is not None and stop_event.is_set():
                        return
                    got = os.path.getsize(part) if os.path.exists(part) else 0
                    if got >= want:
                        with results_lock:
                            results.append(True)
                        return
                    cmd = [self.curl_exe(), "-sL", "--fail",
                           "--retry", "3", "--retry-delay", "2", "--retry-all-errors",
                           "--connect-timeout", "20",
                           "-r", "%d-%d" % (start + got, end), src]
                    if proxy:
                        cmd += ["-x", proxy]
                    fh = open(part, "ab")
                    proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.DEVNULL,
                                            creationflags=NO_WINDOW)
                    with self._lock:
                        self._procs.append(proc)
                    while proc.poll() is None:
                        if stop_event is not None and stop_event.is_set():
                            proc.terminate()
                            fh.close()
                            return
                        time.sleep(0.2)
                    fh.close()
                    if os.path.getsize(part) >= want:
                        with results_lock:
                            results.append(True)
                        return
            with results_lock:
                results.append(False)

        threads = []
        for idx, (start, end) in enumerate(plan.ranges):
            t = threading.Thread(target=worker, args=(idx, start, end), daemon=True)
            t.start()
            threads.append(t)

        last = -1
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
            done = done_bytes(part_dir, plan)
            mbps = (done - last) / 1048576.0 / 0.5 if last >= 0 else 0
            last = done
            eta = int((plan.total - done) / (mbps * 1048576.0)) if mbps > 0 else 0
            if progress:
                progress(done, plan.total, mbps, eta)
        if (stop_event is None or not stop_event.is_set()) and (
                not results or not all(results)):
            raise DownloadError("部分分段失败；已保留进度，再点一次会续传")
