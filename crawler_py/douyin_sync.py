from datetime import datetime
from typing import Any, Dict, List, Optional

import pymysql
from pymysql import IntegrityError
from pymysql.connections import Connection
from pymysql.cursors import Cursor

from db_config import DB_CONFIG
from douyin_hot_search import fetch_douyin_hot_search


DOUYIN_PLATFORM = "douyin"
DOUYIN_TOP_N = 50
DOUYIN_AI_TOP_N = 10

# 这里不要用 pending，避免现有 material_worker_playwright.py 把抖音任务取走后标记 failed。
# 下一步我们会写 douyin_material_worker.py，专门处理 pending_douyin。
DOUYIN_MATERIAL_PENDING_STATUS = "pending_douyin"


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
    """
    当前识别规则：
    同一平台 + 标题完全一致 = 同一热点。
    """
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
    """
    更新热点当前状态。
    注意：hotspot 是主体表 + 当前状态表，所以这里会覆盖当前排名、热度、标签和抓取时间。
    """
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
    """
    写入榜单快照。
    抖音当前主要写入普通 50 条热榜；如果后续 douyin_hot_search.py 能识别特殊项，也可以兼容写入。
    """
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
    """
    只给普通榜单写趋势。
    特殊项/置顶项不参与普通排名，不写入 trend，避免污染趋势图。
    """
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
        # 同一 hotspot_id + record_time 已存在时跳过，避免重复趋势点。
        return False


def upsert_hotspot_snapshot_and_trend(
    cursor: Cursor,
    item: Dict[str, Any],
    now: datetime,
) -> Dict[str, Any]:
    platform = item.get("platform") or DOUYIN_PLATFORM
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


def should_generate_douyin_summary(item: Dict[str, Any]) -> bool:
    """
    抖音 AI 简介生成规则：
    - 普通热榜前 10 入队；
    - 如果未来接到了特殊项，也可以入队；
    - 其它普通榜单只保留榜单、趋势，不生成 AI。
    """
    if item.get("isSpecial"):
        return True

    rank_num = item.get("rankNum")
    if rank_num is None:
        return False

    try:
        return 1 <= int(rank_num) <= DOUYIN_AI_TOP_N
    except (TypeError, ValueError):
        return False


def calc_summary_priority(item: Dict[str, Any]) -> int:
    """
    任务优先级：
    - 特殊项最高；
    - 普通榜单排名越靠前，优先级越高。
    """
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
    now: datetime,
) -> bool:
    """
    抖音 AI 简介任务入队。

    如果已经有 summary，就不重复入队。
    如果任务已存在但不是 done，则重新置为 pending，方便失败后重试。
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
        item.get("platform") or DOUYIN_PLATFORM,
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
    抖音材料任务入队。

    注意：
    这里状态使用 pending_douyin，而不是 pending。
    原因是当前已有 material_worker_playwright.py 只支持微博；
    如果抖音任务也用 pending，会被微博 worker 取走并标记 failed。
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
        item.get("platform") or DOUYIN_PLATFORM,
        item.get("title"),
        DOUYIN_MATERIAL_PENDING_STATUS,
        now,
        now,
    ))

    return cursor.rowcount > 0


def enqueue_douyin_tasks(
    cursor: Cursor,
    task_items: List[Dict[str, Any]],
    now: datetime,
) -> Dict[str, int]:
    """
    为抖音前 10 热点入队：
    - AI 简介任务；
    - 材料抓取任务。
    """
    ai_task_count = 0
    material_task_count = 0

    for record in task_items:
        hotspot_id = record.get("hotspotId")
        item = record.get("item")

        if not hotspot_id or not item:
            continue

        try:
            if enqueue_ai_summary_task(cursor, hotspot_id, item, now):
                ai_task_count += 1
        except Exception as e:
            print("抖音 AI 简介任务入队跳过，不影响本次同步：", e)

        try:
            if enqueue_material_task(cursor, hotspot_id, item, now):
                material_task_count += 1
        except Exception as e:
            print("抖音材料任务入队跳过，不影响本次同步：", e)

    return {
        "aiTaskCount": ai_task_count,
        "materialTaskCount": material_task_count,
    }


def sync_douyin_hot_search() -> None:
    """
    同步抖音热榜。

    当前抖音链路定位：
    - 抓取普通热榜 50 条；
    - 写入 hotspot / hotspot_snapshot / hotspot_trend；
    - 对前 10 热点入队 AI 简介任务；
    - 对前 10 热点入队抖音材料任务；
    - 抖音材料任务暂由后续 douyin_material_worker.py 专门处理；
    - 不影响微博完整链路。
    """
    data: List[Dict[str, Any]] = fetch_douyin_hot_search(top_n=DOUYIN_TOP_N)

    if not data:
        print("没有抓到任何抖音热榜数据，本次结束")
        return

    now = datetime.now()
    conn = get_connection()

    try:
        inserted_count = 0
        updated_count = 0
        skipped_count = 0
        snapshot_count = 0
        trend_count = 0
        normal_count = 0
        special_count = 0
        ai_task_count = 0
        material_task_count = 0

        task_items: List[Dict[str, Any]] = []

        with conn.cursor() as cursor:
            for item in data:
                if item.get("isSpecial"):
                    special_count += 1
                else:
                    normal_count += 1

                result = upsert_hotspot_snapshot_and_trend(cursor, item, now)

                if result["hotspotAction"] == "inserted":
                    inserted_count += 1
                elif result["hotspotAction"] == "updated":
                    updated_count += 1
                else:
                    skipped_count += 1
                    continue

                snapshot_count += 1

                if result["trendInserted"]:
                    trend_count += 1

                if should_generate_douyin_summary(item):
                    task_items.append({
                        "hotspotId": result["hotspotId"],
                        "item": item,
                    })

            task_result = enqueue_douyin_tasks(cursor, task_items, now)
            ai_task_count = task_result["aiTaskCount"]
            material_task_count = task_result["materialTaskCount"]

        conn.commit()

        print("抖音同步完成")
        print(f"本次抓取总数：{len(data)} 条")
        print(f"普通热榜：{normal_count} 条")
        print(f"特殊/置顶项：{special_count} 条")
        print(f"主表新增：{inserted_count} 条")
        print(f"主表更新：{updated_count} 条")
        print(f"跳过无效数据：{skipped_count} 条")
        print(f"快照新增：{snapshot_count} 条")
        print(f"趋势新增：{trend_count} 条")
        print(f"抖音 AI 简介任务入队：{ai_task_count} 条")
        print(f"抖音材料任务入队：{material_task_count} 条")
        print(f"抖音材料任务状态：{DOUYIN_MATERIAL_PENDING_STATUS}")

    except Exception as e:
        conn.rollback()
        print("抖音同步失败，已回滚：", e)
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    sync_douyin_hot_search()