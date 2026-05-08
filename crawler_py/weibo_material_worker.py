import hashlib
import html
import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, unquote

import pymysql
import requests
from pymysql.connections import Connection
from pymysql.cursors import Cursor

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

from db_config import DB_CONFIG


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

if load_dotenv:
    load_dotenv(ENV_FILE)


WEIBO_PLATFORM = "weibo"

TASK_PENDING_STATUS = "pending"
TASK_PROCESSING_STATUS = "processing"
TASK_DONE_STATUS = "done"
TASK_FAILED_STATUS = "failed"

# 每个热点最多抓 3 条相关微博内容
POSTS_PER_HOTSPOT = 3

# 每条微博最多保存 10 条高赞评论
COMMENTS_PER_POST = 10

# 评论接口最多翻几页。不要太大，避免请求过于激进
COMMENT_MAX_PAGES = 2

# 搜索结果最多翻几页
SEARCH_MAX_PAGES = 2

REQUEST_SLEEP_SECONDS = 0.8
COMMENT_REQUEST_SLEEP_SECONDS = 0.6

# 从浏览器复制微博 Cookie 到 crawler_py/.env
# WEIBO_COOKIE=SUB=xxx; SUBP=xxx; XSRF-TOKEN=xxx; ...
WEIBO_COOKIE = os.getenv("WEIBO_COOKIE", "").strip()

WEIBO_MOBILE_HOME = "https://m.weibo.cn/"
WEIBO_SEARCH_API = "https://m.weibo.cn/api/container/getIndex"
WEIBO_COMMENT_HOTFLOW_API = "https://m.weibo.cn/comments/hotflow"


USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
    ),
]


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


def normalize_cookie(cookie: str) -> str:
    """
    简单清洗 Cookie，避免复制时混入空片段。
    """
    if not cookie:
        return ""

    parts = []
    for part in cookie.split(";"):
        item = part.strip()
        if not item:
            continue
        if "=" not in item:
            continue
        parts.append(item)

    return "; ".join(parts)


def cookie_to_dict(cookie: str) -> Dict[str, str]:
    result: Dict[str, str] = {}

    for part in normalize_cookie(cookie).split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue

        key, value = item.split("=", 1)
        result[key.strip()] = value.strip()

    return result


def get_xsrf_token_from_cookie(cookie: str) -> str:
    cookie_dict = cookie_to_dict(cookie)
    token = cookie_dict.get("XSRF-TOKEN") or cookie_dict.get("xsrf-token") or ""
    return unquote(token)


def clean_html_text(value: Any, limit: int = 3000) -> str:
    """
    清洗微博正文 / 评论中的 HTML。
    """
    if value is None:
        return ""

    text = html.unescape(str(value))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text[:limit]


def clean_text(value: Any, limit: int = 3000) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    text = " ".join(text.split())
    return text[:limit]


def normalize_keyword(title: str) -> str:
    keyword = (title or "").strip()
    if keyword.startswith("#") and keyword.endswith("#") and len(keyword) > 2:
        keyword = keyword[1:-1]
    return keyword.strip()


def to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default

    text = str(value).strip().replace(",", "")
    if not text:
        return default

    try:
        if text.endswith("万"):
            return int(float(text[:-1]) * 10000)
        if text.endswith("亿"):
            return int(float(text[:-1]) * 100000000)

        match = re.search(r"\d+(\.\d+)?", text)
        if not match:
            return default

        return int(float(match.group(0)))
    except Exception:
        return default


def stable_id(*parts: Any, prefix: str = "") -> str:
    raw = "|".join(str(part or "") for part in parts)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return f"{prefix}{digest}" if prefix else digest


