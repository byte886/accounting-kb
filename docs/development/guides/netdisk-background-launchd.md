# 网盘长任务系统后台运行 SOP（macOS launchd）

> **文档类型**：Task（操作指南 — 网盘长任务的 macOS launchd 后台托管）
> **适用**：大盘下载/上传等数小时级任务，脱离终端与 AI 会话由 macOS 用户级 launchd 托管；**计划全部成功后任务自动卸载并移除**。
> 通用的长任务守护方法论另见 `docs/development/performance/long-task-supervisor-guide.md`；本篇是网盘同步场景的 launchd 一次性任务具体配方。
> **路径约定**：项目内命令一律仓库相对路径；launchd 配置必须用绝对路径（系统配置事实），下文中 `<REPO>` 表示仓库根目录绝对路径（如 `/Users/<user>/<repo>`）。

## 1. 组件（两件，均为本机件、不入库）

| 件 | 位置 | 是否入库 |
|----|------|---------|
| LaunchAgent plist | `~/Library/LaunchAgents/com.<user>.netdisk-sync.pull.plist` | 否（系统目录） |
| 运行脚本 | `<REPO>/data/netdisk-sync/runtime/launchd_pull.sh` | 否（data/ 已 gitignore；模板见 §4） |

行为约定：

- `RunAtLoad=true`、`KeepAlive=false`：加载后跑一次；**失败不自动重启**（避免失控刷屏），失败留标记等人工处理。
- 成功（sync_apply 退出码 0）：touch `data/netdisk-sync/logs/<任务>.DONE`，5 秒后自删 plist 并 `launchctl bootout` 卸载自己。
- 失败（退出码非 0）：touch `<任务>.FAILED` 并记录退出码，plist 保留但不重跑。
- 输出统一进 `data/netdisk-sync/logs/<任务>.launchd.log`。

## 2. 安装与启动（一次性，每次长任务）

```bash
# 1) 按 §4 模板放好 runner 与 plist（替换 <REPO>、计划文件名、任务名），校验：
plutil -lint ~/Library/LaunchAgents/com.<user>.netdisk-sync.pull.plist

# 2) 加载并立即运行：
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.<user>.netdisk-sync.pull.plist

# 3) 查状态（state = running / pid）：
launchctl print gui/$(id -u)/com.<user>.netdisk-sync.pull | grep -E 'state =|pid =|last exit'
```

任务归属用户 GUI 域（gui/$(id -u)），**关闭终端、退出 AI 会话都不影响**；注销/重启后需重新 bootstrap（一次性任务不做开机自启）。

## 3. 日常操作

```bash
# 看进度（在仓库根目录）
grep -c '] OK' data/netdisk-sync/logs/pull_<TS>.launchd.log
tail -f data/netdisk-sync/logs/pull_<TS>.launchd.log

# 是否完成 / 失败
ls data/netdisk-sync/logs/pull_<TS>.DONE data/netdisk-sync/logs/pull_<TS>.FAILED 2>/dev/null

# 中途停止（已下文件不丢，重跑同一计划幂等续传）
launchctl bootout gui/$(id -u)/com.<user>.netdisk-sync.pull
pkill -f sync_apply.py

# 停止后恢复：重新 bootstrap；或服务还在时直接 kickstart
launchctl kickstart gui/$(id -u)/com.<user>.netdisk-sync.pull

# 排障：launchd 生命周期日志
log show --last 30m --style compact --predicate 'eventMessage CONTAINS "netdisk-sync"'
```

注意：

- macOS 睡眠会挂起进程；唤醒后在途文件可能失败进清单，末尾重跑同一计划即可（同大小跳过、`.part` 重下该文件）。
- `Bootstrap failed: 5: Input/output error` 多为同名服务残留或 plist 已被自删：先 `bootout` 再 `bootstrap`。
- launchd 用 `/usr/bin/python3`（系统 Python，版本可能较旧），脚本需保持兼容；曾因 argparse 可选位置参数 `default` 值不在 `choices` 内而在旧版本报错。

## 4. 模板

### 4.1 runner：`data/netdisk-sync/runtime/launchd_pull.sh`（chmod +x）

```bash
#!/bin/bash
# launchd 一次性后台任务：跑大盘回拉；计划全部成功后自动卸载并移除本后台任务
set -u
REPO="<REPO>"                       # 例：/Users/<user>/<repo>
LABEL="com.<user>.netdisk-sync.pull"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(/usr/bin/id -u)"
JOB="pull_<TS>"

cd "$REPO" || exit 2
# 同步根与凭证（不入库的本机配置；按实际路径填写）
# shellcheck disable=SC1091
source data/netdisk-sync/runtime/sync.env

/usr/bin/python3 code/scripts/netdisk/sync_apply.py down \
  data/netdisk-sync/snapshots/plan_<TS>.json --workers 3
rc=$?

if [ "$rc" -eq 0 ]; then
  /usr/bin/touch "data/netdisk-sync/logs/$JOB.DONE"
  # 先删 plist 再卸载（卸载会杀掉本任务残留进程，故延迟并放后台）
  /bin/bash -c "sleep 5; /bin/rm -f '$PLIST'; /bin/launchctl bootout gui/$UID_NUM/$LABEL 2>/dev/null" >/dev/null 2>&1 &
else
  /usr/bin/touch "data/netdisk-sync/logs/$JOB.FAILED"
  echo "[$(/bin/date +%Y%m%d_%H%M%S)] sync_apply 退出码 $rc，后台任务保留但不自动重启，等待人工处理" \
    >> "data/netdisk-sync/logs/$JOB.FAILED"
fi
exit "$rc"
```

`runtime/sync.env`（不入库）至少包含：`NETDISK_LOCAL_ROOT`、`NETDISK_CLOUD_ROOT`、`BAIDU_ENC_PASS`（或从 `~/.doubao/secrets/master.pass` 读取）、可选 `BAIDU_CRED_FILE` 与限速变量。

### 4.2 plist：`~/Library/LaunchAgents/com.<user>.netdisk-sync.pull.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.<user>.netdisk-sync.pull</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string><REPO>/data/netdisk-sync/runtime/launchd_pull.sh</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/<user></string>
        <key>PATH</key>
        <string>/usr/bin:/bin:/usr/local/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>WorkingDirectory</key>
    <string><REPO></string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><false/>
    <key>ProcessType</key><string>Background</string>
    <key>StandardOutPath</key><string><REPO>/data/netdisk-sync/logs/pull_<TS>.launchd.log</string>
    <key>StandardErrorPath</key><string><REPO>/data/netdisk-sync/logs/pull_<TS>.launchd.log</string>
</dict>
</plist>
```

> 换任务（如上传）：复制 runner 改计划文件名与方向、改 Label/日志名，另建 plist；不要并发跑两个操作同一根目录的任务。
