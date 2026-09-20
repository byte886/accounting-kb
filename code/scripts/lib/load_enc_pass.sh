#!/bin/bash
# =============================================================================
# load_enc_pass.sh — 解析主加密密码并 export BAIDU_ENC_PASS（供各脚本 source）
#
# 主密码绝不写进入库脚本。三级回退（优先级从高到低）：
#   1) 已存在的环境变量 BAIDU_ENC_PASS（CI / 手动临时指定）
#   2) 本机主密码文件 $DOUBAO_MASTER_PASS_FILE（默认 ~/.doubao/secrets/master.pass，
#      600 权限、在所有 git 仓库之外、永不入库）——保证自动化非交互
#   3) 交互安全输入 read -s（人工运行）
# 都拿不到则报错退出。加解密算法与全局命令 secrets 一致，规范见
# mac-system-toolkit 的 references/secret-encryption.md。
#
# 用法（在脚本顶部、定位到 SCRIPT_DIR 之后）：
#   source "$SCRIPT_DIR/lib/load_enc_pass.sh"
# =============================================================================

: "${DOUBAO_MASTER_PASS_FILE:=$HOME/.doubao/secrets/master.pass}"

if [ -z "${BAIDU_ENC_PASS:-}" ]; then
  if [ -f "$DOUBAO_MASTER_PASS_FILE" ]; then
    BAIDU_ENC_PASS="$(tr -d '\r\n' < "$DOUBAO_MASTER_PASS_FILE")"
  elif [ -t 0 ]; then
    read -s -p "Enter BAIDU encryption password: " BAIDU_ENC_PASS; echo
  fi
fi

if [ -z "${BAIDU_ENC_PASS:-}" ]; then
  echo "[load_enc_pass] 未取得主密码：请 export BAIDU_ENC_PASS，或建立 600 权限的 $DOUBAO_MASTER_PASS_FILE" >&2
  # 被 source 时 return，被直接执行时 exit
  return 1 2>/dev/null || exit 1
fi

export BAIDU_ENC_PASS
