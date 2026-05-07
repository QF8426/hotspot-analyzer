from datetime import datetime
from typing import Any, Dict, List, Optional

import pymysql
from pymysql import IntegrityError
from pymysql.connections import Connection
from pymysql.cursors import Cursor

from db_config import DB_CONFIG
from bilibili_hot_search import fetch_bilibili_hot_search


BILIBILI_PLATFORM = "bilibili"
BILIBILI_TOP_N = 50

# B站前 10 进入材料任务 + AI 任务
BILIBILI_MATERIAL_TOP_N = 10
BILIBILI_AI_TOP_N = 10

# B站材料任务单独使用 pending_bilibili，避免被微博/抖音 worker 误取
BILIBILI_MATERIAL_PENDING_STATUS = "pending_bilibili"


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
        now,
    ))
    return int(cursor.lastrowid)


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
        hotspot_id,
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
        item.get("crawlTime"),
    ))


def insert_trend(cursor: Cursor, hotspot_id: int, item: Dict[str, Any], now: datetime) -> bool:
    if item.get("isSpecial"):
        return False

    if not item.get("isRanked"):
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
            now,
        ))
        return True
    except IntegrityError:
        return False


def is_top_n(item: Dict[str, Any], top_n: int) -> bool:
    rank_num = item.get("rankNum")
    if rank_num is None:
        return False

    try:
        return 1 <= int(rank_num) <= top_n
    except (TypeError, ValueError):
        return False


def should_enqueue_bilibili_material(item: Dict[str, Any]) -> bool:
    """
    B站材料抓取规则：
    只对热搜前 10 入队材料任务。
    """
    return is_top_n(item, BILIBILI_MATERIAL_TOP_N)


def should_enqueue_bilibili_ai_summary(item: Dict[str, Any]) -> bool:
    """
    B站 AI 简介规则：
    只对热搜前 10 入队 AI 简介任务。
    具体是否生成，由 ai_summary_worker 判断材料是否准备完成。
    """
    return is_top_n(item, BILIBILI_AI_TOP_N)


def calc_summary_priority(item: Dict[str, Any]) -> int:
    """
    AI 任务优先级：
    排名越靠前，优先级越高。
    """
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
    now: datetime,
) -> bool:
    """
    B站 AI 简介任务入队。

    注意：
    这里只负责把任务放进 hotspot_ai_summary_task。
    AI 是否真正生成，由 ai_summary_worker 判断：
    - 必须已经有材料；
    - 对应材料任务不能还处于 pending / processing。
    """
    if has_ai_summary(cursor, hotspot_id):
        return False

    sql = """
        INSERT INTO hotspot_ai_summary_task (
            hotspot_id,
            platform,
            title,
            priority,
            status,
            error_message,
            created_at,
            updated_at
        ) VALUES (%s, %s, %s, %s, 'pending', NULL, %s, %s)
        ON DUPLICATE KEY UPDATE
            platform = VALUES(platform),
            title = VALUES(title),
            priority = GREATEST(priority, VALUES(priority)),
            status = CASE
                WHEN status = 'done' THEN status
                ELSE 'pending'
            END,
            error_message = CASE
                WHEN status = 'done' THEN error_message
                ELSE NULL
            END,
            updated_at = VALUES(updated_at)
    """
    cursor.execute(sql, (
        hotspot_id,
        item.get("platform") or BILIBILI_PLATFORM,
        item.get("title"),
        calc_summary_priority(item),
        now,
        now,
    ))

    return cursor.rowcount > 0