def parse_weibo_time(value: Any) -> Optional[datetime]:
    """
    微博 created_at 可能是：
    - Wed May 07 10:22:33 +0800 2026
    - 5分钟前
    - 今天 10:22
    - 2026-05-07 10:22
    这里尽量解析，解析不了就返回 None。
    """
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    formats = [
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo:
                return dt.replace(tzinfo=None)
            return dt
        except Exception:
            pass

    return None


def build_search_referer(keyword: str) -> str:
    containerid = f"100103type=1&q={keyword}"
    return f"https://m.weibo.cn/search?containerid={quote(containerid)}"


def build_status_url(mid: str, user_id: Optional[str] = None) -> str:
    if mid:
        return f"https://m.weibo.cn/status/{mid}"
    return "https://m.weibo.cn"


def create_session(keyword: str = "") -> requests.Session:
    session = requests.Session()

    cookie = normalize_cookie(WEIBO_COOKIE)
    xsrf_token = get_xsrf_token_from_cookie(cookie)

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": build_search_referer(keyword or "微博"),
        "Origin": "https://m.weibo.cn",
        "MWeibo-Pwa": "1",
        "X-Requested-With": "XMLHttpRequest",
        "Connection": "keep-alive",
    }

    if cookie:
        headers["Cookie"] = cookie

    if xsrf_token:
        headers["X-XSRF-TOKEN"] = xsrf_token

    session.headers.update(headers)
    return session


def save_weibo_debug_response(debug_name: str, response: requests.Response) -> None:
    """
    保存微博接口的异常返回，方便判断是登录页、风控页还是空响应。
    """
    debug_dir = BASE_DIR / "debug_weibo"
    debug_dir.mkdir(exist_ok=True)

    safe_name = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fa5-]", "_", debug_name)[:80]
    debug_file = debug_dir / f"{safe_name}.txt"

    content_type = response.headers.get("content-type", "")

    try:
        debug_file.write_text(
            "\n".join([
                f"status_code={response.status_code}",
                f"content_type={content_type}",
                f"url={response.url}",
                "",
                "headers:",
                json.dumps(dict(response.headers), ensure_ascii=False, indent=2),
                "",
                "body:",
                response.text[:5000],
            ]),
            encoding="utf-8",
        )
        print(f"已保存微博异常响应：{debug_file}")
    except Exception as e:
        print(f"保存微博异常响应失败：{e}")


def fetch_json_with_debug(
    session: requests.Session,
    url: str,
    params: Dict[str, Any],
    referer: str,
    debug_name: str,
) -> Optional[Dict[str, Any]]:
    """
    请求微博接口，并在返回非 JSON 时保存调试文件。
    """
    try:
        response = session.get(
            url,
            params=params,
            headers={
                "Referer": referer,
            },
            timeout=15,
            allow_redirects=True,
        )
    except Exception as e:
        print(f"微博接口请求失败：{debug_name}，原因：{e}")
        return None

    content_type = response.headers.get("content-type", "")
    text = response.text or ""
    preview = text[:300].replace("\n", " ").replace("\r", " ")

    if response.status_code != 200:
        print(
            f"微博接口状态码异常：{debug_name}，"
            f"status={response.status_code}，content_type={content_type}，preview={preview}"
        )
        save_weibo_debug_response(debug_name, response)
        return None

    stripped = text.lstrip()
    if not stripped.startswith("{") and not stripped.startswith("["):
        print(
            f"微博接口返回的不是 JSON：{debug_name}，"
            f"content_type={content_type}，url={response.url}，preview={preview}"
        )
        save_weibo_debug_response(debug_name, response)
        return None

    try:
        return response.json()
    except Exception as e:
        print(
            f"微博接口 JSON 解析失败：{debug_name}，"
            f"原因={e}，content_type={content_type}，url={response.url}，preview={preview}"
        )
        save_weibo_debug_response(debug_name, response)
        return None


def warm_up_session(session: requests.Session, keyword: str) -> None:
    """
    轻量预热，模拟先打开移动端页面。
    """
    try:
        session.get(WEIBO_MOBILE_HOME, timeout=10)
        time.sleep(random.uniform(0.3, 0.8))

        session.get(build_search_referer(keyword), timeout=10)
        time.sleep(random.uniform(0.3, 0.8))
    except Exception as e:
        print(f"微博预热请求失败，继续尝试接口：{e}")


