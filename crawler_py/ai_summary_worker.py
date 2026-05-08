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

try:
    from cross_platform_matcher import analyze_cross_platform_status
except Exception as import_error:
    analyze_cross_platform_status = None
    CROSS_PLATFORM_IMPORT_ERROR = import_error
else:
    CROSS_PLATFORM_IMPORT_ERROR = None


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

# 跨平台综合分析时，最多给模型传入的材料字符数。
CROSS_PLATFORM_MATERIAL_MAX_CHARS = 9000
CROSS_PLATFORM_PER_PLATFORM_MAX_CHARS = 2800

# 是否启用跨平台简介增强。
ENABLE_CROSS_PLATFORM_ANALYSIS = True

# 匹配到多平台热点但材料没齐时，是否等待材料补齐再生成。
WAIT_CROSS_PLATFORM_MATERIALS_READY = True

# 这些状态表示材料任务还没真正完成，AI worker 要等待。
ACTIVE_MATERIAL_TASK_STATUSES = (
    "pending",
    "pending_douyin",
    "pending_bilibili",
    "processing",
    "processing_douyin",
    "processing_bilibili",
)


PROMPT_V4 = """你是“热点详情页文案编辑”。请根据提供的热点基础信息、主体材料和评论，写一段适合放在网页详情页里的热点简介。

你的目标不是写舆情报告，而是让普通用户快速看懂：这个热点是什么、为什么被讨论、目前采集到的材料里大概有哪些声音。

写作要求：
1. 输出 2 个自然段，必要时可以写 3 个自然段，总字数控制在 160–240 字。
2. 第一段先说明这个话题大致是什么，只能基于标题、热点基础信息和材料，不要补充材料外事实。
3. 第二段说明相关内容或评论里主要在讨论什么，但不要把少量样本扩大成“全网态度”。
4. 语言要像网页编辑写给普通用户看的介绍，清楚、自然、克制，不要像论文、报告、新闻通稿或官方公告。
5. 不要使用小标题，不要列表，不要编号，不要写“热点概述”“讨论焦点”“舆情倾向”“代表观点”。
6. 不要机械使用这些词句：从已采集材料看、整体来看、网友纷纷表示、引发广泛关注、值得注意的是、热度持续攀升、舆情倾向、代表观点、样本数量有限。
7. 可以使用更自然的表达，例如“相关内容主要围绕……展开”“评论里有人关注……也有人提到……”“目前能看到的讨论更多集中在……”。
8. 对评论的概括要谨慎，可以写“一部分评论”“有评论提到”“也有人认为”，不要写“多数网友”“全网认为”，除非材料中非常明确。
9. 如果材料或评论较少，可以在最后一句自然说明“目前可参考的材料还不多”，但不要每次都写成免责声明。
10. 必须贴合平台语境：
   - 微博：可称为“微博热搜话题”“相关微博内容”；
   - 抖音：可称为“抖音热榜话题”“相关视频和评论区”；
   - B站：可称为“B站热搜话题”“相关视频和评论区”，不要写成微博语境。
"""


PROMPT_CROSS_PLATFORM = """你是“跨平台热点详情页文案编辑”。请根据提供的热点基础信息、跨平台匹配结果、各平台材料和评论，写一段适合放在网页详情页里的跨平台综合简介。

你的目标不是写舆情报告，而是让普通用户快速看懂：这个热点在多个平台上是否都被讨论，各平台关注点有什么差异，热度和讨论方式大致有什么不同。

写作要求：
1. 输出 2–3 个自然段，总字数控制在 220–320 字。
2. 第一段说明这个话题大致是什么，并自然说明它同时出现在多个平台的热点列表中。
3. 第二段比较不同平台的讨论重点，例如微博更偏事件传播、抖音更偏视频评论互动、B站更偏复盘解释或长视频讨论。但必须基于材料，不要套模板硬写。
4. 如果材料里能看出热度、排名或互动差异，可以轻描淡写说明，不要把平台热度值直接当成可比较的绝对数值。
5. 不要写成报告，不要写小标题，不要列表，不要编号。
6. 不要使用“舆情倾向”“代表观点”“网友纷纷表示”“引发广泛关注”“整体来看”等套话。
7. 对评论的概括要谨慎，可以写“一部分评论”“有评论提到”“也有人认为”，不要写“全网认为”。
8. 如果某个平台材料较少，只能温和说明“目前该平台可参考材料较少”，不要强行比较。
9. 语言自然、清楚、克制，像网页详情页里的说明文字。
"""


