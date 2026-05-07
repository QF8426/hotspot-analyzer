from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import os
import re
import pymysql
from pymysql.connections import Connection
from pymysql.cursors import Cursor
from zhipuai import ZhipuAI

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

from db_config import DB_CONFIG


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
if load_dotenv:
    load_dotenv(ENV_FILE)

API_KEY = os.getenv("ZHIPUAI_API_KEY")
MODEL_NAME = os.getenv("ZHIPUAI_MODEL", "glm-4.5-air")

# 当前 AI 分析规则：最多读取 3 条帖子/视频，每条帖子/视频最多读取 10 条高赞评论。
POST_LIMIT = 3
COMMENTS_PER_POST = 10
MATERIAL_MAX_CHARS = 3600

# 这些状态表示材料任务还没真正完成，AI worker 要等待。
ACTIVE_MATERIAL_TASK_STATUSES = (
    "pending",
    "pending_douyin",
    "pending_bilibili",
    "processing",
    "processing_douyin",
    "processing_bilibili",
)


PROMPT_V3 = """你是“热点简介编辑助手”。请根据给定的热点基础信息、主体材料和评论，写一段适合放在前端详情页的热点简介。

写作目标：像编辑在整理一条热点说明，而不是生成报告。

严格要求：
1. 不要使用【热点概括】【讨论焦点】【舆情倾向】【代表性观点】等字段标题。
2. 不要写成列表，不要编号，不要分点。
3. 输出 2–3 个自然段，总字数控制在 180–260 字。
4. 第一段说明这个话题大致是什么，必须基于材料，不得补充材料外事实。
5. 第二段概括讨论焦点和评论情绪，可以写“从已采集材料看”“目前评论主要……”。
6. 如果样本有限、评论较少或材料不足，最后用一句自然的话说明边界，不要单独写“不确定项”。
7. 语言自然、克制、顺滑，不夸张、不营销、不煽动。
8. 禁止使用这些套话：引发广泛关注、网友纷纷表示、整体来看、值得注意的是、热度持续攀升、可见一斑。
9. 可以概括评论里的高频观点，但不要虚构引语，不要把少量评论写成全网态度。
10. 必须贴合平台语境：
   - 微博：可称为“微博热搜话题”“微博讨论”；
   - 抖音：可称为“抖音热榜话题”“相关视频和评论区”；
   - B站：可称为“B站热搜话题”“相关视频和评论区”，不要写成微博语境。
"""

DEFAULT_PROMPT = PROMPT_V3

BLACKLIST_PHRASES = [
    "引发广泛关注",
    "网友纷纷表示",
    "整体来看",
    "值得注意的是",
    "热度持续攀升",
    "可见一斑",
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


def get_ai_client() -> Optional[ZhipuAI]:
    if not API_KEY:
        print("未配置 ZHIPUAI_API_KEY，跳过 AI 分析生成。请检查 crawler_py/.env")
        return None

    return ZhipuAI(api_key=API_KEY)


def platform_label(platform: str) -> str:
    mapping = {
        "weibo": "微博",
        "douyin": "抖音",
        "bilibili": "B站",
    }
    return mapping.get(platform or "", platform or "未知平台")


def get_active_material_status_placeholders() -> str:
    return ",".join(["%s"] * len(ACTIVE_MATERIAL_TASK_STATUSES))


def fetch_pending_tasks(cursor: Cursor, limit: int) -> List[Dict[str, Any]]:
    """
    只取真正可以生成 AI 简介的 pending 任务。

    条件：
    1. AI 任务本身是 pending；
    2. 已经存在至少 1 条主体材料；
    3. 对应热点不存在仍在 pending / processing 的材料任务。

    这样可以避免：
    - B站/抖音材料还没抓完，AI 就提前生成；
    - 老的空材料任务挡住后面已完成材料的新任务。
    """
    placeholders = get_active_material_status_placeholders()

    sql = f"""
        SELECT t.id, t.hotspot_id, t.platform, t.title, t.priority, t.status
        FROM hotspot_ai_summary_task t
        WHERE t.status = 'pending'
          AND EXISTS (
              SELECT 1
              FROM hotspot_material_post p
              WHERE p.hotspot_id = t.hotspot_id
                AND p.content IS NOT NULL
                AND p.content <> ''
              LIMIT 1
          )
          AND NOT EXISTS (
              SELECT 1
              FROM hotspot_material_task mt
              WHERE mt.hotspot_id = t.hotspot_id
                AND mt.status IN ({placeholders})
              LIMIT 1
          )
        ORDER BY t.priority DESC, t.created_at ASC
        LIMIT %s
    """

    params = list(ACTIVE_MATERIAL_TASK_STATUSES) + [limit]
    cursor.execute(sql, params)
    return list(cursor.fetchall())


def count_waiting_material_tasks(cursor: Cursor) -> int:
    """
    统计还不能生成的 AI pending 任务数量。

    不能生成的原因：
    - 没有主体材料；
    - 或者材料任务还处于 pending / processing。
    """
    placeholders = get_active_material_status_placeholders()

    sql = f"""
        SELECT COUNT(*) AS count
        FROM hotspot_ai_summary_task t
        WHERE t.status = 'pending'
          AND (
              NOT EXISTS (
                  SELECT 1
                  FROM hotspot_material_post p
                  WHERE p.hotspot_id = t.hotspot_id
                    AND p.content IS NOT NULL
                    AND p.content <> ''
                  LIMIT 1
              )
              OR EXISTS (
                  SELECT 1
                  FROM hotspot_material_task mt
                  WHERE mt.hotspot_id = t.hotspot_id
                    AND mt.status IN ({placeholders})
                  LIMIT 1
              )
          )
    """
    cursor.execute(sql, ACTIVE_MATERIAL_TASK_STATUSES)
    row = cursor.fetchone() or {}
    return int(row.get("count") or 0)


def clean_material_text(text: Any, limit: int) -> str:
    value = str(text or "").replace("\n", " ").replace("\r", " ").strip()
    value = " ".join(value.split())
    return value[:limit]


def format_material_time(value: Any) -> str:
    if not value:
        return "时间未知"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)[:16]


