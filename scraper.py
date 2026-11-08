#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三省招标公告抓取器（山东 / 安徽 / 新疆）
========================================
数据来源与方式（均为低频访问：每次运行每接口 1-4 次请求，仅抓主动公开的政府公告）：
  山东  https://www.ccgp-shandong.gov.cn  官方 JSON 接口（网站搜索功能同款接口），按关键词检索
  安徽  https://zfcg.ah.gov.cn            政采云公告接口（首页采购公告板块同款），抓最新列表后本地过滤
  新疆  http://www.ccgp-xinjiang.gov.cn   政采云体系，无头浏览器渲染后解析（兜底方案）

输出 data/tenders.json，供投标情报台前端拉取。
用法：
  python3 scraper.py                # 全量（含新疆，需要 playwright）
  python3 scraper.py --no-xinjiang  # 跳过新疆（无 playwright 环境时）
"""
import json, os, sys, time, urllib.parse
from datetime import datetime

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tenders.json")
KEYWORDS = ["消毒", "医疗设备", "医疗器械", "医用耗材"]   # 山东按标题检索用
KEEP = ["消毒", "医疗设备", "医疗器械", "医用耗材", "医用", "病房", "护理", "手术",
        "灭菌", "药剂", "药品", "试剂", "卫生用品", "救护", "体检", "血透", "透析",
        "监护", "内窥", "口腔", "眼科", "超声", "影像", "康复"]  # 本地过滤
SLEEP = 3  # 请求间隔（秒），礼貌抓取

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*"})


def keep(title: str) -> bool:
    return any(k in title for k in KEEP)


def add(items, seen, **kw):
    t = (kw.get("title") or "").strip()
    key = (t, kw.get("date", ""))
    if not t or key in seen:
        return
    seen.add(key)
    items.append(kw)


# ---------------- 山东：官方搜索接口 ----------------
def shandong(items, seen):
    url = "https://www.ccgp-shandong.gov.cn:8087/api/website/site/searchAllByCode"
    base = {"type": "01", "colCode": "", "area": "", "cityType": "", "title": "",
            "projectCode": "", "currentPage": 1, "pageSize": 20, "buyKind": "",
            "buyType": "", "unitName": "", "startTime": "", "endTime": "",
            "oldData": 0, "homePage": 0, "mergeType": 0, "captchaCode": "", "captchaUuid": ""}
    n = 0
    for kw in KEYWORDS:
        body = dict(base, title=kw)
        try:
            r = session.post(url, json=body, timeout=20,
                             headers={"Referer": "https://www.ccgp-shandong.gov.cn/",
                                      "Origin": "https://www.ccgp-shandong.gov.cn"})
            recs = (((r.json().get("data") or {}).get("data") or {}).get("records")) or []
        except Exception as e:
            print(f"  [山东] {kw} 失败: {e}"); time.sleep(SLEEP); continue
        for x in recs:
            title = x.get("title", "")
            if not keep(title):
                continue
            pid = x.get("id", "")
            link = "https://www.ccgp-shandong.gov.cn/detail?id=" + urllib.parse.quote(pid, safe="")
            add(items, seen, province="山东", city=x.get("areaName", ""), title=title,
                date=(x.get("date") or "")[:10], method=x.get("buyKindCode", ""),
                agency=x.get("userName", ""), url=link, deadline="", budget=None)
            n += 1
        print(f"  [山东] 关键词「{kw}」命中 {len(recs)} 条")
        time.sleep(SLEEP)
    return n


# ---------------- 安徽：政采云列表接口（浏览器会话内调用，规避风控） ----------------
AH_SUBS = ["ZcyAnnouncement3008", "ZcyAnnouncement3001", "ZcyAnnouncement3002",
           "ZcyAnnouncement3020", "ZcyAnnouncement3011", "ZcyAnnouncement3003"]
AH_PARENT = "oJCosldFbaJFzmyFhz1c6Q=="

def anhui(items, seen):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [安徽] 未安装 playwright，跳过")
        return 0
    n = 0
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = b.new_context(user_agent=UA)
            pg = ctx.new_page()
            pg.goto("https://zfcg.ah.gov.cn/", timeout=45000, wait_until="domcontentloaded")
            pg.wait_for_timeout(6000)  # 建立正常会话 cookie
            for code in AH_SUBS:
                body = {"pageNo": 1, "pageSize": 30, "categoryCode": code,
                        "_t": int(time.time() * 1000)}
                try:
                    r = pg.request.post(
                        "https://zfcg.ah.gov.cn/portal/category", data=json.dumps(body),
                        headers={"Content-Type": "application/json",
                                 "Referer": "https://zfcg.ah.gov.cn/site/category?districtCode=340000"})
                    j = r.json()
                    if not j.get("success"):
                        print(f"  [安徽] {code} 被风控({j.get('error')})，跳过"); time.sleep(SLEEP); continue
                    lst = (((j.get("result") or {}).get("data") or {}).get("data")) or []
                except Exception as e:
                    print(f"  [安徽] {code} 失败: {e}"); time.sleep(SLEEP); continue
                for x in lst:
                    title = (x.get("title") or "").strip()
                    if not keep(title):
                        continue
                    aid = x.get("articleId", "")
                    link = (f"https://zfcg.ah.gov.cn/site/detail?parentId={urllib.parse.quote(AH_PARENT, safe='')}"
                            f"&articleId={urllib.parse.quote(aid, safe='')}")
                    bd = x.get("bidOpeningTime")
                    deadline = datetime.fromtimestamp(bd / 1000).strftime("%Y-%m-%d %H:%M") if bd else ""
                    pub = x.get("publishDate")
                    date = datetime.fromtimestamp(pub / 1000).strftime("%Y-%m-%d") if pub else ""
                    add(items, seen, province="安徽", city=x.get("districtName", ""), title=title,
                        date=date, method=x.get("procurementMethod") or "", agency=x.get("author") or "",
                        url=link, deadline=deadline, budget=x.get("budgetPrice"))
                    n += 1
                time.sleep(SLEEP)
            b.close()
    except Exception as e:
        print(f"  [安徽] 失败: {e}")
    print(f"  [安徽] 6类公告过滤后 {n} 条")
    return n


# ---------------- 新疆：无头浏览器渲染兜底 ----------------
def xinjiang(items, seen):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [新疆] 未安装 playwright，跳过（pip install playwright && playwright install chromium）")
        return 0
    n = 0
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=["--no-sandbox"])
            pg = b.new_page(user_agent=UA)
            pg.goto("http://www.ccgp-xinjiang.gov.cn/", timeout=45000, wait_until="domcontentloaded")
            pg.wait_for_timeout(9000)
            html = pg.content()
            b.close()
        import re
        ls = re.findall(r'<a[^>]+href="([^"]{10,200}(?:bidding|notice|detail)[^"]*)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{6,80})', html)
        for u, t in ls:
            t = t.strip()
            if not keep(t) or "zcygov.cn" not in u and "ccgp-xinjiang" not in u:
                continue
            u = u.replace("&amp;", "&")
            add(items, seen, province="新疆", city="", title=t, date="", method="",
                agency="", url=u, deadline="", budget=None)
            n += 1
        print(f"  [新疆] 渲染抓取 {n} 条")
    except Exception as e:
        print(f"  [新疆] 失败: {e}")
    return n


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    items, seen = [], set()
    print("开始抓取", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    shandong(items, seen)
    anhui(items, seen)
    if "--no-xinjiang" not in sys.argv:
        xinjiang(items, seen)
    items.sort(key=lambda x: x.get("date", ""), reverse=True)

    # 保护：全部源都失败时不要用空数据覆盖旧数据（常见于境外 IP 访问被拒）
    if not items:
        old = 0
        if os.path.exists(OUT):
            try:
                old = len(json.load(open(OUT, encoding="utf-8")).get("items") or [])
            except Exception:
                old = 0
        print(f"警告：本次 0 条（网络不可达或全部被拦截），保留旧数据 {old} 条，退出码 2")
        sys.exit(2)

    out = {"updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "keywords": KEEP[:4], "count": len(items), "items": items}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"完成：共 {len(items)} 条 → {OUT}")


if __name__ == "__main__":
    main()