PROMPT_SAFE_RETRY = """你是“热点详情页文案编辑”。请根据提供的热点基础信息和经过清洗的材料，写一段非常克制、客观、温和的热点简介。

这是一次安全重试。你的任务不是分析争议，不是评价对错，而是用普通用户能理解的方式说明：这个话题大致是什么，相关内容主要在讨论哪些方向。

写作要求：
1. 输出 2 个自然段，总字数控制在 120–200 字。
2. 只做客观介绍，不复述攻击性评论，不引用评论原文。
3. 不评价谁对谁错，不扩展材料外事实。
4. 不使用小标题，不列表，不编号。
5. 不写“舆情倾向”“代表观点”“网友纷纷表示”“引发广泛关注”。
6. 如果评论材料不足，就主要概括主体材料，不强行判断评论态度。
7. 语言要自然、清楚、克制，像网页详情页里的简短说明。
8. 必须贴合平台语境：
   - 微博：可称为“微博热搜话题”“相关微博内容”；
   - 抖音：可称为“抖音热榜话题”“相关视频和评论区”；
   - B站：可称为“B站热搜话题”“相关视频和评论区”，不要写成微博语境。
"""


PROMPT_CROSS_PLATFORM_SAFE_RETRY = """你是“跨平台热点详情页文案编辑”。请根据经过清洗的跨平台材料，写一段非常克制、客观、温和的跨平台简介。

这是一次安全重试。你的任务不是评价争议，不是复述评论原文，而是简要说明这个话题在多个平台上的讨论方向。

写作要求：
1. 输出 2 个自然段，总字数控制在 160–240 字。
2. 只做客观介绍，不复述攻击性评论，不引用评论原文。
3. 不评价谁对谁错，不扩展材料外事实。
4. 不使用小标题，不列表，不编号。
5. 不写“舆情倾向”“代表观点”“网友纷纷表示”“引发广泛关注”。
6. 可以简要比较不同平台的内容形态和讨论重点，但不要夸大结论。
7. 语言自然、清楚、克制，像网页详情页里的说明文字。
"""

DEFAULT_PROMPT = PROMPT_V4

BLACKLIST_PHRASES = [
    "引发广泛关注",
    "网友纷纷表示",
    "整体来看",
    "值得注意的是",
    "热度持续攀升",
    "可见一斑",
    "从已采集材料看，",
    "从已采集材料看",
    "从目前已采集材料看，",
    "从目前已采集材料看",
    "舆情倾向",
    "代表观点",
    "不能代表完整舆论结论",
    "不代表完整舆论结论",
]

RISKY_WORDS_FOR_RETRY = [
    "死",
    "杀",
    "血",
    "枪",
    "刀",
    "暴力",
    "恐怖",
    "袭击",
    "爆炸",
    "极端",
    "去死",
    "傻逼",
    "垃圾",
    "畜生",
    "恶心",
    "滚",
    "卖国",
    "造谣",
    "煽动",
    "境外势力",
    "国家机密",
    "政治敏感",
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
        "cross_platform": "跨平台",
    }
    return mapping.get(platform or "", platform or "未知平台")


def get_active_material_status_placeholders() -> str:
    return ",".join(["%s"] * len(ACTIVE_MATERIAL_TASK_STATUSES))


def is_content_filter_error(error: Exception) -> bool:
    text = str(error or "")
    return (
        "1301" in text
        or "contentFilter" in text
        or "不安全或敏感内容" in text
        or "敏感内容" in text
    )


def fetch_pending_tasks(cursor: Cursor, limit: int) -> List[Dict[str, Any]]:
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


def clean_retry_text(text: Any, limit: int = 160) -> str:
    value = str(text or "")
    for word in RISKY_WORDS_FOR_RETRY:
        value = value.replace(word, "")

    value = value.replace("\n", " ").replace("\r", " ").strip()
    value = " ".join(value.split())

    return value[:limit]


