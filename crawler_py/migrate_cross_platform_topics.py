"""
把旧的跨平台简介数据迁移到新的联合热点主题表。

用途：
1. 读取 hotspot_ai_summary 中 analysis_type='cross_platform' 的旧数据；
2. 解析 related_hotspot_ids；
3. 创建/更新 cross_platform_topic；
4. 写入 cross_platform_topic_hotspot 关联关系；
5. 将旧简介同步到 cross_platform_topic.summary。

运行方式：
    cd crawler_py
    python migrate_cross_platform_topics.py

可选：
    python migrate_cross_platform_topics.py --dry-run
"""

import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import pymysql
from pymysql.connections import Connection

from db_config import DB_CONFIG
from cross_platform_matcher import upsert_cross_platform_topic, platform_label


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


def parse_hotspot_ids(value: Any) -> List[int]:
    if value is None:
        return []

    ids: List[int] = []
    for part in str(value).replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue

    result: List[int] = []
    seen: Set[int] = set()
    for item in ids:
        if item in seen:
            continue
        result.append(item)
        seen.add(item)
    return result


def fetch_cross_platform_summaries(cursor) -> List[Dict[str, Any]]:
    sql = """
        SELECT id, hotspot_id, platform, title, summary, related_hotspot_ids, related_platforms, created_at
        FROM hotspot_ai_summary
        WHERE analysis_type = 'cross_platform'
          AND related_hotspot_ids IS NOT NULL
          AND related_hotspot_ids <> ''
        ORDER BY created_at ASC, id ASC
    """
    cursor.execute(sql)
    return list(cursor.fetchall())


def fetch_hotspots_by_ids(cursor, hotspot_ids: List[int]) -> List[Dict[str, Any]]:
    if not hotspot_ids:
        return []

    placeholders = ",".join(["%s"] * len(hotspot_ids))
    sql = f"""
        SELECT id, platform, title, rank_num, hot_value, tags, is_special, source_url, crawl_time
        FROM hotspot
        WHERE id IN ({placeholders})
    """
    cursor.execute(sql, hotspot_ids)
    rows = list(cursor.fetchall())

    order_map = {item: index for index, item in enumerate(hotspot_ids)}
    rows.sort(key=lambda row: order_map.get(int(row.get("id")), 999999))
    return rows


def build_cross_result_from_summary(row: Dict[str, Any], hotspots: List[Dict[str, Any]]) -> Dict[str, Any]:
    current_id = row.get("hotspot_id")

    current: Optional[Dict[str, Any]] = None
    for hotspot in hotspots:
        if int(hotspot.get("id")) == int(current_id):
            current = hotspot
            break

    if current is None and hotspots:
        current = hotspots[0]

    matches = []
    current_id_value = int(current.get("id")) if current and current.get("id") else None
    for hotspot in hotspots:
        if current_id_value is not None and int(hotspot.get("id")) == current_id_value:
            continue
        item = dict(hotspot)
        # 旧数据没有精确匹配分数，用空值交给 topic 表按已有信息展示。
        item["similarity_score"] = None
        item["common_char_score"] = None
        matches.append(item)

    return {
        "current": current or {},
        "matches": matches,
        "all_hotspots": hotspots,
        "platform_count": len({item.get("platform") for item in hotspots if item.get("platform")}),
    }


def migrate(dry_run: bool = False) -> Dict[str, Any]:
    conn = get_connection()
    migrated_groups = 0
    skipped_rows = 0
    processed_group_keys: Set[Tuple[int, ...]] = set()
    topic_ids: List[int] = []

    try:
        with conn.cursor() as cursor:
            rows = fetch_cross_platform_summaries(cursor)
            print(f"发现旧跨平台简介记录：{len(rows)} 条")

            for row in rows:
                ids = parse_hotspot_ids(row.get("related_hotspot_ids"))
                current_id = row.get("hotspot_id")
                if current_id:
                    try:
                        current_id = int(current_id)
                        if current_id not in ids:
                            ids.insert(0, current_id)
                    except Exception:
                        pass

                group_key = tuple(sorted(set(ids)))
                if len(group_key) < 2:
                    skipped_rows += 1
                    print(f"跳过：summary_id={row.get('id')}，有效关联热点不足 2 个，ids={ids}")
                    continue

                if group_key in processed_group_keys:
                    skipped_rows += 1
                    print(f"跳过重复组：summary_id={row.get('id')}，group={group_key}")
                    continue

                hotspots = fetch_hotspots_by_ids(cursor, list(group_key))
                if len(hotspots) < 2:
                    skipped_rows += 1
                    print(f"跳过：summary_id={row.get('id')}，主表中可找到热点不足 2 个，group={group_key}")
                    continue

                platform_count = len({item.get("platform") for item in hotspots if item.get("platform")})
                if platform_count < 2:
                    skipped_rows += 1
                    print(f"跳过：summary_id={row.get('id')}，关联热点不足 2 个平台，group={group_key}")
                    continue

                cross_result = build_cross_result_from_summary(row, hotspots)

                print("-" * 80)
                print(f"迁移跨平台组：summary_id={row.get('id')}，group={group_key}")
                print("关联平台：" + "、".join(platform_label(item.get("platform")) for item in hotspots))
                print("主标题：" + str((cross_result.get("current") or {}).get("title") or row.get("title") or ""))

                if dry_run:
                    topic_id = None
                else:
                    topic_id = upsert_cross_platform_topic(
                        cursor=cursor,
                        cross_result=cross_result,
                        summary=row.get("summary"),
                        now=datetime.now(),
                    )
                    if topic_id:
                        topic_ids.append(int(topic_id))

                processed_group_keys.add(group_key)
                migrated_groups += 1
                print(f"完成：topic_id={topic_id}")

            if dry_run:
                conn.rollback()
                print("dry-run 模式：未提交任何数据库修改")
            else:
                conn.commit()
                print("迁移已提交")

        return {
            "migrated_groups": migrated_groups,
            "skipped_rows": skipped_rows,
            "topic_ids": topic_ids,
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    result = migrate(dry_run=dry_run)
    print("=" * 80)
    print(
        f"迁移完成：新增/更新联合热点组 {result['migrated_groups']} 组；"
        f"跳过 {result['skipped_rows']} 条；"
        f"topic_ids={result['topic_ids']}"
    )
