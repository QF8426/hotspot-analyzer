import hashlib
import json
import os
import random
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode

import pymysql
import requests
from pymysql.connections import Connection
from pymysql.cursors import Cursor

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from db_config import DB_CONFIG
from material_config import (
    BILIBILI_COMMENT_CANDIDATE_SIZE,
    COMMENTS_PER_MATERIAL,
    MATERIALS_PER_HOTSPOT,
)


BILIBILI_PLATFORM = "bilibili"

TASK_PENDING_STATUS = "pending_bilibili"
TASK_PROCESSING_STATUS = "processing_bilibili"
TASK_DONE_STATUS = "done"
TASK_FAILED_STATUS = "failed"

# 统一材料采集标准：每个热点最多保存 3 条主体材料，每条主体材料最多保存 5 条高赞评论。
# B站仍会扩大候选池，再按点赞数排序取前 5。
POST_LIMIT_PER_HOTSPOT = MATERIALS_PER_HOTSPOT
COMMENTS_PER_VIDEO = COMMENTS_PER_MATERIAL
COMMENT_CANDIDATE_SIZE = BILIBILI_COMMENT_CANDIDATE_SIZE

BILIBILI_HOME_URL = "https://www.bilibili.com/"
BILIBILI_NAV_API = "https://api.bilibili.com/x/web-interface/nav"
BILIBILI_WBI_SEARCH_API = "https://api.bilibili.com/x/web-interface/wbi/search/type"
BILIBILI_REPLY_HOT_API = "https://api.bilibili.com/x/v2/reply/hot"
BILIBILI_REPLY_WBI_MAIN_API = "https://api.bilibili.com/x/v2/reply/wbi/main"
BILIBILI_SEARCH_PAGE = "https://search.bilibili.com/all"

# 可选：从浏览器复制 B站 Cookie 放到 .env
# BILIBILI_COOKIE=buvid3=xxx; b_nut=xxx; SESSDATA=xxx; bili_jct=xxx;
BILIBILI_COOKIE = os.getenv("BILIBILI_COOKIE", "").strip()


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
]


MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32,
    15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19,
    29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61,
    26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63,
    57, 62, 11, 36, 20, 34, 44, 52,
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
    )


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default

        if isinstance(value, int):
            return value

        text = str(value).strip()
        if not text or text in {"--", "-"}:
            return default

        text = text.replace(",", "")

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


def ts_to_datetime(value: Any) -> Optional[datetime]:
    try:
        if value is None:
            return None

        num = int(value)
        if num <= 0:
            return None

        return datetime.fromtimestamp(num)
    except Exception:
        return None


def clean_html_text(text: Optional[str]) -> str:
    if not text:
        return ""

    value = str(text)
    value = value.replace("<em class=\"keyword\">", "")
    value = value.replace("</em>", "")
    value = re.sub(r"<[^>]+>", "", value)

    return value.strip()


def build_search_page_url(keyword: str) -> str:
    return f"{BILIBILI_SEARCH_PAGE}?keyword={quote(keyword)}"


def build_video_url(bvid: Optional[str], aid: Optional[Any], arcurl: Optional[str] = None) -> str:
    if arcurl:
        return arcurl

    if bvid:
        return f"https://www.bilibili.com/video/{bvid}"

    if aid:
        return f"https://www.bilibili.com/video/av{aid}"

    return "https://www.bilibili.com"


def create_session() -> requests.Session:
    session = requests.Session()

    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": BILIBILI_SEARCH_PAGE,
        "Origin": "https://search.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })

    if BILIBILI_COOKIE:
        session.headers.update({
            "Cookie": BILIBILI_COOKIE
        })

    return session


def warm_up_session(session: requests.Session, keyword: str) -> None:
    try:
        session.get(BILIBILI_HOME_URL, timeout=10)
        time.sleep(random.uniform(0.5, 1.0))

        session.get(build_search_page_url(keyword), timeout=10)
        time.sleep(random.uniform(0.5, 1.0))
    except Exception as e:
        print("B站预热请求失败，继续尝试接口：", e)


def get_url_key(url: str) -> str:
    filename = url.rsplit("/", 1)[-1]
    return filename.split(".", 1)[0]


