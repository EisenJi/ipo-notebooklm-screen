# IPO NotebookLM Screen

> 可复用的 A 股与港股 IPO 尽调流水线。
> 收集招股书、同行财报、政策文件；可选推送至 NotebookLM 后端；输出 markdown 形式的参与/观望/放弃决策表。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 目录

- [概述](#概述)
- [特性](#特性)
- [安装](#安装)
- [快速开始](#快速开始)
- [使用方法](#使用方法)
  - [1. 环境检查](#1-环境检查)
  - [2. 编写工作流规格](#2-编写工作流规格)
  - [3. 运行筛选](#3-运行筛选)
  - [4. 通过 NotebookLM 提问](#4-通过-notebooklm-提问)
  - [5. 生成决策表](#5-生成决策表)
- [后端策略](#后端策略)
- [项目结构](#项目结构)
- [依赖](#依赖)
- [自动克隆行为](#自动克隆行为)
- [常见问题](#常见问题)
- [授权](#授权)

---

## 概述

本 skill 将一个指定的 IPO 候选人转化为可复用的尽调材料包，并输出最终的 markdown 决策表。

**默认假设：**

- 你已经有一个目标上市公司。
- 输出是实操性的打新决策，而非学术性总结。
- 最新的官方材料最重要。

**工作流程：**

1. 确定范围 — 发行人名称、上市市场、当前阶段、业务线、同行组。
2. 收集核心决策材料 — 招股书、发行公告、同行报告、政策文件。
3. 构建整洁的材料目录并生成清单。
4. 可选推送至 NotebookLM 后端。
5. 将标准尽调问题改写为发行人专属版本。
6. 按顺序提问并输出 markdown 决策表。

---

## 特性

| 特性 | 说明 |
|---------|-------------|
| **市场感知** | 自动区分 A 股与港股 IPO 的问题集。 |
| **多业务线拆分** | 若不同业务线需要不同同行组，每个线独立创建 notebook。 |
| **PDF 优先** | 优先使用官方 PDF，仅在 PDF 不可获时退而使用 URL。 |
| **后端解耦** | 稳定的 `manifest_only` 路径始终可用；`notebooklm` 仅为可选。 |
| **自动升级** | `auto` 策略在材料规模或复杂度达标时自动切换到 `notebooklm`。 |
| **Source 范围控制** | 通过 `--source-ids` 将每个问题限制在最小相关材料集。 |
| **CLI 不稳定时降级** | 若客户端超时，切换至网页端查看答案，由 Codex 汇总。 |
| **巨潮集成** | `scripts/cninfo_fetch.py` 一键抓取同行报告。 |
| **自动克隆依赖** | 若本地缺少 `notebooklm-client`，skill 自动克隆并构建。 |

---

## 安装

```bash
git clone https://github.com/YOUR_ORG/ipo-notebooklm-screen.git
cd ipo-notebooklm-screen
pip install -r requirements.txt
```

环境要求：

- Python 3.10+
- Node.js 18+
- `git` 与 `npm`（用于自动克隆）

---

## 快速开始

```bash
# 1. 检查环境
python3 scripts/preflight.py

# 2. 复制示例规格并编辑
cp assets/ipo-workflow-spec.example.json my-spec.json
# --- 编辑 my-spec.json，填入发行人、同行、路径 ---

# 3. 运行筛选（默认 manifest_only）
python3 scripts/run_ipo_screen.py --spec my-spec.json

# 4. 或强制使用 NotebookLM 后端
python3 scripts/run_ipo_screen.py --spec my-spec.json --backend notebooklm --backend-policy required
```

---

## 使用方法

### 1. 环境检查

```bash
python3 scripts/preflight.py
```

输出 JSON 报告，覆盖：

- `python3`、`node`、`notebooklm` CLI 可用性
- 本地源码版检测（自动探测或自动克隆）
- Python 依赖状态（`httpx`）
- 已选的文件上传客户端

### 2. 编写工作流规格

参见 `assets/ipo-workflow-spec.example.json` 了解完整模式。最小示例：

```json
{
  "issuer": "示例公司",
  "workspace": "./output/example-corp",
  "backend": "manifest_only",
  "backend_policy": "auto",
  "notebooks": [
    {
      "title": "示例公司 — 核心业务",
      "sources": [
        { "kind": "file", "path": "./prospectus.pdf" },
        { "kind": "url", "url": "https://www.example.com/ir" }
      ]
    }
  ]
}
```

### 3. 运行筛选

```bash
python3 scripts/run_ipo_screen.py --spec my-spec.json
```

脚本执行以下步骤：

1. 根据策略和准备就绪状态确定后端计划。
2. 收集材料（巨潮抓取、本地文件、URL）。
3. 将材料交给选定的后端。
4. 在 workspace 中写入 `run-summary.json`。

### 4. 通过 NotebookLM 提问

若使用了 `notebooklm` 后端：

```bash
# 列出 notebook
notebooklm list --transport http

# 查看详情
notebooklm detail <notebook-id> --transport http

# 添加额外材料
python3 scripts/notebooklm_adapter.py add-file <notebook-id> ./extra-report.pdf
python3 scripts/notebooklm_adapter.py add-url <notebook-id> "https://example.com/page"
```

阅读 `references/question-adaptation.md` 了解如何将标准 8 大问题家族改写为发行人专属版本。

### 5. 生成决策表

最终输出格式由 `assets/decision-table-template.md` 定义，必须包含：

- 一段式发行人摘要
- 分业务线的同行视角
- 正面信号列表
- 红旗列表
- 决策结论：`Participate`、`Watch` 或 `Skip`
- 置信度说明，指出证据薄弱或缺失的部分

---

## 后端策略

| 策略 | 行为 |
|--------|----------|
| `forbid` | 始终保留在 `manifest_only`。 |
| `auto` | 默认值。仅当客户端可用且材料规模达标时才升级到 `notebooklm`。 |
| `required` | 必须使用 `notebooklm`；若客户端不可用则早期报错。 |

`auto` 的自动升级条件：

- notebook 数量 ≥ 2
- 总 source 数量 ≥ 10
- `cninfo_reports` 同行 source ≥ 3
- `analysis_objective` 中明确出现 `NotebookLM`、`source-ids`、节省 token 或多轮分析等目标，且材料规模至少为中等

---

## 项目结构

```
ipo-notebooklm-screen/
├── SKILL.md                          # Codex / Hermes 的 skill 定义
├── README.md                         # 英文文档
├── README.zh.md                      # 中文文档（本文件）
├── requirements.txt                  # Python 依赖
├── assets/
│   ├── decision-table-template.md    # 最终输出格式
│   ├── question-template.md          # 标准 8 大问题家族
│   ├── ipo-workflow-spec.example.json # 示例规格
│   └── ipo_analyst_prompt.txt        # 默认角色提示词
├── references/
│   ├── source-playbook.md            # 材料优先级与市场规则
│   └── question-adaptation.md        # 问题改写指南
└── scripts/
    ├── preflight.py                  # 环境检查
    ├── notebooklm_adapter.py         # 客户端适配器（带自动克隆）
    ├── notebooklm_create.mjs         # 创建 notebook 的辅助脚本
    ├── cninfo_fetch.py               # 巨潮报告抓取器
    ├── backends.py                   # 后端抽象层
    └── run_ipo_screen.py             # 流水线协调器
```

---

## 依赖

**Python：**

- `httpx` — 巨潮抓取与 HTTP 传输

**Node.js：**

- `notebooklm-client` — 若本地不存在，从 [icebear0828/notebooklm-client](https://github.com/icebear0828/notebooklm-client) 自动克隆。

**系统：**

- `git`、`npm`、`node`、`python3`

---

## 自动克隆行为

若本地未找到 `notebooklm-client` 构建版本，skill 会自动克隆至 `~/.codex/skills/notebooklm-client`，并执行 `npm install && npm run build`。

若需要覆盖自动探测路径，可通过环境变量指定：

```bash
export NOTEBOOKLM_CLIENT_ROOT=/path/to/notebooklm-client           # 可选覆盖
export NOTEBOOKLM_CLIENT_ENTRY=/path/to/notebooklm-client/dist/cli.js  # 可选覆盖
export NOTEBOOKLM_CLIENT_INDEX=/path/to/notebooklm-client/dist/index.js  # 可选覆盖
```

---

## 常见问题

| 现象 | 原因 | 解决 |
|---------|-------|-----|
| `No compatible NotebookLM client found` | 缺少 `notebooklm-client` 且自动克隆失败 | 确保已安装 `git` 和 `npm`；或手动克隆仓库 |
| `Selected NotebookLM client cannot create notebooks` | 本地构建缺少 helper 或不支持 `create` | 检查 `scripts/notebooklm_create.mjs` 是否存在；或在规格中提供 `notebook_id` |
| `NotebookLM command failed` | 沙箱中的网络限制 | 在沙箱外运行，或切换到 `manifest_only` |
| `httpx not found` | Python 依赖未安装 | `pip install -r requirements.txt` |

---

## 授权

MIT License — 详见 [LICENSE](LICENSE)。

---

**English docs** → [README.md](./README.md)