def sanitize_material_data_for_retry(material_data: Dict[str, Any]) -> Dict[str, Any]:
    posts = material_data.get("posts") or []
    comments = material_data.get("comments") or []

    safe_posts: List[Dict[str, Any]] = []
    for post in posts[:3]:
        new_post = dict(post)
        new_post["title"] = clean_retry_text(new_post.get("title"), 80)
        new_post["content"] = clean_retry_text(new_post.get("content"), 220)
        new_post["author_name"] = clean_retry_text(new_post.get("author_name"), 40)
        safe_posts.append(new_post)

    sorted_comments = sorted(
        comments,
        key=lambda item: int(item.get("like_count") or 0),
        reverse=True,
    )

    safe_comments: List[Dict[str, Any]] = []
    for comment in sorted_comments[:3]:
        new_comment = dict(comment)
        new_comment["content"] = clean_retry_text(new_comment.get("content"), 90)
        new_comment["author_name"] = clean_retry_text(new_comment.get("author_name"), 40)
        safe_comments.append(new_comment)

    return {
        "posts": safe_posts,
        "comments": safe_comments,
    }


def sanitize_cross_platform_result_for_retry(cross_result: Dict[str, Any]) -> Dict[str, Any]:
    result_copy = dict(cross_result or {})
    material_bundle = dict(result_copy.get("material_bundle") or {})
    platform_items = material_bundle.get("platform_items") or []

    safe_platform_items = []
    for item in platform_items:
        safe_item = dict(item)
        safe_materials = sanitize_material_data_for_retry(item.get("materials") or {})
        safe_item["materials"] = safe_materials
        safe_item["post_count"] = len(safe_materials.get("posts") or [])
        safe_item["comment_count"] = len(safe_materials.get("comments") or [])
        safe_platform_items.append(safe_item)

    material_bundle["platform_items"] = safe_platform_items
    material_bundle["platform_count"] = len({
        item.get("platform")
        for item in safe_platform_items
        if item.get("platform")
    })

    result_copy["material_bundle"] = material_bundle
    return result_copy


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
        content = clean_material_text(post.get("content") or "", 180)
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
                f"相关微博内容：{post_title} {content}"
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
        content = clean_material_text(comment.get("content") or "", 90)
        like_count = comment.get("like_count") or 0
        reply_count = comment.get("reply_count") or 0

        line = f"[{comment_ref}][{comment_time}][{author}] 评论：{content}（点赞{like_count}，回复{reply_count}）"
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
材料数量：主体材料{post_count}条，评论{comment_count}条，共{total_count}条
材料时间范围：{time_range}
</basic_info>

<materials>
{materials_text}
</materials>

