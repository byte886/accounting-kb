#!/usr/bin/env python3
"""百度网盘文件管理脚本 - 上传、列出、重命名、移动、删除、创建目录

用法:
  BAIDU_ENC_PASS=<主密码> python3 baidu_upload.py upload <本地文件> <网盘路径>
  BAIDU_ENC_PASS=<主密码> python3 baidu_upload.py list <网盘目录>
  BAIDU_ENC_PASS=<主密码> python3 baidu_upload.py rename <网盘路径> <新名称>
  BAIDU_ENC_PASS=<主密码> python3 baidu_upload.py move <网盘源路径> <目标父目录> [新名称]
  BAIDU_ENC_PASS=<主密码> python3 baidu_upload.py delete <网盘路径>
  BAIDU_ENC_PASS=<主密码> python3 baidu_upload.py mkdir <网盘目录>

兼容旧用法: python3 baidu_upload.py <本地文件> <网盘路径> [token]

网盘路径必须以 /apps/CPA课程归档/ 开头（该沙箱根名与应用授权绑定、不可改名；2026-09-12 起课程统一在 /apps/CPA课程归档/会计知识库/高顿/CPA/ 下，见 ADR-020）。
直连百度服务器（国内服务，不走代理）。
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

CHUNK_SIZE = 4 * 1024 * 1024  # 4MB
API_BASE = "https://pan.baidu.com/rest/2.0/xpan/file"
UPLOAD_BASE = "https://d.pcs.baidu.com/rest/2.0/pcs/superfile2"


def get_token():
    """从加密文件解密获取 access_token"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    enc_file = os.path.join(project_dir, ".secrets", "baidu_credentials.enc")

    password = os.environ.get("BAIDU_ENC_PASS", "")
    if not password:
        import getpass
        password = getpass.getpass("Enter decryption password: ")

    result = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-d", "-pbkdf2",
         "-pass", f"pass:{password}", "-base64", "-in", enc_file],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Decrypt failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)["access_token"]


def curl_api(url, params=None, data=None, file_path=None, file_field="file", timeout=300):
    """通过 curl 直连调用 API（不走代理）"""
    if params:
        # query 参数必须百分号编码：远端 path 含空格/中文【】时，裸字符会让
        # superfile2 分片上传的 URL 非法（curl 退出码非 0、stderr 为空，表现为 "curl failed:"）。
        # precreate/create 走 POST --data-urlencode 已编码，唯独分片上传的 query 曾漏编码。
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in params.items())

    cmd = ["curl", "-s", "--connect-timeout", "10"]

    if file_path:
        # 上传分片可经环境变量限速（如 BAIDU_UPLOAD_RATE=1500k / 2m），
        # 避免占满上行带宽影响其它 App；只限速上传分片，list/mkdir 等小请求不受影响。
        rate = os.environ.get("BAIDU_UPLOAD_RATE", "").strip()
        if rate:
            cmd += ["--limit-rate", rate]
        cmd += ["-F", f"{file_field}=@{file_path}"]
    if data:
        for k, v in data.items():
            cmd += ["--data-urlencode", f"{k}={v}"]
    elif not file_path:
        cmd += ["-X", "POST"]

    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr}")
    return json.loads(result.stdout)


