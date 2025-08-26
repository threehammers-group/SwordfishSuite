# SwordfishSuite

[![GitHub license](https://img.shields.io/github/license/threehammers-group/SwordfishSuite)](https://github.com/threehammers-group/SwordfishSuite)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/threehammers-group/SwordfishSuite/pulls)

**SwordfishSuite** 是一款受 Burp Suite 启发的现代化 Web 安全测试平台。它集成了智能代理、流量拦截、负载扫描和强大的插件系统，旨在为安全研究人员和渗透测试工程师提供一款高效、可定制的应用利器。

## ✨ 核心特性

- **智能拦截代理**：无缝拦截、查看和修改 HTTP/HTTPS 流量，支持多种客户端，操作流畅直观。
- **集成APP分析**：可集成云手机平台，直接在SwordfishSuite查看分析手机APP流量（暂不开放）。
- **可扩展插件系统**：基于 Python 的完整插件生态，允许您轻松编写自定义扫描检查器和数据分析工具。
- **GUI界面操作**：提供用户友好的图形化界面 (GUI) 以满足交互式测试需求。
- **流量数据转发**：支持流量二次转发（原始流量和HAR格式），方便各种扩展。

## 🚀 快速开始

### 前置要求

在运行 SwordfishSuite 之前，如果你需要自己开发插件：
- **Python** 3.10 或更高版本
- `pip` 包管理工具

### 安装

1. **从 GitHub 下载Release版本压缩：**
   ```bash
   git clone https://github.com/threehammers-group/SwordfishSuite.git
   cd Swordfish
   ./Swordfish.exe
   ```


### 如何使用

1. **启动应用：**
   - **GUI 模式 (推荐):**
     ```bash
     ./Swordfish.exe或鼠标双击即可
     ```

2. **安装证书：**
   第一次启动程序，点击工具栏安装证书按钮，CA 证书以支持 HTTPS 解密(证书存储位置->本地计算机->指定下列存储->受信任的根证书颁发机构->完成)
   

3. **开始探索！**
   点击工具栏开始按钮，拦截流量，重放请求，使用负载测试器，或者开发新插件定制自己的专属功能。

## 📖 文档

有关更详细的文档，包括高级配置、插件开发指南和故障排除，请访问我们的 [Wiki](https://github.com/threehammers-group/SwordfishSuite/wiki)。

## 🤝 参与贡献

我们热烈欢迎任何形式的贡献！无论是提交 Bug、提出新功能、改进文档还是提交 Pull Request。


请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详细的贡献指南。

## 📜 许可证

本项目采用 Apache-2.0 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 💬 联系方式

- **提交 Issue:** [GitHub Issues](https://github.com/threehammers-group/SwordfishSuite/issues)

## 🙏 致谢

感谢 Burp Suite、mitmproxy、Reqable等优秀工具带来的灵感。
特别感谢 Reqable开源的re_editor
感谢所有贡献者和使用者！

---

**免责声明：** 请仅在获得明确授权的目标上使用此工具。开发者对工具的滥用不承担任何责任。