def fetch_materials_by_hotspot_id(
    cursor: Cursor,
    hotspot_id: int,
    post_limit: int = POST_LIMIT,
    comments_per_post: int = COMMENTS_PER_POST,
) -> Dict[str, Any]:
    """
    读取某个热点的主体材料和热门评论。

    主体材料可能是：
    - 微博帖子；
    - 抖音视频；
    - B站视频。
    """
    post_sql = """
        SELECT id, title, content, author_name, like_count, comment_count, repost_count, source_url,
               publish_time, crawl_time, created_at
        FROM hotspot_material_post
        WHERE hotspot_id = %s
          AND content IS NOT NULL
          AND content <> ''
        ORDER BY like_count DESC, comment_count DESC, created_at DESC
        LIMIT %s
    """
    cursor.execute(post_sql, (hotspot_id, post_limit))
    posts = list(cursor.fetchall())

    comment_items: List[Dict[str, Any]] = []
    for post in posts:
        post_id = post.get("id")
        if not post_id:
            continue

        comment_sql = """
            SELECT id, material_post_id, content, author_name, like_count, reply_count,
                   publish_time, crawl_time, created_at
            FROM hotspot_material_comment
            WHERE material_post_id = %s
              AND content IS NOT NULL
              AND content <> ''
            ORDER BY like_count DESC, created_at DESC
            LIMIT %s
        """
        cursor.execute(comment_sql, (post_id, comments_per_post))
        comment_items.extend(list(cursor.fetchall()))

    return {
        "posts": posts,
        "comments": comment_items,
    }


