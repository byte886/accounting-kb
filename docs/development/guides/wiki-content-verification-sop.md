# 飞书知识库内容验证 SOP

> **文档类型**：Task（操作指南）
> **更新频率**：流程变更时
> **维护者**：AI自动维护 + 用户审核
> **读者**：AI代理

## 目的

确保同步到飞书知识库的内容**完整、正确、符合模板要求**，不仅验证链接，更验证内容本身。每次知识详解同步飞书后，必须执行本 SOP 验证，通过后才算该课程同步闭环。

**与链接验证 SOP 的分工**：
- [wiki-link-verification-sop.md](./wiki-link-verification-sop.md)：验证内部链接格式（cite）、坏链、导航说明
- 本文档：验证**内容完整性**和**模板符合性**（章节点五要素、知识点四节结构、内容非空、frontmatter剥离）

## 验证范围（四层）

| 层级 | 位置 | 数量（会计课参考值） | 验证重点 |
|------|------|----------------------|----------|
| 第一层 | 课程根节点（总览页） | 1 | 章节列表完整、全局资料链接、课程概述、学习建议 |
| 第二层 | 章 README（模块组父节点） | 30 | 信息块、子节点目录清单、本组主线、重点内容、学习建议 |
| 第三层 | 知识点详解篇 | 144 | 四节结构、frontmatter剥离、内容非空、易错点格式 |
| 第四层 | 课程全局篇 | 2 | 考试指导速查手册、课程做题思路解析内容完整 |
| **合计** | | **177** | 全部通过才算闭环 |

## 章节点（模块组父节点）验证标准

基于 [KNOWLEDGE_BASE_TEMPLATE.md](../templates/KNOWLEDGE_BASE_TEMPLATE.md)，章节点必须包含**五要素**：

### 要素1：信息块
- [ ] 包含"覆盖知识点：N 个"（数量与该章实际知识点数一致）
- [ ] 包含"题量：N 道"（无 papers 来源期可省略或标 N/A）
- [ ] 包含"来源：讲义/转写/题答"
- [ ] 包含"适用 26 考季"
- [ ] 包含"更新 YYYY-MM-DD"

### 要素2：子节点目录清单
- [ ] 包含"知识点目录"章节标题
- [ ] 列出该章**全部**知识点（不缺不重）
- [ ] 每个知识点为 `<cite>` 内部引用（不是纯文本、不是相对链接、不是完整URL）
- [ ] 每个 cite 后有一句摘要
- [ ] cite 的 doc-id（obj_token）在台账 `wiki_node_map.tsv` 中存在
- [ ] 知识点数量与信息块中"覆盖知识点：N 个"一致

### 要素3：本组主线/概述
- [ ] 包含"本组主线"或"概述与学习目标"章节
- [ ] 2-4 句，说明本章讲什么、考试地位、学习目标

### 要素4：重点内容
- [ ] 包含"重点内容"章节标题
- [ ] 3-7 条（不少于3条，不多于7条）
- [ ] 每条有粗体标题 + 简述

### 要素5：学习建议
- [ ] 包含"学习建议"章节标题
- [ ] 说明学习顺序、与相邻章关系、投入建议

### 章节点禁止项
- [ ] 不包含正文知识点内容（父节点只做目录，正文在子页面）
- [ ] 不包含与子页面重复的框架
- [ ] 不包含流程/维护说明（归工程文档）

## 知识点详解篇验证标准

### 结构验证
- [ ] 包含四节结构：知识拆解 / 考试指导 / 题答解析 / 学员补充（学员补充可省）
- [ ] H1/H2/H3 不跳级
- [ ] 无 papers 来源期：第三节"题答解析"保留标题 + 回补占位说明，status=draft

### 格式验证
- [ ] 顶部 OKF frontmatter 已剥离（飞书端不显示 `---...---` YAML）
- [ ] 正文顶部保留 `>` Context Block（人读展示）
- [ ] 易错点格式统一为 ❌→✅ 对比表（如有易错点）
- [ ] description 压缩至 100-150 字

