#!/bin/bash
# check_git_hygiene.sh — Git 仓库卫生体检（只读，不修改任何文件/暂存区）
# ---------------------------------------------------------------------------
# 查四件事：
#   ① 已被 git 跟踪的文件里，是否混入运行产物/环境/数据（存量漏网）
#   ② 未跟踪项分类：像运行产物的提示补 .gitignore，其余提示确认是否入库
#   ③ 被跟踪的大文件（>1MB）
#   ④ .git 与工作区体积
# 运行产物模式 ARTIFACT_RE 必须与 scripts/pre-commit 第 4 项、.gitignore 三处保持一致；
# 新增一类运行产物时三处同步（依据 PROJECT_STRUCTURE_MAINTENANCE「产物落点与忽略模式表」）。
# 用法: bash scripts/check_git_hygiene.sh
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

ARTIFACT_RE='(^|/)(venv|env|node_modules|__pycache__|\.tmp[^/]*|logs)(/|$)|(^|/)data/|(^|/)\.[A-Za-z0-9_]*done$|\.done$|\.pyc$|\.DS_Store$|(^|/)(transcripts_full|transcripts)(/|$)'
WHITELIST='^transcription/requirements\.txt$'
issues=0

echo "=== ① 已跟踪文件中的运行产物（应为空）==="
found="$(git ls-files | grep -E "$ARTIFACT_RE" | grep -vE "$WHITELIST" || true)"
if [ -n "$found" ]; then
  echo "$found" | sed 's/^/  ❌ /'; issues=$((issues + 1))
else
  echo "  ✓ 无"
fi

echo ""
echo "=== ② 未跟踪项（未被 .gitignore 忽略；判断该入库还是补忽略）==="
untracked="$(git ls-files --others --exclude-standard)"
if [ -n "$untracked" ]; then
  while IFS= read -r f; do
    if echo "$f" | grep -qE "$ARTIFACT_RE"; then
      echo "  ⚠️ 像运行产物，建议补 .gitignore: $f"; issues=$((issues + 1))
    else
      echo "  · 待确认是否入库: $f"
    fi
  done <<< "$untracked"
else
  echo "  ✓ 无未跟踪项"
fi

echo ""
echo "=== ③ 被跟踪的大文件（>1MB，成品大文件应走网盘）==="
big=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  sz=$(stat -f%z "$f" 2>/dev/null || echo 0)
  if [ "${sz:-0}" -gt 1048576 ]; then echo "  $((sz / 1024))KB  $f"; big=1; fi
done < <(git ls-files)
[ "$big" -eq 0 ] && echo "  ✓ 无 >1MB 的被跟踪文件"

echo ""
echo "=== ④ 体积 ==="
echo "  .git: $(du -sh .git | cut -f1)    工作区总计: $(du -sh . | cut -f1)"

echo ""
if [ "$issues" -gt 0 ]; then
  echo "❌ 发现 $issues 类卫生问题（见上 ⚠️/❌）；正式文件请正常 add，运行产物请补 .gitignore 并 git rm --cached。"
  exit 1
fi
echo "✅ 仓库卫生检查通过：无运行产物混入跟踪、无疑似漏忽略。"
exit 0
