# 网盘日常增量检查 SOP（快速知道“哪里变了”）

> **文档类型**：Task（操作指南 — 网盘日常增量检查与台账维护）
> **回答的问题**：其他人（或自己在别处）动了云端/本地文件后，怎么快速发现变化、怎么落地，且多人操作互不破坏。
> **工具**：`code/scripts/netdisk/sync_check.py`；全量对齐流程见 [netdisk-alignment-sop.md](netdisk-alignment-sop.md)。

## 1. 原理（为什么快）

- 台账 `data/netdisk-sync/ledger/ledger.json` 记录基线：每个目录的 `server_mtime`，每个文件的 size/mtime/fs_id。
- 检查时只重列“mtime 变化的目录”：父目录 mtime 随子内容上传而刷新（已实测），未变目录整棵剪枝跳过。
- 数千目录全列要十几分钟；剪枝后无变化时通常**秒级**（实测 4300+ 目录约 1–2 秒）。
- **删除/移动只报告不自动执行**；每周或存疑时 `--full` 全量兜底。

## 2. 首次建台账（一次全量对齐完成后）

```bash
cd <仓库根目录>
export NETDISK_LOCAL_ROOT="/Volumes/<盘>/<本地同步根>"
export NETDISK_CLOUD_ROOT="/apps/<应用沙箱根>/<云端同步根>"
python3 code/scripts/netdisk/sync_check.py init data/netdisk-sync/ledger/ledger.json
# init 必须能拿到两个根：参数 --local-root/--cloud-root 或上面两个环境变量，缺参会报错
```

## 3. 日常检查

```bash
python3 code/scripts/netdisk/sync_check.py check data/netdisk-sync/ledger/ledger.json \
  --current-out data/netdisk-sync/snapshots/current_$(date +%Y%m%d_%H%M%S).json
```

报告分区：

- **云端变化**：新增目录/文件、修改（size 或 mtime 变）、删除、疑似移动（fs_id 命中新路径）；
- **本地变化**：同上（本地无 fs_id，移动按删除+新增报告）；
- **待同步动作**：待下载/待上传/待建目录数量，以及需人工裁定的 size 冲突。

`report` 子命令可离线对比任意两份状态快照（不请求 token）：

```bash
python3 code/scripts/netdisk/sync_check.py report \
  data/netdisk-sync/ledger/ledger.json data/netdisk-sync/snapshots/current_<TS>.json
```

## 4. 把变化落地为同步动作

1. 云端新增 → 走 down 补拉；本地新增 → 走 up 补传（上传前重新取最新云端快照）。
2. 云端删除/移动 → **只在报告里提示**，由人决定是否跟随，防止他人临时整理时误删本地。
3. 冲突（同路径大小不一致）→ 进 `size_conflicts`，人工裁定。
4. 具体执行走 [netdisk-alignment-sop.md](netdisk-alignment-sop.md) 第 2–5 步。

## 5. 台账基线提交（ledger commit）

变化**处理完成后**，再跑一次 `check`（应全 0），用那份快照替换台账：

```bash
python3 code/scripts/netdisk/sync_check.py check data/netdisk-sync/ledger/ledger.json \
  --current-out data/netdisk-sync/snapshots/verified_$(date +%Y%m%d_%H%M%S).json
# 确认输出全 0 后：
cp data/netdisk-sync/snapshots/verified_<TS>.json data/netdisk-sync/ledger/ledger.json
```

> 必须用“同步后复跑、0 变化”的快照替换；不能用变化处理前的旧快照，否则基线停在旧状态。

## 6. 节奏建议

- 每次准备做同步前：`check`；
- 每周一次：`check --full` 全量审计（mtime 剪枝是优化，不是唯一真相源）；
- 每次对齐验收 diff rc=0 后：重新 `init` 或按第 5 步提交基线。

## 7. 多人操作安全性

| 他人在别处的动作 | 对本工具的影响 |
|------|------|
| 上传新文件 | 当轮可能漏掉；check 即见，下轮补拉；未传完（三步未 create）不可见，不会下到半成品 |
| 删除文件 | 报告“云端已删除”；不自动删本地；网盘回收站 10 天可恢复 |
| 移动/改名 | fs_id 命中时报告“疑似移动”；否则表现为删除+新增 |
| 限流 | errno=1 strict 重试，只影响当次耗时，不会产生错误结论 |
| 同路径双向上传 | 唯一真冲突（rtype=3 后写者生效）；大批量上传前先刷新云端快照 |