def build_search_request_variants(keyword: str, page: int) -> List[Dict[str, Any]]:
    """
    微博 H5 搜索接口参数在不同时间可能会有差异。
    这里准备几种常见参数组合，按顺序尝试。
    """
    containerid = f"100103type=1&q={keyword}"

    return [
        {
            "containerid": containerid,
            "page_type": "searchall",
            "page": page,
        },
        {
            "containerid": containerid,
            "page": page,
        },
        {
            "containerid": containerid,
            "type": "all",
            "queryVal": keyword,
            "page": page,
        },
        {
            "containerid": f"100103type=1&q=#{keyword}#",
            "page_type": "searchall",
            "page": page,
        },
    ]


def extract_mblogs_from_search_payload(payload: Any) -> List[Dict[str, Any]]:
    """
    从微博搜索接口返回中递归提取 mblog 对象。
    """
    result: List[Dict[str, Any]] = []

    def looks_like_mblog(obj: Dict[str, Any]) -> bool:
        if not isinstance(obj, dict):
            return False

        has_id = bool(obj.get("id") or obj.get("idstr") or obj.get("mid"))
        has_text = bool(obj.get("text") or obj.get("text_raw"))
        has_user = isinstance(obj.get("user"), dict)

        return has_id and has_text and has_user

    def walk(obj: Any) -> None:
        if isinstance(obj, list):
            for item in obj:
                walk(item)
            return

        if not isinstance(obj, dict):
            return

        mblog = obj.get("mblog")
        if isinstance(mblog, dict) and looks_like_mblog(mblog):
            result.append(mblog)

        if looks_like_mblog(obj):
            result.append(obj)

        for value in obj.values():
            if isinstance(value, (dict, list)):
                walk(value)

    walk(payload)

    deduped: List[Dict[str, Any]] = []
    seen = set()

    for item in result:
        mid = str(item.get("id") or item.get("idstr") or item.get("mid") or "").strip()
        if not mid:
            continue
        if mid in seen:
            continue
        deduped.append(item)
        seen.add(mid)

    return deduped


def normalize_weibo_mblog(mblog: Dict[str, Any], keyword: str) -> Optional[Dict[str, Any]]:
    """
    将微博 mblog 对象转换成项目材料结构。
    """
    if not isinstance(mblog, dict):
        return None

    mid = str(mblog.get("id") or mblog.get("idstr") or mblog.get("mid") or "").strip()
    if not mid:
        return None

    content = clean_html_text(mblog.get("text_raw") or mblog.get("text"), limit=3000)
    if len(content) < 5:
        return None

    user = mblog.get("user") or {}
    user_id = str(user.get("id") or user.get("idstr") or "").strip() or None
    author_name = clean_text(user.get("screen_name") or user.get("name"), 100) or None

    page_info = mblog.get("page_info") or {}
    pics = mblog.get("pics") or []

    cover_url = None
    media_urls = None

    if isinstance(page_info, dict):
        page_pic = page_info.get("page_pic")
        if isinstance(page_pic, dict):
            cover_url = page_pic.get("url")
        elif page_pic:
            cover_url = str(page_pic)

    if isinstance(pics, list) and pics:
        urls = []
        for pic in pics:
            if not isinstance(pic, dict):
                continue

            large = pic.get("large")
            url = large.get("url") if isinstance(large, dict) else None
            url = url or pic.get("url")

            if url:
                urls.append(str(url))

        if urls:
            media_urls = json.dumps(urls, ensure_ascii=False)
            if not cover_url:
                cover_url = urls[0]

    source_url = build_status_url(mid, user_id=user_id)

    like_count = to_int(mblog.get("attitudes_count") or mblog.get("like_count"))
    comment_count = to_int(mblog.get("comments_count") or mblog.get("comment_count"))
    repost_count = to_int(mblog.get("reposts_count") or mblog.get("repost_count"))

    created_at = mblog.get("created_at")
    publish_time = parse_weibo_time(created_at)

    title = keyword

    material_content_parts = [
        f"微博正文：{content}",
    ]

    if author_name:
        material_content_parts.append(f"作者：{author_name}")

    material_content_parts.append(
        f"互动数据：点赞 {like_count}，评论 {comment_count}，转发 {repost_count}"
    )

    return {
        "mid": mid,
        "sourceItemId": mid[:100],
        "contentType": "post",
        "title": title,
        "content": "\n".join(material_content_parts),
        "authorName": author_name,
        "sourceUrl": source_url,
        "coverUrl": cover_url,
        "mediaUrls": media_urls,
        "likeCount": like_count,
        "commentCount": comment_count,
        "repostCount": repost_count,
        "publishTime": publish_time,
        "rawJson": json.dumps(mblog, ensure_ascii=False)[:60000],
    }


