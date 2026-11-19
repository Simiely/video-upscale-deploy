# 问题：用 import_module 做节点冒烟测试永远失败

**TL;DR**：`custom_nodes` 下的目录名带连字符且不是 Python 包，`importlib.import_module("custom_nodes.ComfyUI-FlashVSR_Ultra_Fast")` 必然失败，会误导成"安装失败"。

- 问题：安装脚本的冒烟测试报导入错误，但节点其实是好的
- 根因：测试方法本身不成立——目录名不是合法标识符
- 解决：改用 ComfyUI 自带的 `main.py --quick-test-for-ci`，它会真实加载全部自定义节点后退出
- 预防：验证"节点能否被 ComfyUI 加载"要用 ComfyUI 自己的加载器，不要绕过去手工 import