def build_material_input(
    title: str,
    platform: str,
    material_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    按 P1/P2/C1/C2 编号组织材料。
    模型只负责写简介，不负责猜样本数量。
    """
    posts = material_data.get("posts") or []
    comments = material_data.get("comments") or []

    material_lines: List[str] = []
    material_refs: List[str] = []
    times: List[datetime] = []
    total_len = 0

    label = platform_label(platform)

    def add_time(row: Dict[str, Any]) -> None:
        value = row.get("publish_time") or row.get("crawl_time") or row.get("created_at")
        if isinstance(value, datetime):
            times.append(value)

    for index, post in enumerate(posts, start=1):
        add_time(post)
        post_ref = f"P{index}"
        material_refs.append(post_ref)

        post_time = format_material_time(post.get("publish_time") or post.get("crawl_time") or post.get("created_at"))
        author = clean_material_text(post.get("author_name") or "未知用户", 20)
        post_title = clean_material_text(post.get("title") or "", 50)
        content = clean_material_text(post.get("content") or "", 160)
        like_count = post.get("like_count") or 0
        comment_count = post.get("comment_count") or 0
        repost_count = post.get("repost_count") or 0

        if platform == "bilibili":
            line = (
                f"[{post_ref}][{post_time}][{author}] "
                f"B站相关视频：{post_title} {content}"
                f"（点赞{like_count}，评论{comment_count}）"
            )
        elif platform == "douyin":
            line = (
                f"[{post_ref}][{post_time}][{author}] "
                f"抖音相关视频：{post_title} {content}"
                f"（点赞{like_count}，评论{comment_count}，转发{repost_count}）"
            )
        else:
            line = (
                f"[{post_ref}][{post_time}][{author}] "
                f"相关帖子：{post_title} {content}"
                f"（点赞{like_count}，评论{comment_count}，转发{repost_count}）"
            )

        if total_len + len(line) <= MATERIAL_MAX_CHARS:
            material_lines.append(line)
            total_len += len(line)

    for index, comment in enumerate(comments, start=1):
        add_time(comment)
        comment_ref = f"C{index}"
        material_refs.append(comment_ref)

        comment_time = format_material_time(comment.get("publish_time") or comment.get("crawl_time") or comment.get("created_at"))
        author = clean_material_text(comment.get("author_name") or "用户", 20)
        content = clean_material_text(comment.get("content") or "", 80)
        like_count = comment.get("like_count") or 0
        reply_count = comment.get("reply_count") or 0

        line = f"[{comment_ref}][{comment_time}][{author}] {content}（点赞{like_count}，回复{reply_count}）"
        if total_len + len(line) <= MATERIAL_MAX_CHARS:
            material_lines.append(line)
            total_len += len(line)

    post_count = len(posts)
    comment_count = len(comments)
    total_count = post_count + comment_count

    if times:
        start_time = min(times).strftime("%Y-%m-%d %H:%M")
        end_time = max(times).strftime("%Y-%m-%d %H:%M")
        time_range = f"{start_time} ~ {end_time}"
    else:
        time_range = "未知"

    materials_text = "\n".join(material_lines) if material_lines else "暂无可用材料。"
    refs_text = "、".join(material_refs[:8]) if material_refs else "无"

    final_input = f"""<basic_info>
标题：{title}
平台：{label}（platform={platform}）
样本数量：主体材料{post_count}条，评论{comment_count}条，共{total_count}条
时间范围：{time_range}
</basic_info>

<materials>
{materials_text}
</materials>

请基于以上材料写简介。材料编号仅用于你理解来源，不要在最终输出中机械罗列编号。"""

    return {
        "prompt_input": final_input,
        "post_count": post_count,
        "comment_count": comment_count,
        "total_count": total_count,
        "time_range": time_range,
        "material_refs": refs_text,
        "has_materials": bool(material_lines),
        "platform": platform,
        "platform_label": label,
    }


def build_fallback_summary(title: str, platform: str = "weibo", has_materials: bool = False) -> str:
    label = platform_label(platform)

    if has_materials:
        return (
            f"{title}正在{label}平台受到关注，系统已采集到部分相关内容和评论。"
            f"目前模型未能完成进一步归纳，详情页可先结合趋势图、来源链接和已采集材料继续观察。"
            f"由于该内容为系统兜底说明，不代表完整舆情结论。"
        )

    return (
        f"{title}正在{label}平台受到关注。系统暂未采集到足够的相关内容和评论，"
        f"因此暂不对讨论焦点和舆情倾向作明确判断。你可以先通过热度趋势和来源链接了解该话题的变化。"
    )


def validate_and_fix_summary(summary: str, title: str, material_meta: Dict[str, Any]) -> str:
    text = (summary or "").strip()
    platform = material_meta.get("platform") or "weibo"

    if not text:
        return build_fallback_summary(
            title,
            platform=platform,
            has_materials=material_meta.get("has_materials", False),
        )

    for phrase in BLACKLIST_PHRASES:
        text = text.replace(phrase, "")

    text = re.sub(r"【[^】]{1,12}】", "", text)

    paragraphs = []
    for part in re.split(r"\n+", text):
        part = part.strip(" ：:；;，,。\t ")
        if part:
            paragraphs.append(part)

    text = "\n\n".join(paragraphs).strip()

    comment_count = int(material_meta.get("comment_count", 0) or 0)
    if comment_count < 5 and "样本" not in text:
        text += "\n\n由于当前评论样本有限，上述内容更适合作为阶段性观察，不能代表完整舆论结论。"

    return text.strip()


def fetch_hotspot_context(cursor: Cursor, hotspot_id: int) -> Dict[str, Any]:
    sql = """
        SELECT id, platform, title, rank_num, hot_value, tags, is_special, source_url, crawl_time
        FROM hotspot
        WHERE id = %s
        LIMIT 1
    """
    cursor.execute(sql, (hotspot_id,))
    return cursor.fetchone() or {}


def mark_task_done(cursor: Cursor, task_id: int) -> None:
    sql = """
        UPDATE hotspot_ai_summary_task
        SET status = 'done', error_message = NULL, updated_at = %s
        WHERE id = %s
    """
    cursor.execute(sql, (datetime.now(), task_id))


def mark_task_failed(cursor: Cursor, task_id: int, message: str) -> None:
    sql = """
        UPDATE hotspot_ai_summary_task
        SET status = 'failed', error_message = %s, updated_at = %s
        WHERE id = %s
    """
    cursor.execute(sql, (message[:500], datetime.now(), task_id))


def build_hotspot_context_text(hotspot: Dict[str, Any], fallback_title: str) -> str:
    title = hotspot.get("title") or fallback_title
    platform = hotspot.get("platform") or "weibo"
    rank_num = hotspot.get("rank_num")
    hot_value = hotspot.get("hot_value")
    tags = hotspot.get("tags")
    is_special = hotspot.get("is_special")
    source_url = hotspot.get("source_url")

    parts = [
        f"标题：{title}",
        f"平台：{platform_label(platform)}",
    ]

    if rank_num is not None:
        parts.append(f"平台内排名：{rank_num}")

    if hot_value is not None:
        parts.append(f"热度/排序值：{hot_value}")

    if tags:
        parts.append(f"标签：{tags}")

    if source_url:
        parts.append(f"来源链接：{source_url}")

    if is_special:
        parts.append("该话题属于置顶/特殊展示项")

    return "；".join(parts)


def generate_ai_summary(
    client: ZhipuAI,
    title: str,
    hotspot_context: Dict[str, Any],
    material_data: Dict[str, Any],
) -> str:
    platform = hotspot_context.get("platform") or "weibo"
    material_meta = build_material_input(title, platform, material_data)
    context_text = build_hotspot_context_text(hotspot_context, title)

    prompt = f"""{DEFAULT_PROMPT}

热点基础信息：
{context_text}

{material_meta['prompt_input']}"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个克制、自然的热点简介编辑助手，只能基于用户提供的材料写前端可读的自然段简介。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        raw_summary = response.choices[0].message.content.strip()
        return validate_and_fix_summary(raw_summary, title, material_meta)

    except Exception as e:
        print(f"AI 模型调用失败，使用兜底分析：{e}")
        return build_fallback_summary(
            title,
            platform=platform,
            has_materials=material_meta.get("has_materials", False),
        )


def upsert_ai_summary(
    cursor: Cursor,
    task: Dict[str, Any],
    summary: str,
    now: datetime,
) -> None:
    sql = """
        INSERT INTO hotspot_ai_summary (
            hotspot_id, platform, title, summary, created_at
        ) VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            platform = VALUES(platform),
            title = VALUES(title),
            summary = VALUES(summary)
    """
    cursor.execute(sql, (
        task.get("hotspot_id"),
        task.get("platform"),
        task.get("title"),
        summary,
        now,
    ))


def run_ai_summary_worker(limit: int = 3) -> int:
    client = get_ai_client()
    if client is None:
        return 0

    conn = get_connection()
    generated_count = 0

    try:
        with conn.cursor() as cursor:
            tasks = fetch_pending_tasks(cursor, limit)
            waiting_count = count_waiting_material_tasks(cursor)

            if not tasks:
                if waiting_count > 0:
                    print(f"暂无可生成的 AI 简介任务；仍有 {waiting_count} 条 pending 任务在等待材料抓取")
                else:
                    print("暂无待生成的 AI 简介任务")
                return 0

            print(f"发现可生成 AI 简介任务：{len(tasks)} 条；等待材料任务：{waiting_count} 条")

            for task in tasks:
                task_id = task.get("id")
                hotspot_id = task.get("hotspot_id")
                title = task.get("title") or "该话题"

                try:
                    material_data = fetch_materials_by_hotspot_id(
                        cursor,
                        hotspot_id,
                        post_limit=POST_LIMIT,
                        comments_per_post=COMMENTS_PER_POST,
                    )

                    post_count = len(material_data.get("posts") or [])
                    comment_count = len(material_data.get("comments") or [])
                    total_count = post_count + comment_count

                    if post_count == 0:
                        print(f"hotspot_id={hotspot_id} 材料读取为空，跳过本轮 AI 生成；任务保持 pending")
                        continue

                    hotspot_context = fetch_hotspot_context(cursor, hotspot_id)
                    platform = hotspot_context.get("platform") or task.get("platform") or "weibo"

                    print(
                        f"hotspot_id={hotspot_id}（{platform_label(platform)}）读取到主体材料 {post_count} 条、"
                        f"评论 {comment_count} 条，共 {total_count} 条材料，开始生成自然段版 AI 简介"
                    )

                    summary = generate_ai_summary(client, title, hotspot_context, material_data)
                    upsert_ai_summary(cursor, task, summary, datetime.now())

                    generated_count += 1

                    mark_task_done(cursor, task_id)
                    conn.commit()

                except Exception as e:
                    conn.rollback()
                    print(f"AI 简介任务失败，hotspot_id={hotspot_id}：{e}")

                    try:
                        mark_task_failed(cursor, task_id, str(e))
                        conn.commit()
                    except Exception:
                        conn.rollback()

        print(f"AI 简介生成完成：写入/更新 {generated_count} 条")
        return generated_count

    finally:
        conn.close()


if __name__ == "__main__":
    run_ai_summary_worker(limit=5)