# GitHub 工作流

> **文档类型**：Task（操作指南）
> **更新频率**：流程变更时
> **维护者**：AI自动维护
> **读者**：AI代理

本文档记录项目的 GitHub 访问配置、SSH 配置、代理设置和常见问题处理。

## 1. 访问方式对比

经测试（2026-08-27，国内网络环境）：

| 方式 | 结果 | 耗时 | 说明 |
|------|------|------|------|
| HTTPS 直连 | ❌ 失败 | 10秒超时 | github.com 被墙 |
| HTTPS + ClashX 代理 | ✅ 成功 | 3.0秒 | 需开代理，94KB/s |
| SSH (github.com:22) | ✅ 成功 | 5.2秒 | 走 SSH config 配置 |
| **SSH 直连 (ssh.github.com:443)** | ✅ **成功** | **3.3秒** | **不需要代理！** |

**推荐方式：SSH 直连 ssh.github.com:443**
- 不需要开 ClashX 代理
- 密钥认证，不需要每次输入 token
- 443 端口走 HTTPS 通道，国内通常不被墙

## 2. SSH 配置

`~/.ssh/config` 中 github.com 的配置：

```ssh-config
Host github.com
  HostName ssh.github.com
  Port 443
  User git
  IdentityFile ~/.ssh/id_rsa_softwawrecheng
  StrictHostKeyChecking accept-new
  # 注：ssh.github.com:443 国内可直连，无需代理
  # 如需代理可取消下一行注释：
  # ProxyCommand nc -X connect -x 127.0.0.1:7890 %h %p
```

### 密钥文件

- 路径：`~/.ssh/id_rsa_softwawrecheng`
- 关联 GitHub 账号：byte886（曾用名 Web3Stack404、softwarecheng）
- 公钥已添加到 GitHub 账号

### 测试连接

```bash
ssh -T git@github.com
# 预期输出：Hi byte886! You've successfully authenticated...
```

## 3. Git Remote 配置

项目使用 SSH 方式：

```bash
# 查看当前 remote
git remote -v

# 切换到 SSH（如当前是 HTTPS）
git remote set-url origin git@github.com:byte886/gaodun-course-knowledge-base.git

# 切换到 HTTPS（如需）
git remote set-url origin https://github.com/byte886/gaodun-course-knowledge-base.git
```

## 4. 代理配置

### 4.1 ClashX 代理

- 代理地址：`http://127.0.0.1:7890`
- 用于：GitHub HTTPS 访问、Google 搜索、Homebrew、npm 等
- 不用于：高顿课程页、百度 API、百度网盘（直连更快）

### 4.2 Git 临时使用代理（HTTPS 方式时）

```bash
# 单次 push 使用代理
git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 push origin master

# 永久配置（不推荐，SSH 方式更好）
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
```

### 4.3 SSH 使用代理（如需）

在 `~/.ssh/config` 的 github.com 配置中添加：
```ssh-config
ProxyCommand nc -X connect -x 127.0.0.1:7890 %h %p
```

## 5. 常见问题处理

### 5.1 SSH 连接失败

**症状**：`ssh: connect to host ssh.github.com port 443: Connection refused`

**排查步骤**：
1. 测试网络：`ping ssh.github.com`
2. 测试 443 端口：`nc -zv ssh.github.com 443`
3. 如果直连失败，启用 SSH config 中的 ProxyCommand
4. 确认 ClashX 代理已开启（127.0.0.1:7890）

### 5.2 HTTPS push 失败

**症状**：`fatal: unable to access 'https://github.com/...': Failed to connect`

**解决方案**：
1. 切换到 SSH 方式（推荐）
2. 或使用代理：`git -c http.proxy=http://127.0.0.1:7890 push`

### 5.3 Permission denied (publickey)

**症状**：`git@github.com: Permission denied (publickey).`

**排查步骤**：
1. 确认密钥文件存在：`ls -la ~/.ssh/id_rsa_softwawrecheng`
2. 确认 SSH config 中 IdentityFile 路径正确
3. 测试连接：`ssh -vT git@github.com`（查看详细日志）
4. 确认公钥已添加到 GitHub 账号

### 5.4 Push 速度慢

**可能原因**：
1. 走了代理但代理速度慢 → 尝试 SSH 直连 443
2. **提交包含大文件或历史中有大文件** → 见下方「大文件管理」
3. 网络波动 → 重试

## 6. 大文件管理

> **教训记录（2026-08-27）**：audio.wav（291MB）被误提交进 git 历史，虽然后来删除了，但仍存在于历史中，导致整个仓库 213MB，push 极慢。用 `git-filter-repo` 清理后仓库降至 93KB，秒传。

### 6.1 预防措施

**每次 commit 前必须检查**：

```bash
# 检查暂存区是否有大于1MB的文件
git diff --cached --name-only | while read f; do
  [ -f "$f" ] && [ $(wc -c < "$f") -gt 1048576 ] && echo "⚠️  大文件: $(du -h "$f" | cut -f1) $f"
done
```

