# 百度网盘开放平台 API 笔记（沙箱应用 / 目录同步场景）

> **文档类型**：Reference（已实测的 API 事实与踩坑）
> 来源：网盘目录双向对齐工具链实测；应用接入与 token 刷新见 [netdisk-setup.md](netdisk-setup.md)。只记同步用到的结论，不含任何 token/密钥。
> 配套工具：`code/scripts/netdisk/` 下 `pan_inventory.py`（盘点）、`sync_plan.py`（计划）、`sync_apply.py`（执行）、`sync_check.py`（增量台账）、`baidu_upload.py`（API 封装，含上传与下载）。

## 1. 授权与沙箱

- 应用数据被限制在沙箱目录 `/apps/<应用名>/` 下；网盘客户端显示为“我的应用数据 / <应用名>”。
- 沙箱外的任何读写/list 返回 `errno=31064 (file is not authorized)`；**listall 在沙箱根也一样 31064**。
- 文件一旦被移出沙箱目录，应用永久不可见。
- access_token 30 天；过期/失效返回 `errno=111`，用 refresh_token 走 OAuth 刷新并回写密文。

## 2. 已验证可行

| 能力 | 接口 | 关键点 |
|------|------|--------|
| 逐目录列文件 | `GET https://pan.baidu.com/rest/2.0/xpan/file?method=list&dir=<path>&num=10000&web=5` | 返回 `server_filename / fs_id / size / isdir / server_mtime`；分页 `order=name&desc=0&start=` |
| 创建目录 | `file?method=create`（`path`、`isdir=1`） | 逐级创建；**`method=mkdir` 本应用可能返回 31064**；create 默认 rtype=1，对**已存在目录会改名成 `<名>_<时间戳>`**，必须先列父目录确认不存在再建 |
| 分片上传 | `file?method=precreate` → `pcs/superfile2?method=upload` → `file?method=create` | 三步；body 固定 `rtype=3` 同名覆盖；**precreate 与 create 都要带 rtype=3**；`ondup` 对三步上传无效 |
| 下载直链 | `multimedia?method=filemetas&fsids=[id]&dlink=1` 取 `dlink` | 再 `curl -sL -H "User-Agent: pan.baidu.com" "<dlink>&access_token=<token>"`；缺 UA 或不带 token 会失败；dlink 8 小时有效 |
| 移动/重命名 | `file?method=filemanager&opera=move/rename` | 服务端秒移、不重传 |
| 删除 | `file?method=filemanager&opera=delete` | 进回收站，**10 天可恢复**；API 无法清空回收站 |

## 3. 已验证死路（不要重试）

| 尝试 | 结果 | 结论 |
|------|------|------|
| `xpan/file?method=listall`（带/不带 dir、含沙箱根） | `31064 file is not authorized` | 沙箱应用无权用递归接口 |
| `xpan/file?method=search`（GET/POST；空词/时间窗 pub/有关键词） | `errno=2` | 搜索对沙箱应用不可用 |

→ 全量盘点只能**并发逐目录 list**（工具链用并发 3）。

## 4. 限流与正确性坑

- 高频请求触发限流时返回 `errno=1`（User limits），**不是错误地返回空列表**；若代码把 errno≠0 吞成空目录，会把“没列出来”误判成“目录为空”，造成漏传/误删判断。
- 对策：`pan_inventory.strict_list` 遇非 0 errno 直接抛异常 + 指数退避重试（5 次）；并发 ≤3；断点缓存 `.part`，中断可续扫。
- 下载/上传均为多步操作：
  - 下载先落 `.part`，校验字节数等于快照 size 后才 `os.replace` 原子改名；半成品不会被当正式件；
  - 上传三步未完成（未 create）前，云端目录里看不到该文件，其他人/客户端不会看到半成品。

## 5. mtime 行为（增量剪枝依据）

- list 返回的目录项含 `server_mtime`（Unix 秒）。
- 实测：**子目录/文件上传后，所有受影响父目录的 server_mtime 一并刷新**（批量上传当日整条路径 mtime 一致）。
- 因此“目录 mtime 未变 → 整棵子树跳过”的剪枝成立；文件项以 size + mtime + fs_id 记录。
- 兜底：每周或存疑时全量扫描（mtime 剪枝是优化，不是唯一真相源）。

## 6. 网络

- 百度域名国内直连，不走代理。
- 礼貌参数：并发 3；curl `--limit-rate` 由 `BAIDU_DOWNLOAD_RATE` / `BAIDU_UPLOAD_RATE` 控制（单连接值，并发时聚合约 N 倍）。
