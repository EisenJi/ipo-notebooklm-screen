# IPO NotebookLM Screen 使用说明

这是一个用于 **将上市公司材料收集、交给可选 backend 处理、并产出打新决策表** 的 skill。

## 灵感来源

这个 skill 的工作流设计受到这条 X 推文启发，并结合了本地实际执行过程中的工程化改造：

- https://x.com/MinLiBuilds/status/2046002143937941988

适用场景：

- 你已经有一个准备上市的公司名字
- 你想围绕招股书、发行公告、同行财报、监管政策做 IPO 尽调
- 你希望把材料整理好，再选择性地喂给 NotebookLM 或其他 backend，让 Codex 汇总为最终的 `Participate / Watch / Skip` 决策表

## Skill 做什么

这个 skill 会指导 Codex：

1. 确定公司所属市场和主要业务线
2. 判断是否需要按业务线拆成多个 notebook
3. 收集 IPO 核心材料与同行材料
4. 把材料交给一个 backend 处理
5. 把标准 IPO 尽调问题改写成该公司的专属问题
6. 汇总结果为 markdown 决策表

## 依赖

这个 skill 的核心外部依赖是：

- `notebooklm-client`
- `httpx` Python 包

相关链接：

- GitHub 仓库：<https://github.com/icebear0828/notebooklm-client>
- NotebookLM 网页端：<https://notebooklm.google.com/>

本地执行时，默认有两种使用方式：

### 1. 全局安装版 CLI

如果本机已经安装：

```bash
notebooklm --help
```

适合：

- `list`
- `detail`
- `chat`
- `analyze`

但要注意：

- 某些版本的全局 CLI 可能**不暴露 `--file`**
- 这会影响本地 PDF 直接上传

### 2. 本地源码版 CLI

如果全局版能力不够，默认切换到本地源码版：

```bash
export NOTEBOOKLM_CLIENT_ROOT=/path/to/notebooklm-client
node "$NOTEBOOKLM_CLIENT_ROOT/dist/cli.js" --help
```

适合：

- `source add --file`
- `source add --url`
- `analyze --file`
- 本地 PDF、财报、公告文件上传

这个 skill 默认假设：

- 优先使用 `notebooklm-client`
- 如果全局版缺少 `--file`，则切到源码版 `node dist/cli.js`
- 如果 CLI 回答不稳定，则切回 NotebookLM 网页端查看答案，再由 Codex 汇总
- 当前环境下，本地源码版支持 `source add --file`
- `create` 虽然没有在 CLI help 中暴露，但当前 skill 已通过本地 helper 接上源码库里的 `createNotebook()`
- `configure` 仍然不保证可用
- 因此 workflow 默认不把 NotebookLM 当成唯一执行路径

## Backend 设计

当前 workflow 明确分成两层：

- 稳定层
  - 材料收集
  - 目录结构
  - `manifest.json`
  - IPO 问题模板
  - 最终 markdown 决策表
- 易变层
  - Notebook 创建
  - Source 上传
  - Persona 配置
  - Notebook 对话

当前支持两个 backend：

- `manifest_only`
  - 默认值
  - 只负责生成本地材料目录和 manifest
  - 不调用任何外部 notebook client
- `notebooklm`
  - 可选
  - 通过 `scripts/notebooklm_adapter.py` 调用非官方 NotebookLM client
  - 适合在 client 状态稳定时做上传和问答

这样即使 Google 或第三方 client 更新导致接口变化，默认流程仍然可以完成材料收集和结构化交付。

沙箱说明：

- `preflight` 和 readiness 现在默认是“能力探测”，不是“联网探测”
- `list` / `detail` / `source add` / `create` 后续如果执行失败，原因可能是默认沙箱下的网络权限，而不是 NotebookLM client 本身不可用
- 因此要把 “client 能力存在” 和 “当前环境允许联网调用” 分开判断

## Backend Policy

除了 backend 名称，现在还支持独立的 `backend_policy`，用于约束 agent 何时必须用 NotebookLM。

可选值：

- `required`
  - 只要环境允许，就必须走 `notebooklm`
  - agent 不能仅凭“边际收益不高”跳过
- `auto`
  - 默认值
  - 由 runner 根据材料规模和任务目标判断是否自动升级到 `notebooklm`
- `forbid`
  - 明确禁止使用 NotebookLM
  - 只走 `manifest_only`

`auto` 当前会在以下场景自动切到 `notebooklm`：

- notebook 数量 `>= 2`
- source 数量 `>= 10`
- `cninfo_reports` 同行 source 数量 `>= 3`
- `analysis_objective` 中明确出现 `NotebookLM`、`source-ids`、`save token`、`multi-round` 等目标，且材料规模至少达到中等复杂度

但 `auto` 不会只看“想不想用 NotebookLM”，还会检查能否真正执行：

