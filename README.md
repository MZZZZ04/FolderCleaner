# <img width="256" height="256" alt="app" src="https://github.com/user-attachments/assets/32514641-c155-482b-bbbe-560d8bde8948" />定时清理指定文件夹 (FolderCleaner)


一个 Windows 桌面工具，定时自动清理用户指定文件夹中的冗余文件。适用场景：下载目录、缓存目录、日志目录等容易膨胀的文件夹，设置一次后常驻后台自动维护。

![平台](https://img.shields.io/badge/平台-Windows-blue) ![界面](https://img.shields.io/badge/界面-GUI%20桌面-green) ![技术](https://img.shields.io/badge/Python-3.9-yellow)

---

## 功能特性

| 模块 | 说明 |
|------|------|
| **虚拟路径机制** | 物理路径不变，应用内用虚拟别名管理；一条物理目录可挂多个虚拟条目、复用多套规则 |
| **清理规则** | 按**日期** / **大小** / **类型** / **关键词** / **清空** / **组合条件** / **白名单例外** 共 7 种规则自由搭配 |
| **定时调度** | 常驻后台按周期自动触发（每天 / 每 N 天 / 每周 / 指定日期时刻）；程序启动时自动补偿检查过期任务 |
| **程序内置回收站** | 清理不是直接删除：文件先转入程序回收站暂存，按设定保留时间（默认 7 天）到期才自动清空 |
| **误删恢复** | 回收站内文件可随时一键恢复到原路径，清理日志全程可追溯 |
| **占用文件保护** | 正在被其他程序使用的文件自动跳过，不误清理 |
| **系统路径保护** | 系统保护路径（Windows、Program Files 等）禁止设为清理目标 |
| **界面形式** | 图形面板（5 大页面）+ 系统托盘常驻 + 桌面通知 |
| **跨电脑可移植** | 单文件 exe 复制到任意电脑双击即用，无需安装 Python；程序启动自动创建数据目录和回收站 |

---

## 使用方式

### 方式一：直接运行（免安装）

把 `dist/FolderCleaner.exe` 复制到任意位置（或 U 盘/移动硬盘），双击即可使用，无需安装任何依赖。

### 方式二：安装程序

运行 `dist/installer/FolderCleaner_Setup.exe`（全中文安装向导，带一键卸载，卸载时默认保留用户数据）。

### 方式三：从源码运行

需要 Python 3.9 + 以下依赖：

```bash
pip install PySide6 APScheduler
python launcher.py
```

---

## 项目结构

```
src/
├── main.py               # 程序入口（含启动画面）
├── config.py             # 全局配置 / 数据目录 / 回收站定位
├── database.py           # SQLite 数据层
├── models.py             # 数据模型
├── scheduler.py          # 定时调度
├── cleaner/
│   ├── rules.py          # 清理规则扫描
│   ├── engine.py         # 清理引擎
│   └── recycle.py        # 程序内置回收站
├── ui/                   # 界面（主窗口 / 5 页面 / 弹窗 / 托盘）
└── utils/
tests/                    # pytest 单元测试（22 项）
```

---

## 技术栈

- **Python 3.9**
- **PySide6** — 图形界面
- **APScheduler** — 定时调度
- **SQLite** — 数据存储
- **PyInstaller** — 打包单文件 exe
- **Inno Setup** — 安装程序

---

## 截图

<img width="922" height="652" alt="bandicam 0065" src="https://github.com/user-attachments/assets/f90f371a-c222-4978-9967-7263f58713ea" />
<img width="922" height="652" alt="bandicam 0064" src="https://github.com/user-attachments/assets/0bcd57ed-97a4-4b35-b23e-2b7b9bdb2426" />
<img width="922" height="652" alt="bandicam 0063" src="https://github.com/user-attachments/assets/b82b287f-cdbe-4144-b904-3a86a7bf656e" />
<img width="922" height="652" alt="bandicam 0062" src="https://github.com/user-attachments/assets/2df7801d-3081-4918-8f6f-0a4e7bb4b4bb" />
<img width="922" height="652" alt="bandicam 0066" src="https://github.com/user-attachments/assets/d441751a-cb9e-42f1-bf6f-1da9ab374b68" />


---

## 更新记录

完整更新记录见项目文档《更新表》（未随源码上传）。最近版本：

- **v1.20** 项目目录整理
- **v1.19** Inno Setup 安装程序 + 一键卸载（全中文安装界面）
- **v1.18** 跨电脑可移植性加固（exe 复制即用，回收站自动回退）
- **v1.17** exe 文件名改为英文 FolderCleaner（界面保持中文）
- **v1.16** 启动画面 + 设置页显示默认回收站路径
