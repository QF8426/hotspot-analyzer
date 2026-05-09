import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


WEIBO_HOT_URL = "https://weibo.com/ajax/side/hotSearch"


def safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None

    text = str(value).strip().replace(",", "")
    if text == "":
        return None

    digits = "".join(ch for ch in text if ch.isdigit())
    if digits == "":
        return None

    return int(digits)


def build_source_url(word: str, scheme: Optional[str]) -> Optional[str]:
    if scheme:
        scheme = str(scheme).strip()
        if scheme.startswith("//"):
            return "https:" + scheme
        if scheme.startswith("http"):
            return scheme

    if word:
        return f"https://s.weibo.com/weibo?q=%23{word}%23"

    return None


def normalize_title(text: Any) -> Optional[str]:
    """
    标题清洗规则：
    1. 去掉首尾空格
    2. 优先保留真实标题文本
    3. 去掉明显无意义的前后空白
    """
    if text is None:
        return None

    title = str(text).strip()
    if not title:
        return None

    # 去掉连续空白
    title = " ".join(title.split())

    return title or None


def normalize_tag(tag: Any, title: Optional[str] = None) -> Optional[str]:
    """
    标签清洗规则：
    1. 只保留短标签
    2. 如果标签和标题相同，直接丢弃
    3. 如果标签过长，视为脏数据，直接丢弃
    4. 去掉首尾 #
    """
    if tag is None:
        return None

    text = str(tag).strip()
    if not text:
        return None

    text = text.strip("#").strip()
    if not text:
        return None

    if title and text == str(title).strip():
        return None

    # 太长通常不是标签，而是标题/描述脏数据
    if len(text) > 4:
        return None

    # 过滤掉明显像句子的内容
    bad_chars = [" ", "，", "。", "：", "；", "、", "/", "\\"]
    if any(ch in text for ch in bad_chars):
        return None

    return text


def extract_normal_title(item: Dict[str, Any]) -> Optional[str]:
    """
    普通热搜标题：
    优先使用 word，其次 note
    不再使用 word_scheme 作为标题兜底，因为它经常带脏内容
    """
    candidates = [
        item.get("word"),
        item.get("note"),
    ]

    for candidate in candidates:
        title = normalize_title(candidate)
        if title:
            return title

    return None


def extract_special_title(item: Dict[str, Any]) -> Optional[str]:
    """
    特殊项标题：
    仍然优先取 word / note / title
    尽量不使用 word_scheme，避免拼出奇怪标题
    """
    candidates = [
        item.get("word"),
        item.get("note"),
        item.get("title"),
    ]

    for candidate in candidates:
        title = normalize_title(candidate)
        if title:
            return title

    return None


def extract_tag(item: Dict[str, Any], title: Optional[str]) -> Optional[str]:
    """
    标签优先级：
    icon_desc > label_name > small_icon_desc
    note/desc 不再作为通用标签来源，因为太容易把描述文本混进来
    """
    candidates = [
        item.get("icon_desc"),
        item.get("label_name"),
        item.get("small_icon_desc"),
    ]

    for candidate in candidates:
        tag = normalize_tag(candidate, title)
        if tag:
            return tag

    return None


def parse_normal_item(item: Dict[str, Any], rank_num: int, crawl_time: str) -> Optional[Dict[str, Any]]:
    word = extract_normal_title(item)
    if not word:
        return None

    raw_hot = (
        item.get("raw_hot")
        or item.get("num")
        or item.get("hot")
        or item.get("hot_value")
    )
    hot_value = safe_int(raw_hot)

    tags = extract_tag(item, word)

    scheme = item.get("scheme")
    source_url = build_source_url(word, scheme)

    return {
        "platform": "weibo",
        "title": word,
        "rankNum": rank_num,
        "hotValue": hot_value,
        "tags": tags,
        "isRanked": True,
        "isSpecial": False,
        "sourceUrl": source_url,
        "crawlTime": crawl_time,
    }


def parse_special_item(item: Dict[str, Any], crawl_time: str) -> Optional[Dict[str, Any]]:
    """
    解析置顶/特殊项
    这类数据通常不参与正常排名，所以：
    - rankNum = None
    - isRanked = False
    - isSpecial = True
    """
    word = extract_special_title(item)
    if not word:
        return None

    raw_hot = (
        item.get("raw_hot")
        or item.get("num")
        or item.get("hot")
        or item.get("hot_value")
    )
    hot_value = safe_int(raw_hot)

    tags = extract_tag(item, word)

    scheme = item.get("scheme")
    source_url = build_source_url(word, scheme)

    return {
        "platform": "weibo",
        "title": word,
        "rankNum": None,
        "hotValue": hot_value,
        "tags": tags,
        "isRanked": False,
        "isSpecial": True,
        "sourceUrl": source_url,
        "crawlTime": crawl_time,
    }


def append_if_valid(result: List[Dict[str, Any]], parsed: Optional[Dict[str, Any]], seen_titles: set) -> None:
    if not parsed:
        return

    title = parsed.get("title")
    if not title:
        return

    if title in seen_titles:
        return

    result.append(parsed)
    seen_titles.add(title)


def try_extract_special_items(data_obj: Dict[str, Any], result: List[Dict[str, Any]], seen_titles: set, crawl_time: str) -> None:
    """
    尝试从多个可能字段中提取置顶/特殊项
    微博接口这部分结构不完全稳定，所以这里做兼容处理
    """
    possible_special_keys = [
        "hotgov",
        "top",
        "top_band",
        "special",
        "special_band",
        "special_list",
        "band_list",
        "hotword",
        "banner",
        "ad",
    ]

    for key in possible_special_keys:
        value = data_obj.get(key)
        if not value:
            continue

        if isinstance(value, dict):
            parsed = parse_special_item(value, crawl_time)
            append_if_valid(result, parsed, seen_titles)

        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    parsed = parse_special_item(item, crawl_time)
                    append_if_valid(result, parsed, seen_titles)


def fetch_weibo_hot_search() -> List[Dict[str, Any]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        ),
        "Referer": "https://weibo.com/",
        "Accept": "application/json, text/plain, */*",
    }

    resp = requests.get(WEIBO_HOT_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    data = resp.json()
    data_obj = data.get("data", {})
    realtime_list = data_obj.get("realtime", [])

    results: List[Dict[str, Any]] = []
    seen_titles = set()
    # 同一轮微博榜单必须使用同一个 crawl_time。
    # 平台页当前榜单是按 snapshot 中 MAX(crawl_time) 取最新一轮，
    # 如果每条热点各自 datetime.now()，跨秒时可能导致同一轮榜单被拆开。
    batch_crawl_time = datetime.now().isoformat(timespec="seconds")

    # 先抓置顶/特殊项
    try_extract_special_items(data_obj, results, seen_titles, batch_crawl_time)

    # 再抓普通热搜
    rank = 1
    for item in realtime_list:
        if not isinstance(item, dict):
            continue

        parsed = parse_normal_item(item, rank, batch_crawl_time)
        if not parsed:
            continue

        append_if_valid(results, parsed, seen_titles)
        rank += 1

    return results


if __name__ == "__main__":
    try:
        result = fetch_weibo_hot_search()
        print(f"抓取成功，共 {len(result)} 条")
        print(json.dumps(result[:15], ensure_ascii=False, indent=2))
    except Exception as e:
        print("抓取失败：", e)