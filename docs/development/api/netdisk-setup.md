# 百度网盘开放平台接入文档

> **文档类型**：Reference（参考资料）
> **更新频率**：API变更时
> **维护者**：AI自动维护
> **读者**：AI代理

## 概述

通过百度网盘开放平台 API 实现课程视频和文档的自动上传、目录管理。应用名称：**CPA课程归档**，类型：个人开发者/软件/学习教育。

## 一、创建过程记录（2026-08-26）

### 1.1 前置条件

- 百度账号已完成实名认证
- 登录 [百度网盘开放平台](https://pan.baidu.com/union/home)

### 1.2 开发者认证

1. 登录后首页右上角显示"未申请认证"
2. 点击"快速接入"按钮（class=`apply-for-join`），打开新标签页 `https://pan.baidu.com/union/apply?from=header`
3. 选择接入类型：**个人**（最多创建1个应用）
4. 阅读并同意《百度网盘开放平台开发者服务协议》，点击"同意并继续"
5. 填写个人认证表单：
   - 身份信息（姓名、身份证号）：从实名认证自动填充
   - 联系方式（手机号、邮箱）：从百度账号自动填充
   - 属性：个人开发者
   - 一级行业分类：教育
   - 二级行业分类：在线教育
6. 点击"提交申请"，即时通过（显示"恭喜你，个人认证成功"）

**注意**：个人开发者最多创建1个应用。如需更多应用需企业认证。

### 1.3 创建应用

1. 认证成功后点击"控制台"，进入 `https://pan.baidu.com/union/console/applist`
2. 点击"创建应用"
3. 填写表单：
   - 应用用途：个人使用
   - 应用类型：软件
   - 应用分类：学习教育
   - 应用名称：CPA课程归档（最多12字符）
   - 应用描述：个人CPA备考课程视频和讲义文档的云存储归档管理工具，调用百度网盘文件上传、目录创建、文件管理等基础能力，将课程资料按科目和章节组织存储。
4. 点击"立即创建"，状态为"已上线"（个人应用无需人工审核）

### 1.4 获取应用凭证

在应用列表点击"编辑"进入应用详情页 `https://pan.baidu.com/union/console/app/<appid>`：

| 凭证 | 值 | 说明 |
|------|-----|------|
| AppID | 124199604 | 应用ID |
| AppKey | 3Sqrzxm1VQVjb93uEM7kQtd1yneYeWHN | OAuth client_id |
| SecretKey | （加密存储） | OAuth client_secret |
| SignKey | （加密存储） | 签名密钥（部分API需要） |

### 1.5 配置 OAuth 回调地址

1. 在应用详情页"安全设置"区域，点击"添加OAuth授权回调页地址"
2. 填入 `http://localhost:8080`
3. 点击"确定"保存

### 1.6 OAuth 授权流程

#### Step 1: 启动临时 HTTP 服务接收授权码

```bash
python3 -c "
import http.server
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type','text/html;charset=utf-8')
        self.end_headers()
        self.wfile.write('<h2>授权成功</h2>'.encode())
        with open('/tmp/baidu_oauth_code.txt','w') as f: f.write(self.path)
        print('CODE:', self.path, flush=True)
    def log_message(self,*a): pass
s = http.server.HTTPServer(('127.0.0.1',8080), H)
s.handle_request()
"
```

#### Step 2: 浏览器打开授权 URL

```
https://openapi.baidu.com/oauth/2.0/authorize?response_type=code&client_id=<AppKey>&redirect_uri=http://localhost:8080&scope=basic,netdisk&display=page
```

#### Step 3: 用户点击"授权"

浏览器跳转到 `http://localhost:8080/?code=<AUTH_CODE>`，临时服务接收 code。

#### Step 4: 用 code 换取 access_token

```bash
curl -X POST "https://openapi.baidu.com/oauth/2.0/token" \
  -d "grant_type=authorization_code" \
  -d "code=<AUTH_CODE>" \
  -d "client_id=<AppKey>" \
  -d "client_secret=<SecretKey>" \
  -d "redirect_uri=http://localhost:8080"
```

返回：
- `access_token`：有效期 30 天（2592000秒）
- `refresh_token`：有效期约 10 年，用于刷新 access_token
- `scope`：basic netdisk

#### Step 5: 刷新 access_token（过期后）

```bash
curl -X POST "https://openapi.baidu.com/oauth/2.0/token" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=<REFRESH_TOKEN>" \
  -d "client_id=<AppKey>" \
  -d "client_secret=<SecretKey>"
```

## 二、API 使用

### 2.1 沙箱目录限制

**重要**：个人应用只能在 `/apps/<应用名>/` 目录下操作（沙箱模式）。

- 沙箱根目录：`/apps/CPA课程归档/`
- 在网盘客户端中对应：`我的应用数据/CPA课程归档/`
- 尝试在沙箱外操作会返回错误 31064 "file is not authorized"

### 2.2 目录结构规划

完整命名规范见 [NAMING_CONVENTION.md](../../project-management/standards/NAMING_CONVENTION.md)。

```
/apps/CPA课程归档/                     ← 应用沙箱根，名称与授权绑定、不可改名（见 ADR-020）
└── 会计知识库/
    └── 高顿/                           ← 教育公司名
        └── CPA/                        ← 专业名（课程直接挂这一层，无"课程库"中间层）
            └── 【26考季】VIPCPA系列-税法（蔡俊峻老师）/
                ├── 原始资源/         ← videos/NN_讲题/{video.mp4,transcript.md}
                │                    ← notes/NN_模块/{讲义_*.pdf,讲义_*_OCR.md}
                └── 知识详解/         ← NN_模块组/{官方知识点}.md + 课程全局篇
                                     （不传 data/_workspace / transcript.json / tmp / logs）
# 同级另有 股票知识库 / 珠宝知识库，与 会计知识库 平级、互不隶属
```

### 2.3 常用 API

**直连即可，不需要代理**（Tailscale DNS 已配置 114.114.114.114 全局 nameserver 并开启 Override DNS servers）。

#### 获取用户信息

```bash
curl -s "https://pan.baidu.com/rest/2.0/xpan/nas?method=uinfo&access_token=<TOKEN>"
```

#### 创建文件夹

```bash
curl -s -X POST "https://pan.baidu.com/rest/2.0/xpan/file?method=mkdir&access_token=<TOKEN>" \
  --data-urlencode "path=/apps/CPA课程归档/税法-蔡俊峻"
```

#### 获取文件列表

```bash
curl -s "https://pan.baidu.com/rest/2.0/xpan/file?method=list&access_token=<TOKEN>&dir=<URL编码的路径>&order=time&desc=1"
```

#### 上传文件（分片上传）

使用 `code/scripts/baidu_upload.py` 脚本：

```bash
# 上传文件
BAIDU_ENC_PASS=<主密码> python3 code/scripts/baidu_upload.py upload <本地文件> <网盘路径>

# 列出目录
BAIDU_ENC_PASS=<主密码> python3 code/scripts/baidu_upload.py list <网盘目录>

# 重命名文件/目录
BAIDU_ENC_PASS=<主密码> python3 code/scripts/baidu_upload.py rename <网盘路径> <新名称>

# 删除文件/目录
BAIDU_ENC_PASS=<主密码> python3 code/scripts/baidu_upload.py delete <网盘路径>

# 创建目录
BAIDU_ENC_PASS=<主密码> python3 code/scripts/baidu_upload.py mkdir <网盘目录>

# 兼容旧用法（等同于 upload）
BAIDU_ENC_PASS=<主密码> python3 code/scripts/baidu_upload.py <本地文件> <网盘路径>
```

流程：precreate（预创建）→ upload（4MB分片上传）→ create（合并）。支持 MD5 秒传和断点续传。

> [!IMPORTANT]
> **同名文件覆盖必须传 `rtype=3`（2026-09-06 踩坑沉淀，官方文档：pan.baidu.com/union/document/upload）**
>
> 上传三步接口（precreate/create）控制重名的参数是 **`rtype`（int）**，不是 `ondup`：
>
> | rtype | 行为 |
> |---|---|
> | 0 | 不重命名，同名直接返回冲突错误 |
> | 1 | **默认**，只要 path 冲突就重命名为 `文件名_YYYYMMDD_HHMMSS.后缀` |
> | 2 | path 冲突且 block_list（内容）不同才重命名 |
> | 3 | **覆盖同名**（更新文件时必须用这个） |
>
> - `rtype` 在 **precreate 和 create 两步都要传**，放在 POST body（与 path/size/block_list 一起，官方示例即 `-d` 表单）。
> - `ondup` 是 **filemanager 复制/移动（copy/move）接口** 的参数，对上传三步接口**完全无效**；误传 ondup 不会报错，只会静默走默认 rtype=1，产生大量 `_时间戳` 改名文件。
> - `code/scripts/baidu_upload.py` 已在 precreate/create 固定 `rtype=3`；若将来看到网盘出现 `xxx_20260906_*.md` 这类文件，先检查 rtype 是否被改回。
> - 通用参数 `access_token` 必须在 URL query 里；业务参数在 body。

#### 删除文件/文件夹

```bash
curl -s -X POST "https://pan.baidu.com/rest/2.0/xpan/file?method=filemanager&access_token=<TOKEN>&opera=delete" \
  -d 'filelist=["/apps/CPA课程归档/测试目录"]'
```

#### 重命名文件/文件夹

```bash
curl -s -X POST "https://pan.baidu.com/rest/2.0/xpan/file?method=filemanager&access_token=<TOKEN>&opera=rename" \
  --data-urlencode 'filelist=[{"path":"/apps/CPA课程归档/旧名","newname":"新名称"}]'
```

**注意**：参数名是 `newname`，不是 `newtitle`。使用 `method=rename` 端点会返回 31296 internal error，必须使用 `method=filemanager&opera=rename`。

#### 移动文件/文件夹

```bash
curl -s -X POST "https://pan.baidu.com/rest/2.0/xpan/file?method=filemanager&access_token=<TOKEN>&opera=move" \
  -d 'filelist=[{"path":"/apps/CPA课程归档/旧路径","dest":"/apps/CPA课程归档/新路径"}]'
```

### 2.4 错误码

| 错误码 | 含义 | 处理 |
|--------|------|------|
| 0 | 成功 | — |
| 2 | 参数错误 | 检查请求参数 |
| -6 | 无权限访问 | 检查 access_token 和 scope |
| 111 | access_token 过期 | 用 refresh_token 刷新 |
| 31061 | 文件已存在 | mkdir 时目录已存在，可忽略 |
| 31064 | 文件未授权 | 路径超出沙箱目录 `/apps/<app名>/` |
| 42211 | 分片上传错误 | 检查分片参数 |

## 三、管理与维护

### 3.1 Token 管理

- access_token 有效期 30 天，过期前用 refresh_token 刷新
- refresh_token 有效期约 10 年，刷新后会返回新的 refresh_token（需更新保存）
- 凭证加密存储在 `.secrets/baidu_credentials.enc`（AES-256-CBC，主密码由用户保管、不入库）
- 解密命令：`openssl enc -aes-256-cbc -d -pbkdf2 -pass pass:<主密码> -base64 -in .secrets/baidu_credentials.enc`

### 3.2 应用管理

- 应用详情页：`https://pan.baidu.com/union/console/app/124199604`
- 可编辑：应用名称、描述、OAuth回调地址
- 可重置：SecretKey（重置后需重新授权）
- 删除应用：应用列表 → 删除（不可恢复）

### 3.3 授权管理

- 百度账号授权管理页：https://passport.baidu.com/accountbind
- 可在此取消应用授权，取消后 access_token 立即失效

### 3.4 网络代理

- openapi.baidu.com 和 pan.baidu.com API 端点在当前网络环境下需走 ClashX 代理（127.0.0.1:7890）
- 网盘网页端（pan.baidu.com）可直连
- 如代理不可用，需检查 ClashX 是否运行

## 四、凭证安全

- 所有凭证（AppKey/SecretKey/access_token/refresh_token）加密存储，不提交明文
- 加密文件 `.secrets/baidu_credentials.enc` 已提交到 GitHub 公有仓库（无密码无法解密）
- 解密密码由用户保管，AI 不记忆密码，需要时询问用户
- 如怀疑凭证泄露，立即在应用详情页重置 SecretKey 并重新授权

### 3.5 网络配置（Tailscale DNS 修复）

**问题**：Tailscale MagicDNS 接管系统 DNS（100.100.100.100）但未配置全局 nameserver 转发，导致非 Tailscale 域名解析超时（5秒+），表现为百度网盘 app 慢、命令行 curl 超时。

**解决**（已在 Tailscale 后台配置）：
1. 登录 https://login.tailscale.com/admin/dns
2. Global nameservers 中已有 114.114.114.114
3. 打开 **Override DNS servers** 开关（关键！）
4. 配置后 Quad100（100.100.100.100）会将非 Tailscale 域名转发给 114 DNS

**Tailscale 开机自启**：已配置 `TailscaleStartOnLogin=1` + `restartState=maintainCurrentState`，开机自动启动并保持连接。