- 是否存在支持 `--file` 的 client
- 是否所有 notebook 都已提供 `notebook_id`
- 如果没有 `notebook_id`，是否存在同时支持 `create` 的 file-capable client

只有这些条件满足时，`auto` 才会真的切到 `notebooklm`。否则会保留在 `manifest_only`，并把原因写进 summary。

如果 policy 是 `required`，runner 会在 planning 阶段直接检查这些条件；不满足就明确报错，而不是等进入 backend 后再失败。

另外：

- 如果本地源码库存在，当前 skill 会优先用 helper-backed create 补齐 `notebook_id`
- 所以“CLI 没有 create 子命令”不再等于“不能创建 notebook”

## 脚本层

当前仓库现在带了最小可执行脚本：

- `python3 scripts/preflight.py`
  - 检查 `python3`、`node`、`notebooklm-client`、本地源码版 CLI、`httpx`
  - 输出 JSON，说明哪一个客户端支持 `--file`
  - 如需本地源码版，使用 `NOTEBOOKLM_CLIENT_ROOT` 或 `NOTEBOOKLM_CLIENT_ENTRY` 指定位置
- `python3 scripts/notebooklm_adapter.py inspect --needs-file`
  - 探测当前可用的 NotebookLM 客户端
  - 会把 helper-backed create 一并计入本地源码版能力
- `scripts/backends.py`
  - backend 抽象层
  - 当前包含 `manifest_only` 和 `notebooklm`
- `python3 scripts/cninfo_fetch.py --stock <code,org_id,market,label,role,scope> --output-root <dir> --reporting-year 2026`
  - 从巨潮下载同行最新定期报告或年报
  - `scope` 支持：`latest` / `annual_only` / `periodic_only`
- `python3 scripts/run_ipo_screen.py --spec assets/ipo-workflow-spec.example.json`
  - 按 spec 串联材料收集并交给 backend
  - 默认 backend 是 `manifest_only`
  - 可以通过 `--backend notebooklm` 覆盖
  - 可以通过 `--backend-policy required|auto|forbid` 约束 backend 选择
  - 当前环境如用 `notebooklm`，建议在 spec 中提供已有 `notebook_id`

安装 Python 依赖：

```bash
pip install -r requirements.txt
```

## Features

这个 skill 具备以下能力：

### 1. IPO 材料分层收集

- 自动区分 `A股 IPO` 和 `港股 IPO`
- 自动判断要优先找哪些材料
- 默认优先级：
  1. 官方 PDF
  2. 官方披露 URL
  3. 媒体页面作为补充

### 2. 多业务线自动拆 notebook

- 如果公司存在两条以上主要业务线，且同行组不同
- 默认拆成多个 NotebookLM notebook
- 避免把不同业务线的同行和问答混在一起

### 3. PDF 优先喂料

- 招股书、年报、季报、发行公告优先找 PDF
- PDF 能找到时，不默认退化成网页
- 只有在 PDF 难以获取时，才使用 URL source

### 4. backend 解耦策略

- 默认 backend 是 `manifest_only`
- 先完成材料下载、目录整理、manifest 生成
- 只有在需要时才切到 `notebooklm` backend
- `notebooklm` backend 的所有不稳定交互都封在 `scripts/notebooklm_adapter.py`
- 如果当前环境无法 helper-backed create，或 `configure` 不可用
- `notebooklm` backend 退化为：
  - 使用已有 notebook id
  - 或退回 `manifest_only`

### 5. NotebookLM 使用策略

- 如果用户明确要求使用 NotebookLM，建议把 `backend_policy` 设为 `required`
- 如果是多同行、多轮提问、跨材料综合分析，建议至少用 `auto`
- 只有单次事实抽取、小材料集、本地直接可比对时，`manifest_only` 的边际收益才通常更高
- 命中 `required` 或 `auto` 触发条件时，agent 不能主观跳过 NotebookLM 路径
- `auto` 的前提是 NotebookLM 路径“可执行”，不是只要“理论上有帮助”就切换

### 6. 问题自动改写

- 把标准 8 个 IPO 尽调问题改写成发行人专属版本
- 自动替换：
  - 公司名
  - 同行组
  - 市场结构
  - 当前财报周期

### 7. A股/港股问法分流

- A股默认不问“基石投资者”
- A股改问：
  - 战略配售
  - 网下询价
  - 限售安排
- 港股则保留：
  - 基石投资者
  - 认购金额
  - 锁定期

### 8. 短问题优先

- 默认一问一事
- 先拿方向性结论
- 再追问详细原因
- 避免一条问题要求 NotebookLM 输出完整大报告

### 9. Source 范围控制

- 对大 notebook 默认先跑 `detail`
- 拿到 `source id`
- 提问时优先通过 `--source-ids` 缩小上下文范围
- 减少超时、跑偏和跨业务线混答

### 10. CLI 不稳定时的降级路径

