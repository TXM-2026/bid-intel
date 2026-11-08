#!/bin/bash
# 一键部署投标情报台到 GitHub Pages + 开启定时抓取
# 用法： source /root/.codebuddy/skills/github-connector/scripts/get_token.sh github && bash deploy_github.sh [仓库名]
set -e

REPO_NAME="${1:-bid-intel}"
DIR="/workspace/bidapp"

if [ -z "$GITHUB_TOKEN" ]; then
  echo "缺少 GITHUB_TOKEN"; exit 1
fi

API="https://api.github.com"
OWNER=$(curl -s -H "Authorization: Bearer ${GITHUB_TOKEN}" "$API/user" | python3 -c "import json,sys;print(json.load(sys.stdin)['login'])")
echo "账号：$OWNER  仓库：$REPO_NAME"

# 1. 建仓库（已存在则复用）
CODE=$(curl -s -o /tmp/repo.json -w "%{http_code}" -X POST "$API/user/repos" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" -H "Accept: application/vnd.github+json" \
  -d "{\"name\":\"${REPO_NAME}\",\"private\":false,\"description\":\"消毒产品与医疗器械投标情报台（自动抓取山东/安徽/新疆招标公告）\",\"has_issues\":false,\"has_wiki\":false}")
if [ "$CODE" = "201" ]; then echo "✓ 仓库已创建";
elif [ "$CODE" = "422" ]; then echo "· 仓库已存在，复用";
else echo "创建失败 HTTP $CODE"; cat /tmp/repo.json; exit 1; fi

# 2. 推送代码
cd "$DIR"
rm -f github-workflow-scrape.yml          # 已放入 .github/workflows/
touch .nojekyll
git init -q 2>/dev/null || true
git config user.name "tenders-bot"
git config user.email "bot@users.noreply.github.com"
git remote remove origin 2>/dev/null || true
git remote add origin "https://oauth2:${GITHUB_TOKEN}@github.com/${OWNER}/${REPO_NAME}.git"
git add -A
git commit -qm "投标情报台：自动抓取 + 进度看板 + 真实案例" || echo "· 无新变更"
git branch -M main
git push -u origin main -f
echo "✓ 代码已推送"

# 3. 开 GitHub Pages（main 根目录）
sleep 3
PC=$(curl -s -o /tmp/pages.json -w "%{http_code}" -X POST "$API/repos/${OWNER}/${REPO_NAME}/pages" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" -H "Accept: application/vnd.github+json" \
  -d '{"source":{"branch":"main","path":"/"}}')
if [ "$PC" = "201" ] || [ "$PC" = "409" ]; then echo "✓ Pages 已开启"; else echo "Pages HTTP $PC"; cat /tmp/pages.json; fi

# 4. 立即触发一次抓取
sleep 3
curl -s -o /dev/null -w "触发抓取 HTTP %{http_code}\n" -X POST \
  "$API/repos/${OWNER}/${REPO_NAME}/actions/workflows/scrape.yml/dispatches" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" -H "Accept: application/vnd.github+json" \
  -d '{"ref":"main"}'

echo ""
echo "=============================================="
echo "页面地址：https://${OWNER}.github.io/${REPO_NAME}/"
echo "仓库地址：https://github.com/${OWNER}/${REPO_NAME}"
echo "Actions ：https://github.com/${OWNER}/${REPO_NAME}/actions"
echo "=============================================="
echo "首次部署 Pages 约需 1-2 分钟生效；Actions 首次抓取也在 2 分钟内完成。"
