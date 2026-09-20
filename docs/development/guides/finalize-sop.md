# 阶段④收尾 SOP（网盘备份・飞书统一同步・过程件清理）

> **文档类型**
>
> ：Task（操作指南）
> **更新频率**
>
> ：收尾流程变更时
> **维护者**
>
> ：AI 自动维护
> **读者**
>
> ：AI 代理

本 SOP 管 " 知识详解生成并自检通过后，怎么备份网盘、统一同步飞书知识库、并按序清理工作区（`data/_workspace`）与旧件 "。



* 流程位置与校验门：[WORKFLOW.md 阶段④](../../WORKFLOW.md)

* 四地分工：[DIRECTORY\_STRUCTURE.md 第〇章](../../DIRECTORY_STRUCTURE.md)

* 网盘：[netdisk-setup.md](../api/netdisk-setup.md)；飞书：[feishu-api.md](../api/feishu-api.md)、[feishu-knowledge-base-maintenance.md](./feishu-knowledge-base-maintenance.md)

* 上游：`knowledge-detail-build-sop.md`



***

## 一、前置门

阶段③全量自检通过（92 篇齐、题量对账、链接有效）；**本阶段任何一步失败都可回退，不带着不一致向下走。**

## 二、作业步骤

### 步骤 1　百度网盘备份（镜像 "原始资源 + 知识详解" 两层）



1. 上传课程目录的 `原始资源/` 与 `知识详解/`，路径与本地同构：`/apps/CPA课程归档/会计知识库/高顿/CPA/{课程名}/`；

2. **不传** `data/_workspace/<profile>/`、`transcript.json`、tmp、logs；

3. **知识来源原料先归位再备份（重要）**：`papers/`（接口采集的试卷题答 JSON，含题目/标准答案/解析/知识点标签）与 `notes-raw/`（用户笔记与留言原件）虽位于 `data/_workspace/<profile>/`，但本质是**知识来源原料、不是可丢弃过程件**。清 `_workspace` 前必须先把它们复制归位到 `原始资源/papers/`、`原始资源/user-notes/`（Desktop 与 data 两份都归位），随本步骤一并传网盘；归位并核对一致后，`_workspace` 内的原件才允许在步骤 3 清。最终 `原始资源/` 为四类：`notes/`（讲义 PDF+OCR）、`videos/`（video.mp4+transcript.md）、`papers/`（题答 JSON）、`user-notes/`（笔记留言原件）；

4. 命令：`BAIDU_ENC_PASS=*** python3 code/scripts/netdisk/baidu_upload.py`（凭证 `.secrets/baidu_credentials.enc`，国内直连）；分片上传 + MD5 秒传、断点续传；同名覆盖 precreate/create 都传 `rtype=3`（见 netdisk-setup.md）；

5. 传后核对本地↔网盘**文件数与大小**一致，且要**逐讲核对到文件类型**：videos 每讲必须同时有 `video.mp4` 和 `transcript.md`（不能只核 mp4 数量，本课程曾出现单讲漏传 transcript.md）；papers/user-notes 按文件名集合 diff；改名走 rename 级联、不重传。

#### 名师课视频：hevc 按科滚动门控覆盖与双机限速（2026-09-16 立 / 2026-09-17 改按科滚动，见 ADR-022 文末演进注记）

名师课（ep3）视频先离线重压为 hevc（见 [video-processing.md](../tools/video-processing.md) 双机小节），再**按科滚动**覆盖网盘早期传过的 h264（某科全 hevc 即传、不等其他科压完）。这是对上面步骤 1 第 4 条的特化，**优先级高于"传了就行"**：

1. **按科滚动门控（防 h264 混传，最重要；2026-09-17 由"整科等压缩结束"放宽）**：一门课必须**全部** `*_video.mp4` 经 ffprobe 为 hevc（非 hevc 计数=0）**且当前没在压该科**，即可上传该科视频——**不必等同一压缩任务里的其他科目压完**（上传走限速网络、压缩吃 CPU、目录按 profile 隔离，可与另一科压缩并行；整机一次仍只传一科）。"在压该科"判据：本机看该科 videos 下有无 `.compress_tmp*`（一个 compress 进程可带多个 `--course`，不能只看进程名），目标机看门按 `pgrep --course <科>`；**正在压的那一科绝不探测/上传**（压几讲传几讲会让同科 h264/hevc 混杂）。`code/scripts/sync_ep3_ready.sh <profile> 1 videos` 的 ready_filter 只挑"完整讲"（meta 与非空视频齐备）、**不判编码**，编码门控必须在调用方实现（本机 `code/scripts/ep3_local_supervisor.sh`、目标机 `logs/target_netdisk_watch.sh`）。在跑检测只匹配带解释器前缀的真进程（`pgrep -f 'python3 .*compress_ep3_videos\.py'`、`'bash .*sync_ep3_ready\.sh'`），裸 `pgrep -f 脚本名` 会误匹配命令行含该文本的 grep/外层 shell 而漏拉。链路：`sync_ep3_ready.sh` → `sync_course_netdisk.sh`（xargs -P 派生）→ `upload_course.sh`（讲内串行）→ `baidu_upload.py`。

