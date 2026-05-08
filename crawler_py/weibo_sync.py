from datetime import datetime
from typing import Dict, Any, List, Optional

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import Cursor
from pymysql import IntegrityError

from db_config import DB_CONFIG
from weibo_hot_search import fetch_weibo_hot_search


def get_connection() -> Connection:
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG["charset"],
        autocommit=False
    )


def find_hotspot_id(cursor: Cursor, platform: str, title: str) -> Optional[int]:
    sql = """
        SELECT id
        FROM hotspot
        WHERE platform = %s AND title = %s
        LIMIT 1
    """
    cursor.execute(sql, (platform, title))
    row = cursor.fetchone()
    return row[0] if row else None


def insert_hotspot(cursor: Cursor, item: Dict[str, Any], now: datetime) -> int:
    sql = """
        INSERT INTO hotspot (
            platform,
            title,
            rank_num,
            hot_value,
            tags,
            is_ranked,
            is_special,
            source_url,
            crawl_time,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(sql, (
        item.get("platform"),
        item.get("title"),
        item.get("rankNum"),
        item.get("hotValue"),
        item.get("tags"),
        1 if item.get("isRanked") else 0,
        1 if item.get("isSpecial") else 0,
        item.get("sourceUrl"),
        item.get("crawlTime"),
        now
    ))
    return cursor.lastrowid


def update_hotspot(cursor: Cursor, hotspot_id: int, item: Dict[str, Any], now: datetime) -> None:
    sql = """
        UPDATE hotspot
        SET rank_num = %s,
            hot_value = %s,
            tags = %s,
            is_ranked = %s,
            is_special = %s,
            source_url = %s,
            crawl_time = %s,
            created_at = %s
        WHERE id = %s
    """
    cursor.execute(sql, (
        item.get("rankNum"),
        item.get("hotValue"),
        item.get("tags"),
        1 if item.get("isRanked") else 0,
        1 if item.get("isSpecial") else 0,
        item.get("sourceUrl"),
        item.get("crawlTime"),
        now,
        hotspot_id
    ))


def insert_snapshot(cursor: Cursor, item: Dict[str, Any], hotspot_id: int) -> None:
    sql = """
        INSERT INTO hotspot_snapshot (
            hotspot_id,
            platform,
            title,
            rank_num,
            hot_value,
            tags,
            is_ranked,
            is_special,
            crawl_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(sql, (
        hotspot_id,
        item.get("platform"),
        item.get("title"),
        item.get("rankNum"),
        item.get("hotValue"),
        item.get("tags"),
        1 if item.get("isRanked") else 0,
        1 if item.get("isSpecial") else 0,
        item.get("crawlTime")
    ))


def insert_trend(cursor: Cursor, hotspot_id: int, item: Dict[str, Any], now: datetime) -> bool:
    if item.get("isSpecial"):
        return False

    sql = """
        INSERT INTO hotspot_trend (
            hotspot_id,
            rank_num,
            hot_value,
            record_time,
            created_at
        ) VALUES (%s, %s, %s, %s, %s)
    """
    try:
        cursor.execute(sql, (
            hotspot_id,
            item.get("rankNum"),
            item.get("hotValue"),
            item.get("crawlTime"),
            now
        ))
        return True
    except IntegrityError:
        return False


def should_generate_summary(item: Dict[str, Any]) -> bool:
    if item.get("isSpecial"):
        return True

    rank_num = item.get("rankNum")
    if rank_num is None:
        return False

    try:
        return 1 <= int(rank_num) <= 10
    except (TypeError, ValueError):
        return False


def calc_summary_priority(item: Dict[str, Any]) -> int:
    if item.get("isSpecial"):
        return 100

    rank_num = item.get("rankNum")
    try:
        return max(1, 100 - int(rank_num))
    except (TypeError, ValueError):
        return 1


def has_ai_summary(cursor: Cursor, hotspot_id: int) -> bool:
    sql = """
        SELECT id
        FROM hotspot_ai_summary
        WHERE hotspot_id = %s
        LIMIT 1
    """
    cursor.execute(sql, (hotspot_id,))
    return cursor.fetchone() is not None


def enqueue_ai_summary_task(
    cursor: Cursor,
    hotspot_id: int,
    item: Dict[str, Any],
    now: datetime
) -> bool:
    if has_ai_summary(cursor, hotspot_id):
        return False

    sql = """
        INSERT INTO hotspot_ai_summary_task (
            hotspot_id,
            platform,
            title,
            priority,
            status,
            created_at,
            updated_at
        ) VALUES (%s, %s, %s, %s, 'pending', %s, %s)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            priority = GREATEST(priority, VALUES(priority)),
            updated_at = VALUES(updated_at)
    """
    cursor.execute(sql, (
        hotspot_id,
        item.get("platform"),
        item.get("title"),
        calc_summary_priority(item),
        now,
        now
    ))

    return cursor.rowcount > 0


def enqueue_missing_ai_summary_tasks(
    cursor: Cursor,
    summary_items: List[Dict[str, Any]],
    now: datetime
) -> int:
    task_count = 0

    for record in summary_items:
        hotspot_id = record.get("hotspotId")
        item = record.get("item")

        if not hotspot_id or not item:
            continue

        try:
            if enqueue_ai_summary_task(cursor, hotspot_id, item, now):
                task_count += 1
        except Exception as e:
            print("AI 简介任务入队跳过，不影响本次同步：", e)
            return task_count

    return task_count


def enqueue_material_task(
    cursor: Cursor,
    hotspot_id: int,
    item: Dict[str, Any],
    now: datetime
) -> bool:
    sql = """
        INSERT INTO hotspot_material_task (
            hotspot_id,
            platform,
            title,
            status,
            created_at,
            updated_at
        ) VALUES (%s, %s, %s, 'pending', %s, %s)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            updated_at = VALUES(updated_at)
    """
    cursor.execute(sql, (
        hotspot_id,
        item.get("platform"),
        item.get("title"),
        now,
        now
    ))

    return cursor.rowcount > 0


def enqueue_missing_material_tasks(
    cursor: Cursor,
    summary_items: List[Dict[str, Any]],
    now: datetime
) -> int:
    task_count = 0

    for record in summary_items:
        hotspot_id = record.get("hotspotId")
        item = record.get("item")

        if not hotspot_id or not item:
            continue

        try:
            if enqueue_material_task(cursor, hotspot_id, item, now):
                task_count += 1
        except Exception as e:
            print("材料任务入队跳过，不影响本次同步：", e)
            return task_count

    return task_count


def upsert_hotspot_snapshot_and_trend(
    cursor: Cursor,
    item: Dict[str, Any],
    now: datetime
) -> Dict[str, Any]:
    hotspot_id = find_hotspot_id(cursor, item.get("platform"), item.get("title"))

    if hotspot_id is None:
        hotspot_id = insert_hotspot(cursor, item, now)
        hotspot_action = "inserted"
    else:
        update_hotspot(cursor, hotspot_id, item, now)
        hotspot_action = "updated"

    insert_snapshot(cursor, item, hotspot_id)
    trend_inserted = insert_trend(cursor, hotspot_id, item, now)

    return {
        "hotspotId": hotspot_id,
        "hotspotAction": hotspot_action,
        "trendInserted": trend_inserted
    }


def sync_weibo_hot_search() -> int:
    data: List[Dict[str, Any]] = fetch_weibo_hot_search()
    if not data:
        print("没有抓到任何微博热搜数据，本次结束")
        return 0

    now = datetime.now()
    conn = get_connection()

    try:
        inserted_count = 0
        updated_count = 0
        trend_count = 0
        snapshot_count = 0
        special_count = 0
        normal_count = 0
        ai_task_count = 0
        material_task_count = 0
        summary_items: List[Dict[str, Any]] = []

        with conn.cursor() as cursor:
            for item in data:
                if item.get("isSpecial"):
                    special_count += 1
                else:
                    normal_count += 1

                result = upsert_hotspot_snapshot_and_trend(cursor, item, now)

                if result["hotspotAction"] == "inserted":
                    inserted_count += 1
                else:
                    updated_count += 1

                snapshot_count += 1

                if result["trendInserted"]:
                    trend_count += 1

                if should_generate_summary(item):
                    summary_items.append({
                        "hotspotId": result["hotspotId"],
                        "item": item
                    })

            ai_task_count = enqueue_missing_ai_summary_tasks(cursor, summary_items, now)
            material_task_count = enqueue_missing_material_tasks(cursor, summary_items, now)

        conn.commit()

        print("同步完成")
        print(f"本次抓取总数：{len(data)} 条")
        print(f"普通热搜：{normal_count} 条")
        print(f"特殊/置顶项：{special_count} 条")
        print(f"主表新增：{inserted_count} 条")
        print(f"主表更新：{updated_count} 条")
        print(f"快照新增：{snapshot_count} 条")
        print(f"趋势新增：{trend_count} 条")
        print(f"AI 简介任务入队：{ai_task_count} 条")
        print(f"材料任务入队：{material_task_count} 条")

        return inserted_count

    except Exception as e:
        conn.rollback()
        print("同步失败，已回滚：", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    sync_weibo_hot_search()