def fetch_weibo_posts_by_requests(
    keyword: str,
    limit: int = POSTS_PER_HOTSPOT,
) -> List[Dict[str, Any]]:
    """
    使用微博移动端搜索接口抓取相关微博内容。
    """
    session = create_session(keyword)
    warm_up_session(session, keyword)

    materials: List[Dict[str, Any]] = []
    seen = set()

    for page in range(1, SEARCH_MAX_PAGES + 1):
        variants = build_search_request_variants(keyword, page)

        for variant_index, params in enumerate(variants, start=1):
            debug_name = f"search_{keyword}_page_{page}_variant_{variant_index}"

            payload = fetch_json_with_debug(
                session=session,
                url=WEIBO_SEARCH_API,
                params=params,
                referer=build_search_referer(keyword),
                debug_name=debug_name,
            )

            if not payload:
                continue

            ok = payload.get("ok")
            if ok not in (1, "1", None):
                print(
                    f"微博搜索接口 ok 异常：keyword={keyword}，page={page}，"
                    f"variant={variant_index}，ok={ok}，payload={str(payload)[:300]}"
                )
                continue

            mblogs = extract_mblogs_from_search_payload(payload)

            print(
                f"微博搜索接口解析：keyword={keyword}，page={page}，variant={variant_index}，"
                f"提取到 mblog 候选 {len(mblogs)} 条"
            )

            for mblog in mblogs:
                material = normalize_weibo_mblog(mblog, keyword)
                if not material:
                    continue

                source_id = material.get("sourceItemId")
                if not source_id or source_id in seen:
                    continue

                materials.append(material)
                seen.add(source_id)

                if len(materials) >= limit:
                    break

            if len(materials) >= limit:
                break

        if len(materials) >= limit:
            break

        time.sleep(random.uniform(REQUEST_SLEEP_SECONDS, REQUEST_SLEEP_SECONDS + 0.5))

    if not materials:
        raise RuntimeError(
            "微博移动端搜索接口未解析到相关微博。请查看 crawler_py/debug_weibo 下的调试文件，"
            "判断返回内容是登录页、风控页、空响应还是接口结构变化。"
        )

    print(f"微博搜索材料抓取完成：keyword={keyword}，保存候选 {len(materials)} 条")
    return materials[:limit]


def normalize_weibo_comment(raw_comment: Dict[str, Any], mid: str) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_comment, dict):
        return None

    content = clean_html_text(
        raw_comment.get("text_raw")
        or raw_comment.get("text")
        or raw_comment.get("content"),
        limit=1000,
    )

    if len(content) < 2:
        return None

    source_comment_id = str(
        raw_comment.get("id")
        or raw_comment.get("idstr")
        or raw_comment.get("comment_id")
        or raw_comment.get("mid")
        or stable_id(mid, content, prefix="weibo_comment_")
    ).strip()

    if not source_comment_id:
        return None

    user = raw_comment.get("user") or {}
    author_name = clean_text(
        user.get("screen_name")
        or user.get("name")
        or raw_comment.get("user_name"),
        100,
    ) or None

    like_count = to_int(
        raw_comment.get("like_count")
        or raw_comment.get("like_counts")
        or raw_comment.get("attitudes_count")
        or raw_comment.get("likeCount")
    )

    reply_count = to_int(
        raw_comment.get("total_number")
        or raw_comment.get("reply_count")
        or raw_comment.get("comments_count")
        or raw_comment.get("replyCount")
    )

    publish_time = parse_weibo_time(raw_comment.get("created_at"))

    return {
        "sourceCommentId": source_comment_id[:100],
        "content": content,
        "authorName": author_name,
        "likeCount": like_count,
        "replyCount": reply_count,
        "publishTime": publish_time,
        "rawJson": json.dumps(raw_comment, ensure_ascii=False)[:60000],
    }


