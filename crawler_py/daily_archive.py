from datetime import datetime
from typing import Optional

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import Cursor

from db_config import DB_CONFIG


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


def archive_normal_hotspots(
    cursor: Cursor,
    archive_date: Optional[str] = None,
    interval_minutes: int = 5
) -> int:
    """
    归档普通热点（来自 hotspot_trend）
    archive_date 格式：YYYY-MM-DD
    如果不传，则默认归档昨天
    """
    if archive_date:
        where_sql = "DATE(ht.record_time) = %s"
        params = (archive_date, interval_minutes)
    else:
        where_sql = "ht.record_time >= CURDATE() - INTERVAL 1 DAY AND ht.record_time < CURDATE()"
        params = (interval_minutes,)

    sql = f"""
        INSERT INTO hotspot_daily_summary (
            summary_date,
            hotspot_id,
            platform,
            title,
            max_hot_value,
            best_rank_num,
            appear_count,
            duration_minutes,
            first_seen_time,
            last_seen_time,
            is_special
        )
        SELECT
            DATE(ht.record_time) AS summary_date,
            ht.hotspot_id,
            h.platform,
            h.title,
            MAX(ht.hot_value) AS max_hot_value,
            MIN(ht.rank_num) AS best_rank_num,
            COUNT(*) AS appear_count,
            COUNT(*) * %s AS duration_minutes,
            MIN(ht.record_time) AS first_seen_time,
            MAX(ht.record_time) AS last_seen_time,
            0 AS is_special
        FROM hotspot_trend ht
        JOIN hotspot h ON ht.hotspot_id = h.id
        WHERE {where_sql}
        GROUP BY
            DATE(ht.record_time),
            ht.hotspot_id,
            h.platform,
            h.title
        ON DUPLICATE KEY UPDATE
            platform = VALUES(platform),
            title = VALUES(title),
            max_hot_value = VALUES(max_hot_value),
            best_rank_num = VALUES(best_rank_num),
            appear_count = VALUES(appear_count),
            duration_minutes = VALUES(duration_minutes),
            first_seen_time = VALUES(first_seen_time),
            last_seen_time = VALUES(last_seen_time),
            is_special = VALUES(is_special),
            updated_at = CURRENT_TIMESTAMP
    """

    cursor.execute(sql, params)
    return cursor.rowcount


def archive_special_hotspots(
    cursor: Cursor,
    archive_date: Optional[str] = None,
    interval_minutes: int = 5
) -> int:
    """
    归档特殊项/置顶项（来自 hotspot_snapshot）
    archive_date 格式：YYYY-MM-DD
    如果不传，则默认归档昨天
    """
    if archive_date:
        where_sql = "DATE(hs.crawl_time) = %s"
        params = (archive_date, interval_minutes)
    else:
        where_sql = "hs.crawl_time >= CURDATE() - INTERVAL 1 DAY AND hs.crawl_time < CURDATE()"
        params = (interval_minutes,)

    sql = f"""
        INSERT INTO hotspot_daily_summary (
            summary_date,
            hotspot_id,
            platform,
            title,
            max_hot_value,
            best_rank_num,
            appear_count,
            duration_minutes,
            first_seen_time,
            last_seen_time,
            is_special
        )
        SELECT
            DATE(hs.crawl_time) AS summary_date,
            hs.hotspot_id,
            hs.platform,
            hs.title,
            NULL AS max_hot_value,
            NULL AS best_rank_num,
            COUNT(*) AS appear_count,
            COUNT(*) * %s AS duration_minutes,
            MIN(hs.crawl_time) AS first_seen_time,
            MAX(hs.crawl_time) AS last_seen_time,
            1 AS is_special
        FROM hotspot_snapshot hs
        WHERE {where_sql}
          AND hs.is_special = 1
        GROUP BY
            DATE(hs.crawl_time),
            hs.hotspot_id,
            hs.platform,
            hs.title
        ON DUPLICATE KEY UPDATE
            platform = VALUES(platform),
            title = VALUES(title),
            max_hot_value = VALUES(max_hot_value),
            best_rank_num = VALUES(best_rank_num),
            appear_count = VALUES(appear_count),
            duration_minutes = VALUES(duration_minutes),
            first_seen_time = VALUES(first_seen_time),
            last_seen_time = VALUES(last_seen_time),
            is_special = VALUES(is_special),
            updated_at = CURRENT_TIMESTAMP
    """

    cursor.execute(sql, params)
    return cursor.rowcount


def cleanup_old_snapshot(
    cursor: Cursor,
    keep_days: int = 7
) -> int:
    """
    清理超过保留天数的 snapshot 数据
    """
    sql = """
        DELETE FROM hotspot_snapshot
        WHERE crawl_time < CURDATE() - INTERVAL %s DAY
    """
    cursor.execute(sql, (keep_days,))
    return cursor.rowcount


def cleanup_old_trend(
    cursor: Cursor,
    keep_days: int = 7
) -> int:
    """
    清理超过保留天数的 trend 数据
    """
    sql = """
        DELETE FROM hotspot_trend
        WHERE record_time < CURDATE() - INTERVAL %s DAY
    """
    cursor.execute(sql, (keep_days,))
    return cursor.rowcount


def run_daily_archive(
    archive_date: Optional[str] = None,
    interval_minutes: int = 5,
    keep_days: int = 7,
    do_cleanup: bool = False
) -> None:
    """
    主流程：
    1. 归档普通热点
    2. 归档特殊项
    3. 可选：清理旧 snapshot / trend

    archive_date:
        - None：默认归档昨天
        - '2026-04-05'：手动归档指定日期

    interval_minutes:
        - 你当前抓取频率（分钟）
        - 用于计算 duration_minutes

    keep_days:
        - 清理实时层数据时，保留最近多少天

    do_cleanup:
        - False：只归档，不清理
        - True：归档后顺便清理旧数据
    """
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            normal_rows = archive_normal_hotspots(
                cursor,
                archive_date=archive_date,
                interval_minutes=interval_minutes
            )

            special_rows = archive_special_hotspots(
                cursor,
                archive_date=archive_date,
                interval_minutes=interval_minutes
            )

            snapshot_deleted = 0
            trend_deleted = 0

            if do_cleanup:
                snapshot_deleted = cleanup_old_snapshot(cursor, keep_days=keep_days)
                trend_deleted = cleanup_old_trend(cursor, keep_days=keep_days)

        conn.commit()

        target_date = archive_date if archive_date else "昨天"
        print("日归档完成")
        print(f"归档日期：{target_date}")
        print(f"普通热点归档影响行数：{normal_rows}")
        print(f"特殊项归档影响行数：{special_rows}")

        if do_cleanup:
            print(f"清理 snapshot 行数：{snapshot_deleted}")
            print(f"清理 trend 行数：{trend_deleted}")
        else:
            print("本次未执行清理")

    except Exception as e:
        conn.rollback()
        print("日归档失败，已回滚：", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_daily_archive(
        archive_date="2026-04-05",
        interval_minutes=5,
        keep_days=7,
        do_cleanup=False
    )

    # 你以后如果要手动测试某一天，可以改成：
    # run_daily_archive(
    #     archive_date="2026-04-05",
    #     interval_minutes=5,
    #     keep_days=7,
    #     do_cleanup=False
    # )