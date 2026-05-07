from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

import argparse
import json
import requests


DOUYIN_HOT_SEARCH_URL = "https://aweme-hl.snssdk.com/aweme/v1/hot/search/list/"


# 抖音接口中常见的标签编码。
# 目前根据实际输出先修正：1 = 新，3 = 热。
# 后续如果 debug 发现新的编码，再继续补。
DOUYIN_LABEL_MAP = {
    "1": "新",
    "2": "荐",
    "3": "热",
    "4": "独家",
    "5": "辟谣",
    "6": "直播",
    "7": "挑战",
}


# 可能承载置顶/特殊项的字段名。
# 当前接口暂时没有抓到手机端顶部置顶项，但保留探测逻辑。
SPECIAL_LIST_KEYS = [
    "top_word",
    "top_words",
    "top_word_list",
    "hotgov",
    "hotgovs",
    "fixed_word",
    "fixed_word_list",
    "recommend_word",
    "recommend_word_list",
    "recommend_list",
    "announcement",
    "announcement_list",
    "sentence_list",
]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalize_title(item: Dict[str, Any]) -> str:
    """
    抖音热榜接口中常见标题字段：
    - word
    - keyword
    - sentence
    - title
    """
    title = (
        item.get("word")
        or item.get("keyword")
        or item.get("sentence")
        or item.get("title")
        or item.get("name")
        or item.get("desc")
        or ""
    )
    return str(title).strip()


def _normalize_hot_value(item: Dict[str, Any]) -> int:
    """
    抖音接口常见热度字段：
    - hot_value
    - hotValue
    - score
    - view_count
    """
    return (
        _safe_int(item.get("hot_value"))
        or _safe_int(item.get("hotValue"))
        or _safe_int(item.get("score"))
        or _safe_int(item.get("view_count"))
        or _safe_int(item.get("viewCount"))
        or 0
    )


def _map_label_value(value: Any) -> Optional[str]:
    """
    把抖音接口里的标签字段转成中文。
    关键修复：
    - 3 -> 热
    - 1 -> 新
    - [3] -> 热
    - [3, 1] -> 热,新
    """
    if value is None:
        return None

    # 修复 [3] / [3, 1] 这种列表标签
    if isinstance(value, (list, tuple, set)):
        tags: List[str] = []
        for item in value:
            mapped = _map_label_value(item)
            if not mapped:
                continue

            # mapped 可能是 "热,新"，这里继续拆一下，避免嵌套后重复
            for part in str(mapped).split(","):
                part = part.strip()
                if part and part not in tags:
                    tags.append(part)

        return ",".join(tags) if tags else None

    # 修复 {"name": "热"} / {"label": 3} 这种对象标签
    if isinstance(value, dict):
        for key in [
            "name",
            "title",
            "text",
            "label_name",
            "label",
            "desc",
            "tag_name",
            "tag",
        ]:
            mapped = _map_label_value(value.get(key))
            if mapped:
                return mapped
        return None

    text = str(value).strip()
    if not text:
        return None

    # 修复字符串形式的列表，例如 "[3]"
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            return _map_label_value(parsed)
        except Exception:
            return None

    # 数字标签：1 / 3 这类
    if text in DOUYIN_LABEL_MAP:
        return DOUYIN_LABEL_MAP[text]

    # 已经是中文标签
    allowed = {"热", "新", "独家", "辟谣", "挑战", "首发", "直播", "荐"}
    if text in allowed:
        return text

    # 过滤长文本、标题、时间描述、奇怪数字
    if len(text) > 6:
        return None
    if text.isdigit():
        return None

    return text


def _normalize_tags(item: Dict[str, Any]) -> str:
    """
    规范化抖音标签。
    注意：
    - 不直接展示 word_type，避免出现 3,1 这种数字。
    - 但可以把 word_type 映射成中文标签。
    - 支持 label / tag / word_type / label_list / tag_list 等多种形式。
    """
    candidates = [
        item.get("label"),
        item.get("tag"),
        item.get("label_name"),
        item.get("label_desc"),
        item.get("tag_name"),
        item.get("tag_desc"),
        item.get("word_label"),
        item.get("word_sub_board"),
        item.get("word_type"),
    ]

    list_candidates = [
        item.get("label_list"),
        item.get("tag_list"),
        item.get("labels"),
        item.get("tags"),
    ]

    tags: List[str] = []

    def add_tag(value: Any) -> None:
        mapped = _map_label_value(value)
        if not mapped:
            return

        for part in str(mapped).split(","):
            part = part.strip()
            if part and part not in tags:
                tags.append(part)

    for value in candidates:
        add_tag(value)

    for values in list_candidates:
        add_tag(values)

    return ",".join(tags)


def _build_source_url(title: str) -> str:
    """
    抖音热榜接口通常不直接返回稳定详情链接。
    当前使用抖音搜索页作为来源链接，保证前端来源按钮可跳转。
    """
    return f"https://www.douyin.com/search/{quote(title)}"


