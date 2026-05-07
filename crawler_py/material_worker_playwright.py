import argparse
import hashlib
import html
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import quote, urljoin

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import Cursor

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except Exception:
    sync_playwright = None
    PlaywrightTimeoutError = Exception

from db_config import DB_CONFIG


# 当前采样规则：每个热点抓 3 条相关内容，每条内容尝试抓 10 条热门评论。
POSTS_PER_HOTSPOT = 3
COMMENTS_PER_POST = 10

# 浏览器自动化相关配置
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
BROWSER_PROFILE_DIR = BASE_DIR / "weibo_browser_profile"

SEARCH_PAGE_URL = "https://s.weibo.com/weibo?q={keyword}"
WEIBO_HOME_URL = "https://weibo.com"
WEIBO_MOBILE_HOME_URL = "https://m.weibo.cn"

PAGE_TIMEOUT_MS = 25000
REQUEST_SLEEP_SECONDS = 1.2


if load_dotenv:
    load_dotenv(ENV_FILE)


def get_connection() -> Connection:
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG["charset"],
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def clean_html_text(value: Optional[str]) -> str:
    if not value:
        return ""

    text = html.unescape(str(value))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_keyword(title: str) -> str:
    keyword = (title or "").strip()
    if keyword.startswith("#") and keyword.endswith("#") and len(keyword) > 2:
        keyword = keyword[1:-1]
    return keyword.strip()


def to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    text = str(value).strip()
    text = text.replace(",", "")
    try:
        if text.endswith("万"):
            return int(float(text[:-1]) * 10000)
        if text.endswith("亿"):
            return int(float(text[:-1]) * 100000000)
        return int(float(text))
    except Exception:
        return default


def stable_id(*parts: Any, prefix: str = "") -> str:
    raw = "|".join(str(part or "") for part in parts)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return f"{prefix}{digest}" if prefix else digest


def parse_count_from_text(text: str, labels: List[str]) -> int:
    if not text:
        return 0

    for label in labels:
        # 常见形式：赞 123、赞3万、评论 18、转发 2
        pattern = rf"{label}\s*([0-9]+(?:\.[0-9]+)?[万亿]?)"
        match = re.search(pattern, text)
        if match:
            return to_int(match.group(1), 0)

    return 0


def extract_comment_dicts_from_payload(payload: Any, limit: int = COMMENTS_PER_POST) -> List[Dict[str, Any]]:
    """
    从微博页面产生的 JSON 响应里递归提取评论。
    浏览器自动化时，评论通常是页面异步请求返回的 JSON，比纯 DOM 解析更稳。
    """
    comments: List[Dict[str, Any]] = []
    seen = set()

    def walk(obj: Any) -> None:
        if len(comments) >= limit * 3:
            return

        if isinstance(obj, list):
            for item in obj:
                walk(item)
            return

        if not isinstance(obj, dict):
            return

        text = clean_html_text(obj.get("text_raw") or obj.get("text") or obj.get("content"))
        comment_id = str(obj.get("id") or obj.get("idstr") or obj.get("comment_id") or "").strip()

        # 尽量只把“像评论”的对象收进来，避免把微博正文、配置项误识别成评论。
        looks_like_comment = bool(text) and (
            bool(comment_id)
            or "like_count" in obj
            or "total_number" in obj
            or "reply_count" in obj
            or isinstance(obj.get("user"), dict)
        )

        if looks_like_comment and len(text) >= 2:
            user = obj.get("user") or {}
            source_comment_id = comment_id or stable_id(text, prefix="weibo_comment_")

            if source_comment_id not in seen:
                comments.append({
                    "sourceCommentId": str(source_comment_id)[:100],
                    "content": text[:1000],
                    "authorName": user.get("screen_name") or user.get("name"),
                    "likeCount": to_int(obj.get("like_count") or obj.get("like_counts") or obj.get("attitudes_count")),
                    "replyCount": to_int(obj.get("total_number") or obj.get("reply_count") or obj.get("comments_count")),
                    "publishTime": None,
                    "rawJson": json.dumps(obj, ensure_ascii=False)[:60000],
                })
                seen.add(source_comment_id)

        for value in obj.values():
            if isinstance(value, (dict, list)):
                walk(value)

    walk(payload)
    comments.sort(key=lambda item: item.get("likeCount", 0), reverse=True)
    return comments[:limit]