def upload_file(local_path, remote_path, token):
    """分片上传文件到百度网盘"""
    file_size = os.path.getsize(local_path)
    print(f"Uploading: {local_path} ({file_size / 1024 / 1024:.1f} MB)")
    print(f"Remote: {remote_path}")

    # 1. 计算分片 MD5
    chunks = []
    block_list = []
    with open(local_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            chunks.append(chunk)
            block_list.append(hashlib.md5(chunk).hexdigest())
    print(f"Chunks: {len(chunks)}")

    # 2. precreate
    print("[1/3] Precreate...")
    # rtype=3 覆盖同名（官方文档：0冲突/1冲突即重命名[默认]/2内容不同才重命名/3覆盖）
    # 注意：上传三步接口用 rtype，不是 ondup（ondup 是 filemanager 复制/移动接口的参数）
    result = curl_api(API_BASE, {
        "method": "precreate",
        "access_token": token,
    }, {
        "path": remote_path,
        "size": str(file_size),
        "isdir": "0",
        "autoinit": "1",
        "rtype": "3",
        "block_list": json.dumps(block_list),
    })
    if result.get("errno") != 0:
        print(f"Precreate failed: {result}", file=sys.stderr)
        sys.exit(1)
    uploadid = result["uploadid"]
    need_upload = result.get("block_list", list(range(len(chunks))))
    print(f"  Need upload: {len(need_upload)} chunks (MD5 sec-upload possible)")

    # 3. 上传分片
    tmp_dir = tempfile.mkdtemp(prefix="baidu_upload_")
    try:
        for i, seq in enumerate(need_upload):
            chunk_file = os.path.join(tmp_dir, f"chunk_{seq}")
            with open(chunk_file, "wb") as f:
                f.write(chunks[seq])

            pct = (i + 1) / len(need_upload) * 100
            print(f"[2/3] Chunk {seq} ({i+1}/{len(need_upload)}, {pct:.0f}%)...", end=" ", flush=True)
            result = curl_api(UPLOAD_BASE, {
                "method": "upload",
                "access_token": token,
                "type": "tmpfile",
                "path": remote_path,
                "uploadid": uploadid,
                "partseq": str(seq),
            }, file_path=chunk_file)
            os.remove(chunk_file)

            if "md5" in result:
                print("OK")
            else:
                print(f"FAILED: {result}")
                sys.exit(1)
    finally:
        # 容错清理：分片残留/系统占用导致目录非空时不能抛错，
        # 否则会在下方 create 合并前中断、造成云端缺件（曾现 Errno 66）。
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # 4. create (合并)
    print("[3/3] Merging chunks...")
    # rtype=3 覆盖同名（precreate/create 都要传；默认 1 会重命名为 文件名_日期.后缀）
    result = curl_api(API_BASE, {
        "method": "create",
        "access_token": token,
    }, {
        "path": remote_path,
        "size": str(file_size),
        "isdir": "0",
        "rtype": "3",
        "block_list": json.dumps(block_list),
        "uploadid": uploadid,
    })
    if result.get("errno") != 0:
        print(f"Create failed: {result}", file=sys.stderr)
        sys.exit(1)
    print(f"  Done! fs_id: {result.get('fs_id')}, size: {result.get('size')}")
    return result


def mkdir_p(remote_dir, token):
    """递归创建网盘目录（沙箱内，跳过 /apps 系统目录）"""
    parts = remote_dir.strip("/").split("/")
    current = ""
    for part in parts:
        current += "/" + part
        if current == "/apps":
            continue
        result = curl_api(API_BASE, {
            "method": "mkdir",
            "access_token": token,
        }, {"path": current})
        if result.get("errno") == 0:
            print(f"  Created: {current}")
        elif result.get("errno") == 31061 or result.get("error_code") == 31061:
            pass  # already exists
        else:
            print(f"  mkdir {current} returned: {result}")


def list_files(remote_dir, token):
    """列出网盘目录下的文件和子目录"""
    import urllib.parse
    url = f"{API_BASE}?method=list&access_token={token}&dir={urllib.parse.quote(remote_dir)}&web=web"
    cmd = ["curl", "-s", "--connect-timeout", "10", url]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    data = json.loads(result.stdout)
    if data.get("errno") != 0:
        print(f"List failed: {data}", file=sys.stderr)
        return []
    items = data.get("list", [])
    for item in items:
        t = "目录" if item["isdir"] else f"{item['size']}B"
        print(f"  {item['server_filename']} ({t})")
    return items


def rename_file(remote_path, new_name, token):
    """重命名网盘文件或目录（使用 filemanager API）"""
    filelist = json.dumps([{"path": remote_path, "newname": new_name}])
    result = curl_api(API_BASE, {
        "method": "filemanager",
        "access_token": token,
        "opera": "rename",
    }, {
        "filelist": filelist,
    })
    if result.get("errno") == 0:
        print(f"  Renamed: {remote_path} -> {new_name}")
    else:
        print(f"  Rename failed: {result}", file=sys.stderr)
    return result


def move_file(src_path, dest_dir, token, new_name=None):
    """移动网盘文件或目录到目标父目录（filemanager opera=move，服务端秒移、不重传）。

    dest_dir 为目标「父目录」；可选 new_name 同时改名。支持整目录移动。
    """
    entry = {"path": src_path, "dest": dest_dir}
    if new_name:
        entry["newname"] = new_name
    filelist = json.dumps([entry])
    result = curl_api(API_BASE, {
        "method": "filemanager",
        "access_token": token,
        "opera": "move",
    }, {
        "filelist": filelist,
    })
    target = f"{dest_dir}/{new_name or os.path.basename(src_path)}"
    if result.get("errno") == 0:
        print(f"  Moved: {src_path} -> {target}")
    else:
        print(f"  Move failed: {result}", file=sys.stderr)
    return result


def delete_file(remote_path, token):
    """删除网盘文件或目录（使用 filemanager API）"""
    filelist = json.dumps([remote_path])
    result = curl_api(API_BASE, {
        "method": "filemanager",
        "access_token": token,
        "opera": "delete",
    }, {
        "filelist": filelist,
    })
    if result.get("errno") == 0:
        print(f"  Deleted: {remote_path}")
    else:
        print(f"  Delete failed: {result}", file=sys.stderr)
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    token = get_token()

    # 兼容旧用法: python3 baidu_upload.py <本地文件> <网盘路径>
    if command not in ("upload", "list", "rename", "move", "delete", "mkdir"):
        local_file = sys.argv[1]
        remote_file = sys.argv[2]
        if not os.path.isfile(local_file):
            print(f"File not found: {local_file}", file=sys.stderr)
            sys.exit(1)
        remote_dir = os.path.dirname(remote_file)
        if remote_dir and remote_dir != "/":
            print(f"Ensuring directory: {remote_dir}")
            mkdir_p(remote_dir, token)
        upload_file(local_file, remote_file, token)
        sys.exit(0)

    if command == "upload":
        if len(sys.argv) < 4:
            print("用法: baidu_upload.py upload <本地文件> <网盘路径>", file=sys.stderr)
            sys.exit(1)
        local_file = sys.argv[2]
        remote_file = sys.argv[3]
        if not os.path.isfile(local_file):
            print(f"File not found: {local_file}", file=sys.stderr)
            sys.exit(1)
        remote_dir = os.path.dirname(remote_file)
        if remote_dir and remote_dir != "/":
            print(f"Ensuring directory: {remote_dir}")
            mkdir_p(remote_dir, token)
        upload_file(local_file, remote_file, token)

    elif command == "list":
        if len(sys.argv) < 3:
            print("用法: baidu_upload.py list <网盘目录>", file=sys.stderr)
            sys.exit(1)
        list_files(sys.argv[2], token)

    elif command == "rename":
        if len(sys.argv) < 4:
            print("用法: baidu_upload.py rename <网盘路径> <新名称>", file=sys.stderr)
            sys.exit(1)
        rename_file(sys.argv[2], sys.argv[3], token)

    elif command == "move":
        if len(sys.argv) < 4:
            print("用法: baidu_upload.py move <网盘源路径> <目标父目录> [新名称]", file=sys.stderr)
            sys.exit(1)
        new_name = sys.argv[4] if len(sys.argv) >= 5 else None
        move_file(sys.argv[2], sys.argv[3], token, new_name)

    elif command == "delete":
        if len(sys.argv) < 3:
            print("用法: baidu_upload.py delete <网盘路径>", file=sys.stderr)
            sys.exit(1)
        delete_file(sys.argv[2], token)

    elif command == "mkdir":
        if len(sys.argv) < 3:
            print("用法: baidu_upload.py mkdir <网盘目录>", file=sys.stderr)
            sys.exit(1)
        mkdir_p(sys.argv[2], token)
