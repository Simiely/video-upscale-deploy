# -*- coding: utf-8 -*-
"""文字规范检查（CI 用，零第三方依赖）。

两条都是这个仓库的铁律，以前只写在 AGENTS 的「常用命令」里靠人记：

1. **`.ps1` 必须是 UTF-8 with BOM**：PowerShell 5.1 判断编码只看 BOM，
   没有就按系统 ANSI（cp936）解码 —— 中文注释会让脚本直接解析失败。
2. **仓库里不得存 CRLF**：`core.autocrlf` 是本地配置、跟克隆时机有关，
   两个副本会不一致（2026-10-30 就因此把 25 个文件误判成"不同"）。
   规则写在根 `.gitattributes`，这里做兜底断言。

退出码 0 = 全部通过；1 = 有违规（CI 会红）。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

BOM = b"\xef\xbb\xbf"


def tracked_files(pattern=None):
    cmd = ["git", "ls-files", "-z"]
    if pattern:
        cmd.append(pattern)
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return [p.decode("utf-8") for p in out.split(b"\0") if p]


def kit_managed():
    """kit 托管文件由 schema/kit.lock.json 按字节哈希锁定，本仓无权改其编码。

    BOM 会让 sha256 变（哈希按原始字节算、只归一化 CRLF），改了就 `KIT LOCK: FAIL`。
    这些文件的编码归上游 repo-kit 管，这里只校验本仓自己写的脚本。
    名单从 lock 读，不手维护 glob——否则等于在 lock 之外再造一份会漂移的清单。
    """
    lock = Path("schema/kit.lock.json")
    if not lock.exists():
        return set()
    return set(json.loads(lock.read_text(encoding="utf-8-sig")).get("files", {}))


def check_bom():
    bad = []
    skip = kit_managed()
    tracked = tracked_files("*.ps1")
    files = [p for p in tracked if p not in skip]
    skipped = len(tracked) - len(files)
    for p in files:
        with open(p, "rb") as fh:
            if fh.read(3) != BOM:
                bad.append(p)
    print("BOM 检查：%d 个 .ps1（跳过 %d 个 kit 托管），违规 %d 个"
          % (len(files), skipped, len(bad)))
    for p in bad:
        print("  [缺 BOM] %s" % p)
    return not bad


def check_eol():
    """index 里出现 CRLF 就说明有文件绕过了 .gitattributes（多半是手工提交的）。"""
    out = subprocess.run(["git", "ls-files", "--eol"], capture_output=True,
                         check=True, text=True, encoding="utf-8", errors="replace").stdout
    bad = []
    for line in out.splitlines():
        if line.startswith("i/crlf") or " i/crlf " in line:
            bad.append(line.split("\t", 1)[-1])
    print("行尾检查：index 内 CRLF 文件 %d 个" % len(bad))
    for p in bad:
        print("  [index 是 CRLF] %s" % p)
    return not bad


def main():
    ok = check_bom()
    ok = check_eol() and ok
    print("\n结果：", "通过" if ok else "有违规")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
