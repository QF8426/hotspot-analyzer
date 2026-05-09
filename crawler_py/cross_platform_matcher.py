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

# 单个热点详情页触发匹配时使用的标题相似度阈值
DEFAULT_SIMILARITY_THRESHOLD = 0.46

# 单个热点详情页触发匹配时使用的共同字符覆盖率阈值
DEFAULT_COMMON_CHAR_THRESHOLD = 0.35

# 主动扫描跨平台候选热点组时，阈值要更严格，避免把无关热点误分到一组
SCAN_SIMILARITY_THRESHOLD = 0.55
SCAN_COMMON_CHAR_THRESHOLD = 0.42

# 主动扫描时至少需要几个平台同时出现，默认 3 平台才自动入队
SCAN_MIN_PLATFORM_COUNT = 3

# 主动扫描每轮最多处理几组，避免任务暴涨
SCAN_MAX_GROUPS = 3

# 主动扫描时最多读取最近热点数量
SCAN_MAX_CANDIDATES = 800

# 主动扫描发现的跨平台组，AI 任务优先级
SCAN_AI_TASK_PRIORITY = 80

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

ACTIVE_AI_TASK_STATUSES = {
    "pending",
    "processing",
}

DONE_STATUS = "done"
FAILED_STATUS = "failed"


# =========================
# 事件一致性校验规则
# =========================

# 这些词很容易让两个标题看起来相似，但它们太泛，不能单独证明“同一事件”
WEAK_TOPIC_WORDS = [
    "世界杯",
    "转播权",
    "热搜",
    "热榜",
    "热门",
    "话题",
    "相关",
    "最新",
    "回应",
    "官方",
    "平台",
    "多个平台",
    "多平台",
    "2026",
    "2026年",
]

# 表示“已经拿到/已经确定”的动作
CONFIRMED_ACTION_WORDS = [
    "拿下",
    "获得",
    "拿到",
    "取得",
    "签约",
    "签下",
    "签订",
    "敲定",
    "确定",
    "确认",
    "官宣",
    "达成",
    "成交",
    "买下",
    "购买",
    "中标",
]

# 表示“没谈成/没确定/拒绝”的动作
UNRESOLVED_ACTION_WORDS = [
    "未谈拢",
    "仍未谈拢",
    "没谈拢",
    "尚未谈拢",
    "未签约",
    "仍未签约",
    "尚未签约",
    "未签",
    "没签",
    "谈崩",
    "拒绝",
    "拒购",
    "拒绝购买",
    "无缘",
    "未定",
    "尚未确定",
    "悬而未决",
    "陷入僵局",
    "僵局",
    "搁置",
    "流产",
]

# 一些相对具体的地域、组织、主体锚点。第一版不做复杂 NER，先用词典拦截明显误匹配
STRONG_ANCHOR_WORDS = [
    "香港",
    "澳门",
    "台湾",
    "中国香港",
    "中国澳门",
    "央视",
    "中央电视台",
    "央视频",
    "国际足联",
    "fifa",
    "中国",
    "印度",
    "美国",
    "墨西哥",
    "加拿大",
    "美加墨",
    "多国",
    "球迷",
    "英超",
    "欧冠",
    "世俱杯",
]

# 金额、人数、年份等数字锚点。数字不同不一定冲突，但如果动作也冲突，就更要拒绝
NUMBER_ANCHOR_PATTERN = re.compile(
    r"\d+(?:\.\d+)?(?:亿|万|万美元|亿元|人民币|元|人|万人|次|届|天|周|月|年)?"
)


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


def remove_weak_topic_words(title: str) -> str:
    """
    去掉过于泛化的主题词，用来判断两个标题是否只是在共享“大话题”，而不是同一事件。
    例如：
    - 世界杯转播权仍未谈拢 -> 仍未谈拢
    - 香港拿下世界杯转播权 -> 香港拿下
    """
    text = normalize_title(title)

    for word in WEAK_TOPIC_WORDS:
        text = text.replace(word.lower(), "")
        text = text.replace(word, "")

    return text.strip()


def extract_action_flags(title: str) -> Dict[str, bool]:
    """
    提取标题里的事件动作方向：
    - confirmed：已经拿下/已经确定
    - unresolved：未谈拢/拒绝/未签约/僵局
    """
    text = normalize_title(title)

    confirmed = any(word in text for word in CONFIRMED_ACTION_WORDS)
    unresolved = any(word in text for word in UNRESOLVED_ACTION_WORDS)

    return {
        "confirmed": confirmed,
        "unresolved": unresolved,
    }


