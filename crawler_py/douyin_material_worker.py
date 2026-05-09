import argparse
import json
import os
import time
import random
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, parse_qs, urlparse

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

from material_config import (
    COMMENTS_PER_MATERIAL,
    DOUYIN_COMMENT_FETCH_COUNT,
    MATERIALS_PER_HOTSPOT,
)


DOUYIN_PLATFORM = "douyin"
TASK_PENDING_STATUS = "pending_douyin"

# 统一材料采集标准：每个热点最多保存 3 条主体材料，每条主体材料最多保存 5 条高赞评论。
# 抖音仍会先抓一批候选评论，再按点赞数排序取前 5。
POSTS_PER_HOTSPOT = MATERIALS_PER_HOTSPOT
COMMENTS_PER_VIDEO = COMMENTS_PER_MATERIAL
COMMENT_FETCH_COUNT = DOUYIN_COMMENT_FETCH_COUNT

# 请求间隔，避免太激进
REQUEST_SLEEP_SECONDS = 1.2
COMMENT_REQUEST_SLEEP_SECONDS = 0.8

# .env 配置项
DOUYIN_COOKIE = os.getenv("DOUYIN_COOKIE", "").strip()

# 评论接口增强参数：这些来自浏览器真实请求，部分可能会过期
DOUYIN_WEBID = os.getenv("DOUYIN_WEBID", "").strip()
DOUYIN_UIFID = os.getenv("DOUYIN_UIFID", "").strip()
DOUYIN_VERIFY_FP = os.getenv("DOUYIN_VERIFY_FP", "").strip()
DOUYIN_FP = os.getenv("DOUYIN_FP", "").strip()
DOUYIN_MS_TOKEN = os.getenv("DOUYIN_MS_TOKEN", "").strip()
DOUYIN_A_BOGUS = os.getenv("DOUYIN_A_BOGUS", "").strip()
DOUYIN_X_SECSIG = os.getenv("DOUYIN_X_SECSIG", "").strip()

# bd-ticket-guard 相关请求头
DOUYIN_BD_TICKET_GUARD_CLIENT_DATA = os.getenv("DOUYIN_BD_TICKET_GUARD_CLIENT_DATA", "").strip()
DOUYIN_BD_TICKET_GUARD_REE_PUBLIC_KEY = os.getenv("DOUYIN_BD_TICKET_GUARD_REE_PUBLIC_KEY", "").strip()
DOUYIN_BD_TICKET_GUARD_VERSION = os.getenv("DOUYIN_BD_TICKET_GUARD_VERSION", "2").strip()
DOUYIN_BD_TICKET_GUARD_WEB_SIGN_TYPE = os.getenv("DOUYIN_BD_TICKET_GUARD_WEB_SIGN_TYPE", "1").strip()
DOUYIN_BD_TICKET_GUARD_WEB_VERSION = os.getenv("DOUYIN_BD_TICKET_GUARD_WEB_VERSION", "2").strip()

# 可选：把真实 cURL 里的评论 Query 参数整段放进 .env。
# 例如：
# DOUYIN_COMMENT_EXTRA_QUERY=pc_img_format=webp&pc_libra_divert=Windows&support_h265=1...
# 不建议把 aweme_id/cursor/count 放进去，代码会自动覆盖。
DOUYIN_COMMENT_EXTRA_QUERY = os.getenv("DOUYIN_COMMENT_EXTRA_QUERY", "").strip()


SEARCH_ENDPOINTS = [
    {
        "name": "search_item",
        "url": "https://www.douyin.com/aweme/v1/web/search/item/",
    },
    {
        "name": "general_search_single",
        "url": "https://www.douyin.com/aweme/v1/web/general/search/single/",
    },
    {
        "name": "discover_search",
        "url": "https://www.douyin.com/aweme/v1/web/discover/search/",
    },
]


