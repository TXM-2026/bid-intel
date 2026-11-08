# 投标情报台 · 自动抓取部署说明

## 目录内容

| 文件 | 作用 |
|---|---|
| index.html | 前端应用（已支持自动拉取 data/tenders.json） |
| scraper.py | 三省抓取器：山东（官方JSON接口）+ 安徽（政采云接口，浏览器会话）+ 新疆（无头浏览器渲染） |
| data/tenders.json | 抓取结果（前端自动加载） |
| github-workflow-scrape.yml | GitHub Actions 定时任务模板（放到仓库 .github/workflows/scrape.yml） |

## 部署步骤（约 15 分钟）

1. 建 GitHub 仓库（公开），上传本目录全部文件
2. 把 `github-workflow-scrape.yml` 移到 `.github/workflows/scrape.yml`
3. Settings → Pages → 开启，选择 main 分支根目录
4. 访问 `https://<用户名>.github.io/<仓库名>/` 即为在线版；前端会自动读取 `data/tenders.json`
5. Actions 页面每天 6:00 / 14:00（北京时间）自动抓取，也可手动触发

## 合规与礼貌抓取原则（务必遵守）

- 只抓**主动公开**的政府公告，每个接口每次运行 1-6 次请求，每天 2 次
- **不破解验证码**：遇到 NEED_CAPTCHA 立即跳过该来源，当天放弃，绝不重试破解
- 山东接口预留验证码字段，低频访问下未触发；若触发即停
- 安徽风控较敏感（Referer/Cookie 校验），脚本已用真实浏览器会话调用；若持续被拦，等 24 小时或更换部署 IP

## 关键接口备忘（抓取器内部已实现，留档备查）

- 山东：`POST https://www.ccgp-shandong.gov.cn:8087/api/website/site/searchAllByCode`
  body 含 title（关键词）/ currentPage / pageSize；详情页 `https://www.ccgp-shandong.gov.cn/detail?id=<url编码的id>`
- 安徽：`POST https://zfcg.ah.gov.cn/portal/category`
  body: {pageNo, pageSize, categoryCode: "ZcyAnnouncement3001~3020"}；Referer 必须是站内列表页；详情 `https://zfcg.ah.gov.cn/site/detail?parentId=oJCosldFbaJFzmyFhz1c6Q==&articleId=<articleId>`
- 新疆：无独立接口，无头浏览器渲染 http://www.ccgp-xinjiang.gov.cn/ 后解析链接（政采云体系 zxxj/fwsc.zcygov.cn）

## 后续可扩展

- 增加省份：照安徽的「监听列表页接口 → 复刻请求」流程即可
- 微信推送：抓取后调用 Server酱/企业微信 webhook，把新公告推到手机
- 更换部署：任何能跑 Python + 定时任务的环境都可以（轻量云服务器约 ¥50/月）
