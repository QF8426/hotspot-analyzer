import re
import sys
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import Cursor

from db_config import DB_CONFIG


# 匹配时间窗口：只在最近 24 小时热点里找相似项
DEFAULT_LOOKBACK_HOURS = 24

# 每个平台最多保留 1 个最相似热点
MAX_MATCHES_PER_PLATFORM = 1

# 标题相似度阈值。第一版先保守一点，避免误匹配太多
DEFAULT_SIMILARITY_THRESHOLD = 0.46

# 共同字符覆盖率阈值。用于辅助避免两个标题只是短词碰巧相似
DEFAULT_COMMON_CHAR_THRESHOLD = 0.35

SUPPORTED_PLATFORMS = ("weibo", "douyin", "bilibili")

PLATFORM_LABELS = {
    "weibo": "微博",
    "douyin": "抖音",
    "bilibili": "B站",
}

# 各平台材料任务的 pending / processing 状态不同
MATERIAL_PENDING_STATUS_BY_PLATFORM = {
    "weibo": "pending",
    "douyin": "pending_douyin",
    "bilibili": "pending_bilibili",
}

MATERIAL_PROCESSING_STATUS_BY_PLATFORM = {
    "weibo": "processing",
    "douyin": "processing_douyin",
    "bilibili": "processing_bilibili",
}

ACTIVE_MATERIAL_TASK_STATUSES = {
    "pending",
    "pending_douyin",
    "pending_bilibili",
    "processing",
    "processing_douyin",
    "processing_bilibili",
}

DONE_STATUS = "done"
FAILED_STATUS = "failed"


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


def platform_label(platform: str) -> str:
    return PLATFORM_LABELS.get(platform or "", platform or "未知平台")


def normalize_title(title: str) -> str:
    """
    标题归一化：
    - 去掉首尾 #；
    - 去掉常见标点；
    - 去掉空格；
    - 去掉部分平台提示词；
    - 英文统一小写。
    """
    text = str(title or "").strip().lower()

    if text.startswith("#") and text.endswith("#") and len(text) > 2:
        text = text[1:-1]

    remove_words = [
        "微博",
        "抖音",
        "b站",
        "bilibili",
        "热搜",
        "热榜",
        "热门",
        "回应",
        "最新",
    ]

    for word in remove_words:
        text = text.replace(word, "")

    text = re.sub(r"[#【】\[\]（）()《》<>“”\"'‘’：:，,。.!！?？、/\\|_\-—+*=~`·\s]", "", text)

    return text.strip()


def char_set(text: str) -> set:
    """
    中文标题第一版先按字符集合计算重合度。
    这比直接分词简单，也不需要额外依赖。
    """
    return set(normalize_title(text))


def common_char_score(title_a: str, title_b: str) -> float:
    a = char_set(title_a)
    b = char_set(title_b)

    if not a or not b:
        return 0.0

    return len(a & b) / max(1, min(len(a), len(b)))


def sequence_similarity(title_a: str, title_b: str) -> float:
    a = normalize_title(title_a)
    b = normalize_title(title_b)

    if not a or not b:
        return 0.0

    # 包含关系：比如“4只皮皮虾1035元”和“4只皮皮虾1035元涉事海鲜店回应”
    # 这种应当认为比较相近。
    if a in b or b in a:
        shorter = min(len(a), len(b))
        longer = max(len(a), len(b))
        contain_score = shorter / max(1, longer)
        return max(0.72, contain_score)

    return SequenceMatcher(None, a, b).ratio()


def calc_title_similarity(title_a: str, title_b: str) -> float:
    """
    综合相似度：
    - SequenceMatcher 负责整体序列相似；
    - common_char_score 负责共同字符覆盖；
    - 取加权分数。
    """
    seq_score = sequence_similarity(title_a, title_b)
    common_score = common_char_score(title_a, title_b)

    return round(seq_score * 0.75 + common_score * 0.25, 4)