def enqueue_material_task(
    cursor: Cursor,
    hotspot_id: int,
    item: Dict[str, Any],
    now: datetime,
) -> bool:
    """
    B站材料任务入队。

    注意：
    状态使用 pending_bilibili。
    这样不会被微博 material_worker_playwright.py 误取，也不会被抖音 worker 误取。
    """
    sql = """
        INSERT INTO hotspot_material_task (
            hotspot_id,
            platform,
            title,
            status,
            error_message,
            created_at,
            updated_at
        ) VALUES (%s, %s, %s, %s, NULL, %s, %s)
        ON DUPLICATE KEY UPDATE
            platform = VALUES(platform),
            title = VALUES(title),
            status = CASE
                WHEN status = 'done' THEN status
                ELSE VALUES(status)
            END,
            error_message = CASE
                WHEN status = 'done' THEN error_message
                ELSE NULL
            END,
            updated_at = VALUES(updated_at)
    """
    cursor.execute(sql, (
        hotspot_id,
        item.get("platform") or BILIBILI_PLATFORM,
        item.get("title"),
        BILIBILI_MATERIAL_PENDING_STATUS,
        now,
        now,
    ))

    return cursor.rowcount > 0


def upsert_hotspot_snapshot_and_trend(
    cursor: Cursor,
    item: Dict[str, Any],
    now: datetime,
) -> Dict[str, Any]:
    platform = item.get("platform") or BILIBILI_PLATFORM
    title = item.get("title")

    if not title:
        return {
            "hotspotId": None,
            "hotspotAction": "skipped",
            "trendInserted": False,
        }

    hotspot_id = find_hotspot_id(cursor, platform, title)

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
        "trendInserted": trend_inserted,
    }


def sync_bilibili_hot_search(limit: int = BILIBILI_TOP_N) -> None:
    """
    同步 B站热搜。

    当前 B站链路：
    - 抓取 B站热搜词条；
    - 写入 hotspot；
    - 写入 hotspot_snapshot；
    - 写入 hotspot_trend；
    - 对前 10 入队 B站材料任务 pending_bilibili；
    - 对前 10 入队 AI 简介任务 pending；
    - AI worker 会等待材料任务完成后再生成简介。
    """
    data: List[Dict[str, Any]] = fetch_bilibili_hot_search(limit=limit)

    if not data:
        print("没有抓到任何 B站热搜数据，本次结束")
        return

    now = datetime.now()
    conn = get_connection()

    try:
        inserted_count = 0
        updated_count = 0
        skipped_count = 0
        snapshot_count = 0
        trend_count = 0
        material_task_count = 0
        ai_task_count = 0

        with conn.cursor() as cursor:
            for item in data:
                result = upsert_hotspot_snapshot_and_trend(cursor, item, now)

                if result["hotspotAction"] == "inserted":
                    inserted_count += 1
                elif result["hotspotAction"] == "updated":
                    updated_count += 1
                else:
                    skipped_count += 1
                    continue

                hotspot_id = result["hotspotId"]
                snapshot_count += 1

                if result["trendInserted"]:
                    trend_count += 1

                if should_enqueue_bilibili_material(item):
                    try:
                        if enqueue_material_task(cursor, hotspot_id, item, now):
                            material_task_count += 1
                    except Exception as e:
                        print("B站材料任务入队跳过，不影响本次同步：", e)

                if should_enqueue_bilibili_ai_summary(item):
                    try:
                        if enqueue_ai_summary_task(cursor, hotspot_id, item, now):
                            ai_task_count += 1
                    except Exception as e:
                        print("B站 AI 简介任务入队跳过，不影响本次同步：", e)

        conn.commit()

        print("B站同步完成")
        print(f"本次抓取总数：{len(data)} 条")
        print(f"主表新增：{inserted_count} 条")
        print(f"主表更新：{updated_count} 条")
        print(f"跳过无效数据：{skipped_count} 条")
        print(f"快照新增：{snapshot_count} 条")
        print(f"趋势新增：{trend_count} 条")
        print(f"B站材料任务入队：{material_task_count} 条")
        print(f"B站材料任务状态：{BILIBILI_MATERIAL_PENDING_STATUS}")
        print(f"B站 AI 简介任务入队：{ai_task_count} 条")

    except Exception as e:
        conn.rollback()
        print("B站同步失败，已回滚：", e)
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    sync_bilibili_hot_search()