**push 前检查仓库大小**：

```bash
# 检查仓库打包大小
git count-objects -vH | grep size-pack

# 检查历史中最大的10个文件
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | awk '/^blob/ {print $3, $4}' | sort -rn | head -10
```

### 6.2 .gitignore 必须排除的大文件类型

```gitignore
# 音视频
*.wav
*.mp3
*.aac
*.mp4
*.mov
*.mkv
*.ts
*.m3u8

# 文档（大文件）
*.pdf
*.doc
*.docx
*.ppt
*.pptx
*.xls
*.xlsx

# 虚拟环境
venv/
.venv/
*/venv/

# 缓存和临时
__pycache__/
*.pyc
.DS_Store
*.log

# 生成结果目录
transcription/trancode/scripts/
transcription/transcripts_full/
transcription/transcripts_test/
transcription/pdf_test_pages/
```

### 6.3 清理历史中的大文件

如果大文件已经进入历史，用 `git-filter-repo` 清理：

```bash
# 安装
pip3 install git-filter-repo

# 移除所有大于10MB的blob（重写历史）
git filter-repo --strip-blobs-bigger-than 10M --force

# 重新添加remote（filter-repo会移除remote）
git remote add origin git@github.com:byte886/gaodun-course-knowledge-base.git

# 强制push（历史已重写）
git push --force origin master
```

**注意**：重写历史后，所有协作者需要重新克隆仓库。本项目为单人项目，可安全使用。

### 6.4 存储分工（不可混淆）

| 内容类型 | 存储位置 | 是否进 git |
|----------|----------|------------|
| 代码、脚本、文档 | GitHub 仓库 | ✅ |
| 视频、音频、PDF | 项目内 `data/高顿/`（实体、gitignore）+ 百度网盘 | ❌ |
| 转写文字稿 | 本地课程目录 + 百度网盘 + 飞书知识库 | ❌ |
| 加密凭证 | GitHub 仓库（.enc 文件） | ✅ |
| 明文凭证 | 本地，永不提交 | ❌ |

## 7. 分支策略

### 7.1 单人项目策略

本项目为单人维护项目，采用简化的分支策略：

- **master 分支**：主分支，直接提交，保持稳定可运行
- **不使用 feature 分支**：单人项目不需要复杂的分支管理
- **重大变更前可创建临时分支**：如重构、大功能开发，完成后合并回 master

### 7.2 提交前检查清单

每次 `git commit` 前，pre-commit hook 会自动检查（见第8节）。此外人工确认：

- [ ] 没有大文件被误提交（>1MB 应警惕，>10MB 必须排除）
- [ ] 没有明文凭证（密码、token、密钥）
- [ ] 生成结果（视频、音频、PDF、文字稿）不在暂存区
- [ ] commit message 符合规范（type: description）
- [ ] 每个 commit 只做一件事（原子提交）

## 8. 原子提交原则

### 8.1 什么是原子提交

每个 commit 只做**一件完整的事**，不混合多个无关变更。

**好的例子**：
```
docs: 添加GitHub工作流文档
refactor: 重构项目目录结构
fix: 修复上传脚本路径缺少高顿层
```

**不好的例子**：
```
更新文档和修复bug和清理文件  # 混合了3件事
```

### 8.2 为什么要原子提交

- 便于回滚：出问题时只 revert 一个 commit
- 便于审查：每个 commit 的目的清晰
- 便于追溯：git blame 时能准确找到变更原因
- 便于 cherry-pick：可以选择性地应用某个变更

### 8.3 提交时机：按变更类型分场景

原子提交解决"一个 commit 装多少"，本节解决"**什么时候** commit、要不要等验收"。是否延迟提交与变更扩散度对齐（分级见 [AGENTS.md 3.2](../../../AGENTS.md)）：

| 场景 | 典型动作 | 提交策略 |
|------|----------|----------|
| 框架 / 结构 / 规范治理（L1/L2） | 批量改名/移动/删除、改命名或治理规范、动目录骨架、新增或删除持久文档与机制 | 本地全部改完先 `git add` 暂存 → **用户整体验收后**，说"提交"才合成一个（或少数几个）原子 commit；验收前不 push |
| 日常开发 / 课程生产（L0、单任务闭环） | 走完一讲、修好一个脚本、完成 WORKFLOW 一个步骤、错字/断链等小修 | **按自然里程碑及时 commit**（一讲一 commit、一功能一 commit、L0 随手 commit），不堆积在暂存区、不必每次停下等验收 |

**commit 与 push 分开**：
- 日常增量可及时本地 commit 保住成果、保持历史连续；但 **push 到远程不默认自动**，按用户约定的节奏执行；
- 治理类高扩散变更，commit 与 push 都等用户验收；
- 一句话：**动骨架/规范等人把关，做增量/产出及时落库**。

