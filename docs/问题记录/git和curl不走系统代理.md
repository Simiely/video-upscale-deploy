# 问题：git / curl 不走系统代理，GitHub 直连被重置

**TL;DR**：本机代理是 `127.0.0.1:7890`，但 `git`/`curl` 默认不读系统代理，git 协议连 GitHub 偶尔直接失败。（源自 `seedvr2-local-deploy`）

- 现象：`git clone` 卡住 / 被 reset；权重下载失败。
- 解决：`git`/`curl` 显式 `-x http://127.0.0.1:7890`；克隆节点改用 zip 包而非 git 协议。
- 预防：下载节点 / 权重前先确认代理链路能通。