def get_mixin_key(orig: str) -> str:
    return "".join(orig[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def remove_wbi_illegal_chars(value: str) -> str:
    return re.sub(r"[!'()*]", "", value)


def sign_wbi_params(params: Dict[str, Any], img_key: str, sub_key: str) -> Dict[str, Any]:
    mixin_key = get_mixin_key(img_key + sub_key)

    signed_params = dict(params)
    signed_params["wts"] = int(time.time())

    filtered_params: Dict[str, Any] = {}
    for key, value in signed_params.items():
        if value is None:
            continue

        if isinstance(value, str):
            filtered_params[key] = remove_wbi_illegal_chars(value)
        else:
            filtered_params[key] = value

    query = urlencode(sorted(filtered_params.items()))
    w_rid = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()

    filtered_params["w_rid"] = w_rid
    return filtered_params


def get_wbi_keys(session: requests.Session) -> tuple[str, str]:
    response = session.get(BILIBILI_NAV_API, timeout=15)
    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:
        raise RuntimeError(f"B站 nav 接口返回异常：{data}")

    payload = data.get("data") or {}
    wbi_img = payload.get("wbi_img") or {}

    img_url = wbi_img.get("img_url")
    sub_url = wbi_img.get("sub_url")

    if not img_url or not sub_url:
        raise RuntimeError(f"B站 nav 接口没有返回 wbi_img：{data}")

    return get_url_key(img_url), get_url_key(sub_url)


def request_bilibili_video_search(
    session: requests.Session,
    keyword: str,
    page: int = 1,
) -> Dict[str, Any]:
    img_key, sub_key = get_wbi_keys(session)

    params = {
        "search_type": "video",
        "keyword": keyword,
        "page": page,
        "order": "totalrank",
        "duration": 0,
        "tids": 0,
        "page_size": 20,
    }

    signed_params = sign_wbi_params(params, img_key, sub_key)

    headers = {
        "Referer": build_search_page_url(keyword),
    }

    response = session.get(
        BILIBILI_WBI_SEARCH_API,
        params=signed_params,
        headers=headers,
        timeout=20,
    )

    if response.status_code == 412:
        raise RuntimeError(
            "B站搜索接口返回 412。通常是 Cookie 不足、buvid3 缺失、WBI 签名失败或请求过快。"
            "建议从浏览器复制 B站 Cookie 到 .env 的 BILIBILI_COOKIE。"
        )

    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:
        raise RuntimeError(f"B站视频搜索接口返回异常：{data}")

    return data


def fetch_bilibili_video_materials(
    keyword: str,
    limit: int = POST_LIMIT_PER_HOTSPOT,
) -> List[Dict[str, Any]]:
    session = create_session()
    warm_up_session(session, keyword)

    data = request_bilibili_video_search(session, keyword, page=1)

    payload = data.get("data") or {}
    raw_list = payload.get("result") or []

    materials: List[Dict[str, Any]] = []

    for item in raw_list:
        bvid = item.get("bvid")
        aid = item.get("aid")
        arcurl = item.get("arcurl")

        source_item_id = bvid or (f"av{aid}" if aid else None)
        if not source_item_id:
            continue

        title = clean_html_text(item.get("title"))
        description = clean_html_text(item.get("description") or item.get("desc"))

        if not title:
            continue

        author_name = item.get("author") or item.get("typename") or ""

        play_count = safe_int(item.get("play"))
        like_count = safe_int(item.get("like"))
        favorite_count = safe_int(item.get("favorites"))
        danmaku_count = safe_int(item.get("video_review"))
        comment_count = safe_int(item.get("review"))

        source_url = build_video_url(bvid, aid, arcurl)

        content_parts = [
            f"视频标题：{title}",
        ]

        if description:
            content_parts.append(f"视频简介：{description}")

        if author_name:
            content_parts.append(f"作者：{author_name}")

        content_parts.append(
            f"互动数据：播放 {play_count}，点赞 {like_count}，收藏 {favorite_count}，弹幕 {danmaku_count}，评论 {comment_count}"
        )

        material = {
            "aid": aid,
            "bvid": bvid,
            "source_item_id": source_item_id,
            "content_type": "video",
            "title": title,
            "content": "\n".join(content_parts),
            "author_name": str(author_name) if author_name else None,
            "source_url": source_url,
            "cover_url": item.get("pic"),
            "media_urls": None,
            "like_count": like_count,
            "comment_count": comment_count,
            "repost_count": 0,
            "publish_time": ts_to_datetime(item.get("pubdate") or item.get("senddate")),
            "raw_json": json.dumps(item, ensure_ascii=False),
        }

        materials.append(material)

        if len(materials) >= limit:
            break

    return materials


def request_hot_comments(session: requests.Session, aid: int) -> List[Dict[str, Any]]:
    """
    优先请求热评接口。
    """
    params = {
        "type": 1,
        "oid": aid,
        "ps": COMMENT_CANDIDATE_SIZE,
        "pn": 1,
    }

    response = session.get(
        BILIBILI_REPLY_HOT_API,
        params=params,
        headers={"Referer": f"https://www.bilibili.com/video/av{aid}"},
        timeout=15,
    )

    if response.status_code == 412:
        raise RuntimeError("B站热评接口返回 412，可能需要更新 BILIBILI_COOKIE")

    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:
        print(f"B站热评接口返回异常，准备回退普通评论：{data}")
        return []

    payload = data.get("data") or {}
    replies = payload.get("replies") or []

    return replies if isinstance(replies, list) else []


def request_main_comments(session: requests.Session, aid: int) -> List[Dict[str, Any]]:
    """
    回退请求 wbi/main 普通评论接口。
    """
    img_key, sub_key = get_wbi_keys(session)

    params = {
        "oid": aid,
        "type": 1,
        "mode": 3,
        "plat": 1,
        "web_location": 1315875,
    }

    signed_params = sign_wbi_params(params, img_key, sub_key)

    response = session.get(
        BILIBILI_REPLY_WBI_MAIN_API,
        params=signed_params,
        headers={"Referer": f"https://www.bilibili.com/video/av{aid}"},
        timeout=15,
    )

    if response.status_code == 412:
        raise RuntimeError("B站普通评论接口返回 412，可能需要更新 BILIBILI_COOKIE")

    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:
        print(f"B站普通评论接口返回异常：{data}")
        return []

    payload = data.get("data") or {}
    replies = payload.get("replies") or []

    return replies if isinstance(replies, list) else []


def parse_bilibili_comment(reply: Dict[str, Any], material_post_id: int, hotspot_id: int) -> Optional[Dict[str, Any]]:
    rpid = reply.get("rpid")
    if not rpid:
        return None

    content_obj = reply.get("content") or {}
    message = (content_obj.get("message") or "").strip()

    if not message:
        return None

    member = reply.get("member") or {}

    return {
        "hotspot_id": hotspot_id,
        "material_post_id": material_post_id,
        "platform": BILIBILI_PLATFORM,
        "source_comment_id": str(rpid),
        "content": message,
        "author_name": member.get("uname"),
        "like_count": safe_int(reply.get("like")),
        "reply_count": safe_int(reply.get("rcount")),
        "publish_time": ts_to_datetime(reply.get("ctime")),
        "raw_json": json.dumps(reply, ensure_ascii=False),
    }


def fetch_bilibili_comments_for_video(
    aid: Optional[Any],
    material_post_id: int,
    hotspot_id: int,
    limit: int = COMMENTS_PER_VIDEO,
) -> List[Dict[str, Any]]:
    if not aid:
        return []

    try:
        aid_int = int(aid)
    except Exception:
        return []

    session = create_session()

    replies: List[Dict[str, Any]] = []

    try:
        replies = request_hot_comments(session, aid_int)
    except Exception as e:
        print(f"B站热评抓取失败，准备尝试普通评论：{e}")

    if not replies:
        try:
            replies = request_main_comments(session, aid_int)
        except Exception as e:
            print(f"B站普通评论抓取失败：{e}")
            return []

    comments: List[Dict[str, Any]] = []

    for reply in replies:
        parsed = parse_bilibili_comment(reply, material_post_id, hotspot_id)
        if parsed:
            comments.append(parsed)

    comments.sort(key=lambda x: x.get("like_count") or 0, reverse=True)

    return comments[:limit]


def fetch_pending_tasks(cursor: Cursor, limit: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT id, hotspot_id, platform, title
        FROM hotspot_material_task
        WHERE platform = %s
          AND status = %s
        ORDER BY updated_at ASC, id ASC
        LIMIT %s
    """
    cursor.execute(sql, (BILIBILI_PLATFORM, TASK_PENDING_STATUS, limit))
    rows = cursor.fetchall()

    tasks: List[Dict[str, Any]] = []
    for row in rows:
        tasks.append({
            "id": row[0],
            "hotspot_id": row[1],
            "platform": row[2],
            "title": row[3],
        })

    return tasks


def mark_task_processing(cursor: Cursor, task_id: int) -> None:
    sql = """
        UPDATE hotspot_material_task
        SET status = %s,
            error_message = NULL,
            updated_at = %s
        WHERE id = %s
    """
    cursor.execute(sql, (TASK_PROCESSING_STATUS, datetime.now(), task_id))


def mark_task_done(cursor: Cursor, task_id: int) -> None:
    sql = """
        UPDATE hotspot_material_task
        SET status = %s,
            error_message = NULL,
            updated_at = %s
        WHERE id = %s
    """
    cursor.execute(sql, (TASK_DONE_STATUS, datetime.now(), task_id))


def mark_task_failed(cursor: Cursor, task_id: int, error_message: str) -> None:
    sql = """
        UPDATE hotspot_material_task
        SET status = %s,
            error_message = %s,
            updated_at = %s
        WHERE id = %s
    """
    cursor.execute(sql, (
        TASK_FAILED_STATUS,
        error_message[:500],
        datetime.now(),
        task_id,
    ))


def count_existing_posts(cursor: Cursor, hotspot_id: int) -> int:
    sql = """
        SELECT COUNT(*)
        FROM hotspot_material_post
        WHERE hotspot_id = %s
          AND platform = %s
    """
    cursor.execute(sql, (hotspot_id, BILIBILI_PLATFORM))
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def fetch_existing_posts(cursor: Cursor, hotspot_id: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT id, hotspot_id, source_item_id, title, raw_json
        FROM hotspot_material_post
        WHERE hotspot_id = %s
          AND platform = %s
        ORDER BY like_count DESC, id ASC
        LIMIT %s
    """
    cursor.execute(sql, (hotspot_id, BILIBILI_PLATFORM, POST_LIMIT_PER_HOTSPOT))
    rows = cursor.fetchall()

    posts: List[Dict[str, Any]] = []

    for row in rows:
        raw_json_text = row[4]
        raw_obj: Dict[str, Any] = {}

        if raw_json_text:
            try:
                raw_obj = json.loads(raw_json_text)
            except Exception:
                raw_obj = {}

        posts.append({
            "id": row[0],
            "hotspot_id": row[1],
            "source_item_id": row[2],
            "title": row[3],
            "raw_json": raw_obj,
            "aid": raw_obj.get("aid"),
            "bvid": raw_obj.get("bvid"),
        })

    return posts


def count_existing_comments(cursor: Cursor, material_post_id: int) -> int:
    sql = """
        SELECT COUNT(*)
        FROM hotspot_material_comment
        WHERE material_post_id = %s
          AND platform = %s
    """
    cursor.execute(sql, (material_post_id, BILIBILI_PLATFORM))
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def insert_material_post(
    cursor: Cursor,
    hotspot_id: int,
    keyword: str,
    material: Dict[str, Any],
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
            raw_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            hotspot_id = VALUES(hotspot_id),
            keyword = VALUES(keyword),
            title = VALUES(title),
            content = VALUES(content),
            author_name = VALUES(author_name),
            source_url = VALUES(source_url),
            cover_url = VALUES(cover_url),
            like_count = VALUES(like_count),
            comment_count = VALUES(comment_count),
            repost_count = VALUES(repost_count),
            publish_time = VALUES(publish_time),
            crawl_time = VALUES(crawl_time),
            raw_json = VALUES(raw_json)
    """
    cursor.execute(sql, (
        hotspot_id,
        BILIBILI_PLATFORM,
        keyword,
        material.get("source_item_id"),
        material.get("content_type"),
        material.get("title"),
        material.get("content"),
        material.get("author_name"),
        material.get("source_url"),
        material.get("cover_url"),
        material.get("media_urls"),
        material.get("like_count"),
        material.get("comment_count"),
        material.get("repost_count"),
        material.get("publish_time"),
        datetime.now(),
        material.get("raw_json"),
    ))

    select_sql = """
        SELECT id
        FROM hotspot_material_post
        WHERE platform = %s
          AND source_item_id = %s
        LIMIT 1
    """
    cursor.execute(select_sql, (BILIBILI_PLATFORM, material.get("source_item_id")))
    row = cursor.fetchone()

    if not row:
        raise RuntimeError("B站视频材料写入后未能查到 material_post_id")

    return int(row[0])


def insert_material_comment(cursor: Cursor, comment: Dict[str, Any]) -> bool:
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
            raw_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        comment.get("hotspot_id"),
        comment.get("material_post_id"),
        comment.get("platform"),
        comment.get("source_comment_id"),
        comment.get("content"),
        comment.get("author_name"),
        comment.get("like_count"),
        comment.get("reply_count"),
        comment.get("publish_time"),
        datetime.now(),
        comment.get("raw_json"),
    ))

    # rowcount == 1 通常表示新插入；重复更新不算新增评论
    return cursor.rowcount == 1


def fill_comments_for_posts(cursor: Cursor, posts: List[Dict[str, Any]]) -> int:
    total_inserted = 0

    for post in posts:
        material_post_id = post["id"]
        hotspot_id = post["hotspot_id"]

        existing_comments = count_existing_comments(cursor, material_post_id)
        if existing_comments >= COMMENTS_PER_VIDEO:
            continue

        aid = post.get("aid")
        if not aid:
            continue

        comments = fetch_bilibili_comments_for_video(
            aid=aid,
            material_post_id=material_post_id,
            hotspot_id=hotspot_id,
            limit=COMMENTS_PER_VIDEO,
        )

        for comment in comments:
            if insert_material_comment(cursor, comment):
                total_inserted += 1

        time.sleep(random.uniform(0.5, 1.2))

    return total_inserted


def process_one_task(cursor: Cursor, task: Dict[str, Any]) -> Dict[str, Any]:
    task_id = task["id"]
    hotspot_id = task["hotspot_id"]
    keyword = task["title"]

    mark_task_processing(cursor, task_id)

    existing_count = count_existing_posts(cursor, hotspot_id)

    video_inserted_count = 0

    if existing_count < POST_LIMIT_PER_HOTSPOT:
        materials = fetch_bilibili_video_materials(keyword, limit=POST_LIMIT_PER_HOTSPOT)

        if not materials and existing_count == 0:
            mark_task_failed(cursor, task_id, "未搜索到 B站相关视频材料")
            return {
                "status": "failed",
                "videoInserted": 0,
                "commentInserted": 0,
                "message": "未搜索到 B站相关视频材料",
            }

        for material in materials:
            insert_material_post(cursor, hotspot_id, keyword, material)
            video_inserted_count += 1

    posts = fetch_existing_posts(cursor, hotspot_id)
    comment_inserted_count = fill_comments_for_posts(cursor, posts)

    mark_task_done(cursor, task_id)

    return {
        "status": "done",
        "videoInserted": video_inserted_count,
        "commentInserted": comment_inserted_count,
        "message": f"写入 B站视频材料 {video_inserted_count} 条，写入评论 {comment_inserted_count} 条",
    }


def run_bilibili_material_worker(limit: int = 2) -> None:
    """
    B站材料 worker。

    每次处理 limit 个 pending_bilibili 任务。
    每个热点最多 3 条视频材料。
    每条视频最多 5 条高赞评论。
    使用 requests + Cookie + WBI 签名。
    """
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            tasks = fetch_pending_tasks(cursor, limit)

            if not tasks:
                print("没有待处理的 B站材料任务")
                return

            print(f"本次准备处理 B站材料任务：{len(tasks)} 条")

            for task in tasks:
                try:
                    result = process_one_task(cursor, task)
                    conn.commit()

                    print(
                        f"B站材料任务 {task['id']} 处理完成："
                        f"{result['status']}，{result['message']}"
                    )

                    time.sleep(random.uniform(1.0, 2.0))

                except Exception as e:
                    conn.rollback()

                    with conn.cursor() as err_cursor:
                        mark_task_failed(err_cursor, task["id"], str(e))
                    conn.commit()

                    print(f"B站材料任务 {task['id']} 处理失败：{e}")

    finally:
        conn.close()


if __name__ == "__main__":
    run_bilibili_material_worker(limit=2)