- 如果 `notebooklm-client` 能加料，但回传长回答不稳定
- skill 默认允许切换到 NotebookLM 网页端查看答案
- 再由 Codex 汇总成 markdown 决策表

### 11. 最终产出标准化

- 输出统一的 markdown 决策表
- 包括：
  - 核心业务
  - 同行对比
  - 募资用途
  - 风险拆分
  - 财务质量
  - 关联交易与独立性
  - 最终结论：`Participate / Watch / Skip`

## 默认原则

- **多业务线公司默认拆 notebook**
  - 如果同行组不同，就不要放在同一个 notebook 里问
- **优先 PDF**
  - 招股书、年报、季报、发行公告能找 PDF 就优先 PDF
  - URL 作为次优选择
- **一次只问一件事**
  - 不要一条问题要求 NotebookLM 输出完整大报告
- **先短结论，后补细节**
  - 先拿方向性判断，再追问证据和差异原因
- **优先限制 source 范围**
  - 大 notebook 要先 `detail`
  - 提问时尽量用 `--source-ids`

## 推荐执行步骤

1. 先跑 `python3 scripts/preflight.py`
2. 确定发行人、市场、主要业务线
3. 判断是否要拆成多个 notebook
4. 收集核心材料
   - 招股书/招股意向书
   - 发行安排、风险公告
   - 同行最新财报
   - 监管政策
5. 对同行报告可先用 `scripts/cninfo_fetch.py` 统一抓取并生成 manifest
6. 设定 `backend_policy`
   - 小材料集可用 `forbid` 或 `auto`
   - 多同行、多轮问答建议 `required`
7. 默认先用 `manifest_only` backend 产出本地材料包，或由 `auto` 自动升级到 `notebooklm`
8. 对大 notebook 先 `detail`
9. 按短问题顺序发问
10. 如果 CLI 回答不稳，切网页端查看
11. 汇总为 markdown 决策表

## A股与港股的区别

### A股 IPO

重点关注：

- 招股书 / 招股意向书
- 发行安排及初步询价公告
- 投资风险特别公告
- 战略配售安排
- 限售安排

注意：

- **不要默认问“基石投资者”**
- A股更应该问：
  - 是否存在战略配售
  - 配售对象是谁
  - 限售多久
  - 网下询价和定价逻辑是什么

### 港股 IPO

重点关注：

- 聆讯后资料集 / PHIP
- Prospectus
- 配发结果公告
- Cornerstone investors

## 常用输出

最终输出通常包括：

- 业务结构判断
- 同行对比
- 募资用途与稀释
- 风险拆分
- 财务质量
- 关联交易与独立性
- 最终结论：`Participate / Watch / Skip`

## 如何触发

直接这样说即可：

```text
用 $ipo-notebooklm-screen 分析长裕集团，收集 A股 IPO 材料、同行财报，拆成锆材料和特种尼龙两个 notebook，通过 notebooklm-client 提问，并输出 markdown 打新决策表。
```

或者：

```text
用 $ipo-notebooklm-screen 分析公司A，重点看招股书、战略配售、同行季报和关联交易，最后给我一个是否参与打新的 markdown 决策表。
```

如果要走脚本化流程，可以先复制 `assets/ipo-workflow-spec.example.json` 并填入自己的材料路径、同行 `org_id`、backend 和已有 `notebook_id`。

推荐命令：

```bash
python3 scripts/run_ipo_screen.py --spec assets/ipo-workflow-spec.example.json
```

如果确认当前 NotebookLM client 可用，再显式切 backend：

```bash
python3 scripts/run_ipo_screen.py --spec assets/ipo-workflow-spec.example.json --backend notebooklm
```

如果你想强制要求 agent 走 NotebookLM 路径，直接在 spec 里写：

```json
{
  "backend_policy": "required"
}
```

如果当前环境没有 `create` 能力，就还需要给每个 notebook 提供 `notebook_id`。

## NotebookLM client 不稳定时怎么办

这是这个 skill 在 `notebooklm` backend 下的标准 fallback：

1. 继续用 `notebooklm-client` 建 notebook 和加材料
2. 把问题拆短
3. 用 `--source-ids` 缩小范围
4. 如果 CLI 取回答超时，就改去 NotebookLM 网页端查看答案
5. 再由 Codex 把网页端答案汇总成最终决策表

注意：

- fallback 发生在已经尝试满足 `backend_policy` 之后
- 不能因为“可能边际收益不高”而在 policy 要求前直接跳过

这不算失败，而是该 skill 允许的正常降级路径。

## 产出物

使用这个 skill 后，通常应至少得到：

- 一个材料目录
- 一组 `manifest.json`
- 一份提问清单
- 一份 markdown 打新决策表

如果选择了 `notebooklm` backend，额外可能得到：

- 一个或多个 NotebookLM notebook