## 9. pre-commit Hook

### 9.1 作用

在 `git commit` 执行前自动运行检查脚本，防止不符合规范的内容进入仓库。

### 9.2 检查内容

| 检查项 | 阈值 | 动作 |
|--------|------|------|
| 大文件 | >1MB | ⚠️ 警告 |
| 超大文件 | >10MB | ❌ 阻止提交 |
| 音视频/文档 | .mp4/.wav/.pdf等 | ⚠️ 警告 |
| 运行产物误入 | venv/env/node_modules、data/、logs/、.tmp/、完成哨兵、题缓存等命中模式表 ARTIFACT_RE，或被 .gitignore 忽略却被 `git add -f` 强塞 | ❌ 阻止提交 |
| 敏感信息 | password/token/secret等 | ⚠️ 警告 |
| 新文档登记/头部标注 | 新增.md未登记DOCUMENTATION_MAP或缺类型标注 | ⚠️ 警告 |
| 相对链接有效性 | 暂存.md的相对链接目标不存在（跳过代码块/行内代码/外链/锚点） | ❌ 阻止提交 |
| 文档类型词白名单 | 类型词不在7类权威词表（Task/Concept/Reference/Governance/Active/Knowledge/Template） | ❌ 阻止提交 |

### 9.3 安装

```bash
# 项目已包含 code/scripts/pre-commit，安装到 .git/hooks/
cp code/scripts/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

> 运行产物模式表 `ARTIFACT_RE` 与根 `.gitignore` 互为备份，新增一类运行产物时两处同步（依据 PROJECT_STRUCTURE_MAINTENANCE 2.1）。pre-commit 只查本次暂存（增量拦截）；需要排查存量时跑只读的全量体检 `bash code/scripts/check/check_git_hygiene.sh`。

### 9.4 跳过检查（特殊情况）

```bash
# 确认安全时可跳过
git commit --no-verify -m "message"
```

**注意**：仅在确认安全时使用，不要习惯性跳过。

## 10. 敏感信息管理

### 10.1 原则

- **明文凭证永不提交**：密码、token、私钥等
- **加密文件可以提交**：`.enc` 后缀的加密文件（用 openssl 加密）
- **凭证模板可以提交**：如 `.env.example`，但不包含真实值

### 10.2 加密存储

```bash
# 加密
openssl enc -aes-256-cbc -pbkdf2 -pass pass:<密码> -base64 -in 明文.json -out 明文.enc

# 解密
openssl enc -aes-256-cbc -d -pbkdf2 -pass pass:<密码> -base64 -in 明文.enc -out 明文.json
```

### 10.3 已误提交敏感信息怎么办

1. 立即更换泄露的凭证（token、密码等）
2. 从历史中移除：`git filter-repo --path 敏感文件 --invert-paths`
3. 强制 push：`git push --force`
4. 将文件加入 `.gitignore`

## 11. .gitignore 不生效的处理

### 11.1 原因

文件已经被 git 跟踪后，再添加到 `.gitignore` 不会自动停止跟踪。

### 11.2 解决方案

```bash
# 从 git 索引中移除（保留本地文件）
git rm --cached 文件名
# 或移除整个目录
git rm --cached -r 目录名/

# 确认 .gitignore 包含该文件/目录
echo "文件名" >> .gitignore

# 提交
git add .gitignore
git commit -m "chore: 从版本控制中移除xxx"
```

### 11.3 验证

```bash
# 检查文件是否还被跟踪
git ls-files | grep 文件名
# 无输出表示已停止跟踪
```

## 12. 仓库维护

### 12.1 定期清理

```bash
# 清理不可达对象，压缩仓库
git gc --prune=now --aggressive

# 查看仓库大小
git count-objects -vH

# 查看历史中最大的10个文件
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | awk '/^blob/ {print $3, $4}' | sort -rn | head -10
```

### 12.2 维护时机

- 大文件清理后
- 大量 commit 后（如重构）
- push 速度明显变慢时
- 定期（如每月一次）

## 13. 提交规范

### 13.1 Commit Message 格式

```
<type>: <简短描述>

<详细描述（可选）>
```

**Type 类型**：
- `feat`：新功能
- `fix`：修复 bug
- `docs`：文档更新
- `refactor`：重构（不影响功能）
- `chore`：构建/工具/依赖调整
- `test`：测试相关

### 13.2 示例

```
docs: 添加项目维护规则，更新GitHub目录结构

- 添加项目维护规则（结构维护原则、检查触发时机、存储分工）
- 更新GitHub仓库目录结构（脚本统一放code/scripts/、文档按领域分类）
```

## 14. 参考资料

- [GitHub SSH 官方文档](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [GitHub 通过 HTTPS 端口使用 SSH](https://docs.github.com/en/authentication/troubleshooting-ssh/using-ssh-over-the-https-port)