def has_action_direction_conflict(title_a: str, title_b: str) -> bool:
    """
    判断事件动作是否冲突。
    例如：
    - 香港拿下世界杯转播权
    - 世界杯转播权仍未谈拢
    这两个共享“世界杯转播权”，但动作方向相反，不能合并。
    """
    flags_a = extract_action_flags(title_a)
    flags_b = extract_action_flags(title_b)

    return (
        (flags_a["confirmed"] and flags_b["unresolved"])
        or (flags_b["confirmed"] and flags_a["unresolved"])
    )


def extract_strong_anchors(title: str) -> set:
    """
    提取相对具体的锚点：
    - 地域：香港、澳门、印度等
    - 机构：央视、国际足联等
    - 数字金额：21亿、1.7亿、2.5-3亿美元等
    """
    text = normalize_title(title)
    anchors = set()

    for word in STRONG_ANCHOR_WORDS:
        if word.lower() in text or word in text:
            anchors.add(word)

    for match in NUMBER_ANCHOR_PATTERN.findall(str(title or "")):
        if match:
            anchors.add(match)

    return anchors


def meaningful_common_score(title_a: str, title_b: str) -> float:
    """
    去掉弱主题词后，再计算共同字符覆盖率。
    如果两个标题去掉“世界杯/转播权”后几乎没有共同内容，就不能轻易合并。
    """
    a = remove_weak_topic_words(title_a)
    b = remove_weak_topic_words(title_b)

    if not a or not b:
        return 0.0

    set_a = set(a)
    set_b = set(b)

    if not set_a or not set_b:
        return 0.0

    return len(set_a & set_b) / max(1, min(len(set_a), len(set_b)))


def is_weak_topic_only_match(title_a: str, title_b: str, similarity: float) -> bool:
    """
    判断两个标题是不是主要靠弱主题词相似。
    这种情况要谨慎：
    - 世界杯转播权仍未谈拢
    - 香港拿下世界杯转播权
    """
    meaningful_score = meaningful_common_score(title_a, title_b)
    weak_removed_a = remove_weak_topic_words(title_a)
    weak_removed_b = remove_weak_topic_words(title_b)

    if not weak_removed_a or not weak_removed_b:
        return True

    # 相似度不算特别高，且弱词之外共同内容很少，基本就是泛主题相似
    return similarity < 0.78 and meaningful_score < 0.28


def has_anchor_scope_conflict(title_a: str, title_b: str) -> bool:
    """
    锚点范围冲突的辅助判断。
    这不是绝对规则，只拦截非常典型的情况：
    - 一个标题明确是“香港拿下”
    - 另一个标题是“多国未签/整体未谈拢”
    """
    anchors_a = extract_strong_anchors(title_a)
    anchors_b = extract_strong_anchors(title_b)

    text_a = normalize_title(title_a)
    text_b = normalize_title(title_b)

    # 香港/澳门/台湾等明确地区获得，与另一个标题的“多国未签/整体未谈拢”容易不是同一事件
    region_words = {"香港", "澳门", "台湾", "中国香港", "中国澳门"}
    broad_words = {"多国"}

    a_region = bool(anchors_a & region_words)
    b_region = bool(anchors_b & region_words)
    a_broad = bool(anchors_a & broad_words)
    b_broad = bool(anchors_b & broad_words)

    if a_region and b_broad and has_action_direction_conflict(title_a, title_b):
        return True

    if b_region and a_broad and has_action_direction_conflict(title_a, title_b):
        return True

    # 一个标题明确“香港拿下/获得”，另一个完全没有香港且是未谈拢方向，也拒绝
    if "香港" in text_a and "香港" not in text_b and has_action_direction_conflict(title_a, title_b):
        return True

    if "香港" in text_b and "香港" not in text_a and has_action_direction_conflict(title_a, title_b):
        return True

    return False


def is_event_consistent(
    title_a: str,
    title_b: str,
    similarity: float,
    common_score: float,
) -> Tuple[bool, str]:
    """
    事件一致性校验。

    字符串相似度负责“召回候选”，这个函数负责“拦截明显不是同一事件”的情况。

    当前重点拦截：
    1. 动作方向冲突：拿下/获得 vs 未谈拢/拒绝/未签约；
    2. 只靠弱主题词相似：都包含“世界杯转播权”，但弱词之外几乎没共同内容；
    3. 锚点范围冲突：香港拿下 vs 多国未签/整体未谈拢。
    """
    normalized_a = normalize_title(title_a)
    normalized_b = normalize_title(title_b)

    if not normalized_a or not normalized_b:
        return False, "empty_title"

    if has_action_direction_conflict(title_a, title_b):
        return False, "action_direction_conflict"

    if has_anchor_scope_conflict(title_a, title_b):
        return False, "anchor_scope_conflict"

    if is_weak_topic_only_match(title_a, title_b, similarity):
        return False, "weak_topic_only_match"

    # 如果两个标题都有强锚点，但强锚点完全不交集，同时相似度不是极高，也谨慎拒绝
    anchors_a = extract_strong_anchors(title_a)
    anchors_b = extract_strong_anchors(title_b)

    if anchors_a and anchors_b:
        shared_anchors = anchors_a & anchors_b

        # 如果都只有“世界杯/转播权”这类弱词，前面已经处理；
        # 这里主要处理明确锚点完全不同的情况。
        if not shared_anchors and similarity < 0.82:
            flags_a = extract_action_flags(title_a)
            flags_b = extract_action_flags(title_b)

            # 两边动作方向不同或其中一边没有明确动作时，拒绝
            if flags_a != flags_b or not (flags_a["confirmed"] or flags_a["unresolved"]):
                return False, "strong_anchor_mismatch"

    return True, "ok"


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
        matched = similarity >= 0.62 and common_score >= 0.50
    else:
        matched = similarity >= similarity_threshold and common_score >= common_char_threshold

    if not matched:
        return False, similarity, common_score

    consistent, reason = is_event_consistent(
        title_a=title_a,
        title_b=title_b,
        similarity=similarity,
        common_score=common_score,
    )

    if not consistent:
        return False, similarity, common_score

    return True, similarity, common_score


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


