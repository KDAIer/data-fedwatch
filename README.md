# FedWatch Scraper

自动化下载 CME FedWatch Tool 页面中「Historical → Downloads」区域的历史概率文件（CSV）。脚本会自动打开页面、接受 Cookie、关闭遮挡弹窗，滚动并进入 Downloads 视图，然后依次点击页面上的下载卡片，将文件保存到本地 `downloads/` 目录。

目标页面：
[CME FedWatch Tool](https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html)

## 功能

- 自动进入 FedWatch 页面并处理 Cookie 同意与覆盖弹窗。
- 自动定位到「Historical → Downloads」板块。
- 不依赖日期文本，直接扫描并点击下载卡片，获取全部 CSV 文件。
- 自动创建 `downloads/` 目录并按建议文件名保存；若重名自动追加序号。

## 目录结构

- `fedwatch_scraper.py`：主脚本（Playwright for Python）。
- `downloads/`：下载产出目录（运行时自动创建）。
- `README.md`：本文档。

## 环境要求

- Windows 10/11，PowerShell（默认即可）。
- Python 3.9+（推荐 3.10/3.11）。
- 可访问公网以下载 Playwright 浏览器驱动。

## 快速开始（Windows PowerShell）

1. 进入项目目录：

   ```powershell
   cd fedwatch_scraper
   ```
2. 创建并启用虚拟环境：

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -U pip
   ```
3. 安装依赖并安装浏览器驱动：

   ```powershell
   python -m pip install playwright
   python -m playwright install
   ```
4. 运行脚本：

   ```powershell
   python .\fedwatch_scraper.py
   ```

首次运行会弹出一个有界面浏览器窗口（脚本默认使用非无头模式，便于观察与排障）。如需静默运行，可将脚本中的 `headless=False` 改为 `True`。

## 运行说明（脚本做了什么）

1. 打开 FedWatch 页面，等待加载完成。
2. 点击 OneTrust Cookie「接受」按钮（若存在）。
3. 关闭左下角「Visualize the Pace of the Treasury Roll」弹窗（若无法定位，则以 JS 强制隐藏）。
4. 定位并点击侧边栏的「Downloads」入口（必要时遍历 iframe）。
5. 在 Downloads 区域扫描所有下载卡片链接（包括「All upcoming meetings」）。
6. 逐个点击触发下载，将文件保存到 `downloads/` 目录。

## 常见问题与排障

- net::ERR_HTTP2_PROTOCOL_ERROR 或页面长时间无响应：

  - 这通常是网络不稳定或被目标站点限流导致，可稍后重试，或切换网络环境。
  - 也可以把浏览器切换为有头模式（当前默认即为有头）以观察页面渲染是否被弹层遮挡。
- 未能进入 Downloads 页面 / 未找到「Downloads」：

  - 页面主体在 iframe 中，脚本已包含遍历 frame 的逻辑；若站点改版，请在 `fedwatch_scraper.py` 中调整定位器（搜索“Downloads”相关代码片段）。
- 没有任何文件下载：

  - 检查页面是否有浮层遮挡（脚本会尝试关闭/隐藏）。
  - 打开开发者工具观察下载链接是否被站点改为异步 API 调用，必要时可在脚本中监听 `page.on('response', ...)` 捕获真实下载地址。
- 浏览器驱动未安装/版本不匹配：

  - 执行：`python -m playwright install`（需在已激活的虚拟环境中）。

## 法律与合规

请确保遵守 CME Group 网站的使用条款与 robots 协议，合理控制抓取频率，仅用于合法合规的研究或内部使用。若对方网站结构或条款变更，请自行评估并调整脚本。