请基于以上材料写简介。材料编号仅用于你理解来源，不要在最终输出中机械罗列编号，也不要写成材料报告。"""

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


def build_cross_platform_context_text(cross_result: Dict[str, Any]) -> str:
    current = cross_result.get("current") or {}
    matches = cross_result.get("matches") or []
    material_check = cross_result.get("material_check") or {}

    lines = []

    current_platform = current.get("platform")
    lines.append(
        f"当前热点：{platform_label(current_platform)}｜"
        f"标题：{current.get('title')}｜"
        f"平台内排名：{current.get('rank_num')}｜"
        f"热度/排序值：{current.get('hot_value')}"
    )

    if matches:
        lines.append("匹配到的其它平台相似热点：")
        for item in matches:
            lines.append(
                f"- {platform_label(item.get('platform'))}｜"
                f"标题：{item.get('title')}｜"
                f"相似度：{item.get('similarity_score')}｜"
                f"平台内排名：{item.get('rank_num')}｜"
                f"热度/排序值：{item.get('hot_value')}"
            )

    related_platforms = material_check.get("related_platforms") or []
    ready_platforms = material_check.get("ready_platforms") or []

    lines.append(f"关联平台：{'、'.join(platform_label(p) for p in related_platforms)}")
    lines.append(f"已具备材料的平台：{'、'.join(platform_label(p) for p in ready_platforms)}")
    lines.append(f"分析模式：{material_check.get('analysis_mode')}")

    return "\n".join(lines)


def build_cross_platform_material_input(cross_result: Dict[str, Any]) -> Dict[str, Any]:
    material_bundle = cross_result.get("material_bundle") or {}
    platform_items = material_bundle.get("platform_items") or []

    material_sections: List[str] = []
    total_len = 0
    total_posts = 0
    total_comments = 0
    platforms = []

    for item in platform_items:
        platform = item.get("platform") or ""
        label = item.get("platform_label") or platform_label(platform)
        hotspot = item.get("hotspot") or {}
        materials = item.get("materials") or {}

        posts = materials.get("posts") or []
        comments = materials.get("comments") or []

        total_posts += len(posts)
        total_comments += len(comments)
        platforms.append(platform)

        section_lines = [
            f"【{label}】",
            f"热点标题：{hotspot.get('title')}",
            f"平台内排名：{hotspot.get('rank_num')}；热度/排序值：{hotspot.get('hot_value')}",
            f"材料数量：主体材料{len(posts)}条，评论{len(comments)}条",
        ]

        section_len = sum(len(line) for line in section_lines)

        for post_index, post in enumerate(posts, start=1):
            post_time = format_material_time(post.get("publish_time") or post.get("crawl_time") or post.get("created_at"))
            author = clean_material_text(post.get("author_name") or "未知用户", 20)
            post_title = clean_material_text(post.get("title") or "", 50)
            content = clean_material_text(post.get("content") or "", 150)
            like_count = post.get("like_count") or 0
            comment_count = post.get("comment_count") or 0
            repost_count = post.get("repost_count") or 0

            if platform == "bilibili":
                line = (
                    f"[{label}-P{post_index}][{post_time}][{author}] "
                    f"相关视频：{post_title} {content}"
                    f"（点赞{like_count}，评论{comment_count}）"
                )
            elif platform == "douyin":
                line = (
                    f"[{label}-P{post_index}][{post_time}][{author}] "
                    f"相关视频：{post_title} {content}"
                    f"（点赞{like_count}，评论{comment_count}，转发{repost_count}）"
                )
            else:
                line = (
                    f"[{label}-P{post_index}][{post_time}][{author}] "
                    f"相关微博内容：{post_title} {content}"
                    f"（点赞{like_count}，评论{comment_count}，转发{repost_count}）"
                )

            if section_len + len(line) <= CROSS_PLATFORM_PER_PLATFORM_MAX_CHARS:
                section_lines.append(line)
                section_len += len(line)

        for comment_index, comment in enumerate(comments, start=1):
            comment_time = format_material_time(comment.get("publish_time") or comment.get("crawl_time") or comment.get("created_at"))
            author = clean_material_text(comment.get("author_name") or "用户", 20)
            content = clean_material_text(comment.get("content") or "", 80)
            like_count = comment.get("like_count") or 0
            reply_count = comment.get("reply_count") or 0

            line = (
                f"[{label}-C{comment_index}][{comment_time}][{author}] "
                f"评论：{content}（点赞{like_count}，回复{reply_count}）"
            )

            if section_len + len(line) <= CROSS_PLATFORM_PER_PLATFORM_MAX_CHARS:
                section_lines.append(line)
                section_len += len(line)

        section_text = "\n".join(section_lines)

        if total_len + len(section_text) <= CROSS_PLATFORM_MATERIAL_MAX_CHARS:
            material_sections.append(section_text)
            total_len += len(section_text)

    materials_text = "\n\n".join(material_sections) if material_sections else "暂无可用跨平台材料。"

    prompt_input = f"""<cross_platform_materials>
{materials_text}
</cross_platform_materials>

