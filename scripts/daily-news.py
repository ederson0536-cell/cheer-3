#!/usr/bin/env python3
"""
Daily News Script - With detailed analysis
"""
import json
import urllib.request
from datetime import datetime
import sys

NOTION_API = "ntn_i22531036946mxbXeoh2kbxXS3bwjeRiWc2m4vj9jUS8Zs"
NOTION_PAGE_ID = "31c0864b-a24e-80c5-b7b8-ea508e0d5332"

def fetch_news():
    """Fetch news with detailed analysis"""
    # Mock data with full analysis
    news_items = [
        {
            "title": "🌍 全球股市回调",
            "summary": "受中东局势影响，全球股市下跌",
            "analysis": """
【背景】
- 中东地区紧张局势升级，导致投资者避险情绪升温
- 黄金、美元等避险资产需求上升

【影响】
- 短线：股市承压，可能持续1-2周
- 中线：若局势缓和，股市有望反弹
- 对A股：有一定联动效应，但影响有限

【建议】
- 关注事态发展
- 可适当配置避险资产
"""
        },
        {
            "title": "🇨🇳 中国货币政策",
            "summary": "央行表示维持适度宽松",
            "analysis": """
【背景】
- 央行货币政策委员会召开会议
- 重申稳健货币政策基调

【影响】
- 对市场：流动性保持合理充裕
- 对企业：融资环境有望改善
- 对个人：房贷利率可能继续下行

【解读】
- 稳增长仍是首要目标
- 结构性货币政策工具将发力
"""
        },
        {
            "title": "💻 科技动态",
            "summary": "AI领域持续快速发展",
            "analysis": """
【趋势】
- 大模型能力持续提升
- AI应用场景不断拓展

【影响】
- 行业：AI赛道竞争加剧
- 就业：部分岗位可能被替代
- 生活：智能化程度提高

【建议】
- 关注AI应用落地情况
- 把握产业变革机会
"""
        }
    ]
    return news_items

def delete_old():
    url = f"https://api.notion.com/v1/blocks/{NOTION_PAGE_ID}/children"
    try:
        req = urllib.request.Request(url, method="GET", headers={"Authorization": f"Bearer {NOTION_API}", "Notion-Version": "2022-06-28"})
        response = urllib.request.urlopen(req, timeout=30)
        result = json.loads(response.read().decode())
        if "results" not in result:
            return
        for block in result["results"][2:]:
            try:
                urllib.request.urlopen(urllib.request.Request(f"https://api.notion.com/v1/blocks/{block['id']}", method="DELETE", headers={"Authorization": f"Bearer {NOTION_API}", "Notion-Version": "2022-06-28"}), timeout=10)
            except:
                pass
    except:
        pass

def upload(news):
    timestamp = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    blocks = [{"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": f"📰 {timestamp} 新闻深度解读"}}]}}]
    for item in news:
        blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": item['title']}}]}})
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"📝 {item.get('summary', '')}"}}]}})
        if item.get('analysis'):
            blocks.append({"object": "block", "type": "quote", "quote": {"rich_text": [{"type": "text", "text": {"content": item['analysis'].strip()}}]}})
        blocks.append({"object": "block", "type": "divider", "divider": {}})
    blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"生成时间: {timestamp}"}}]}})
    
    try:
        req = urllib.request.Request(f"https://api.notion.com/v1/blocks/{NOTION_PAGE_ID}/children", data=json.dumps({"children": blocks}).encode(), method="PATCH", headers={"Authorization": f"Bearer {NOTION_API}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"})
        urllib.request.urlopen(req, timeout=30)
        print("✅ Uploaded with analysis")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def should_run(force=False):
    """Check if news should run now"""
    if force:
        return True
    return datetime.now().hour in [8, 20]

if __name__ == "__main__":
    force = "--force" in sys.argv or "-f" in sys.argv
    if not should_run(force):
        hour = datetime.now().hour
        print(f"⏰ Not 8am/8pm, skipping (hour: {hour}). Use --force to run anyway.")
        sys.exit(0)
    print("🗑️ Deleting old...")
    delete_old()
    print("📥 Fetching news...")
    news = fetch_news()
    print(f"📤 Uploading {len(news)} items...")
    upload(news)
    print("✅ Done!")
