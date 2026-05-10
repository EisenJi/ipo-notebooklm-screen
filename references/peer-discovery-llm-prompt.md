# Peer Discovery LLM Prompt Template

Use this prompt when the agent needs to generate Layer-2 peer candidates based on the issuer's business description.

## When to use

- After extracting explicit comparables from the prospectus (Layer 1)
- When the prospectus list is short, biased, or missing obvious competitors
- Before calling `peer_discovery.py --llm-candidates`

## Input

Issuer business description (from prospectus or NotebookLM summary).

## Prompt

```
基于以下发行人业务描述，推荐 5-10 家 A 股上市公司作为同行可比公司：

业务描述：
{issuer_business_description}

要求：
1. 只推荐 A 股上市公司（有股票代码）
2. 优先考虑主营业务高度重合的公司
3. 如果直接竞争对手未上市，推荐产业链上下游或技术路线相近的上市公司
4. 对每个推荐公司，用一句话说明推荐理由
5. 返回格式：公司名称（股票代码）- 推荐理由
```

## Example output

```
东材科技（601208）- 国内电子材料龙头，有电容膜及绝缘材料业务，与发行人同属电子薄膜赛道
铜峰电子（600237）- 老牌薄膜电容器材料企业，主营聚丙烯薄膜，直接竞争关系
大东南（002263）- BOPP薄膜产能较大，虽然偏包装膜但技术平台相近
```

## Next step

Parse the returned company names and pass them to:

```bash
python3 scripts/peer_discovery.py \
  --prospectus-text /path/to/prospectus.txt \
  --llm-candidates "东材科技" "铜峰电子" "大东南" \
  --max-results 10
```

The script will resolve names to tradeable codes + org_ids via `orgid_resolver.py`.