def extract_comments_from_hotflow_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    data = payload.get("data") or {}

    if isinstance(data, dict):
        comments = data.get("data") or data.get("comments") or []
        if isinstance(comments, list):
            return [item for item in comments if isinstance(item, dict)]

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    return []


def fetch_weibo_hot_comments_by_mid(
    mid: str,
    keyword: str = "",
    limit: int = COMMENTS_PER_POST,
    max_pages: int = COMMENT_MAX_PAGES,
) -> List[Dict[str, Any]]:
    """
    使用 m.weibo.cn/comments/hotflow 抓热门评论。
    """
    mid = clean_text(mid, 100)
    if not mid:
        return []

    session = create_session(keyword)
    comments: List[Dict[str, Any]] = []
    seen = set()

    max_id = None
    max_id_type = 0

    for page in range(1, max_pages + 1):
        params = {
            "id": mid,
            "mid": mid,
            "max_id_type": max_id_type,
        }

        if max_id:
            params["max_id"] = max_id

        payload = fetch_json_with_debug(
            session=session,
            url=WEIBO_COMMENT_HOTFLOW_API,
            params=params,
            referer=build_status_url(mid),
            debug_name=f"comment_{mid}_page_{page}",
        )

        if not payload:
            break

        raw_comments = extract_comments_from_hotflow_payload(payload)

        for raw_comment in raw_comments:
            comment = normalize_weibo_comment(raw_comment, mid=mid)
            if not comment:
                continue

            source_id = comment.get("sourceCommentId")
            if not source_id or source_id in seen:
                continue

            comments.append(comment)
            seen.add(source_id)

        data = payload.get("data") or {}
        if isinstance(data, dict):
            max_id = data.get("max_id")
            max_id_type = data.get("max_id_type", max_id_type)

        if not raw_comments or not max_id:
            break

        if len(comments) >= limit:
            break

        time.sleep(random.uniform(COMMENT_REQUEST_SLEEP_SECONDS, COMMENT_REQUEST_SLEEP_SECONDS + 0.5))

    comments.sort(
        key=lambda item: (
            int(item.get("likeCount") or 0),
            int(item.get("replyCount") or 0),
        ),
        reverse=True,
    )

    top_comments = comments[:limit]

    print(f"微博评论抓取完成：mid={mid}，候选 {len(comments)} 条，保存 {len(top_comments)} 条")
    return top_comments