def try_switch_to_hot_comments(page) -> None:
    """
    尝试把评论区切换成热门/按热度排序。
    不同微博页面文案和 DOM 会变化，所以失败时静默跳过。
    """
    hot_texts = ["按热度", "热度", "热门", "热门评论", "最热", "热评"]
    for text in hot_texts:
        try:
            target = page.get_by_text(text, exact=False).first
            if target.count() > 0:
                target.click(timeout=1200)
                page.wait_for_timeout(1200)
                return
        except Exception:
            continue



def fetch_pending_material_tasks(cursor: Cursor, limit: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT id, hotspot_id, platform, title
        FROM hotspot_material_task
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT %s
    """
    cursor.execute(sql, (limit,))
    return list(cursor.fetchall())


def create_browser_context(headless: bool = False):
    if sync_playwright is None:
        raise RuntimeError(
            "未安装 playwright。请先执行：pip install playwright，然后执行：python -m playwright install chromium"
        )

    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_PROFILE_DIR),
        headless=headless,
        viewport={"width": 1366, "height": 900},
        locale="zh-CN",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ],
    )
    context.set_default_timeout(PAGE_TIMEOUT_MS)
    return playwright, context


def login_weibo_once() -> None:
    """
    第一次使用时运行：python material_worker.py --login
    会打开浏览器，你手动登录微博。登录完成后按回车，登录状态会保存在 crawler_py/weibo_browser_profile。
    """
    playwright, context = create_browser_context(headless=False)
    try:
        page = context.new_page()
        page.goto(WEIBO_HOME_URL, wait_until="domcontentloaded")
        print("浏览器已打开。请在弹出的浏览器中手动登录微博。")
        print("登录成功并确认页面显示你的账号后，回到这个终端按回车继续。")
        input("登录完成后按回车保存登录状态...")
        context.storage_state(path=str(BASE_DIR / "weibo_storage_state.json"))
        print("已保存浏览器登录状态。以后运行 material_worker.py 会复用这个浏览器配置。")
    finally:
        context.close()
        playwright.stop()


def page_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=5000)
    except Exception:
        return ""


def looks_like_login_required(text: str) -> bool:
    if not text:
        return False

    keywords = [
        "登录",
        "注册",
        "验证码",
        "访问异常",
        "安全验证",
        "请先登录",
        "您的访问过于频繁",
    ]
    return any(word in text for word in keywords)


def open_search_page(page, keyword: str) -> None:
    url = SEARCH_PAGE_URL.format(keyword=quote(keyword))
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    # 模拟轻微滚动，让动态内容加载得更完整。
    for _ in range(2):
        page.mouse.wheel(0, random.randint(500, 900))
        page.wait_for_timeout(random.randint(800, 1300))


def extract_text_from_locator(locator) -> str:
    try:
        return clean_html_text(locator.inner_text(timeout=1500))
    except Exception:
        return ""


def extract_first_attribute(locator, name: str) -> Optional[str]:
    try:
        value = locator.first.get_attribute(name, timeout=1500)
        return value
    except Exception:
        return None


def extract_posts_from_search_page(page, keyword: str, limit: int) -> List[Dict[str, Any]]:
    """
    从 s.weibo.com 搜索结果页解析微博卡片。
    该方式比直接打 API 更像正常用户，但微博页面结构可能变化，所以这里做了多种选择器兜底。
    """
    body = page_text(page)
    if looks_like_login_required(body) and "全部" not in body and "相关微博" not in body:
        raise RuntimeError("微博搜索页可能要求登录/验证，请先运行 python material_worker.py --login 手动登录。")

    card_locators = [
        'div.card-wrap[action-type="feed_list_item"]',
        'div.card-wrap',
    ]

    cards = []
    for selector in card_locators:
        try:
            cards = page.locator(selector).all()
            if cards:
                break
        except Exception:
            cards = []

    posts: List[Dict[str, Any]] = []
    seen = set()

    for card in cards:
        if len(posts) >= limit:
            break

        try:
            raw_card_text = extract_text_from_locator(card)
            if not raw_card_text:
                continue

            # 排除导航、推荐、筛选等非微博结果卡片。
            if "高级搜索" in raw_card_text or "相关搜索" in raw_card_text:
                continue

            text_candidates = [
                card.locator("p.txt").last,
                card.locator(".content p").first,
                card.locator("p").first,
            ]

            content = ""
            for candidate in text_candidates:
                content = extract_text_from_locator(candidate)
                if len(content) >= 10:
                    break

            if not content:
                content = raw_card_text

            # 过短或明显不是微博正文的跳过。
            if len(content) < 10:
                continue

            author = extract_text_from_locator(card.locator("a.name").first)
            if not author:
                author = extract_text_from_locator(card.locator(".name").first)

            source_href = (
                extract_first_attribute(card.locator("p.from a"), "href")
                or extract_first_attribute(card.locator("a[action-type='feed_list_item_date']"), "href")
                or extract_first_attribute(card.locator("a[action-type='fl_unfold']"), "href")
                or ""
            )

            source_url = urljoin("https:", source_href) if source_href.startswith("//") else source_href
            if source_url and source_url.startswith("/"):
                source_url = urljoin("https://weibo.com", source_url)

            mid = (
                card.get_attribute("mid") if hasattr(card, "get_attribute") else None
            ) or source_url or stable_id(keyword, content, prefix="weibo_post_")

            mid = str(mid).strip()
            if mid in seen:
                continue

            like_count = parse_count_from_text(raw_card_text, ["赞", "点赞"])
            comment_count = parse_count_from_text(raw_card_text, ["评论"])
            repost_count = parse_count_from_text(raw_card_text, ["转发"])

            posts.append({
                "sourceItemId": mid[:100],
                "contentType": "post",
                "title": keyword,
                "content": content,
                "authorName": author or None,
                "sourceUrl": source_url or None,
                "coverUrl": None,
                "mediaUrls": None,
                "likeCount": like_count,
                "commentCount": comment_count,
                "repostCount": repost_count,
                "publishTime": None,
                "rawJson": json.dumps({
                    "keyword": keyword,
                    "source_url": source_url,
                    "raw_text": raw_card_text[:3000],
                }, ensure_ascii=False),
                "mid": mid,
            })
            seen.add(mid)

        except Exception:
            continue

    return posts[:limit]


def fetch_weibo_posts_by_browser(context, keyword: str, limit: int = POSTS_PER_HOTSPOT) -> List[Dict[str, Any]]:
    page = context.new_page()
    try:
        open_search_page(page, keyword)
        posts = extract_posts_from_search_page(page, keyword, limit=limit)

        if not posts:
            body = page_text(page)
            if looks_like_login_required(body):
                raise RuntimeError("微博搜索页没有返回有效内容，疑似登录态失效或触发验证。请重新运行 python material_worker.py --login。")
            raise RuntimeError("微博搜索页未解析到相关帖子，可能是页面结构变化或该关键词结果较少。")

        return posts
    finally:
        page.close()


def extract_comments_from_detail_page(page, limit: int) -> List[Dict[str, Any]]:
    """
    兜底方案：从微博详情页可见 DOM 中解析评论。
    优先级低于网络 JSON 抓取，但当接口响应未被捕获时仍可补数据。
    """
    try_switch_to_hot_comments(page)

    for _ in range(5):
        page.mouse.wheel(0, random.randint(800, 1400))
        page.wait_for_timeout(random.randint(900, 1500))

    candidates = [
        "div[comment_id]",
        "div[class*='comment']",
        "div[class*='Comment']",
        ".list_li",
        ".WB_text",
    ]

    comments: List[Dict[str, Any]] = []
    seen = set()

    for selector in candidates:
        try:
            nodes = page.locator(selector).all()
        except Exception:
            nodes = []

        for node in nodes:
            if len(comments) >= limit * 2:
                break

            text = extract_text_from_locator(node)
            if not text or len(text) < 3:
                continue

            # 过滤明显不是评论的内容。
            if any(word in text for word in ["转发", "收藏", "举报", "微博正文", "相关推荐", "同时转发"]):
                if len(text) < 20:
                    continue

            source_comment_id = (
                extract_first_attribute(node, "comment_id")
                or extract_first_attribute(node, "mid")
                or stable_id(text, prefix="weibo_comment_")
            )

            if source_comment_id in seen:
                continue

            like_count = parse_count_from_text(text, ["赞", "点赞"])

            comments.append({
                "sourceCommentId": str(source_comment_id)[:100],
                "content": text[:1000],
                "authorName": None,
                "likeCount": like_count,
                "replyCount": 0,
                "publishTime": None,
                "rawJson": json.dumps({"raw_text": text[:2000], "selector": selector}, ensure_ascii=False),
            })
            seen.add(source_comment_id)

        if len(comments) >= limit:
            break

    comments.sort(key=lambda item: item.get("likeCount", 0), reverse=True)
    return comments[:limit]


def fetch_weibo_hot_comments_by_browser(context, source_url: Optional[str], limit: int = COMMENTS_PER_POST) -> List[Dict[str, Any]]:
    """
    进入微博详情页抓评论。
    优先捕获浏览器加载评论时产生的 JSON 响应；如果没捕获到，再用 DOM 兜底解析。
    返回前按点赞数降序排序，最多保留 limit 条。
    """
    if not source_url:
        return []

    page = context.new_page()
    captured_comments: List[Dict[str, Any]] = []
    seen = set()

    def handle_response(response) -> None:
        url = response.url or ""
        if not any(key in url.lower() for key in ["comment", "comments", "hotflow"]):
            return

        try:
            payload = response.json()
        except Exception:
            return

        for comment in extract_comment_dicts_from_payload(payload, limit=limit):
            comment_id = comment.get("sourceCommentId")
            if comment_id and comment_id not in seen:
                captured_comments.append(comment)
                seen.add(comment_id)

    try:
        page.on("response", handle_response)
        page.goto(source_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        try_switch_to_hot_comments(page)

        # 多滚动几次，触发评论异步加载。这里不使用并发，避免触发风控。
        for _ in range(6):
            page.mouse.wheel(0, random.randint(900, 1500))
            page.wait_for_timeout(random.randint(900, 1600))

        if captured_comments:
            captured_comments.sort(key=lambda item: item.get("likeCount", 0), reverse=True)
            return captured_comments[:limit]

        dom_comments = extract_comments_from_detail_page(page, limit=limit)
        dom_comments.sort(key=lambda item: item.get("likeCount", 0), reverse=True)
        return dom_comments[:limit]

    except Exception as e:
        print(f"评论抓取跳过，url={source_url}，原因：{e}")
        return []
    finally:
        try:
            page.close()
        except Exception:
            pass


def insert_material_post(
    cursor: Cursor,
    hotspot_id: int,
    platform: str,
    keyword: str,
    material: Dict[str, Any],
    now: datetime,
) -> int:
    sql = """
        INSERT INTO hotspot_material_post (
            hotspot_id,
            platform,
            keyword,
            source_item_id,
            content_type,
            title,
            content,
            author_name,
            source_url,
            cover_url,
            media_urls,
            like_count,
            comment_count,
            repost_count,
            publish_time,
            crawl_time,
            raw_json,
            created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            hotspot_id = VALUES(hotspot_id),
            keyword = VALUES(keyword),
            title = VALUES(title),
            content = VALUES(content),
            author_name = VALUES(author_name),
            source_url = VALUES(source_url),
            cover_url = VALUES(cover_url),
            media_urls = VALUES(media_urls),
            like_count = VALUES(like_count),
            comment_count = VALUES(comment_count),
            repost_count = VALUES(repost_count),
            publish_time = VALUES(publish_time),
            crawl_time = VALUES(crawl_time),
            raw_json = VALUES(raw_json),
            id = LAST_INSERT_ID(id)
    """
    cursor.execute(sql, (
        hotspot_id,
        platform,
        keyword,
        material.get("sourceItemId"),
        material.get("contentType") or "post",
        material.get("title"),
        material.get("content"),
        material.get("authorName"),
        material.get("sourceUrl"),
        material.get("coverUrl"),
        material.get("mediaUrls"),
        material.get("likeCount") or 0,
        material.get("commentCount") or 0,
        material.get("repostCount") or 0,
        material.get("publishTime"),
        now,
        material.get("rawJson"),
        now,
    ))
    return int(cursor.lastrowid)


def insert_material_comment(
    cursor: Cursor,
    hotspot_id: int,
    material_post_id: int,
    platform: str,
    comment: Dict[str, Any],
    now: datetime,
) -> None:
    sql = """
        INSERT INTO hotspot_material_comment (
            hotspot_id,
            material_post_id,
            platform,
            source_comment_id,
            content,
            author_name,
            like_count,
            reply_count,
            publish_time,
            crawl_time,
            raw_json,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            hotspot_id = VALUES(hotspot_id),
            material_post_id = VALUES(material_post_id),
            content = VALUES(content),
            author_name = VALUES(author_name),
            like_count = VALUES(like_count),
            reply_count = VALUES(reply_count),
            publish_time = VALUES(publish_time),
            crawl_time = VALUES(crawl_time),
            raw_json = VALUES(raw_json)
    """
    cursor.execute(sql, (
        hotspot_id,
        material_post_id,
        platform,
        comment.get("sourceCommentId"),
        comment.get("content"),
        comment.get("authorName"),
        comment.get("likeCount") or 0,
        comment.get("replyCount") or 0,
        comment.get("publishTime"),
        now,
        comment.get("rawJson"),
        now,
    ))


def mark_task_done(cursor: Cursor, task_id: int) -> None:
    sql = """
        UPDATE hotspot_material_task
        SET status = 'done',
            error_message = NULL,
            updated_at = NOW()
        WHERE id = %s
    """
    cursor.execute(sql, (task_id,))


def mark_task_failed(cursor: Cursor, task_id: int, error_message: str) -> None:
    sql = """
        UPDATE hotspot_material_task
        SET status = 'failed',
            error_message = %s,
            updated_at = NOW()
        WHERE id = %s
    """
    cursor.execute(sql, (error_message[:500], task_id))


def run_material_worker(limit: int = 2, headless: bool = False) -> int:
    conn = get_connection()
    done_count = 0

    playwright, context = create_browser_context(headless=headless)

    try:
        now = datetime.now()

        with conn.cursor() as cursor:
            tasks = fetch_pending_material_tasks(cursor, limit)

            if not tasks:
                print("没有待处理材料任务")
                conn.commit()
                return 0

            print(f"发现待处理材料任务：{len(tasks)} 条")

            for task in tasks:
                task_id = task.get("id")
                hotspot_id = task.get("hotspot_id")
                platform = (task.get("platform") or "").lower()
                title = task.get("title")
                keyword = normalize_keyword(title)

                try:
                    if platform != "weibo":
                        raise NotImplementedError(f"当前浏览器材料抓取只支持微博，暂不支持平台：{platform}")

                    if not keyword:
                        raise RuntimeError("热点标题为空，无法抓取材料")

                    materials = fetch_weibo_posts_by_browser(context, keyword, limit=POSTS_PER_HOTSPOT)

                    post_count = 0
                    comment_count = 0

                    for material in materials:
                        material_post_id = insert_material_post(
                            cursor=cursor,
                            hotspot_id=hotspot_id,
                            platform=platform,
                            keyword=keyword,
                            material=material,
                            now=now,
                        )
                        post_count += 1

                        comments = fetch_weibo_hot_comments_by_browser(
                            context,
                            material.get("sourceUrl"),
                            limit=COMMENTS_PER_POST
                        )

                        for comment in comments:
                            insert_material_comment(
                                cursor=cursor,
                                hotspot_id=hotspot_id,
                                material_post_id=material_post_id,
                                platform=platform,
                                comment=comment,
                                now=now,
                            )
                            comment_count += 1

                        time.sleep(random.uniform(REQUEST_SLEEP_SECONDS, REQUEST_SLEEP_SECONDS + 1.2))

                    mark_task_done(cursor, task_id)
                    conn.commit()
                    done_count += 1
                    print(f"材料任务完成：{title}，写入帖子 {post_count} 条，评论 {comment_count} 条")

                except Exception as e:
                    conn.rollback()
                    print(f"材料任务失败：{title}，原因：{e}")
                    try:
                        with conn.cursor() as fail_cursor:
                            mark_task_failed(fail_cursor, task_id, str(e))
                        conn.commit()
                    except Exception:
                        conn.rollback()

        return done_count

    finally:
        try:
            context.close()
        except Exception:
            pass
        try:
            playwright.stop()
        except Exception:
            pass
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="微博材料浏览器自动化 worker")
    parser.add_argument("--login", action="store_true", help="打开浏览器手动登录微博，并保存浏览器登录状态")
    parser.add_argument("--headless", action="store_true", help="无头模式运行。首次和调试阶段不建议开启")
    parser.add_argument("--limit", type=int, default=2, help="本次最多处理多少条材料任务")
    args = parser.parse_args()

    if args.login:
        login_weibo_once()
        return

    run_material_worker(limit=args.limit, headless=args.headless)


if __name__ == "__main__":
    main()
