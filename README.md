# IPO NotebookLM Screen 使用说明

这是一个用于 **将上市公司材料收集、NotebookLM 问答、以及打新决策表产出** 的 skill。

## 灵感来源

这个 skill 的工作流设计受到这条 X 推文启发，并结合了本地实际执行过程中的工程化改造：

- https://x.com/MinLiBuilds/status/2046002143937941988

适用场景：

- 你已经有一个准备上市的公司名字
- 你想围绕招股书、发行公告、同行财报、监管政策做 IPO 尽调
- 你希望把材料喂给 NotebookLM，再让 Codex 汇总为最终的 `Participate / Watch / Skip` 决策表

## Skill 做什么

这个 skill 会指导 Codex：

1. 确定公司所属市场和主要业务线
2. 判断是否需要按业务线拆成多个 notebook
3. 收集 IPO 核心材料与同行材料
4. 用 `notebooklm-client` 把材料送入 NotebookLM
5. 把标准 IPO 尽调问题改写成该公司的专属问题
6. 汇总结果为 markdown 决策表

## 依赖

这个 skill 的核心外部依赖是：

- `notebooklm-client`

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
cd /home/alice/codes/notebooklm-client
node dist/cli.js --help
```

适合：

- `source add --file`
- `analyze --file`
- 本地 PDF、财报、公告文件上传

这个 skill 默认假设：

- 优先使用 `notebooklm-client`
- 如果全局版缺少 `--file`，则切到源码版 `node dist/cli.js`
- 如果 CLI 回答不稳定，则切回 NotebookLM 网页端查看答案，再由 Codex 汇总

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

### 4. notebooklm-client 兼容策略

- 支持用 `notebooklm-client` 建 notebook
- 支持添加 PDF、URL、文本 source
- 如果全局版 CLI 缺少 `--file`
- 默认切换到本地源码版 `node dist/cli.js`

### 5. 问题自动改写

- 把标准 8 个 IPO 尽调问题改写成发行人专属版本
- 自动替换：
  - 公司名
  - 同行组
  - 市场结构
  - 当前财报周期

### 6. A股/港股问法分流

- A股默认不问“基石投资者”
- A股改问：
  - 战略配售
  - 网下询价
  - 限售安排
- 港股则保留：
  - 基石投资者
  - 认购金额
  - 锁定期

### 7. 短问题优先

- 默认一问一事
- 先拿方向性结论
- 再追问详细原因
- 避免一条问题要求 NotebookLM 输出完整大报告

### 8. Source 范围控制

- 对大 notebook 默认先跑 `detail`
- 拿到 `source id`
- 提问时优先通过 `--source-ids` 缩小上下文范围
- 减少超时、跑偏和跨业务线混答

### 9. CLI 不稳定时的降级路径

- 如果 `notebooklm-client` 能加料，但回传长回答不稳定
- skill 默认允许切换到 NotebookLM 网页端查看答案
- 再由 Codex 汇总成 markdown 决策表

### 10. 最终产出标准化

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

1. 确定发行人、市场、主要业务线
2. 判断是否要拆成多个 notebook
3. 收集核心材料
   - 招股书/招股意向书
   - 发行安排、风险公告
   - 同行最新财报
   - 监管政策
4. 优先用 PDF 喂给 NotebookLM
5. 对大 notebook 先 `detail`
6. 按短问题顺序发问
7. 如果 CLI 回答不稳，切网页端查看
8. 汇总为 markdown 决策表

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

## NotebookLM client 不稳定时怎么办

这是这个 skill 的标准 fallback：

1. 继续用 `notebooklm-client` 建 notebook 和加材料
2. 把问题拆短
3. 用 `--source-ids` 缩小范围
4. 如果 CLI 取回答超时，就改去 NotebookLM 网页端查看答案
5. 再由 Codex 把网页端答案汇总成最终决策表

这不算失败，而是该 skill 允许的正常降级路径。

## 产出物

使用这个 skill 后，通常应至少得到：

- 一个或多个 NotebookLM notebook
- 一个材料目录
- 一份提问清单
- 一份 markdown 打新决策表