请基于以上跨平台材料写综合简介。材料编号只用于你理解来源，不要在最终输出中机械罗列编号。"""

    return {
        "prompt_input": prompt_input,
        "post_count": total_posts,
        "comment_count": total_comments,
        "total_count": total_posts + total_comments,
        "platform": "cross_platform",
        "platform_label": "跨平台",
        "platforms": sorted(set(platforms)),
        "has_materials": bool(material_sections),
    }


def ensure_sentence_punctuation(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text

    if text[-1] not in "。！？；.!?;":
        text += "。"

    return text


def normalize_paragraph_format(paragraphs: List[str]) -> str:
    formatted = []

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        paragraph = paragraph.lstrip(" 　\t")
        paragraph = ensure_sentence_punctuation(paragraph)
        formatted.append("　　" + paragraph)

    return "\n".join(formatted).strip()


def build_fallback_summary(title: str, platform: str = "weibo", has_materials: bool = False) -> str:
    label = platform_label(platform)

    if has_materials:
        paragraphs = [
            f"{title}正在{label}平台受到关注，系统已经采集到部分相关内容和评论",
            "不过当前模型暂时没有完成更细致的归纳，用户可以先结合热度趋势和来源链接继续了解这个话题",
        ]
    else:
        paragraphs = [
            f"{title}正在{label}平台受到关注",
            "系统目前还没有采集到足够的相关内容，暂时只能根据标题和热度变化进行基础展示。后续材料补充后，简介可以继续完善",
        ]

    return normalize_paragraph_format(paragraphs)


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

    heading_patterns = [
        r"^热点概述[:：]\s*",
        r"^热点简介[:：]\s*",
        r"^讨论焦点[:：]\s*",
        r"^舆情倾向[:：]\s*",
        r"^代表观点[:：]\s*",
        r"^总结[:：]\s*",
        r"^跨平台观察[:：]\s*",
        r"^跨平台分析[:：]\s*",
    ]

    cleaned_parts = []
    for part in re.split(r"\n+", text):
        part = part.strip(" ：:；;，,。\t ")

        for pattern in heading_patterns:
            part = re.sub(pattern, "", part).strip()

        if part:
            cleaned_parts.append(part)

    normalized_parts = []
    for part in cleaned_parts:
        part = re.sub(r"[ \t]+", " ", part)
        part = part.replace("。。", "。").replace("，，", "，")
        part = part.replace("，。", "。").replace("；。", "。")
        part = part.strip()
        if part:
            normalized_parts.append(part)

    post_count = int(material_meta.get("post_count", 0) or 0)
    comment_count = int(material_meta.get("comment_count", 0) or 0)

    very_limited_material = post_count <= 1 and comment_count < 3
    already_has_limit_note = any(
        phrase in " ".join(normalized_parts)
        for phrase in [
            "材料还不多",
            "信息还不多",
            "可参考的内容还比较少",
            "后续材料",
            "后续内容",
        ]
    )

    if very_limited_material and not already_has_limit_note:
        normalized_parts.append("目前可参考的材料还不多，后续如果采集到更多相关内容，简介还可以继续补充")

    return normalize_paragraph_format(normalized_parts)


def fetch_hotspot_context(cursor: Cursor, hotspot_id: int) -> Dict[str, Any]:
    sql = """
        SELECT id, platform, title, rank_num, hot_value, tags, is_special, source_url, crawl_time
        FROM hotspot
        WHERE id = %s
        LIMIT 1
    """
    cursor.execute(sql, (hotspot_id,))
    return cursor.fetchone() or {}


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
        if platform == "bilibili":
            parts.append(f"排序值：{hot_value}")
        else:
            parts.append(f"热度：{hot_value}")

    if tags:
        parts.append(f"标签：{tags}")

    if source_url:
        parts.append(f"来源链接：{source_url}")

    if is_special:
        parts.append("该话题属于置顶/特殊展示项")

    return "；".join(parts)


def call_model_for_summary(
    client: ZhipuAI,
    prompt: str,
    safe_mode: bool = False,
    cross_platform_mode: bool = False,
) -> str:
    if safe_mode and cross_platform_mode:
        system_content = (
            "你是一个非常克制的跨平台热点详情页文案编辑。"
            "只做客观介绍，不复述敏感评论，不输出攻击性内容，不夸大平台差异。"
        )
        temperature = 0.2
    elif safe_mode:
        system_content = (
            "你是一个非常克制的热点详情页文案编辑。"
            "只做客观介绍，不复述敏感评论，不输出攻击性内容，不夸大结论。"
        )
        temperature = 0.2
    elif cross_platform_mode:
        system_content = (
            "你是一个克制、自然的跨平台热点详情页文案编辑。"
            "只能基于用户提供的多平台材料写前端可读的自然段简介，"
            "要比较平台讨论差异，但不要夸大结论。"
        )
        temperature = 0.35
    else:
        system_content = (
            "你是一个克制、自然的热点详情页文案编辑，"
            "只能基于用户提供的材料写前端可读的自然段简介，不写报告，不夸大结论。"
        )
        temperature = 0.35

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": system_content,
            },
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )

    return response.choices[0].message.content.strip()


def generate_single_platform_summary(
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
        raw_summary = call_model_for_summary(
            client=client,
            prompt=prompt,
            safe_mode=False,
            cross_platform_mode=False,
        )
        return validate_and_fix_summary(raw_summary, title, material_meta)

    except Exception as e:
        if is_content_filter_error(e):
            print(f"AI 内容安全拦截，尝试清洗材料并进行保守重试：{e}")

            try:
                safe_material_data = sanitize_material_data_for_retry(material_data)
                safe_material_meta = build_material_input(title, platform, safe_material_data)

                safe_prompt = f"""{PROMPT_SAFE_RETRY}

热点基础信息：
{context_text}