### 内容验证
- [ ] 内容不为空（字数 > 0）
- [ ] 知识拆解节有实质内容（不是只有标题）
- [ ] 考试指导节有实质内容
- [ ] 无 AI 错题来源
- [ ] 来源标注完整

## 课程根节点（总览页）验证标准

基于 [KNOWLEDGE_BASE_TEMPLATE.md 第二节](../templates/KNOWLEDGE_BASE_TEMPLATE.md#二课程根节点模板)：

- [ ] 包含考季、科目、主讲信息
- [ ] 包含"章节列表"表格，行数与章数一致（会计课30行）
- [ ] 每行章入口为 `<cite>` 内部引用，指向该章 README
- [ ] 包含"全局资料" section，列出 2 篇全局篇 cite
- [ ] 包含"课程概述"（3-5 句）
- [ ] 包含"学习建议"
- [ ] 顶部有左侧树单窗口导航说明

## 全局篇验证标准

### 考试指导速查手册
- [ ] 内容不为空
- [ ] 包含通用税率/公式/对比/易错速查
- [ ] 不含具体业务题（具体题在知识点篇）

### 课程做题思路解析
- [ ] 内容不为空
- [ ] 结合本科目题型的做题套路
- [ ] 有实质内容（不是只有标题）

## 验证步骤

### 第一步：自动化批量检查（必做）

使用脚本批量检查所有节点的内容非空和基本结构：

```bash
# 批量检查所有节点内容是否为空
python3 - << 'PY'
import subprocess, json, os

# 读取台账
map_file = 'data/_workspace/cpa-accounting-2026/logs/wiki_node_map.tsv'
nodes = []
with open(map_file, encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) >= 3:
            nodes.append({'title': parts[0], 'node_token': parts[1], 'obj_token': parts[2]})

print(f'台账节点数: {len(nodes)}')

empty_nodes = []
for i, node in enumerate(nodes):
    # 回读飞书内容
    result = subprocess.run(
        ['lark-cli', 'docs', '+fetch', '--doc', node['obj_token'], '--as', 'user', '--format', 'json'],
        capture_output=True, text=True, timeout=30
    )
    try:
        data = json.loads(result.stdout)
        if data.get('ok'):
            # 正确路径：data.document.content
            content = data.get('data', {}).get('document', {}).get('content', '')
            if len(content.strip()) == 0:
                empty_nodes.append(node['title'])
        else:
            print(f'  读取失败: {node["title"]}: {data.get("msg", "")}')
    except Exception as e:
        print(f'  解析失败: {node["title"]}: {e}')

    if (i+1) % 20 == 0:
        print(f'  已检查 {i+1}/{len(nodes)}')

print(f'\n=== 结果 ===')
print(f'空节点数: {len(empty_nodes)}')
if empty_nodes:
    print('空节点列表:')
    for t in empty_nodes:
        print(f'  - {t}')
PY
```

### 第二步：本地对齐检查（必做）

验证飞书端内容与本地源文件的一致性，确保同步完整、无遗漏、无差异。

**检查内容**：
1. **数量对齐**：飞书端节点数 = 本地文件数 = 台账记录数
2. **标题对齐**：飞书端节点标题与本地文件名一致
3. **内容对齐**：飞书端内容（剥离frontmatter后）与本地源文件正文一致
4. **frontmatter剥离**：飞书端不显示顶部 `---...---` YAML

```bash
# 本地对齐检查
python3 - << 'PY'
import subprocess, json, os, glob, re

profile = 'cpa-accounting-2026'
map_file = f'data/_workspace/{profile}/logs/wiki_node_map.tsv'
local_root = 'data/高顿/CPA/【VIPCPA专享】名师专业课-会计/知识详解'

# 1. 读取台账
wiki_titles = set()
wiki_map = {}
with open(map_file, encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) >= 3:
            wiki_titles.add(parts[0])
            wiki_map[parts[0]] = {'node_token': parts[1], 'obj_token': parts[2]}

# 2. 读取本地文件
local_files = {}
for md in glob.glob(f'{local_root}/**/*.md', recursive=True):
    title = os.path.splitext(os.path.basename(md))[0]
    local_files[title] = md

print(f'=== 数量对齐检查 ===')
print(f'台账节点数: {len(wiki_titles)}')
print(f'本地文件数: {len(local_files)}')
print(f'数量一致: {"✅" if len(wiki_titles) == len(local_files) else "❌"}')

# 3. 标题对齐
only_in_wiki = wiki_titles - set(local_files.keys())
only_in_local = set(local_files.keys()) - wiki_titles
print(f'\n=== 标题对齐检查 ===')
print(f'仅在飞书端（本地缺失）: {len(only_in_wiki)}')
if only_in_wiki:
    for t in list(only_in_wiki)[:5]:
        print(f'  - {t}')
print(f'仅在本地（飞书端缺失）: {len(only_in_local)}')
if only_in_local:
    for t in list(only_in_local)[:5]:
        print(f'  - {t}')

# 4. 内容对齐（抽检10%，至少10篇）
import random
common_titles = list(wiki_titles & set(local_files.keys()))
sample_size = max(10, int(len(common_titles) * 0.1))
sampled = random.sample(common_titles, min(sample_size, len(common_titles)))

print(f'\n=== 内容对齐检查（抽检 {len(sampled)} 篇）===')
mismatch = []
frontmatter_leak = []

for title in sampled:
    obj_token = wiki_map[title]['obj_token']
    local_file = local_files[title]

    # 读取本地文件，剥离frontmatter
    with open(local_file, encoding='utf-8') as f:
        local_content = f.read()
    if local_content.startswith('---'):
        end = local_content.find('---', 3)
        if end > 0:
            local_content = local_content[end+3:].lstrip()

    # 读取飞书内容
    result = subprocess.run(
        ['lark-cli', 'docs', '+fetch', '--doc', obj_token, '--doc-format', 'markdown', '--as', 'user', '--format', 'json'],
        capture_output=True, text=True, timeout=30
    )
    try:
        data = json.loads(result.stdout)
        if data.get('ok'):
            wiki_content = data.get('data', {}).get('document', {}).get('content', '')
        else:
            print(f'  读取失败: {title}')
            continue
    except Exception as e:
        print(f'  解析失败: {title}: {e}')
        continue

    # 检查frontmatter是否泄漏
    if wiki_content.strip().startswith('---'):
        frontmatter_leak.append(title)

    # 简单内容相似度检查（去除空白后比较前500字符）
    local_norm = re.sub(r'\s+', '', local_content)[:500]
    wiki_norm = re.sub(r'\s+', '', wiki_content)[:500]

    if local_norm != wiki_norm and len(local_norm) > 50:
        mismatch.append(title)

print(f'内容不一致: {len(mismatch)}')
if mismatch:
    for t in mismatch[:5]:
        print(f'  - {t}')
print(f'frontmatter泄漏: {len(frontmatter_leak)}')
if frontmatter_leak:
    for t in frontmatter_leak[:5]:
        print(f'  - {t}')

if not mismatch and not frontmatter_leak and not only_in_wiki and not only_in_local:
    print('\n✅ 本地对齐检查全部通过')
else:
    print('\n❌ 本地对齐检查发现问题，需修复后重新同步')
PY
```

### 第三步：章节点模板符合性检查（必做）

抽查全部章节点（会计课30个），验证五要素：

```bash
# 章节点五要素检查
python3 - << 'PY'
import subprocess, json, re

map_file = 'data/_workspace/cpa-accounting-2026/logs/wiki_node_map.tsv'
chapter_nodes = []
with open(map_file, encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) >= 3 and re.match(r'^\d+_', parts[0]):
            chapter_nodes.append({'title': parts[0], 'obj_token': parts[2]})

print(f'章节点数: {len(chapter_nodes)}')

# 五要素检查项
checks = {
    '信息块-覆盖知识点': r'覆盖知识点[：:]\s*\d+',
    '信息块-考季': r'适用\s*\d+\s*考季',
    '信息块-更新时间': r'更新\s*\d{4}-\d{2}-\d{2}',
    '子节点目录': r'知识点目录',
    '本组主线': r'本组主线|概述与学习目标',
    '重点内容': r'重点内容',
    '学习建议': r'学习建议',
    'cite引用': r'<cite[^>]*doc-id=',
}

results = {}
for node in chapter_nodes:
    result = subprocess.run(
        ['lark-cli', 'docs', '+fetch', '--doc', node['obj_token'], '--doc-format', 'xml', '--as', 'user', '--format', 'json'],
        capture_output=True, text=True, timeout=30
    )
    try:
        data = json.loads(result.stdout)
        content = data.get('data', {}).get('document', {}).get('content', '') if data.get('ok') else ''
    except:
        content = ''

    node_results = {}
    for check_name, pattern in checks.items():
        node_results[check_name] = bool(re.search(pattern, content))
    results[node['title']] = node_results

# 汇总
print('\n=== 章节点五要素检查结果 ===')
all_pass = True
for title, node_results in results.items():
    failed = [k for k, v in node_results.items() if not v]
    status = '✅ 全部通过' if not failed else f'❌ 缺少: {", ".join(failed)}'
    print(f'{title}: {status}')
    if failed:
        all_pass = False

print(f'\n总体: {"✅ 全部章节点通过" if all_pass else "❌ 有章节点未通过"}')
PY
```

### 第四步：知识点篇结构检查（抽检）

抽检 10-20% 知识点篇（每章至少1篇），验证四节结构：

```bash
# 知识点篇四节结构检查
python3 - << 'PY'
import subprocess, json, re, random

map_file = 'data/_workspace/cpa-accounting-2026/logs/wiki_node_map.tsv'
knowledge_nodes = []
with open(map_file, encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) >= 3 and not re.match(r'^\d+_', parts[0]) and parts[0] not in ['考试指导速查手册', '课程做题思路解析']:
            knowledge_nodes.append({'title': parts[0], 'obj_token': parts[2]})

# 抽检20%，至少10篇
sample_size = max(10, int(len(knowledge_nodes) * 0.2))
sampled = random.sample(knowledge_nodes, min(sample_size, len(knowledge_nodes)))

print(f'知识点总数: {len(knowledge_nodes)}, 抽检: {len(sampled)}')

checks = {
    '知识拆解': r'知识拆解',
    '考试指导': r'考试指导',
    '题答解析': r'题答解析',
    'frontmatter已剥离': r'^---\s*$',  # 应该不匹配（已剥离）
}

failed_nodes = []
for node in sampled:
    result = subprocess.run(
        ['lark-cli', 'docs', '+fetch', '--doc', node['obj_token'], '--doc-format', 'xml', '--as', 'user', '--format', 'json'],
        capture_output=True, text=True, timeout=30
    )
    try:
        data = json.loads(result.stdout)
        content = data.get('data', {}).get('document', {}).get('content', '') if data.get('ok') else ''
    except:
        content = ''

    missing = []
    for check_name, pattern in checks.items():
        if check_name == 'frontmatter已剥离':
            # 应该不匹配（已剥离），如果匹配说明没剥离
            if re.search(pattern, content, re.MULTILINE):
                missing.append(check_name)
        else:
            if not re.search(pattern, content):
                missing.append(check_name)

    if missing:
        failed_nodes.append((node['title'], missing))

print(f'\n=== 抽检结果 ===')
print(f'通过: {len(sampled) - len(failed_nodes)}/{len(sampled)}')
if failed_nodes:
    print('未通过:')
    for title, missing in failed_nodes:
        print(f'  - {title}: 缺少 {", ".join(missing)}')
PY
```

### 第五步：链接验证（调用已有 SOP）

按 [wiki-link-verification-sop.md](./wiki-link-verification-sop.md) 执行三层链接验证：
- 第一层：课程总览页 16 cite
- 第二层：章 README 知识点目录 cite
- 第三层：知识点详解关联知识点 cite

### 第六步：人工抽检（必做）

自动化检查通过后，人工抽检：
- [ ] 随机打开 3-5 个章节点，确认五要素完整、内容专业
- [ ] 随机打开 5-10 个知识点篇，确认四节结构、内容好懂、无重叠
- [ ] 随机打开 1 个全局篇，确认内容完整
- [ ] 确认章节点目录排序正确（数字_章名格式）
- [ ] 确认无空节点、无重复节点

## 常见问题与修复

| 问题 | 原因 | 修复 |
|------|------|------|
| 章节点内容为空 | 配置 localRoot 指向错误目录，resync 读取不到文件 | 修正配置 `config/courses/<profile>.json` 的 `paths.localRoot`，清除 done 标记，重新同步 |
| 章节点缺少子节点目录 | 本地 README 未按模板写，或同步时链接转换失败 | 检查本地 README 是否有"知识点目录"章节，用 `--force` 重新同步 |
| cite 变成纯文本 | `wiki_link_resolve.py` 转换失败，或台账缺映射 | 检查 `wiki_node_map.tsv` 是否有该标题，用 `--force` 重新同步 |
| frontmatter 未剥离 | resync 脚本版本旧，或文件顶部不是标准 `---...---` | 升级 `resync_wiki_content.py`，检查文件顶部格式，用 `--force` 重新同步 |
| 知识点篇缺少某节 | 本地文件生成时缺失，或同步时内容截断 | 检查本地文件四节是否齐全，补充后用 `--force` 重新同步 |
| 章节点重点内容不足3条 | 本地 README 写得不完整 | 按模板补充本地 README 重点内容至 3-7 条，重新同步 |
| 内容与本地不一致 | 同步后本地文件又被修改，或缓存问题 | 用 `--force` 参数强制重新同步全部 |

## 验收标准

一个课程同步闭环必须同时满足：

1. **内容非空**：177 个节点（会计课参考值）全部内容非空，0 空节点
2. **章节点五要素**：全部章节点（30个）五要素齐全，0 缺失
3. **知识点四节**：抽检知识点篇四节结构完整，frontmatter 已剥离
4. **链接正确**：三层 cite 全部有效，0 坏链，0 残留完整URL（按 wiki-link-verification-sop）
5. **目录正确**：章节点统一"数字_章名"格式，排序与官方一致，无重复节点
6. **人工抽检通过**：随机抽检 10+ 篇，内容专业、好懂、无重叠

**全部通过后**，更新 `TASK_STATUS.md`，标记该课程"飞书同步闭环完成"，再进入下一个课程。

## 参考

- 章节点模板：[KNOWLEDGE_BASE_TEMPLATE.md](../templates/KNOWLEDGE_BASE_TEMPLATE.md)
- 知识库模板：[KNOWLEDGE_BASE_TEMPLATE.md](../templates/KNOWLEDGE_BASE_TEMPLATE.md)
- 知识生成 SOP：[knowledge-base-organization.md](../knowledge/knowledge-base-organization.md)
- 链接验证 SOP：[wiki-link-verification-sop.md](./wiki-link-verification-sop.md)
- 内容重同步脚本：`code/scripts/knowledge/resync_wiki_content.py`（`--force` 强制重刷）
- 节点台账：`data/_workspace/<profile>/logs/wiki_node_map.tsv`