def is_possible_same_hotspot(
    title_a: str,
    title_b: str,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    common_char_threshold: float = DEFAULT_COMMON_CHAR_THRESHOLD,
) -> Tuple[bool, float, float]:
    similarity = calc_title_similarity(title_a, title_b)
    common_score = common_char_score(title_a, title_b)

    normalized_a = normalize_title(title_a)
    normalized_b = normalize_title(title_b)

    if not normalized_a or not normalized_b:
        return False, similarity, common_score

    # 短标题要求更严格，防止误匹配。
    min_len = min(len(normalized_a), len(normalized_b))
    if min_len <= 6:
        return similarity >= 0.62 and common_score >= 0.50, similarity, common_score

    return (
        similarity >= similarity_threshold and common_score >= common_char_threshold,
        similarity,
        common_score,
    )


def fetch_hotspot_by_id(cursor: Cursor, hotspot_id: int) -> Optional[Dict[str, Any]]:
    sql = """
        SELECT id, platform, title, rank_num, hot_value, tags, is_special, source_url, crawl_time
        FROM hotspot
        WHERE id = %s
        LIMIT 1
    """
    cursor.execute(sql, (hotspot_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def fetch_recent_candidate_hotspots(
    cursor: Cursor,
    current_hotspot: Dict[str, Any],
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
) -> List[Dict[str, Any]]:
    """
    查询最近一段时间内其它平台的候选热点。
    """
    current_id = current_hotspot.get("id")
    current_platform = current_hotspot.get("platform")

    now = datetime.now()
    start_time = now - timedelta(hours=lookback_hours)

    sql = """
        SELECT id, platform, title, rank_num, hot_value, tags, is_special, source_url, crawl_time
        FROM hotspot
        WHERE id <> %s
          AND platform <> %s
          AND platform IN ('weibo', 'douyin', 'bilibili')
          AND crawl_time >= %s
          AND title IS NOT NULL
          AND title <> ''
        ORDER BY crawl_time DESC, rank_num ASC
        LIMIT 500
    """
    cursor.execute(sql, (current_id, current_platform, start_time))
    return list(cursor.fetchall())


def find_related_hotspots(
    cursor: Cursor,
    hotspot_id: int,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> Dict[str, Any]:
    """
    查找与当前热点可能属于同一事件的其它平台热点。

    返回：
    {
        "current": 当前热点,
        "matches": [匹配热点...],
        "all_hotspots": [当前热点 + 匹配热点...],
        "platform_count": 平台数量
    }
    """
    current = fetch_hotspot_by_id(cursor, hotspot_id)
    if not current:
        raise RuntimeError(f"hotspot_id={hotspot_id} 不存在")

    candidates = fetch_recent_candidate_hotspots(cursor, current, lookback_hours=lookback_hours)

    matched_by_platform: Dict[str, Dict[str, Any]] = {}
    current_title = current.get("title") or ""

    for candidate in candidates:
        candidate_platform = candidate.get("platform")
        candidate_title = candidate.get("title") or ""

        matched, similarity, common_score = is_possible_same_hotspot(
            current_title,
            candidate_title,
            similarity_threshold=similarity_threshold,
        )

        if not matched:
            continue

        candidate = dict(candidate)
        candidate["similarity_score"] = similarity
        candidate["common_char_score"] = round(common_score, 4)

        old = matched_by_platform.get(candidate_platform)
        if old is None:
            matched_by_platform[candidate_platform] = candidate
            continue

        # 同平台只保留最相似的一个；相似度相同则优先排名更靠前。
        old_score = float(old.get("similarity_score") or 0)
        new_score = float(candidate.get("similarity_score") or 0)

        old_rank = old.get("rank_num") if old.get("rank_num") is not None else 9999
        new_rank = candidate.get("rank_num") if candidate.get("rank_num") is not None else 9999

        if new_score > old_score or (new_score == old_score and new_rank < old_rank):
            matched_by_platform[candidate_platform] = candidate

    matches = sorted(
        matched_by_platform.values(),
        key=lambda item: (
            -float(item.get("similarity_score") or 0),
            item.get("rank_num") if item.get("rank_num") is not None else 9999,
        ),
    )

    all_hotspots = [current] + matches
    platform_count = len({item.get("platform") for item in all_hotspots if item.get("platform")})

    return {
        "current": current,
        "matches": matches,
        "all_hotspots": all_hotspots,
        "platform_count": platform_count,
        "lookback_hours": lookback_hours,
        "similarity_threshold": similarity_threshold,
    }


def count_material_posts(cursor: Cursor, hotspot_id: int) -> int:
    sql = """
        SELECT COUNT(*) AS count
        FROM hotspot_material_post
        WHERE hotspot_id = %s
          AND content IS NOT NULL
          AND content <> ''
    """
    cursor.execute(sql, (hotspot_id,))
    row = cursor.fetchone() or {}
    return int(row.get("count") or 0)


def count_material_comments(cursor: Cursor, hotspot_id: int) -> int:
    sql = """
        SELECT COUNT(*) AS count
        FROM hotspot_material_comment
        WHERE hotspot_id = %s
          AND content IS NOT NULL
          AND content <> ''
    """
    cursor.execute(sql, (hotspot_id,))
    row = cursor.fetchone() or {}
    return int(row.get("count") or 0)


def fetch_material_task(cursor: Cursor, hotspot_id: int) -> Optional[Dict[str, Any]]:
    sql = """
        SELECT id, hotspot_id, platform, title, status, error_message, created_at, updated_at
        FROM hotspot_material_task
        WHERE hotspot_id = %s
        LIMIT 1
    """
    cursor.execute(sql, (hotspot_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def expected_pending_status(platform: str) -> str:
    return MATERIAL_PENDING_STATUS_BY_PLATFORM.get(platform, "pending")


def expected_processing_status(platform: str) -> str:
    return MATERIAL_PROCESSING_STATUS_BY_PLATFORM.get(platform, "processing")


def upsert_material_task_if_needed(
    cursor: Cursor,
    hotspot: Dict[str, Any],
    force_reset_failed: bool = True,
) -> str:
    """
    如果某个热点没有主体材料，则创建或重置材料任务。

    返回状态说明：
    - ready：已经有主体材料
    - active：已有 pending / processing 任务
    - enqueued：本次新建或重置任务
    """
    hotspot_id = int(hotspot.get("id"))
    platform = hotspot.get("platform")
    title = hotspot.get("title") or ""

    post_count = count_material_posts(cursor, hotspot_id)
    if post_count > 0:
        return "ready"

    task = fetch_material_task(cursor, hotspot_id)
    pending_status = expected_pending_status(platform)

    if task:
        status = task.get("status")

        if status in ACTIVE_MATERIAL_TASK_STATUSES:
            return "active"

        if status == FAILED_STATUS and not force_reset_failed:
            return "failed"

    sql = """
        INSERT INTO hotspot_material_task (
            hotspot_id, platform, title, status, error_message, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, NULL, NOW(), NOW())
        ON DUPLICATE KEY UPDATE
            platform = VALUES(platform),
            title = VALUES(title),
            status = VALUES(status),
            error_message = NULL,
            updated_at = NOW()
    """
    cursor.execute(sql, (hotspot_id, platform, title, pending_status))
    return "enqueued"


def inspect_material_status(cursor: Cursor, hotspot: Dict[str, Any]) -> Dict[str, Any]:
    hotspot_id = int(hotspot.get("id"))
    platform = hotspot.get("platform")

    post_count = count_material_posts(cursor, hotspot_id)
    comment_count = count_material_comments(cursor, hotspot_id)
    task = fetch_material_task(cursor, hotspot_id)

    if post_count > 0:
        material_state = "ready"
    elif task and task.get("status") in ACTIVE_MATERIAL_TASK_STATUSES:
        material_state = "waiting"
    elif task and task.get("status") == FAILED_STATUS:
        material_state = "failed"
    else:
        material_state = "missing"

    return {
        "hotspot_id": hotspot_id,
        "platform": platform,
        "platform_label": platform_label(platform),
        "title": hotspot.get("title"),
        "post_count": post_count,
        "comment_count": comment_count,
        "task_status": task.get("status") if task else None,
        "material_state": material_state,
    }


def ensure_related_material_tasks(
    cursor: Cursor,
    related_result: Dict[str, Any],
    force_reset_failed: bool = True,
) -> Dict[str, Any]:
    """
    对当前热点和匹配热点检查材料状态。
    缺材料时自动创建/重置材料任务。
    """
    all_hotspots = related_result.get("all_hotspots") or []

    actions = []
    statuses = []

    for hotspot in all_hotspots:
        before = inspect_material_status(cursor, hotspot)
        action = upsert_material_task_if_needed(
            cursor,
            hotspot,
            force_reset_failed=force_reset_failed,
        )
        after = inspect_material_status(cursor, hotspot)

        actions.append({
            "hotspot_id": hotspot.get("id"),
            "platform": hotspot.get("platform"),
            "title": hotspot.get("title"),
            "action": action,
            "before_state": before.get("material_state"),
            "after_state": after.get("material_state"),
            "task_status": after.get("task_status"),
        })
        statuses.append(after)

    ready_platforms = sorted({
        item.get("platform")
        for item in statuses
        if item.get("material_state") == "ready"
    })

    related_platforms = sorted({
        item.get("platform")
        for item in statuses
        if item.get("platform")
    })

    missing_or_waiting = [
        item for item in statuses
        if item.get("material_state") != "ready"
    ]

    if len(related_platforms) <= 1:
        analysis_mode = "single_platform"
    elif len(ready_platforms) >= 2 and not missing_or_waiting:
        analysis_mode = "cross_platform_ready"
    elif len(ready_platforms) >= 2 and missing_or_waiting:
        analysis_mode = "cross_platform_partial"
    elif len(ready_platforms) == 1:
        analysis_mode = "single_platform_waiting_cross"
    else:
        analysis_mode = "waiting_materials"

    return {
        "analysis_mode": analysis_mode,
        "related_platforms": related_platforms,
        "ready_platforms": ready_platforms,
        "missing_or_waiting": missing_or_waiting,
        "statuses": statuses,
        "actions": actions,
    }


def fetch_materials_for_hotspot(
    cursor: Cursor,
    hotspot_id: int,
    post_limit: int = 3,
    comments_per_post: int = 5,
) -> Dict[str, Any]:
    """
    读取某个热点已有材料。
    这个函数给后续 ai_summary_worker 做跨平台综合 prompt 用。
    """
    post_sql = """
        SELECT id, title, content, author_name, like_count, comment_count, repost_count,
               source_url, publish_time, crawl_time, created_at
        FROM hotspot_material_post
        WHERE hotspot_id = %s
          AND content IS NOT NULL
          AND content <> ''
        ORDER BY like_count DESC, comment_count DESC, created_at DESC
        LIMIT %s
    """
    cursor.execute(post_sql, (hotspot_id, post_limit))
    posts = list(cursor.fetchall())

    comments: List[Dict[str, Any]] = []

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
        comments.extend(list(cursor.fetchall()))

    return {
        "posts": posts,
        "comments": comments,
    }


def build_cross_platform_material_bundle(
    cursor: Cursor,
    related_result: Dict[str, Any],
    post_limit: int = 3,
    comments_per_post: int = 5,
) -> Dict[str, Any]:
    """
    为后续 AI 综合分析准备跨平台材料包。
    只读取已经有主体材料的平台。
    """
    all_hotspots = related_result.get("all_hotspots") or []
    platform_items = []

    for hotspot in all_hotspots:
        hotspot_id = int(hotspot.get("id"))
        post_count = count_material_posts(cursor, hotspot_id)

        if post_count <= 0:
            continue

        material_data = fetch_materials_for_hotspot(
            cursor,
            hotspot_id=hotspot_id,
            post_limit=post_limit,
            comments_per_post=comments_per_post,
        )

        platform_items.append({
            "hotspot": hotspot,
            "platform": hotspot.get("platform"),
            "platform_label": platform_label(hotspot.get("platform")),
            "materials": material_data,
            "post_count": len(material_data.get("posts") or []),
            "comment_count": len(material_data.get("comments") or []),
        })

    return {
        "platform_items": platform_items,
        "platform_count": len({item.get("platform") for item in platform_items}),
    }


def analyze_cross_platform_status(
    hotspot_id: int,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    auto_enqueue_missing_materials: bool = True,
) -> Dict[str, Any]:
    """
    外部主入口。

    用法：
    result = analyze_cross_platform_status(1951)

    返回结果里包含：
    - current：当前热点
    - matches：其它平台相似热点
    - material_check：材料状态与补任务结果
    - material_bundle：已有材料的平台材料包
    """
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            related_result = find_related_hotspots(
                cursor,
                hotspot_id=hotspot_id,
                lookback_hours=lookback_hours,
                similarity_threshold=similarity_threshold,
            )

            if auto_enqueue_missing_materials:
                material_check = ensure_related_material_tasks(cursor, related_result)
                conn.commit()
            else:
                statuses = [
                    inspect_material_status(cursor, hotspot)
                    for hotspot in related_result.get("all_hotspots") or []
                ]
                material_check = {
                    "analysis_mode": "inspect_only",
                    "statuses": statuses,
                    "actions": [],
                    "related_platforms": sorted({item.get("platform") for item in statuses}),
                    "ready_platforms": sorted({
                        item.get("platform")
                        for item in statuses
                        if item.get("material_state") == "ready"
                    }),
                    "missing_or_waiting": [
                        item for item in statuses
                        if item.get("material_state") != "ready"
                    ],
                }

            material_bundle = build_cross_platform_material_bundle(cursor, related_result)

            return {
                "current": related_result.get("current"),
                "matches": related_result.get("matches"),
                "all_hotspots": related_result.get("all_hotspots"),
                "platform_count": related_result.get("platform_count"),
                "material_check": material_check,
                "material_bundle": material_bundle,
            }

    finally:
        conn.close()


def print_match_result(result: Dict[str, Any]) -> None:
    current = result.get("current") or {}
    matches = result.get("matches") or []
    material_check = result.get("material_check") or {}
    material_bundle = result.get("material_bundle") or {}

    print("=" * 70)
    print("跨平台热点匹配结果")
    print("=" * 70)

    print(
        f"当前热点：hotspot_id={current.get('id')}，"
        f"平台={platform_label(current.get('platform'))}，标题={current.get('title')}"
    )

    if not matches:
        print("未匹配到其它平台相似热点。")
    else:
        print(f"匹配到其它平台相似热点：{len(matches)} 条")
        for item in matches:
            print(
                f"- hotspot_id={item.get('id')}，平台={platform_label(item.get('platform'))}，"
                f"相似度={item.get('similarity_score')}，共同字符={item.get('common_char_score')}，"
                f"标题={item.get('title')}"
            )

    print("-" * 70)
    print(f"分析模式：{material_check.get('analysis_mode')}")
    print(f"关联平台：{', '.join(platform_label(p) for p in material_check.get('related_platforms') or [])}")
    print(f"已有材料平台：{', '.join(platform_label(p) for p in material_check.get('ready_platforms') or [])}")

    print("-" * 70)
    print("材料状态：")
    for status in material_check.get("statuses") or []:
        print(
            f"- hotspot_id={status.get('hotspot_id')}，平台={status.get('platform_label')}，"
            f"主体材料={status.get('post_count')}，评论={status.get('comment_count')}，"
            f"材料状态={status.get('material_state')}，任务状态={status.get('task_status')}"
        )

    print("-" * 70)
    print("本次动作：")
    for action in material_check.get("actions") or []:
        print(
            f"- hotspot_id={action.get('hotspot_id')}，平台={platform_label(action.get('platform'))}，"
            f"action={action.get('action')}，before={action.get('before_state')}，"
            f"after={action.get('after_state')}，task_status={action.get('task_status')}"
        )

    print("-" * 70)
    print(
        f"可用于 AI 的材料平台数：{material_bundle.get('platform_count')}，"
        f"平台项数量：{len(material_bundle.get('platform_items') or [])}"
    )
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        target_hotspot_id = int(sys.argv[1])
    else:
        target_hotspot_id = int(input("请输入要分析的 hotspot_id：").strip())

    result_data = analyze_cross_platform_status(
        hotspot_id=target_hotspot_id,
        lookback_hours=DEFAULT_LOOKBACK_HOURS,
        similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD,
        auto_enqueue_missing_materials=True,
    )

    print_match_result(result_data)