{safe_material_meta['prompt_input']}"""

                raw_summary = call_model_for_summary(
                    client=client,
                    prompt=safe_prompt,
                    safe_mode=True,
                    cross_platform_mode=False,
                )
                print("AI 保守重试成功")
                return validate_and_fix_summary(raw_summary, title, safe_material_meta)

            except Exception as retry_error:
                print(f"AI 保守重试仍失败，使用兜底简介：{retry_error}")
                return build_fallback_summary(
                    title,
                    platform=platform,
                    has_materials=material_meta.get("has_materials", False),
                )

        print(f"AI 模型调用失败，使用兜底简介：{e}")
        return build_fallback_summary(
            title,
            platform=platform,
            has_materials=material_meta.get("has_materials", False),
        )


def generate_cross_platform_summary(
    client: ZhipuAI,
    title: str,
    cross_result: Dict[str, Any],
) -> str:
    current = cross_result.get("current") or {}
    current_platform = current.get("platform") or "weibo"

    context_text = build_cross_platform_context_text(cross_result)
    material_meta = build_cross_platform_material_input(cross_result)

    prompt = f"""{PROMPT_CROSS_PLATFORM}

跨平台热点基础信息：
{context_text}

{material_meta['prompt_input']}"""

    try:
        raw_summary = call_model_for_summary(
            client=client,
            prompt=prompt,
            safe_mode=False,
            cross_platform_mode=True,
        )
        return validate_and_fix_summary(raw_summary, title, material_meta)

    except Exception as e:
        if is_content_filter_error(e):
            print(f"AI 跨平台内容安全拦截，尝试清洗跨平台材料并进行保守重试：{e}")

            try:
                safe_cross_result = sanitize_cross_platform_result_for_retry(cross_result)
                safe_context_text = build_cross_platform_context_text(safe_cross_result)
                safe_material_meta = build_cross_platform_material_input(safe_cross_result)

                safe_prompt = f"""{PROMPT_CROSS_PLATFORM_SAFE_RETRY}

跨平台热点基础信息：
{safe_context_text}