# =========================
# 跨平台主题表写入与迁移支撑
# =========================

def collect_topic_hotspots(cross_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    从 cross_result / related_result 中提取同组热点，去重并排序。
    兼容 analyze_cross_platform_status、主动扫描 group、迁移脚本构造出来的结果。
    """
    all_hotspots = cross_result.get("all_hotspots") or []
    current = cross_result.get("current") or {}
    matches = cross_result.get("matches") or []

    candidates: List[Dict[str, Any]] = []
    if current:
        candidates.append(current)
    candidates.extend(matches)
    candidates.extend(all_hotspots)

    result: List[Dict[str, Any]] = []
    seen = set()

    for item in candidates:
        if not item:
            continue
        hotspot_id = item.get("id") or item.get("hotspot_id")
        if not hotspot_id:
            continue
        try:
            hotspot_id = int(hotspot_id)
        except Exception:
            continue
        if hotspot_id in seen:
            continue

        row = dict(item)
        row["id"] = hotspot_id
        result.append(row)
        seen.add(hotspot_id)

    result.sort(
        key=lambda item: (
            item.get("rank_num") if item.get("rank_num") is not None else 999999,
            -(float(item.get("hot_value") or 0)),
            item.get("id") or 0,
        )
    )
    return result


def choose_topic_primary_hotspot(hotspots: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    选择联合热点的主展示标题。
    优先排名靠前，其次热度/排序值高，其次 id 小。
    """
    if not hotspots:
        return None

    return sorted(
        hotspots,
        key=lambda item: (
            item.get("rank_num") if item.get("rank_num") is not None else 999999,
            -(float(item.get("hot_value") or 0)),
            item.get("id") or 0,
        ),
    )[0]


def find_existing_topic_id_by_hotspots(cursor: Cursor, hotspot_ids: List[int]) -> Optional[int]:
    """
    只要这些 hotspot 中任意一个已经属于某个 topic，就复用该 topic。
    如果多个 topic 命中，选择命中数量最多且最新更新的一个。
    """
    ids = [int(item) for item in hotspot_ids if item]
    if not ids:
        return None

    placeholders = ",".join(["%s"] * len(ids))
    sql = f"""
        SELECT r.topic_id, COUNT(*) AS hit_count, MAX(t.updated_at) AS last_update_time
        FROM cross_platform_topic_hotspot r
        LEFT JOIN cross_platform_topic t ON t.id = r.topic_id
        WHERE r.hotspot_id IN ({placeholders})
        GROUP BY r.topic_id
        ORDER BY hit_count DESC, last_update_time DESC, r.topic_id DESC
        LIMIT 1
    """
    cursor.execute(sql, ids)
    row = cursor.fetchone()
    if not row:
        return None
    return int(row.get("topic_id"))


def calculate_topic_confidence(hotspots: List[Dict[str, Any]]) -> Optional[float]:
    scores = []
    for item in hotspots:
        if item.get("similarity_score") is not None:
            try:
                scores.append(float(item.get("similarity_score")))
            except Exception:
                pass

    if not scores:
        return None

    # 当前热点自身通常没有 similarity_score；这里只统计匹配项平均分。
    return round(sum(scores) / len(scores), 2)


def upsert_cross_platform_topic(
    cursor: Cursor,
    cross_result: Dict[str, Any],
    summary: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Optional[int]:
    """
    将一次跨平台匹配结果写入 cross_platform_topic / cross_platform_topic_hotspot。

    这一步让“联合热点”从 related_hotspot_ids 字符串升级为独立业务对象：
    - cross_platform_topic 保存联合事件本身；
    - cross_platform_topic_hotspot 保存该事件关联了哪些平台热点。

    返回 topic_id；如果同组不足 2 个平台，则不创建 topic。
    """
    now = now or datetime.now()
    hotspots = collect_topic_hotspots(cross_result)

    if not hotspots:
        return None

    platforms = sorted({item.get("platform") for item in hotspots if item.get("platform")})
    if len(platforms) < 2:
        return None

    hotspot_ids = [int(item.get("id")) for item in hotspots if item.get("id")]
    if len(hotspot_ids) < 2:
        return None

    primary = choose_topic_primary_hotspot(hotspots) or hotspots[0]
    main_title = primary.get("title") or "跨平台热点"
    related_platforms = ",".join(platforms)
    confidence_score = calculate_topic_confidence(hotspots)

    first_seen_candidates = [
        item.get("crawl_time")
        for item in hotspots
        if item.get("crawl_time")
    ]
    first_seen_time = min(first_seen_candidates) if first_seen_candidates else now
    last_seen_time = max(first_seen_candidates) if first_seen_candidates else now

    topic_id = find_existing_topic_id_by_hotspots(cursor, hotspot_ids)

    if topic_id is None:
        insert_sql = """
            INSERT INTO cross_platform_topic (
                main_title,
                summary,
                topic_status,
                confidence_score,
                platform_count,
                hotspot_count,
                related_platforms,
                first_seen_time,
                last_seen_time,
                created_at,
                updated_at
            ) VALUES (%s, %s, 'active', %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_sql, (
            main_title,
            summary,
            confidence_score,
            len(platforms),
            len(hotspot_ids),
            related_platforms,
            first_seen_time,
            last_seen_time,
            now,
            now,
        ))
        topic_id = int(cursor.lastrowid)
    else:
        update_sql = """
            UPDATE cross_platform_topic
            SET main_title = %s,
                summary = CASE
                    WHEN %s IS NULL OR %s = '' THEN summary
                    ELSE %s
                END,
                confidence_score = COALESCE(%s, confidence_score),
                platform_count = %s,
                hotspot_count = %s,
                related_platforms = %s,
                first_seen_time = CASE
                    WHEN first_seen_time IS NULL OR first_seen_time > %s THEN %s
                    ELSE first_seen_time
                END,
                last_seen_time = CASE
                    WHEN last_seen_time IS NULL OR last_seen_time < %s THEN %s
                    ELSE last_seen_time
                END,
                updated_at = %s
            WHERE id = %s
        """
        cursor.execute(update_sql, (
            main_title,
            summary,
            summary,
            summary,
            confidence_score,
            len(platforms),
            len(hotspot_ids),
            related_platforms,
            first_seen_time,
            first_seen_time,
            last_seen_time,
            last_seen_time,
            now,
            topic_id,
        ))

    primary_id = int(primary.get("id")) if primary.get("id") else None

    relation_sql = """
        INSERT INTO cross_platform_topic_hotspot (
            topic_id,
            hotspot_id,
            platform,
            title,
            match_score,
            is_primary,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            platform = VALUES(platform),
            title = VALUES(title),
            match_score = VALUES(match_score),
            is_primary = VALUES(is_primary)
    """

    for item in hotspots:
        hotspot_id = int(item.get("id"))
        platform = item.get("platform") or ""
        title = item.get("title") or ""
        match_score = item.get("similarity_score")
        if hotspot_id == primary_id and match_score is None:
            match_score = 1.0
        is_primary = 1 if hotspot_id == primary_id else 0

        cursor.execute(relation_sql, (
            topic_id,
            hotspot_id,
            platform,
            title,
            match_score,
            is_primary,
            now,
        ))

    # 兼容 topic 已存在但关联热点数量扩展的情况，最后再统计一次关系表。
    refresh_sql = """
        UPDATE cross_platform_topic t
        SET platform_count = (
                SELECT COUNT(DISTINCT r.platform)
                FROM cross_platform_topic_hotspot r
                WHERE r.topic_id = t.id
            ),
            hotspot_count = (
                SELECT COUNT(*)
                FROM cross_platform_topic_hotspot r
                WHERE r.topic_id = t.id
            ),
            related_platforms = (
                SELECT GROUP_CONCAT(DISTINCT r.platform ORDER BY r.platform SEPARATOR ',')
                FROM cross_platform_topic_hotspot r
                WHERE r.topic_id = t.id
            ),
            updated_at = %s
        WHERE t.id = %s
    """
    cursor.execute(refresh_sql, (now, topic_id))

    return topic_id


def update_cross_platform_topic_summary(
    cursor: Cursor,
    cross_result: Dict[str, Any],
    summary: str,
    now: Optional[datetime] = None,
) -> Optional[int]:
    """
    AI 生成跨平台简介后调用：把简介同步写入 cross_platform_topic.summary。
    """
    return upsert_cross_platform_topic(
        cursor=cursor,
        cross_result=cross_result,
        summary=summary,
        now=now or datetime.now(),
    )


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

            topic_id = None
            if related_result.get("matches"):
                topic_id = upsert_cross_platform_topic(cursor, related_result)
                conn.commit()

            return {
                "current": related_result.get("current"),
                "matches": related_result.get("matches"),
                "all_hotspots": related_result.get("all_hotspots"),
                "platform_count": related_result.get("platform_count"),
                "material_check": material_check,
                "material_bundle": material_bundle,
                "topic_id": topic_id,
            }

    finally:
        conn.close()


# =========================
# 主动扫描跨平台候选热点组
# =========================

def fetch_recent_hotspots_for_scan(
    cursor: Cursor,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    max_candidates: int = SCAN_MAX_CANDIDATES,
) -> List[Dict[str, Any]]:
    """
    主动扫描使用：读取最近一段时间内三平台热点。
    """
    start_time = datetime.now() - timedelta(hours=lookback_hours)

    sql = """
        SELECT id, platform, title, rank_num, hot_value, tags, is_special, source_url, crawl_time
        FROM hotspot
        WHERE platform IN ('weibo', 'douyin', 'bilibili')
          AND crawl_time >= %s
          AND title IS NOT NULL
          AND title <> ''
        ORDER BY
            CASE WHEN rank_num IS NULL THEN 999999 ELSE rank_num END ASC,
            hot_value DESC,
            crawl_time DESC,
            id DESC
        LIMIT %s
    """
    cursor.execute(sql, (start_time, max_candidates))
    return list(cursor.fetchall())


def hotspot_rank_score(hotspot: Dict[str, Any]) -> float:
    """
    用于主动扫描排序：
    - 排名越靠前越高；
    - 置顶热点略加权；
    - 热度只做轻量辅助，避免不同平台热度值无法直接比较的问题。
    """
    rank_num = hotspot.get("rank_num")
    hot_value = float(hotspot.get("hot_value") or 0)

    if rank_num is None:
        rank_score = 0.0
    else:
        rank_score = max(0.0, 60.0 - float(rank_num))

    special_score = 15.0 if hotspot.get("is_special") else 0.0
    hot_score = min(hot_value / 1000000.0, 20.0)

    return rank_score + special_score + hot_score


def build_candidate_group_from_seed(
    seed: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    similarity_threshold: float = SCAN_SIMILARITY_THRESHOLD,
    common_char_threshold: float = SCAN_COMMON_CHAR_THRESHOLD,
) -> Optional[Dict[str, Any]]:
    """
    以某个热点为种子，尝试在其它平台中找同事件热点。
    每个平台只保留相似度最高的一条。
    """
    seed_platform = seed.get("platform")
    seed_title = seed.get("title") or ""

    if not seed_platform or not seed_title:
        return None

    best_by_platform: Dict[str, Dict[str, Any]] = {
        seed_platform: dict(seed)
    }

    for candidate in candidates:
        candidate_id = candidate.get("id")
        if candidate_id == seed.get("id"):
            continue

        candidate_platform = candidate.get("platform")
        candidate_title = candidate.get("title") or ""

        if not candidate_platform or candidate_platform == seed_platform:
            continue

        matched, similarity, common_score = is_possible_same_hotspot(
            seed_title,
            candidate_title,
            similarity_threshold=similarity_threshold,
            common_char_threshold=common_char_threshold,
        )

        if not matched:
            continue

        item = dict(candidate)
        item["similarity_score"] = similarity
        item["common_char_score"] = round(common_score, 4)
        item["seed_hotspot_id"] = seed.get("id")
        item["seed_title"] = seed_title

        old = best_by_platform.get(candidate_platform)
        if old is None:
            best_by_platform[candidate_platform] = item
            continue

        old_score = float(old.get("similarity_score") or 0)
        new_score = float(item.get("similarity_score") or 0)

        old_rank_score = hotspot_rank_score(old)
        new_rank_score = hotspot_rank_score(item)

        if new_score > old_score or (new_score == old_score and new_rank_score > old_rank_score):
            best_by_platform[candidate_platform] = item

    group_hotspots = list(best_by_platform.values())
    platform_count = len({item.get("platform") for item in group_hotspots if item.get("platform")})

    if platform_count <= 1:
        return None

    # 组内再做一次两两一致性检查。只要任意两条明显冲突，就整组放弃。
    for index_a in range(len(group_hotspots)):
        for index_b in range(index_a + 1, len(group_hotspots)):
            title_a = group_hotspots[index_a].get("title") or ""
            title_b = group_hotspots[index_b].get("title") or ""
            similarity = calc_title_similarity(title_a, title_b)
            common_score = common_char_score(title_a, title_b)
            consistent, reason = is_event_consistent(title_a, title_b, similarity, common_score)
            if not consistent:
                return None

    group_hotspots = sorted(
        group_hotspots,
        key=lambda item: (
            item.get("platform") or "",
            item.get("rank_num") if item.get("rank_num") is not None else 999999,
            item.get("id") or 0,
        ),
    )

    hotspot_ids = [int(item.get("id")) for item in group_hotspots if item.get("id")]
    group_key = ",".join(str(item_id) for item_id in sorted(hotspot_ids))

    non_seed_scores = [
        float(item.get("similarity_score") or 0)
        for item in group_hotspots
        if item.get("id") != seed.get("id")
    ]

    avg_similarity = 1.0
    if non_seed_scores:
        avg_similarity = sum(non_seed_scores) / len(non_seed_scores)

    best_rank = min([
        item.get("rank_num") if item.get("rank_num") is not None else 999999
        for item in group_hotspots
    ])

    group_score = (
        platform_count * 1000
        + avg_similarity * 100
        + sum(hotspot_rank_score(item) for item in group_hotspots)
        - best_rank * 0.1
    )

    current = dict(seed)
    matches = []
    for item in group_hotspots:
        if item.get("id") == seed.get("id"):
            continue

        if "similarity_score" not in item:
            matched, similarity, common_score = is_possible_same_hotspot(
                seed_title,
                item.get("title") or "",
                similarity_threshold=similarity_threshold,
                common_char_threshold=common_char_threshold,
            )
            item = dict(item)
            item["similarity_score"] = similarity
            item["common_char_score"] = round(common_score, 4)

        matches.append(item)

    return {
        "group_key": group_key,
        "seed": current,
        "current": current,
        "matches": matches,
        "all_hotspots": group_hotspots,
        "platform_count": platform_count,
        "avg_similarity": round(avg_similarity, 4),
        "best_rank": best_rank,
        "group_score": round(group_score, 4),
    }


def dedupe_and_rank_candidate_groups(
    raw_groups: List[Dict[str, Any]],
    min_platform_count: int = SCAN_MIN_PLATFORM_COUNT,
    max_groups: int = SCAN_MAX_GROUPS,
) -> List[Dict[str, Any]]:
    """
    对扫描出来的候选组去重、排序、限制数量。
    """
    unique_groups: Dict[str, Dict[str, Any]] = {}

    for group in raw_groups:
        if not group:
            continue

        platform_count = int(group.get("platform_count") or 0)
        if platform_count < min_platform_count:
            continue

        group_key = group.get("group_key")
        if not group_key:
            continue

        old = unique_groups.get(group_key)
        if old is None or float(group.get("group_score") or 0) > float(old.get("group_score") or 0):
            unique_groups[group_key] = group

    groups = list(unique_groups.values())
    groups.sort(
        key=lambda item: (
            -int(item.get("platform_count") or 0),
            -float(item.get("avg_similarity") or 0),
            -float(item.get("group_score") or 0),
            item.get("best_rank") if item.get("best_rank") is not None else 999999,
        )
    )

    selected = []
    used_hotspot_ids = set()

    for group in groups:
        group_ids = {
            int(item.get("id"))
            for item in group.get("all_hotspots") or []
            if item.get("id")
        }

        # 避免同一热点在一轮扫描中进入多个组
        if group_ids & used_hotspot_ids:
            continue

        selected.append(group)
        used_hotspot_ids.update(group_ids)

        if len(selected) >= max_groups:
            break

    return selected


def has_existing_cross_platform_summary(cursor: Cursor, hotspot_ids: List[int]) -> bool:
    """
    如果同组中已经有跨平台简介，则本轮主动扫描不重复处理。
    """
    if not hotspot_ids:
        return False

    placeholders = ",".join(["%s"] * len(hotspot_ids))
    sql = f"""
        SELECT COUNT(*) AS count
        FROM hotspot_ai_summary
        WHERE hotspot_id IN ({placeholders})
          AND analysis_type = 'cross_platform'
    """
    cursor.execute(sql, hotspot_ids)
    row = cursor.fetchone() or {}
    return int(row.get("count") or 0) > 0


def fetch_ai_task(cursor: Cursor, hotspot_id: int) -> Optional[Dict[str, Any]]:
    sql = """
        SELECT id, hotspot_id, platform, title, status, priority, error_message, created_at, updated_at
        FROM hotspot_ai_summary_task
        WHERE hotspot_id = %s
        LIMIT 1
    """
    cursor.execute(sql, (hotspot_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def upsert_ai_summary_task_if_needed(
    cursor: Cursor,
    hotspot: Dict[str, Any],
    priority: int = SCAN_AI_TASK_PRIORITY,
    force_reset_done: bool = True,
) -> str:
    """
    主动扫描发现跨平台组后，为组内热点创建或重置 AI 简介任务。

    返回：
    - active：已有 pending / processing
    - done_keep：已有 done 且不重置
    - enqueued：本次新建或重置为 pending
    """
    hotspot_id = int(hotspot.get("id"))
    platform = hotspot.get("platform")
    title = hotspot.get("title") or ""

    task = fetch_ai_task(cursor, hotspot_id)
    if task:
        status = task.get("status")
        if status in ACTIVE_AI_TASK_STATUSES:
            return "active"

        if status == DONE_STATUS and not force_reset_done:
            return "done_keep"

    sql = """
        INSERT INTO hotspot_ai_summary_task (
            hotspot_id,
            platform,
            title,
            status,
            priority,
            error_message,
            created_at,
            updated_at
        ) VALUES (%s, %s, %s, 'pending', %s, NULL, NOW(), NOW())
        ON DUPLICATE KEY UPDATE
            platform = VALUES(platform),
            title = VALUES(title),
            status = CASE
                WHEN status = 'processing' THEN status
                ELSE VALUES(status)
            END,
            priority = GREATEST(priority, VALUES(priority)),
            error_message = NULL,
            updated_at = NOW()
    """
    cursor.execute(sql, (hotspot_id, platform, title, priority))
    return "enqueued"


def build_related_result_from_group(group: Dict[str, Any]) -> Dict[str, Any]:
    """
    将主动扫描得到的 group 转换成 ensure_related_material_tasks / build_cross_platform_material_bundle 可复用的结构。
    """
    all_hotspots = group.get("all_hotspots") or []
    current = group.get("current") or (all_hotspots[0] if all_hotspots else {})
    current_id = current.get("id")

    matches = []
    for item in all_hotspots:
        if item.get("id") == current_id:
            continue
        matches.append(item)

    return {
        "current": current,
        "matches": matches,
        "all_hotspots": all_hotspots,
        "platform_count": len({item.get("platform") for item in all_hotspots if item.get("platform")}),
        "lookback_hours": DEFAULT_LOOKBACK_HOURS,
        "similarity_threshold": SCAN_SIMILARITY_THRESHOLD,
    }


def enqueue_group_material_and_ai_tasks(
    cursor: Cursor,
    group: Dict[str, Any],
    ai_priority: int = SCAN_AI_TASK_PRIORITY,
) -> Dict[str, Any]:
    """
    给主动扫描出来的热点组补材料任务和 AI 任务。
    """
    related_result = build_related_result_from_group(group)

    material_check = ensure_related_material_tasks(
        cursor=cursor,
        related_result=related_result,
        force_reset_failed=True,
    )

    ai_actions = []
    for hotspot in related_result.get("all_hotspots") or []:
        action = upsert_ai_summary_task_if_needed(
            cursor=cursor,
            hotspot=hotspot,
            priority=ai_priority,
            force_reset_done=True,
        )
        ai_actions.append({
            "hotspot_id": hotspot.get("id"),
            "platform": hotspot.get("platform"),
            "title": hotspot.get("title"),
            "action": action,
        })

    material_bundle = build_cross_platform_material_bundle(cursor, related_result)
    topic_id = upsert_cross_platform_topic(cursor, related_result)

    return {
        "related_result": related_result,
        "material_check": material_check,
        "material_bundle": material_bundle,
        "ai_actions": ai_actions,
        "topic_id": topic_id,
    }


def scan_cross_platform_candidate_groups(
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    max_groups: int = SCAN_MAX_GROUPS,
    min_platform_count: int = SCAN_MIN_PLATFORM_COUNT,
    similarity_threshold: float = SCAN_SIMILARITY_THRESHOLD,
    common_char_threshold: float = SCAN_COMMON_CHAR_THRESHOLD,
    max_candidates: int = SCAN_MAX_CANDIDATES,
    auto_enqueue_tasks: bool = True,
    skip_existing_cross_summary: bool = True,
) -> Dict[str, Any]:
    """
    主动扫描跨平台候选热点组。

    作用：
    - 找出最近一段时间内同时出现在多个平台的相似热点；
    - 即使这些热点不在单个平台前 10，也可以认为有跨平台传播价值；
    - 自动补材料任务和 AI 简介任务。

    返回：
    {
        "groups": [...],
        "processed_groups": [...],
        "raw_group_count": n,
        "selected_group_count": n
    }
    """
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            candidates = fetch_recent_hotspots_for_scan(
                cursor=cursor,
                lookback_hours=lookback_hours,
                max_candidates=max_candidates,
            )

            raw_groups = []
            for seed in candidates:
                group = build_candidate_group_from_seed(
                    seed=seed,
                    candidates=candidates,
                    similarity_threshold=similarity_threshold,
                    common_char_threshold=common_char_threshold,
                )
                if group:
                    raw_groups.append(group)

            selected_groups = dedupe_and_rank_candidate_groups(
                raw_groups=raw_groups,
                min_platform_count=min_platform_count,
                max_groups=max_groups,
            )

            processed_groups = []
            skipped_groups = []

            for group in selected_groups:
                hotspot_ids = [
                    int(item.get("id"))
                    for item in group.get("all_hotspots") or []
                    if item.get("id")
                ]

                if skip_existing_cross_summary and has_existing_cross_platform_summary(cursor, hotspot_ids):
                    skipped_groups.append({
                        "group": group,
                        "reason": "existing_cross_platform_summary",
                    })
                    continue

                process_result = {
                    "group": group,
                    "task_result": None,
                }

                if auto_enqueue_tasks:
                    task_result = enqueue_group_material_and_ai_tasks(cursor, group)
                    process_result["task_result"] = task_result

                processed_groups.append(process_result)

            if auto_enqueue_tasks:
                conn.commit()

            return {
                "lookback_hours": lookback_hours,
                "max_groups": max_groups,
                "min_platform_count": min_platform_count,
                "similarity_threshold": similarity_threshold,
                "common_char_threshold": common_char_threshold,
                "candidate_count": len(candidates),
                "raw_group_count": len(raw_groups),
                "selected_group_count": len(selected_groups),
                "processed_group_count": len(processed_groups),
                "skipped_group_count": len(skipped_groups),
                "groups": selected_groups,
                "processed_groups": processed_groups,
                "skipped_groups": skipped_groups,
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


def print_scan_result(result: Dict[str, Any]) -> None:
    print("=" * 80)
    print("跨平台候选热点主动扫描结果")
    print("=" * 80)

    print(f"扫描时间窗口：最近 {result.get('lookback_hours')} 小时")
    print(f"候选热点数量：{result.get('candidate_count')}")
    print(f"原始候选组数量：{result.get('raw_group_count')}")
    print(f"筛选后候选组数量：{result.get('selected_group_count')}")
    print(f"已处理候选组数量：{result.get('processed_group_count')}")
    print(f"跳过候选组数量：{result.get('skipped_group_count')}")
    print("-" * 80)

    processed_groups = result.get("processed_groups") or []
    if not processed_groups:
        print("本轮没有新的跨平台候选组需要处理。")
        print("=" * 80)
        return

    for group_index, item in enumerate(processed_groups, start=1):
        group = item.get("group") or {}
        task_result = item.get("task_result") or {}
        material_check = task_result.get("material_check") or {}
        material_bundle = task_result.get("material_bundle") or {}

        print(f"候选组 #{group_index}")
        print(
            f"group_key={group.get('group_key')}，"
            f"平台数={group.get('platform_count')}，"
            f"平均相似度={group.get('avg_similarity')}，"
            f"综合分={group.get('group_score')}"
        )

        print("组内热点：")
        for hotspot in group.get("all_hotspots") or []:
            print(
                f"- hotspot_id={hotspot.get('id')}，"
                f"平台={platform_label(hotspot.get('platform'))}，"
                f"排名={hotspot.get('rank_num')}，"
                f"标题={hotspot.get('title')}"
            )

        print(f"分析模式：{material_check.get('analysis_mode')}")
        print(f"已有材料平台：{', '.join(platform_label(p) for p in material_check.get('ready_platforms') or [])}")
        print(
            f"可用于 AI 的材料平台数：{material_bundle.get('platform_count')}，"
            f"平台项数量：{len(material_bundle.get('platform_items') or [])}"
        )

        print("材料任务动作：")
        for action in material_check.get("actions") or []:
            print(
                f"- hotspot_id={action.get('hotspot_id')}，"
                f"平台={platform_label(action.get('platform'))}，"
                f"action={action.get('action')}，"
                f"task_status={action.get('task_status')}"
            )

        print("AI任务动作：")
        for action in task_result.get("ai_actions") or []:
            print(
                f"- hotspot_id={action.get('hotspot_id')}，"
                f"平台={platform_label(action.get('platform'))}，"
                f"action={action.get('action')}"
            )

        print("-" * 80)

    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] in ("--scan", "scan"):
        scan_result = scan_cross_platform_candidate_groups(
            lookback_hours=DEFAULT_LOOKBACK_HOURS,
            max_groups=SCAN_MAX_GROUPS,
            min_platform_count=SCAN_MIN_PLATFORM_COUNT,
            similarity_threshold=SCAN_SIMILARITY_THRESHOLD,
            common_char_threshold=SCAN_COMMON_CHAR_THRESHOLD,
            max_candidates=SCAN_MAX_CANDIDATES,
            auto_enqueue_tasks=True,
            skip_existing_cross_summary=True,
        )
        print_scan_result(scan_result)
    else:
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