2. **清视频 done + rtype=3 覆盖**：早期 h264 已传并留 done，sync 见 done 会跳过。某科全 hevc **首次**上传前执行 `reset_videos_done_once`：删 `data/_workspace/<profile>/logs/netdisk_done/` 下所有**非 `notes__` 前缀**的视频 `.done`（**保留 `notes__` 讲义标记**），强制 hevc 全量重传、precreate/create 都传 `rtype=3` 同名覆盖；每科只清一次（标志 `data/_workspace/_account/ep3/supervisor/<prof>.videoreset`，目标机在 `netdisk_watch/`）。注意 done 文件名前缀是**阶段名**（如"全面精讲"），不是字面"videos"，仅讲义那次前缀是 `notes__`。

3. **双机各自限速（科学定值）**：两台分别上传自己负责的科目（本机审计/战略/经济法/税法，目标机会计/财管；目标机的 done 与看门在目标机本地）。每台**讲并发=1**、`BAIDU_UPLOAD_RATE=1100k`（只给分片 curl 加 `--limit-rate`，list/mkdir 小请求不限）。依据：`networkQuality -s` 实测共享出口上行 34.6 Mbps（≈4.3 MB/s）、满载响应 Low（延迟 1.5s、40 RPM）；持续上传合计压在上行约 50% 留余量给豆包/交互，两台对等各 1100k（≈1.1 MB/s），同时传最坏合计占上行 ~52%，再高会重现秒级卡顿。

4. **失败判定别看错**：`sync_course_netdisk.sh` 无论成败都固定打印"失败讲（无 done 标记且本次匹配）:"标题，**真正失败行才是行首恰好 3 个空格 + `- `**。一轮成功的判据是 `grep -q "本轮结束" && ! grep -qE '^[[:space:]]{3}- '`；只 grep"失败讲"标题恒为假，会导致看门每轮空转重拉、永不 mark_done、并卡死后续科目（实战踩过）。**该判定只扫日志最后一轮**（最后一个 `[ep3-ready] profile=` 到文件尾）：日志跨轮 `>>` 累积，早期轮次瞬时失败（后已重传成功）会让扫全文的判定永久卡住（2026-09-18 经济法 189 讲已齐却被历史失败行卡住反复重拉，总管/看门已修）。

5. **孤儿进程分层清理**：`sync_course_netdisk.sh` 的 xargs 父 bash 被杀后，上传子进程会成孤儿被 launchd 收养继续派生。停上传须分层：①杀顶层 sync_ep3_ready/sync_course →②按 upload_one 匹配杀孤儿 xargs 与 `bash -c` →③杀 upload_course/baidu_upload →④`pgrep -x curl`；全程用进程组 PGID 排除当前 shell（禁 `pkill -f`，模式串会匹配自身命令行自杀，详见 video-processing.md 双机小节⑥），连续两轮计数 0 才算根除。

6. **自动覆盖清单必须含全部负责科目**：本机总管上传循环曾只列审计/税法/经济法而漏掉战略，战略实际靠一次性补传才传齐 hevc（终态核验零差异）；新增/调整负责科目时，必须同步进自动覆盖清单，不能依赖人工补传。

7. **传完以终态核验为准、不信 done**：done 只证明"某次上传动作完成"，不证明网盘当前是 hevc。务必按 [netdisk-final-verification-sop.md](netdisk-final-verification-sop.md) 跑 `verify_netdisk_final.py`，rc=0 且无"网盘旧大版"才算完成。核验脚本默认排除点开头隐藏/缓存（`.ep3cache`）；**原始资源滚动备份阶段**知识详解尚在生成/走飞书，命令加 `-x 知识详解`，不拿半成品卡视频备份的完成判定；待课程完整 finalize、知识详解定稿并按本步骤传云后，再跑一次**不带 `-x`** 的两层（原始资源+知识详解）全量核验。

### 步骤 2　飞书知识库统一同步（只同步 "知识详解" 成品）

> 任何飞书写操作前先读 lark-wiki /lark-doc 的 SKILL；本地是源头，
>
> **不在飞书直接编辑**
>
> 。



1. 结构与本地 `知识详解/` **同构**：课程根 → 14 个组父节点 → 92 个知识点子页面 + 两个课程全局篇；CPA 层挂跨课 "通用做题思路解析"；

2. **先建父节点、再建子页面**，父节点写入全部子页面链接 + 一句摘要；