COMMENT_ENDPOINTS = [
    {
        "name": "web_comment_list",
        "url": "https://www.douyin.com/aweme/v1/web/comment/list/",
    }
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
    简单清洗 Cookie。
    从浏览器复制时可能混入 douyin.com 这种非 key=value 片段，
    这里过滤掉，避免请求头格式混乱。
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


def get_cookie_value(cookie: str, key: str) -> str:
    cookie = normalize_cookie(cookie)
    if not cookie:
        return ""

    for part in cookie.split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue

        name, value = item.split("=", 1)
        if name.strip() == key:
            return value.strip()

    return ""


def clean_text(value: Any, limit: int = 2000) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    text = " ".join(text.split())
    return text[:limit]


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
        return int(float(text))
    except Exception:
        return default


def stable_id(*parts: Any, prefix: str = "") -> str:
    raw = "|".join(str(part or "") for part in parts)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return f"{prefix}{digest}" if prefix else digest


def format_publish_time(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None

    try:
        timestamp = int(float(value))

        if timestamp > 10_000_000_000:
            timestamp = timestamp // 1000

        return datetime.fromtimestamp(timestamp)
    except Exception:
        return None


def build_search_url(keyword: str) -> str:
    return f"https://www.douyin.com/search/{quote(keyword)}"


def build_aweme_url(aweme_id: str) -> Optional[str]:
    if not aweme_id:
        return None
    return f"https://www.douyin.com/video/{aweme_id}"


def build_jingxuan_url(aweme_id: str) -> str:
    return f"https://www.douyin.com/jingxuan?modal_id={aweme_id}"


def build_common_headers(keyword: str = "", referer: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
        ),
        "referer": referer or build_search_url(keyword or "抖音"),
        "origin": "https://www.douyin.com",
        "sec-ch-ua": '"Microsoft Edge";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "priority": "u=1, i",
    }

    cookie = normalize_cookie(DOUYIN_COOKIE)
    if cookie:
        headers["cookie"] = cookie

    return headers


def build_comment_headers(keyword: str, aweme_id: str) -> Dict[str, str]:
    """
    评论接口专用 headers。
    这里比搜索接口多了 bd-ticket-guard、uifid、x-secsdk-web-signature 等可选头。
    """
    referer = build_jingxuan_url(aweme_id)
    headers = build_common_headers(keyword=keyword, referer=referer)

    uifid = DOUYIN_UIFID or get_cookie_value(DOUYIN_COOKIE, "UIFID")
    if uifid:
        headers["uifid"] = uifid

    if DOUYIN_X_SECSIG:
        headers["x-secsdk-web-signature"] = DOUYIN_X_SECSIG

    if DOUYIN_BD_TICKET_GUARD_CLIENT_DATA:
        headers["bd-ticket-guard-client-data"] = DOUYIN_BD_TICKET_GUARD_CLIENT_DATA

    if DOUYIN_BD_TICKET_GUARD_REE_PUBLIC_KEY:
        headers["bd-ticket-guard-ree-public-key"] = DOUYIN_BD_TICKET_GUARD_REE_PUBLIC_KEY

    if DOUYIN_BD_TICKET_GUARD_VERSION:
        headers["bd-ticket-guard-version"] = DOUYIN_BD_TICKET_GUARD_VERSION

    if DOUYIN_BD_TICKET_GUARD_WEB_SIGN_TYPE:
        headers["bd-ticket-guard-web-sign-type"] = DOUYIN_BD_TICKET_GUARD_WEB_SIGN_TYPE

    if DOUYIN_BD_TICKET_GUARD_WEB_VERSION:
        headers["bd-ticket-guard-web-version"] = DOUYIN_BD_TICKET_GUARD_WEB_VERSION

    return headers


def parse_extra_query(query_text: str) -> Dict[str, Any]:
    """
    解析 .env 里的 DOUYIN_COMMENT_EXTRA_QUERY。
    """
    if not query_text:
        return {}

    if query_text.startswith("http://") or query_text.startswith("https://"):
        parsed = urlparse(query_text)
        query_text = parsed.query

    raw = parse_qs(query_text, keep_blank_values=True)
    result: Dict[str, Any] = {}

    for key, values in raw.items():
        if not values:
            result[key] = ""
        else:
            result[key] = values[-1]

    return result


def build_common_web_params() -> Dict[str, Any]:
    return {
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
        "update_version_code": "170400",
        "pc_client_type": "1",
        "version_code": "170400",
        "version_name": "17.4.0",
        "cookie_enabled": "true",
        "screen_width": "1707",
        "screen_height": "1067",
        "browser_language": "zh-CN",
        "browser_platform": "Win32",
        "browser_name": "Edge",
        "browser_version": "147.0.0.0",
        "browser_online": "true",
        "engine_name": "Blink",
        "engine_version": "147.0.0.0",
        "os_name": "Windows",
        "os_version": "10",
        "cpu_core_num": "20",
        "device_memory": "16",
        "platform": "PC",
        "downlink": "9.2",
        "effective_type": "4g",
        "round_trip_time": "0",
    }


def build_search_params(keyword: str, offset: int = 0, count: int = 10) -> Dict[str, Any]:
    params = build_common_web_params()
    params.update({
        "search_channel": "aweme_general",
        "keyword": keyword,
        "search_source": "normal_search",
        "query_correct_type": "1",
        "is_filter_search": "0",
        "offset": offset,
        "count": count,
        "need_filter_settings": "0",
        "list_type": "single",
    })
    return params


def build_comment_params(aweme_id: str, cursor: int = 0, count: int = COMMENT_FETCH_COUNT) -> Dict[str, Any]:
    """
    评论接口参数。

    重点：
    - aweme_id/cursor/count 永远由代码根据当前视频覆盖；
    - 其它安全参数优先来自 .env；
    - 如果你把真实请求的 Query 串放进 DOUYIN_COMMENT_EXTRA_QUERY，也会合并进来。
    """
    params = build_common_web_params()

    # 先合并真实请求里复制出来的额外参数
    extra = parse_extra_query(DOUYIN_COMMENT_EXTRA_QUERY)
    params.update(extra)

    # 再覆盖当前视频必须变化的参数
    params.update({
        "aweme_id": aweme_id,
        "cursor": cursor,
        "count": count,
        "item_type": "0",
        "insert_ids": "",
        "whale_cut_token": "",
        "cut_version": "1",
        "rcFT": "",
        "pc_img_format": "webp",
        "pc_libra_divert": "Windows",
        "support_h265": "1",
        "support_dash": "1",
    })

    # 从 env 或 cookie 补关键参数
    webid = DOUYIN_WEBID or get_cookie_value(DOUYIN_COOKIE, "webid") or get_cookie_value(DOUYIN_COOKIE, "MONITOR_WEB_ID")
    uifid = DOUYIN_UIFID or get_cookie_value(DOUYIN_COOKIE, "UIFID")
    verify_fp = DOUYIN_VERIFY_FP or get_cookie_value(DOUYIN_COOKIE, "s_v_web_id")
    fp = DOUYIN_FP or verify_fp
    ms_token = DOUYIN_MS_TOKEN or get_cookie_value(DOUYIN_COOKIE, "msToken")

    if webid:
        params["webid"] = webid
    if uifid:
        params["uifid"] = uifid
    if verify_fp:
        params["verifyFp"] = verify_fp
    if fp:
        params["fp"] = fp
    if ms_token:
        params["msToken"] = ms_token
    if DOUYIN_A_BOGUS:
        params["a_bogus"] = DOUYIN_A_BOGUS
    if DOUYIN_X_SECSIG:
        params["x-secsdk-web-signature"] = DOUYIN_X_SECSIG

    # timestamp 使用当前时间，避免一直用旧时间戳
    params["timestamp"] = str(int(time.time()))

    return params


def fetch_pending_material_tasks(cursor: Cursor, limit: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT id, hotspot_id, platform, title
        FROM hotspot_material_task
        WHERE platform = %s
          AND status = %s
        ORDER BY created_at ASC
        LIMIT %s
    """
    cursor.execute(sql, (DOUYIN_PLATFORM, TASK_PENDING_STATUS, limit))
    return list(cursor.fetchall())


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


def is_music_object(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False

    title = clean_text(obj.get("title"), 200)

    music_markers = [
        "mid",
        "play_url",
        "cover_medium",
        "cover_thumb",
        "owner_id",
        "owner_nickname",
        "is_original",
    ]

    has_music_marker = any(key in obj for key in music_markers)
    has_aweme_marker = any(key in obj for key in ["aweme_id", "awemeId", "video", "statistics", "share_info"])

    if has_music_marker and not has_aweme_marker:
        return True

    if "创作的原声" in title and not isinstance(obj.get("video"), dict):
        return True

    return False


def get_aweme_id(obj: Dict[str, Any]) -> str:
    if not isinstance(obj, dict):
        return ""

    aweme_id = obj.get("aweme_id") or obj.get("awemeId") or ""
    if aweme_id:
        return str(aweme_id).strip()

    if isinstance(obj.get("video"), dict) or isinstance(obj.get("statistics"), dict):
        group_id = obj.get("group_id") or obj.get("gid")
        if group_id:
            return str(group_id).strip()

    if isinstance(obj.get("video"), dict):
        fallback_id = obj.get("id")
        if fallback_id:
            return str(fallback_id).strip()

    return ""


def is_valid_aweme_object(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False

    if is_music_object(obj):
        return False

    aweme_id = get_aweme_id(obj)
    if not aweme_id:
        return False

    video = obj.get("video")
    statistics = obj.get("statistics") or obj.get("stats")
    share_info = obj.get("share_info") or obj.get("shareInfo")

    has_video = isinstance(video, dict) and bool(video)
    has_stats = isinstance(statistics, dict) and bool(statistics)
    has_share = isinstance(share_info, dict) and bool(share_info)

    desc = clean_text(
        obj.get("desc")
        or obj.get("title")
        or obj.get("content")
        or obj.get("text")
        or "",
        500,
    )
    has_content = bool(desc)

    if not has_video:
        return False

    return has_content or has_stats or has_share


def find_aweme_like_dicts(payload: Any, limit: int = 20) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen_ids = set()

    def add_aweme(obj: Any) -> None:
        if not is_valid_aweme_object(obj):
            return

        aweme_id = get_aweme_id(obj)
        if not aweme_id:
            return

        if aweme_id in seen_ids:
            return

        results.append(obj)
        seen_ids.add(aweme_id)

    def walk(obj: Any) -> None:
        if len(results) >= limit * 3:
            return

        if isinstance(obj, list):
            for item in obj:
                walk(item)
            return

        if not isinstance(obj, dict):
            return

        for key in ["aweme_info", "aweme", "aweme_detail"]:
            value = obj.get(key)
            add_aweme(value)

        add_aweme(obj)

        for value in obj.values():
            if isinstance(value, (dict, list)):
                walk(value)

    walk(payload)
    return results[:limit]


def normalize_aweme_to_material(
    aweme: Dict[str, Any],
    keyword: str,
) -> Optional[Dict[str, Any]]:
    if not is_valid_aweme_object(aweme):
        return None

    aweme_id = get_aweme_id(aweme)

    desc = clean_text(
        aweme.get("desc")
        or aweme.get("title")
        or aweme.get("content")
        or aweme.get("text")
        or ""
    )

    if not aweme_id and not desc:
        return None

    author = aweme.get("author") or aweme.get("user") or {}
    if not isinstance(author, dict):
        author = {}

    author_name = (
        author.get("nickname")
        or author.get("name")
        or author.get("unique_id")
        or author.get("short_id")
    )

    statistics = aweme.get("statistics") or aweme.get("stats") or {}
    if not isinstance(statistics, dict):
        statistics = {}

    like_count = (
        to_int(statistics.get("digg_count"))
        or to_int(statistics.get("like_count"))
        or to_int(statistics.get("admire_count"))
    )
    comment_count = to_int(statistics.get("comment_count"))
    share_count = to_int(statistics.get("share_count"))
    collect_count = to_int(statistics.get("collect_count"))

    share_info = aweme.get("share_info") or aweme.get("shareInfo") or {}
    if not isinstance(share_info, dict):
        share_info = {}

    source_url = (
        aweme.get("share_url")
        or aweme.get("shareUrl")
        or share_info.get("share_url")
        or share_info.get("shareUrl")
        or build_aweme_url(aweme_id)
        or build_search_url(keyword)
    )

    cover_url = None
    video = aweme.get("video") or {}
    if not isinstance(video, dict):
        video = {}

    cover = video.get("cover") or video.get("origin_cover") or video.get("dynamic_cover") or {}
    if not isinstance(cover, dict):
        cover = {}

    url_list = cover.get("url_list")
    if isinstance(url_list, list) and url_list:
        cover_url = url_list[0]

    create_time = (
        aweme.get("create_time")
        or aweme.get("createTime")
        or aweme.get("publish_time")
        or aweme.get("publishTime")
    )

    source_item_id = aweme_id or stable_id(keyword, desc, source_url, prefix="douyin_aweme_")

    content_parts = []
    if desc:
        content_parts.append(desc)
    if author_name:
        content_parts.append(f"作者：{author_name}")
    if like_count or comment_count or share_count or collect_count:
        content_parts.append(
            f"互动数据：点赞{like_count}，评论{comment_count}，分享{share_count}，收藏{collect_count}"
        )

    content = "；".join(content_parts).strip()
    if not content:
        content = f"与“{keyword}”相关的抖音视频内容。"

    material_title = desc[:120] if desc else keyword

    return {
        "sourceItemId": str(source_item_id)[:100],
        "contentType": "video",
        "title": material_title,
        "content": content[:3000],
        "authorName": clean_text(author_name, 100) or None,
        "sourceUrl": source_url,
        "coverUrl": cover_url,
        "mediaUrls": None,
        "likeCount": like_count,
        "commentCount": comment_count,
        "repostCount": share_count,
        "publishTime": format_publish_time(create_time),
        "rawJson": json.dumps(aweme, ensure_ascii=False)[:60000],
    }


def request_search_api(endpoint: Dict[str, str], keyword: str, count: int) -> List[Dict[str, Any]]:
    url = endpoint["url"]
    name = endpoint["name"]

    params = build_search_params(keyword=keyword, offset=0, count=max(count, 10))
    headers = build_common_headers(keyword=keyword)

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=15,
    )

    if response.status_code != 200:
        print(f"抖音搜索接口 {name} 状态码异常：{response.status_code}")
        return []

    text = response.text.strip()
    if not text.startswith("{"):
        print(f"抖音搜索接口 {name} 未返回 JSON，前 120 字：{text[:120]}")
        return []

    try:
        payload = response.json()
    except Exception as e:
        print(f"抖音搜索接口 {name} JSON 解析失败：{e}")
        return []

    aweme_dicts = find_aweme_like_dicts(payload, limit=count)

    materials: List[Dict[str, Any]] = []
    seen = set()

    for aweme in aweme_dicts:
        material = normalize_aweme_to_material(aweme, keyword)
        if not material:
            continue

        source_id = material.get("sourceItemId")
        if not source_id or source_id in seen:
            continue

        materials.append(material)
        seen.add(source_id)

        if len(materials) >= count:
            break

    print(f"抖音搜索接口 {name} 解析到视频材料 {len(materials)} 条")
    return materials


def fetch_douyin_materials_by_keyword(
    keyword: str,
    limit: int = POSTS_PER_HOTSPOT,
) -> List[Dict[str, Any]]:
    keyword = clean_text(keyword, 80)
    if not keyword:
        return []

    all_materials: List[Dict[str, Any]] = []
    seen = set()

    for endpoint in SEARCH_ENDPOINTS:
        try:
            materials = request_search_api(endpoint, keyword, count=limit)
        except Exception as e:
            print(f"抖音搜索接口 {endpoint['name']} 请求失败：{e}")
            materials = []

        for material in materials:
            source_id = material.get("sourceItemId")
            if not source_id or source_id in seen:
                continue

            all_materials.append(material)
            seen.add(source_id)

            if len(all_materials) >= limit:
                return all_materials

        time.sleep(random.uniform(REQUEST_SLEEP_SECONDS, REQUEST_SLEEP_SECONDS + 0.8))

    return all_materials[:limit]


def get_comment_id(comment: Dict[str, Any]) -> str:
    if not isinstance(comment, dict):
        return ""

    comment_id = (
        comment.get("cid")
        or comment.get("comment_id")
        or comment.get("commentId")
        or comment.get("id")
        or ""
    )
    return str(comment_id).strip()


def normalize_douyin_comment(
    comment: Dict[str, Any],
    aweme_id: str,
) -> Optional[Dict[str, Any]]:
    if not isinstance(comment, dict):
        return None

    content = clean_text(
        comment.get("text")
        or comment.get("content")
        or comment.get("comment_text")
        or comment.get("commentText")
        or "",
        1000,
    )

    if not content:
        return None

    source_comment_id = get_comment_id(comment)
    if not source_comment_id:
        source_comment_id = stable_id(aweme_id, content, comment.get("create_time"), prefix="douyin_comment_")

    user = comment.get("user") or comment.get("author") or {}
    if not isinstance(user, dict):
        user = {}

    author_name = (
        user.get("nickname")
        or user.get("name")
        or user.get("unique_id")
        or user.get("short_id")
        or comment.get("user_name")
        or comment.get("author_name")
    )

    like_count = (
        to_int(comment.get("digg_count"))
        or to_int(comment.get("like_count"))
        or to_int(comment.get("likeCount"))
    )

    reply_count = (
        to_int(comment.get("reply_comment_total"))
        or to_int(comment.get("reply_count"))
        or to_int(comment.get("replyCount"))
    )

    create_time = (
        comment.get("create_time")
        or comment.get("createTime")
        or comment.get("publish_time")
        or comment.get("publishTime")
    )

    return {
        "sourceCommentId": str(source_comment_id)[:100],
        "content": content,
        "authorName": clean_text(author_name, 100) or None,
        "likeCount": like_count,
        "replyCount": reply_count,
        "publishTime": format_publish_time(create_time),
        "rawJson": json.dumps(comment, ensure_ascii=False)[:60000],
    }


def extract_comments_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    direct_comments = payload.get("comments")
    if isinstance(direct_comments, list):
        return [item for item in direct_comments if isinstance(item, dict)]

    result: List[Dict[str, Any]] = []

    def looks_like_comment(obj: Any) -> bool:
        if not isinstance(obj, dict):
            return False

        has_id = any(key in obj for key in ["cid", "comment_id", "commentId"])
        has_text = any(key in obj for key in ["text", "content", "comment_text", "commentText"])
        has_user = isinstance(obj.get("user"), dict) or isinstance(obj.get("author"), dict)

        return has_id and has_text and has_user

    def walk(obj: Any) -> None:
        if isinstance(obj, list):
            for item in obj:
                walk(item)
            return

        if not isinstance(obj, dict):
            return

        if looks_like_comment(obj):
            result.append(obj)

        for value in obj.values():
            if isinstance(value, (dict, list)):
                walk(value)

    walk(payload)
    return result


def print_comment_response_debug(
    endpoint_name: str,
    aweme_id: str,
    response: requests.Response,
) -> None:
    text = response.text or ""

    print("========== 抖音评论接口 DEBUG ==========")
    print(f"endpoint={endpoint_name}")
    print(f"aweme_id={aweme_id}")
    print(f"status={response.status_code}")
    print(f"content-type={response.headers.get('content-type')}")
    print(f"final_url={response.url}")
    print(f"text_len={len(text)}")
    print(f"text_repr={repr(text[:300])}")
    print("========== DEBUG END ==========")


def fetch_douyin_comments_by_aweme_id(
    aweme_id: str,
    keyword: str,
    fetch_count: int = COMMENT_FETCH_COUNT,
    top_n: int = COMMENTS_PER_VIDEO,
) -> List[Dict[str, Any]]:
    aweme_id = clean_text(aweme_id, 100)
    if not aweme_id:
        return []

    headers = build_comment_headers(keyword=keyword, aweme_id=aweme_id)
    params = build_comment_params(aweme_id=aweme_id, cursor=0, count=fetch_count)

    for endpoint in COMMENT_ENDPOINTS:
        endpoint_name = endpoint["name"]
        endpoint_url = endpoint["url"]

        try:
            response = requests.get(
                endpoint_url,
                params=params,
                headers=headers,
                timeout=15,
            )
        except Exception as e:
            print(f"抖音评论接口请求失败：endpoint={endpoint_name}，aweme_id={aweme_id}，原因：{e}")
            continue

        if response.status_code != 200:
            print_comment_response_debug(endpoint_name, aweme_id, response)
            continue

        text = response.text.strip()

        if not text.startswith("{"):
            print_comment_response_debug(endpoint_name, aweme_id, response)
            continue

        try:
            payload = response.json()
        except Exception as e:
            print(f"抖音评论接口 JSON 解析失败：endpoint={endpoint_name}，aweme_id={aweme_id}，原因：{e}")
            print_comment_response_debug(endpoint_name, aweme_id, response)
            continue

        raw_comments = extract_comments_from_payload(payload)

        comments: List[Dict[str, Any]] = []
        seen = set()

        for raw_comment in raw_comments:
            comment = normalize_douyin_comment(raw_comment, aweme_id=aweme_id)
            if not comment:
                continue

            source_id = comment.get("sourceCommentId")
            if not source_id or source_id in seen:
                continue

            comments.append(comment)
            seen.add(source_id)

        comments.sort(
            key=lambda item: (
                int(item.get("likeCount") or 0),
                int(item.get("replyCount") or 0),
            ),
            reverse=True,
        )

        top_comments = comments[:top_n]

        print(
            f"抖音评论解析完成：endpoint={endpoint_name}，aweme_id={aweme_id}，"
            f"候选 {len(comments)} 条，保存 {len(top_comments)} 条"
        )

        if top_comments:
            return top_comments

        print("========== 抖音评论 JSON 结构 DEBUG ==========")
        print(f"endpoint={endpoint_name}")
        print(f"aweme_id={aweme_id}")
        print(f"payload_keys={list(payload.keys()) if isinstance(payload, dict) else type(payload)}")
        if isinstance(payload, dict):
            for key in ["status_code", "status_msg", "comments", "cursor", "has_more", "total"]:
                print(f"{key}={payload.get(key)}")
        print("========== JSON 结构 DEBUG END ==========")

        time.sleep(random.uniform(COMMENT_REQUEST_SLEEP_SECONDS, COMMENT_REQUEST_SLEEP_SECONDS + 0.6))

    return []


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
        material.get("contentType") or "video",
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


def run_douyin_material_worker(limit: int = 2) -> int:
    """
    批量处理抖音材料任务。

    当前规则：
    - 每个热点抓 3 条视频材料；
    - 每条视频抓一批一级评论；
    - 按点赞数取前 5 条评论入库；
    - 评论抓取失败不影响视频材料任务完成。
    """
    conn = get_connection()
    done_count = 0

    try:
        with conn.cursor() as cursor:
            tasks = fetch_pending_material_tasks(cursor, limit)

            if not tasks:
                print("没有待处理的抖音材料任务")
                conn.commit()
                return 0

            print(f"发现待处理抖音材料任务：{len(tasks)} 条")

            for task in tasks:
                task_id = task.get("id")
                hotspot_id = task.get("hotspot_id")
                title = clean_text(task.get("title"), 100)
                platform = task.get("platform") or DOUYIN_PLATFORM
                now = datetime.now()

                try:
                    if platform != DOUYIN_PLATFORM:
                        raise RuntimeError(f"平台不匹配，当前 worker 只处理 douyin，实际为：{platform}")

                    if not hotspot_id:
                        raise RuntimeError("hotspot_id 为空，无法写入材料")

                    if not title:
                        raise RuntimeError("热点标题为空，无法抓取材料")

                    materials = fetch_douyin_materials_by_keyword(title, limit=POSTS_PER_HOTSPOT)

                    if not materials:
                        raise RuntimeError(
                            "未抓到抖音相关视频材料。可能需要配置 DOUYIN_COOKIE，或当前搜索接口被风控。"
                        )

                    post_count = 0
                    comment_count = 0

                    for material in materials:
                        material_post_id = insert_material_post(
                            cursor=cursor,
                            hotspot_id=hotspot_id,
                            platform=DOUYIN_PLATFORM,
                            keyword=title,
                            material=material,
                            now=now,
                        )
                        post_count += 1

                        aweme_id = str(material.get("sourceItemId") or "").strip()
                        if not aweme_id:
                            continue

                        try:
                            comments = fetch_douyin_comments_by_aweme_id(
                                aweme_id=aweme_id,
                                keyword=title,
                                fetch_count=COMMENT_FETCH_COUNT,
                                top_n=COMMENTS_PER_VIDEO,
                            )

                            for comment in comments:
                                insert_material_comment(
                                    cursor=cursor,
                                    hotspot_id=hotspot_id,
                                    material_post_id=material_post_id,
                                    platform=DOUYIN_PLATFORM,
                                    comment=comment,
                                    now=now,
                                )
                                comment_count += 1

                        except Exception as comment_error:
                            print(
                                f"抖音评论抓取跳过：title={title}，aweme_id={aweme_id}，原因：{comment_error}"
                            )

                        time.sleep(random.uniform(COMMENT_REQUEST_SLEEP_SECONDS, COMMENT_REQUEST_SLEEP_SECONDS + 0.6))

                    mark_task_done(cursor, task_id)
                    conn.commit()
                    done_count += 1

                    print(
                        f"抖音材料任务完成：{title}，写入视频材料 {post_count} 条，写入高赞评论 {comment_count} 条"
                    )

                except Exception as e:
                    conn.rollback()
                    print(f"抖音材料任务失败：{title}，原因：{e}")

                    try:
                        with conn.cursor() as fail_cursor:
                            mark_task_failed(fail_cursor, task_id, str(e))
                        conn.commit()
                    except Exception:
                        conn.rollback()

                time.sleep(random.uniform(REQUEST_SLEEP_SECONDS, REQUEST_SLEEP_SECONDS + 1.2))

        print(f"抖音材料 worker 完成：处理成功 {done_count} 条任务")
        return done_count

    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="抖音材料抓取 worker")
    parser.add_argument("--limit", type=int, default=2, help="本次最多处理多少条抖音材料任务")
    args = parser.parse_args()

    run_douyin_material_worker(limit=args.limit)


if __name__ == "__main__":
    main()