def _normalize_source_url(item: Dict[str, Any], title: str) -> str:
    return (
        item.get("schema")
        or item.get("url")
        or item.get("share_url")
        or item.get("shareUrl")
        or _build_source_url(title)
    )


def _as_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _extract_special_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    尝试从 word_list 之外提取置顶/特殊项。
    如果当前接口没有返回手机端顶部那条，这里会返回空列表，不影响普通榜单。
    """
    result: List[Dict[str, Any]] = []
    seen_titles: Set[str] = set()

    for key in SPECIAL_LIST_KEYS:
        raw_value = data.get(key)
        for item in _as_list(raw_value):
            title = _normalize_title(item)
            if not title or title in seen_titles:
                continue

            result.append(item)
            seen_titles.add(title)

    return result


def _print_debug_payload(payload: Dict[str, Any]) -> None:
    """
    打印接口原始结构，用于排查：
    - 是否存在置顶字段
    - 标签字段到底叫什么
    - word_list 里每条数据有哪些 key
    """
    data = payload.get("data") or {}

    print("========== 抖音接口 DEBUG ==========")
    print("payload keys:", list(payload.keys()))
    print("data keys:", list(data.keys()))

    for key, value in data.items():
        if isinstance(value, list):
            print(f"\n字段 {key}: list, length={len(value)}")
            if value:
                first = value[0]
                if isinstance(first, dict):
                    print("第一条 keys:", list(first.keys()))
                    print(json.dumps(first, ensure_ascii=False, indent=2)[:2500])
                else:
                    print("第一条:", str(first)[:500])

        elif isinstance(value, dict):
            print(f"\n字段 {key}: dict")
            print("keys:", list(value.keys()))
            print(json.dumps(value, ensure_ascii=False, indent=2)[:1500])

        else:
            print(f"\n字段 {key}: {type(value).__name__} = {str(value)[:300]}")

    print("========== DEBUG 结束 ==========")


def fetch_douyin_hot_search(top_n: int = 50, debug: bool = False) -> List[Dict[str, Any]]:
    """
    抓取抖音热榜，并标准化为当前项目统一入库结构。

    返回字段必须适配现有数据库同步逻辑：
    platform/title/rankNum/hotValue/tags/isRanked/isSpecial/sourceUrl/crawlTime
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; Mobile) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.douyin.com/",
    }

    params = {
        "detail_list": 1,
        "cursor": 0,
    }

    try:
        response = requests.get(
            DOUYIN_HOT_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        print(f"抖音热榜抓取失败：{e}")
        return []

    if debug:
        _print_debug_payload(payload)

    data = payload.get("data") or {}
    raw_list = data.get("word_list") or []

    if not isinstance(raw_list, list):
        print("抖音热榜数据格式异常：data.word_list 不是数组")
        return []

    now = datetime.now()
    result: List[Dict[str, Any]] = []
    seen_titles: Set[str] = set()

    # 1. 先尝试加入置顶/特殊项
    special_items = _extract_special_items(data)
    for item in special_items:
        title = _normalize_title(item)
        if not title or title in seen_titles:
            continue

        result.append({
            "platform": "douyin",
            "title": title,
            "rankNum": None,
            "hotValue": _normalize_hot_value(item) or None,
            "tags": _normalize_tags(item),
            "isRanked": False,
            "isSpecial": True,
            "sourceUrl": _normalize_source_url(item, title),
            "crawlTime": now,
        })
        seen_titles.add(title)

    # 2. 再加入普通榜单
    rank = 1
    for item in raw_list:
        normal_count = len([record for record in result if record.get("isRanked")])
        if normal_count >= top_n:
            break

        if not isinstance(item, dict):
            continue

        title = _normalize_title(item)
        if not title or title in seen_titles:
            continue

        result.append({
            "platform": "douyin",
            "title": title,
            "rankNum": rank,
            "hotValue": _normalize_hot_value(item),
            "tags": _normalize_tags(item),
            "isRanked": True,
            "isSpecial": False,
            "sourceUrl": _normalize_source_url(item, title),
            "crawlTime": now,
        })

        seen_titles.add(title)
        rank += 1

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取抖音热榜")
    parser.add_argument("--debug", action="store_true", help="打印抖音接口原始字段，排查置顶项和标签")
    parser.add_argument("--top", type=int, default=50, help="普通榜单抓取数量")
    args = parser.parse_args()

    items = fetch_douyin_hot_search(top_n=args.top, debug=args.debug)

    print(f"抓取到抖音热榜 {len(items)} 条")

    special_count = len([item for item in items if item.get("isSpecial")])
    normal_count = len([item for item in items if item.get("isRanked")])

    print(f"特殊/置顶项：{special_count} 条")
    print(f"普通榜单：{normal_count} 条")

    for item in items[:15]:
        print(item)


if __name__ == "__main__":
    main()