{safe_material_meta['prompt_input']}"""

                raw_summary = call_model_for_summary(
                    client=client,
                    prompt=safe_prompt,
                    safe_mode=True,
                    cross_platform_mode=True,
                )
                print("AI 跨平台保守重试成功")
                return validate_and_fix_summary(raw_summary, title, safe_material_meta)

            except Exception as retry_error:
                print(f"AI 跨平台保守重试仍失败，使用兜底简介：{retry_error}")
                return build_fallback_summary(
                    title,
                    platform=current_platform,
                    has_materials=material_meta.get("has_materials", False),
                )

        print(f"AI 跨平台模型调用失败，使用兜底简介：{e}")
        return build_fallback_summary(
            title,
            platform=current_platform,
            has_materials=material_meta.get("has_materials", False),
        )


def should_wait_for_cross_platform_materials(cross_result: Dict[str, Any]) -> bool:
    matches = cross_result.get("matches") or []
    if not matches:
        return False

    material_check = cross_result.get("material_check") or {}
    analysis_mode = material_check.get("analysis_mode")

    if analysis_mode == "cross_platform_ready":
        material_bundle = cross_result.get("material_bundle") or {}
        platform_count = int(material_bundle.get("platform_count") or 0)
        return platform_count < 2

    return WAIT_CROSS_PLATFORM_MATERIALS_READY


def try_get_cross_platform_result(hotspot_id: int) -> Optional[Dict[str, Any]]:
    if not ENABLE_CROSS_PLATFORM_ANALYSIS:
        return None

    if analyze_cross_platform_status is None:
        print(f"跨平台匹配模块不可用，跳过跨平台分析：{CROSS_PLATFORM_IMPORT_ERROR}")
        return None

    try:
        return analyze_cross_platform_status(
            hotspot_id=hotspot_id,
            auto_enqueue_missing_materials=True,
        )
    except Exception as e:
        print(f"跨平台匹配失败，回退单平台简介：hotspot_id={hotspot_id}，原因：{e}")
        return None


def collect_cross_platform_hotspots(cross_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    all_hotspots = cross_result.get("all_hotspots") or []
    result = []
    seen = set()

    for item in all_hotspots:
        hotspot_id = item.get("id")
        if not hotspot_id or hotspot_id in seen:
            continue

        result.append(item)
        seen.add(hotspot_id)

    return result


def build_cross_platform_related_info(cross_result: Dict[str, Any]) -> Dict[str, str]:
    group_hotspots = collect_cross_platform_hotspots(cross_result)

    hotspot_ids = []
    platforms = []

    for hotspot in group_hotspots:
        hotspot_id = hotspot.get("id")
        platform = hotspot.get("platform")

        if hotspot_id:
            hotspot_ids.append(str(hotspot_id))

        if platform and platform not in platforms:
            platforms.append(platform)

    return {
        "related_hotspot_ids": ",".join(hotspot_ids),
        "related_platforms": ",".join(platforms),
    }


def upsert_ai_summary(
    cursor: Cursor,
    task: Dict[str, Any],
    summary: str,
    now: datetime,
    analysis_type: str = "single_platform",
    related_hotspot_ids: Optional[str] = None,
    related_platforms: Optional[str] = None,
) -> None:
    sql = """
        INSERT INTO hotspot_ai_summary (
            hotspot_id,
            platform,
            title,
            summary,
            analysis_type,
            related_hotspot_ids,
            related_platforms,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            platform = VALUES(platform),
            title = VALUES(title),
            summary = VALUES(summary),
            analysis_type = VALUES(analysis_type),
            related_hotspot_ids = VALUES(related_hotspot_ids),
            related_platforms = VALUES(related_platforms)
    """
    cursor.execute(sql, (
        task.get("hotspot_id"),
        task.get("platform"),
        task.get("title"),
        summary,
        analysis_type,
        related_hotspot_ids,
        related_platforms,
        now,
    ))


def upsert_ai_summary_for_hotspot(
    cursor: Cursor,
    hotspot: Dict[str, Any],
    summary: str,
    now: datetime,
    analysis_type: str = "single_platform",
    related_hotspot_ids: Optional[str] = None,
    related_platforms: Optional[str] = None,
) -> None:
    sql = """
        INSERT INTO hotspot_ai_summary (
            hotspot_id,
            platform,
            title,
            summary,
            analysis_type,
            related_hotspot_ids,
            related_platforms,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            platform = VALUES(platform),
            title = VALUES(title),
            summary = VALUES(summary),
            analysis_type = VALUES(analysis_type),
            related_hotspot_ids = VALUES(related_hotspot_ids),
            related_platforms = VALUES(related_platforms)
    """
    cursor.execute(sql, (
        hotspot.get("id"),
        hotspot.get("platform"),
        hotspot.get("title"),
        summary,
        analysis_type,
        related_hotspot_ids,
        related_platforms,
        now,
    ))


def upsert_cross_platform_summary_for_group(
    cursor: Cursor,
    cross_result: Dict[str, Any],
    summary: str,
    now: datetime,
) -> List[int]:
    group_hotspots = collect_cross_platform_hotspots(cross_result)
    related_info = build_cross_platform_related_info(cross_result)

    related_hotspot_ids = related_info.get("related_hotspot_ids")
    related_platforms = related_info.get("related_platforms")

    written_ids: List[int] = []

    for hotspot in group_hotspots:
        hotspot_id = hotspot.get("id")
        if not hotspot_id:
            continue

        upsert_ai_summary_for_hotspot(
            cursor=cursor,
            hotspot=hotspot,
            summary=summary,
            now=now,
            analysis_type="cross_platform",
            related_hotspot_ids=related_hotspot_ids,
            related_platforms=related_platforms,
        )
        written_ids.append(int(hotspot_id))

    return written_ids


def mark_ai_tasks_done_for_hotspots(cursor: Cursor, hotspot_ids: List[int]) -> None:
    if not hotspot_ids:
        return

    placeholders = ",".join(["%s"] * len(hotspot_ids))
    sql = f"""
        UPDATE hotspot_ai_summary_task
        SET status = 'done',
            error_message = NULL,
            updated_at = %s
        WHERE hotspot_id IN ({placeholders})
    """
    cursor.execute(sql, [datetime.now()] + hotspot_ids)


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


def run_ai_summary_worker(limit: int = 3) -> int:
    client = get_ai_client()
    if client is None:
        return 0

    conn = get_connection()
    generated_count = 0
    skipped_for_cross_materials = 0
    processed_hotspot_ids = set()

    try:
        with conn.cursor() as cursor:
            fetch_limit = max(limit * 3, limit)
            tasks = fetch_pending_tasks(cursor, fetch_limit)
            waiting_count = count_waiting_material_tasks(cursor)

            if not tasks:
                if waiting_count > 0:
                    print(f"暂无可生成的 AI 简介任务；仍有 {waiting_count} 条 pending 任务在等待材料抓取")
                else:
                    print("暂无待生成的 AI 简介任务")
                return 0

            print(
                f"发现可生成 AI 简介候选任务：{len(tasks)} 条；"
                f"本轮最多生成 {limit} 条；等待材料任务：{waiting_count} 条"
            )

            for task in tasks:
                if generated_count >= limit:
                    break

                task_id = task.get("id")
                hotspot_id = task.get("hotspot_id")
                title = task.get("title") or "该话题"

                if hotspot_id in processed_hotspot_ids:
                    print(f"hotspot_id={hotspot_id} 已被同组跨平台简介处理，本轮跳过")
                    continue

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

                    cross_result = try_get_cross_platform_result(hotspot_id)

                    if cross_result:
                        material_check = cross_result.get("material_check") or {}
                        analysis_mode = material_check.get("analysis_mode")
                        matches = cross_result.get("matches") or []
                        ready_platforms = material_check.get("ready_platforms") or []
                        related_platforms = material_check.get("related_platforms") or []

                        if matches and should_wait_for_cross_platform_materials(cross_result):
                            skipped_for_cross_materials += 1
                            print(
                                f"hotspot_id={hotspot_id} 匹配到多平台热点，但材料尚未齐全，"
                                f"本轮暂不生成简介，任务保持 pending。"
                                f"analysis_mode={analysis_mode}，"
                                f"关联平台={','.join(platform_label(p) for p in related_platforms)}，"
                                f"已有材料平台={','.join(platform_label(p) for p in ready_platforms)}"
                            )
                            continue

                        if matches and analysis_mode == "cross_platform_ready":
                            material_bundle = cross_result.get("material_bundle") or {}
                            platform_count = int(material_bundle.get("platform_count") or 0)

                            if platform_count >= 2:
                                print(
                                    f"hotspot_id={hotspot_id} 匹配到多平台热点且材料已齐，"
                                    f"开始生成跨平台综合简介。"
                                    f"平台数={platform_count}，"
                                    f"关联平台={','.join(platform_label(p) for p in related_platforms)}"
                                )

                                summary = generate_cross_platform_summary(
                                    client=client,
                                    title=title,
                                    cross_result=cross_result,
                                )

                                now = datetime.now()
                                written_ids = upsert_cross_platform_summary_for_group(
                                    cursor=cursor,
                                    cross_result=cross_result,
                                    summary=summary,
                                    now=now,
                                )
                                mark_ai_tasks_done_for_hotspots(cursor, written_ids)

                                for written_id in written_ids:
                                    processed_hotspot_ids.add(written_id)

                                generated_count += len(written_ids)
                                conn.commit()

                                print(
                                    f"跨平台简介已写入同组热点：{written_ids}，"
                                    f"并已将这些热点已有 AI 任务标记为 done"
                                )
                                continue

                            print(
                                f"hotspot_id={hotspot_id} 匹配结果不足以做跨平台分析，"
                                f"回退单平台简介。platform_count={platform_count}"
                            )
                            summary = generate_single_platform_summary(
                                client,
                                title,
                                hotspot_context,
                                material_data,
                            )
                        else:
                            print(
                                f"hotspot_id={hotspot_id} 未匹配到其它平台相似热点，"
                                f"按单平台生成简介"
                            )
                            summary = generate_single_platform_summary(
                                client,
                                title,
                                hotspot_context,
                                material_data,
                            )
                    else:
                        print(
                            f"hotspot_id={hotspot_id}（{platform_label(platform)}）读取到主体材料 {post_count} 条、"
                            f"评论 {comment_count} 条，共 {total_count} 条材料，开始生成单平台详情页自然简介"
                        )
                        summary = generate_single_platform_summary(
                            client,
                            title,
                            hotspot_context,
                            material_data,
                        )

                    upsert_ai_summary(
                        cursor=cursor,
                        task=task,
                        summary=summary,
                        now=datetime.now(),
                        analysis_type="single_platform",
                        related_hotspot_ids=None,
                        related_platforms=None,
                    )
                    generated_count += 1
                    processed_hotspot_ids.add(int(hotspot_id))

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

        print(
            f"AI 简介生成完成：写入/更新 {generated_count} 条；"
            f"因等待跨平台材料跳过 {skipped_for_cross_materials} 条"
        )
        return generated_count

    finally:
        conn.close()


if __name__ == "__main__":
    run_ai_summary_worker(limit=5)