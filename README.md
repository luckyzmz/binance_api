# 📊 币安合约双向持仓实时监控仪表盘

> 一个轻量级、开源的 Python 工具，用于在 **币安 USDT 合约（双向持仓模式）** 下自动监控持仓盈亏，并在达到设定阈值时自动平仓。内置 Web 仪表盘，支持实时查看仓位、动态调整止盈止损参数，无需重启程序。

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-green?logo=flask)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-orange)](LICENSE)

---

## ✨ 核心功能

- ✅ **双向持仓支持**：独立监控 LONG（多头）和 SHORT（空头）仓位  
- ✅ **自动止盈止损**：当未实现盈亏 ≥ +X USDT 或 ≤ -Y USDT 时自动市价平仓  
- ✅ **实时 Web 仪表盘**：浏览器中查看所有仓位、标记价格、浮动盈亏  
- ✅ **动态参数调整**：无需停止脚本，直接在网页修改止盈/止损值  
- ✅ **自动刷新**：每 3 秒更新一次数据，无需手动刷新页面  
- ✅ **暗色主题 + 响应式设计**：电脑/手机均可流畅使用  
- ✅ **单文件部署**：无数据库，无复杂依赖，开箱即用

---

## 🖼️ 界面预览

> 📌 **仪表盘截图示意**（实际界面为暗色主题）

| 功能区域 | 说明 |
|--------|------|
| 🎛️ 控制面板 | 输入止盈（如 `1.5`）、止损（如 `-1.0`）、检查间隔（秒） |
| 📈 仓位卡片 | 每个币种一个卡片，显示方向、数量、开仓价、标记价、浮动盈亏 |
| 🟢 绿色盈亏 | 盈利时显示绿色 |
| 🔴 红色盈亏 | 亏损时显示红色 |

> 💡 实际部署后访问 `http://你的IP:5000` 即可看到完整界面。

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- 币安账户（已开通 **USDT 合约交易**）
- 币安 API Key（需开启 **交易权限**）
- 系统：Linux / macOS / Windows（推荐 Linux 服务器）

### 2. 克隆项目

```bash
git clone https://github.com/luckyzmz/binance-api.git
cd binance-api
# 安装 venv（Ubuntu/Debian）
sudo apt install python3-venv -y

# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

pip install flask python-binance
编辑脚本文件（如 bot.py），修改以下两行：
API_KEY = '你的币安API_KEY'
API_SECRET = '你的币安API_SECRET'

6. 设置币安账户为 双向持仓模式
登录 币安合约交易
点击左侧「持仓」→「持仓模式」
切换为 「双向持仓」
7. 运行程序

8. 访问 Web 仪表盘
在浏览器打开：
http://你的服务器IP:5000
示例：http://192.168.1.100:5000 或 http://localhost:5000

 使用说明
手动开仓：在币安网页或 APP 上开仓（本程序只负责平仓）
观察仪表盘：开仓后，仓位会自动出现在 Web 页面
调整策略：
在网页修改「止盈目标」（如 2.0）
修改「止损目标」（如 -1.5）
点击「保存设置」立即生效
自动平仓：当任一仓位盈亏达到阈值，程序将自动市价平仓
