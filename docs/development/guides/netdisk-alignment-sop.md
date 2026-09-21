# 百度网盘 ↔ 本地目录 全量对齐同步 SOP

> **文档类型**：Task（操作指南 — 网盘↔本地目录全量对齐：盘点→计划→试点→执行→验收→台账）
> **适用**：首次全量回拉/上传、大盘补差异、长期未同步后的重新对齐。日常小变化用 [netdisk-incremental-check-sop.md](netdisk-incremental-check-sop.md)。
> **工具**：`code/scripts/netdisk/` 下 `pan_inventory.py` / `sync_plan.py` / `sync_apply.py` / `sync_check.py` / `baidu_upload.py`。
> **安全约定**：云端删除/移动**只报告不自动镜像**；本地删除一律 `mv` 到带时间戳废纸篓，不硬删；size 冲突必须人工裁定。

## 0. 准备

```bash
cd <仓库根目录>
# 凭证：脚本会沿目录向上自动找 <repo>/.secrets/baidu_credentials.enc；
#       也可用 BAIDU_CRED_FILE 指定；主密码走 BAIDU_ENC_PASS 或交互输入。
export BAIDU_ENC_PASS="$(tr -d '\r\n' < ~/.doubao/secrets/master.pass)"  # 无人值守时；交互场景可省略
# 同步根（按实际任务替换；建议写进不入库的本地配置文件再 source）
export NETDISK_LOCAL_ROOT="/Volumes/<盘>/<本地同步根>"
export NETDISK_CLOUD_ROOT="/apps/<应用沙箱根>/<云端同步根>"
export BAIDU_DOWNLOAD_RATE="2m"   # 单连接限速，并发 3 时聚合约 3 倍
TS=$(date +%Y%m%d_%H%M%S); mkdir -p data/netdisk-sync/{snapshots,logs,ledger,runtime}
S=code/scripts/netdisk
```

快照、计划、日志统一落 `data/netdisk-sync/`（`data/` 已 gitignore，含真实文件清单不入库）。

## 1. 双侧盘点（先本地后云端；云端后台跑）

```bash
python3 $S/pan_inventory.py local-snapshot "$NETDISK_LOCAL_ROOT" data/netdisk-sync/snapshots/local_$TS.json
nohup python3 $S/pan_inventory.py cloud-snapshot "$NETDISK_CLOUD_ROOT" \
  data/netdisk-sync/snapshots/cloud_$TS.json --fresh > data/netdisk-sync/logs/cloud_snap_$TS.log 2>&1 &
tail -f data/netdisk-sync/logs/cloud_snap_$TS.log   # 看到“云端快照完成”再继续
```

- 云端目录量大时（数千目录）约 15–25 分钟；`.part` 为断点缓存，中断重跑可续（要彻底重扫加 `--fresh`）。
- 快照自动排除点开头文件与同步临时件（`.part/.tmp/.crdownload/*.baiduyun.p.downloading`），**空目录照收**。

## 2. 对账 + 出计划（只算不做）

```bash
python3 $S/pan_inventory.py diff data/netdisk-sync/snapshots/local_$TS.json \
  data/netdisk-sync/snapshots/cloud_$TS.json | tee data/netdisk-sync/snapshots/diff_$TS.txt
# rc=0 已一致；rc=1 有差异
python3 $S/sync_plan.py data/netdisk-sync/snapshots/local_$TS.json \
  data/netdisk-sync/snapshots/cloud_$TS.json \
  "$NETDISK_LOCAL_ROOT" "$NETDISK_CLOUD_ROOT" data/netdisk-sync/snapshots/plan_$TS.json
```

计划含五类：`mkdirs_cloud / uploads / mkdirs_local / downloads / size_conflicts`。
**`size_conflicts`（同路径双侧大小不一致）必须逐项人工裁定**，工具不会自动覆盖任何一边。

## 3. 试点（强制：先小后大）

先裁剪一个最小计划（示例：只取云→本方向的前几个小目录）：

```bash
python3 - "$TS" <<'PY'
import json, sys
TS = sys.argv[1]
p = json.load(open(f'data/netdisk-sync/snapshots/plan_{TS}.json'))
pre = ('<云端子目录A>/01-', '<云端子目录A>/02-')   # 试点前缀，按实际替换
keep = lambda r: r == '<云端子目录A>' or r.startswith(pre)
p.update(mkdirs_local=[r for r in p['mkdirs_local'] if keep(r)],
         downloads=[f for f in p['downloads'] if f['rel'].startswith(pre)])
json.dump(p, open(f'data/netdisk-sync/snapshots/pilot_{TS}.json','w'), ensure_ascii=False)
PY
python3 $S/sync_apply.py down data/netdisk-sync/snapshots/pilot_$TS.json --dry-run
python3 $S/sync_apply.py down data/netdisk-sync/snapshots/pilot_$TS.json --workers 3
```

试点子树立刻重扫对账，全绿才进入第 4 步。

## 4. 大盘执行（后台、限速、可重跑）

数小时级任务建议交 launchd 托管（关终端不影响、成功自卸载），模板见
[netdisk-background-launchd.md](netdisk-background-launchd.md)；短时任务也可 nohup：

```bash
nohup env BAIDU_DOWNLOAD_RATE=2m python3 $S/sync_apply.py down \
  data/netdisk-sync/snapshots/plan_$TS.json --workers 3 \
  > data/netdisk-sync/logs/pull_$TS.log 2>&1 &
```

- 执行器先建全部目录（含空目录），再并发下载；`.part` 原子落盘、同大小跳过、单文件 3 次重试、失败收集到末尾清单且不中断整体。
- 中断/失败后**直接重跑同一计划**即可幂等续跑。
- 上传方向把 `down` 换 `up`（先 `mkdirs up` 建云端骨架）；**大批量上传前必须重新取最新云端快照**（其他人可能正在云端操作）。

## 5. 验收 + 台账

```bash
python3 $S/pan_inventory.py local-snapshot "$NETDISK_LOCAL_ROOT" data/netdisk-sync/snapshots/local_final_$TS.json
python3 $S/pan_inventory.py diff data/netdisk-sync/snapshots/local_final_$TS.json \
  data/netdisk-sync/snapshots/cloud_$TS.json     # 要求 rc=0
# rc=0 后建立/刷新台账，转入日常增量检查（见 incremental-check SOP）
python3 $S/sync_check.py init data/netdisk-sync/ledger/ledger.json
```

## 6. 删除（仅在收到明确指令时）

1. 先出删除清单（快照 diff / 临时件清单）；2. 等用户明确指令；3. 网盘走 delete（进回收站 10 天可恢复），本地 `mv` 到带时间戳废纸篓，不硬删。

## 7. 多人同时操作云端会怎样

| 他人在别处的动作 | 影响与处理 |
|------|------|
| 上传新文件 | 当轮可能漏掉；下次 check 即见并补拉；三步上传未 create 前不可见，不会下到半成品 |
| 删除文件 | 报告“云端已删除”，不自动删本地；网盘回收站 10 天可恢复 |
| 移动/改名 | fs_id 命中时报告“疑似移动”；否则表现为删除+新增，由人裁定是否跟随 |
| 限流 errno=1 | strict 重试，只影响当次耗时，不会把限流伪装成“空目录” |
| 同路径双向上传 | 唯一真冲突（rtype=3 后写者生效）；大批量上传前先刷新云端快照 |
