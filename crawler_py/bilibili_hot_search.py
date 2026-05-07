import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests


BILIBILI_PLATFORM = "bilibili"

# 手机端热搜接口，更接近你第一张图里的 bilibili 热搜
BILIBILI_APP_HOT_SEARCH_URL = "https://app.bilibili.com/x/v2/search/trending/ranking"

# Web 端热搜接口，更接近你第二张图里的搜索框热搜
BILIBILI_WEB_HOTWORD_URL = "https://s.search.bilibili.com/main/hotword"

BILIBILI_SEARCH_URL = "https://search.bilibili.com/all"


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


WORD_TYPE_TAG_MAP = {
    4: "新",
    5: "热",
    6: "热",
    7: "直播中",
    8: "",
    9: "梗",
    11: "话题",
    12: "独家",
}


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def create_session() -> requests.Session:
    session = requests.Session()

    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": "https://search.bilibili.com/all",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })

    return session


def build_search_url(keyword: str) -> str:
    return f"{BILIBILI_SEARCH_URL}?keyword={quote(keyword)}"


def parse_word_type_tag(item: Dict[str, Any]) -> str:
    """
    B站热搜没有微博那种统一标签字段。
    这里根据 word_type 做一个简单映射：
    新、热、直播中、梗、话题、独家等。
    """
    word_type = safe_int(item.get("word_type"), default=8)
    tag = WORD_TYPE_TAG_MAP.get(word_type, "")

    if tag:
        return tag

    return ""


def calc_rank_score(rank_num: int, limit: int) -> int:
    """
    B站热搜接口没有直接给“热度值”。

    为了适配当前系统里的 hotspot_trend / daily-top 排序，
    这里用“排名反向分”作为 hot_value：
    第 1 名分数最高，第 50 名分数最低。

    注意：
    这不是 B站官方热度，只是系统内部用于排序和趋势展示的 rank score。
    """
    return max(1, (limit - rank_num + 1) * 10000)


def parse_hot_search_item(
    item: Dict[str, Any],
    index: int,
    crawl_time: datetime,
    limit: int,
) -> Optional[Dict[str, Any]]:
    """
    将 B站热搜词条转换为项目统一热点结构。
    """
    title = (
        item.get("show_name")
        or item.get("keyword")
        or item.get("name")
        or ""
    ).strip()

    if not title:
        return None

    rank_num = safe_int(
        item.get("position") or item.get("pos") or item.get("id") or index,
        default=index,
    )

    tags = parse_word_type_tag(item)

    return {
        "platform": BILIBILI_PLATFORM,
        "title": title,
        "rankNum": rank_num,
        "hotValue": calc_rank_score(rank_num, limit),
        "tags": tags,
        "isRanked": True,
        "isSpecial": False,
        "sourceUrl": build_search_url(title),
        "crawlTime": crawl_time,

        # 下面这些字段暂时不写入主链路，后续做 B站材料抓取时可能有用
        "hotId": item.get("hot_id"),
        "keyword": item.get("keyword"),
        "showName": item.get("show_name"),
        "wordType": item.get("word_type"),
        "icon": item.get("icon"),
        "rawItem": item,
    }


def fetch_from_app_api(session: requests.Session, limit: int) -> List[Dict[str, Any]]:
    """
    抓取手机端 bilibili 热搜。
    """
    response = session.get(
        BILIBILI_APP_HOT_SEARCH_URL,
        params={"limit": limit},
        timeout=15,
    )
    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:
        raise RuntimeError(f"B站手机端热搜接口返回异常：{data}")

    payload = data.get("data") or {}
    raw_list = payload.get("list") or []

    crawl_time = datetime.now()
    result: List[Dict[str, Any]] = []

    for index, item in enumerate(raw_list[:limit], start=1):
        parsed = parse_hot_search_item(item, index, crawl_time, limit)
        if parsed:
            result.append(parsed)

    return result


def fetch_from_web_hotword_api(session: requests.Session, limit: int) -> List[Dict[str, Any]]:
    """
    抓取 Web 端搜索热词。
    这个接口一般返回前 10 条，和你第二张网页截图更接近。
    """
    response = session.get(
        BILIBILI_WEB_HOTWORD_URL,
        timeout=15,
    )
    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:
        raise RuntimeError(f"B站 Web 热搜接口返回异常：{data}")

    raw_list = data.get("list") or []

    crawl_time = datetime.now()
    result: List[Dict[str, Any]] = []

    for index, item in enumerate(raw_list[:limit], start=1):
        parsed = parse_hot_search_item(item, index, crawl_time, limit)
        if parsed:
            result.append(parsed)

    return result


def fetch_bilibili_hot_search(limit: int = 50) -> List[Dict[str, Any]]:
    """
    抓取 B站热搜词条。

    优先使用手机端热搜接口，因为它返回数量更多；
    如果手机端接口失败，则回退到 Web 热词接口。
    """
    session = create_session()

    last_error: Optional[Exception] = None

    # 先试手机端接口
    for attempt in range(1, 4):
        try:
            items = fetch_from_app_api(session, limit=limit)
            if items:
                return items

            print(f"B站手机端热搜第 {attempt} 次返回空列表")

        except Exception as e:
            last_error = e
            print(f"B站手机端热搜第 {attempt} 次失败：{e}")

        time.sleep(random.uniform(1.0, 2.5))

    # 手机端失败，再试 Web 热词接口
    for attempt in range(1, 3):
        try:
            items = fetch_from_web_hotword_api(session, limit=limit)
            if items:
                return items

            print(f"B站 Web 热搜第 {attempt} 次返回空列表")

        except Exception as e:
            last_error = e
            print(f"B站 Web 热搜第 {attempt} 次失败：{e}")

        time.sleep(random.uniform(1.0, 2.5))

    raise RuntimeError(f"B站热搜接口连续失败，最后错误：{last_error}")


if __name__ == "__main__":
    items = fetch_bilibili_hot_search(limit=50)

    print(f"抓取到 B站热搜 {len(items)} 条")
    for item in items[:20]:
        print(
            item["rankNum"],
            item["title"],
            item["tags"],
            item["hotValue"],
            item["sourceUrl"],
        )