3. 本地**全量生成并校验后一次性统一同步**（不做分讲同步）；**冲刺模考完成后做最终一次同步**定稿；

4. 同步后**回读**飞书节点：数量、标题层级、正文与本地一致，无空节点 / 重复节点；

5. 目标空间「CPA 备考知识库」，节点 / 空间 ID 等运行参数从台账取，不写死进本文档。

### 步骤 3　过程件按序清理（移废纸篓，不硬删）

清理是**有门禁、有时序**的，不能提前删：



| 顺序 | 对象                                     | 清理条件                                        |
| -- | -------------------------------------- | ------------------------------------------- |
| 1  | `data/_workspace/<profile>/tmp/{download,transcribe}` | 单任务成功即清                                     |
| 2  | `data/_workspace/<profile>/sniff`                     | 抓包结论已沉淀进文档 / 接口档案即删                         |
| 3  | `data/_workspace/<profile>/papers`、`data/_workspace/<profile>/notes-raw` | **先按步骤1归位到 `原始资源/` 并传网盘、核对一致**；笔记还需已提炼进"学员补充"，才可删（原料门槛最高） |
| 4  | 课程级工作区 `<profile>/{manifest,pipeline,logs}` 整体 | **双门禁**：92 篇校验通过 + 原始资源（含 papers/user-notes、videos 逐讲 transcript）已传完网盘，**且**飞书同步回读一致后；账号级 `_account` 不随单课清退 |

> 清理一律 `mv` 到废纸篓（带时间戳后缀，Desktop 与 data 两份分别处理），不 `rm -rf` 硬删；清理后确认课程根只留 `原始资源/`、`知识详解/`（及待步骤 4 清退的旧目录）。

### 步骤 4　旧范式件清退（迁移期）



* 旧按讲目录里的 video/transcript/docs/docs\_text 已迁入 `原始资源/`、旧成品已被阶段③消化后，清旧讲目录与 `.vfetch` 缓存；**清退前必须做交叉校验**：递归统计每个旧讲目录的原料文件（video.mp4/transcript.md/docs PDF/docs_text OCR），按"文件大小→文件名"与新 `原始资源/` 全量集合比对，做到 100% 覆盖、逐个列出未覆盖项并补齐（本课程即以此发现 1 讲漏传 transcript.md，补传后才 100%）；旧成品（知识拆解/考试指导）确认已被 `知识详解/` 按知识点重组消化。**网盘旧目录删除属云端不可逆操作，必须把交叉校验结论列给用户、获明确授权后再删；本地旧目录移废纸篓。**

* `knowledge-base/organized-content/`、`source-materials/` 被消化、与新成品交叉校验后清退；`lecture-resource-map.json` 职责已由 course-manifest 承接，随之移除；

* 最终 Git 仓库不再保留课程成品（只留规范 / 模板 / SOP / 脚本）。

### 步骤 5　收尾报告（在任务中呈现，不单独归档飞书）



* 产出清单：原始资源数量、92 篇与全局篇、网盘文件核对结果、飞书节点链接；

* 校验结论、遗留 / 待确认项、清理记录；

* 报告供用户在任务中查看即可，**不写进飞书知识库**（方法论与过程报告不归档飞书）。



***

## 三、阶段④校验门（整体完成判据）



* [ ] 网盘 "原始资源 + 知识详解" 与本地文件数 / 大小一致、无工作区过程件；

* [ ] 飞书课程→14 组→92 篇 + 全局篇齐全、回读一致、父节点子链接完整；

* [ ] 工作区按分层时序清理、双门禁满足后清课程级残留（`_account` 保留）；旧范式件清退无残留；

* [ ] 四地分工正确：Git 只留工程、本地全量、网盘备份原料 + 成品、飞书为成品知识系统；

* [ ] 若还有冲刺模考未做：保留必要原料，待其完成后回到步骤 1–2 做最终一次同步再彻底收尾。

## 四、常见坑



| 坑                                     | 正确做法                    |
| ------------------------------------- | ----------------------- |
| 边生成边分讲同步飞书                            | 本地全量校验后统一同步，冲刺后最终一次     |
| 把 \data/_workspace/<profile>/transcript.json/tmp 传网盘 | 只传原始资源 + 知识详解两层         |
| 留言还没吸收就删 notes-raw               | 100% 吸收后才删，门槛最高         |
| 双门禁没满足就整体清工作区                         | 92 篇过 + 网盘传完 + 飞书回读一致才清 |
| 在飞书直接改正文                              | 本地是源头，改本地再同步            |
| 过程报告也塞进飞书                             | 只同步课程知识系统，报告在任务里给用户看    |

**文档维护**：同步接口变更改 api 文档、分工变更改 DIRECTORY\_STRUCTURE、流程变更改 WORKFLOW，本 SOP 只写收尾动作。