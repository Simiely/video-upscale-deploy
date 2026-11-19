# 问题：PowerShell 5.1 把中文脚本读成乱码

**TL;DR**：`.ps1` 存成 UTF-8 **without** BOM，PowerShell 5.1 按 ANSI 解码，中文变乱码并直接解析失败。

- 问题：含中文注释/字符串的脚本执行时报语法错误，报错位置和实际错误位置对不上
- 根因：PowerShell 5.1 判断文件编码时不看内容只看 BOM；无 BOM 就退回系统 ANSI 代码页
- 解决：把文件另存为 **UTF-8 with BOM**（写入时先写 `EF BB BF` 三字节）
- 预防：改完 `.ps1` 跑一次 BOM 检查（命令见 [AGENTS.md](../../AGENTS.md)「常用命令」）