def fetch_pending_material_tasks(cursor: Cursor, limit: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT id, hotspot_id, platform, title
        FROM hotspot_material_task
        WHERE platform = %s
          AND status = %s
        ORDER BY updated_at ASC, id ASC
        LIMIT %s
    """
    cursor.execute(sql, (WEIBO_PLATFORM, TASK_PENDING_STATUS, limit))
    return list(cursor.fetchall())


def mark_task_processing(cursor: Cursor, task_id: int) -> None:
    sql = """
        UPDATE hotspot_material_task
        SET status = %s,
            error_message = NULL,
            updated_at = NOW()
        WHERE id = %s
    """
    cursor.execute(sql, (TASK_PROCESSING_STATUS, task_id))


def mark_task_done(cursor: Cursor, task_id: int) -> None:
    sql = """
        UPDATE hotspot_material_task
        SET status = %s,
            error_message = NULL,
            updated_at = NOW()
        WHERE id = %s
    """
    cursor.execute(sql, (TASK_DONE_STATUS, task_id))


def mark_task_failed(cursor: Cursor, task_id: int, error_message: str) -> None:
    sql = """
        UPDATE hotspot_material_task
        SET status = %s,
            error_message = %s,
            updated_at = NOW()
        WHERE id = %s
    """
    cursor.execute(sql, (TASK_FAILED_STATUS, error_message[:500], task_id))


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


def run_weibo_material_worker(limit: int = 2) -> int:
    """
    批量处理微博材料任务。

    当前规则：
    - 每个热点抓 3 条相关微博；
    - 每条微博抓热门评论；
    - 按点赞数取前 10 条评论入库；
    - 不使用 Playwright，不打开浏览器。
    """
    if not normalize_cookie(WEIBO_COOKIE):
        print("未配置 WEIBO_COOKIE。请在 crawler_py/.env 中添加 WEIBO_COOKIE，否则微博材料抓取可能失败。")

    conn = get_connection()
    done_count = 0

    try:
        with conn.cursor() as cursor:
            tasks = fetch_pending_material_tasks(cursor, limit)

            if not tasks:
                print("没有待处理的微博材料任务")
                conn.commit()
                return 0

            print(f"发现待处理微博材料任务：{len(tasks)} 条")

            for task in tasks:
                task_id = task.get("id")
                hotspot_id = task.get("hotspot_id")
                platform = (task.get("platform") or "").lower()
                title = task.get("title")
                keyword = normalize_keyword(title)
                now = datetime.now()

                try:
                    if platform != WEIBO_PLATFORM:
                        raise RuntimeError(f"平台不匹配，当前 worker 只处理 weibo，实际为：{platform}")

                    if not keyword:
                        raise RuntimeError("热点标题为空，无法抓取微博材料")

                    mark_task_processing(cursor, task_id)
                    conn.commit()

                    print(f"开始处理微博材料任务：hotspot_id={hotspot_id}，keyword={keyword}")

                    materials = fetch_weibo_posts_by_requests(
                        keyword=keyword,
                        limit=POSTS_PER_HOTSPOT,
                    )

                    post_count = 0
                    comment_count = 0

                    for material in materials:
                        material_post_id = insert_material_post(
                            cursor=cursor,
                            hotspot_id=hotspot_id,
                            platform=WEIBO_PLATFORM,
                            keyword=keyword,
                            material=material,
                            now=now,
                        )
                        post_count += 1

                        mid = material.get("mid") or material.get("sourceItemId")
                        comments = fetch_weibo_hot_comments_by_mid(
                            mid=mid,
                            keyword=keyword,
                            limit=COMMENTS_PER_POST,
                            max_pages=COMMENT_MAX_PAGES,
                        )

                        for comment in comments:
                            insert_material_comment(
                                cursor=cursor,
                                hotspot_id=hotspot_id,
                                material_post_id=material_post_id,
                                platform=WEIBO_PLATFORM,
                                comment=comment,
                                now=now,
                            )
                            comment_count += 1

                        time.sleep(random.uniform(REQUEST_SLEEP_SECONDS, REQUEST_SLEEP_SECONDS + 0.4))

                    if post_count == 0:
                        raise RuntimeError("没有写入任何微博主体材料")

                    mark_task_done(cursor, task_id)
                    conn.commit()
                    done_count += 1

                    print(
                        f"微博材料任务完成：hotspot_id={hotspot_id}，"
                        f"写入/更新帖子 {post_count} 条，写入/更新评论 {comment_count} 条"
                    )

                except Exception as e:
                    conn.rollback()
                    print(f"微博材料任务失败：hotspot_id={hotspot_id}，原因：{e}")

                    try:
                        mark_task_failed(cursor, task_id, str(e))
                        conn.commit()
                    except Exception:
                        conn.rollback()

                time.sleep(random.uniform(REQUEST_SLEEP_SECONDS, REQUEST_SLEEP_SECONDS + 0.6))

        print(f"微博材料 worker 执行完成：处理成功 {done_count} 条任务")
        return done_count

    finally:
        conn.close()


if __name__ == "__main__":
    run_weibo_material_worker(limit=2)