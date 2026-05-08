from datetime import date, datetime
from typing import Optional, Union

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import Cursor

from db_config import DB_CONFIG


ArchiveDateType = Optional[Union[str, date, datetime]]


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


def normalize_archive_date(archive_date: ArchiveDateType) -> Optional[str]:
    """
    统一归档日期格式。

    支持：
    - None：默认归档昨天
    - "2026-04-08"
    - date(2026, 4, 8)
    - datetime(2026, 4, 8, ...)
    """
    if archive_date is None:
        return None

    if isinstance(archive_date, datetime):
        return archive_date.date().isoformat()

    if isinstance(archive_date, date):
        return archive_date.isoformat()

    return str(archive_date)[:10]


def archive_normal_hotspots(
    cursor: Cursor,
    archive_date: ArchiveDateType = None,
    interval_minutes: int = 5
) -> int:
    """
    归档普通热点，数据来源：hotspot_trend。

    注意：
    SQL 中占位符顺序是：
    1. COUNT(*) * %s AS duration_minutes  -> interval_minutes
    2. DATE(ht.record_time) = %s          -> archive_date

    所以 params 必须是：
    (interval_minutes, archive_date)
    """
    archive_date_text = normalize_archive_date(archive_date)

    if archive_date_text:
        where_sql = "DATE(ht.record_time) = %s"
        params = (interval_minutes, archive_date_text)
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
    archive_date: ArchiveDateType = None,
    interval_minutes: int = 5
) -> int:
    """
    归档特殊项/置顶项，数据来源：hotspot_snapshot。

    注意：
    SQL 中占位符顺序是：
    1. COUNT(*) * %s AS duration_minutes -> interval_minutes
    2. DATE(hs.crawl_time) = %s          -> archive_date

    所以 params 必须是：
    (interval_minutes, archive_date)
    """
    archive_date_text = normalize_archive_date(archive_date)

    if archive_date_text:
        where_sql = "DATE(hs.crawl_time) = %s"
        params = (interval_minutes, archive_date_text)
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
    清理超过保留天数的 snapshot 数据。
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
    清理超过保留天数的 trend 数据。
    """
    sql = """
        DELETE FROM hotspot_trend
        WHERE record_time < CURDATE() - INTERVAL %s DAY
    """
    cursor.execute(sql, (keep_days,))
    return cursor.rowcount


def run_daily_archive(
    archive_date: ArchiveDateType = None,
    interval_minutes: int = 5,
    keep_days: int = 7,
    do_cleanup: bool = False
) -> None:
    """
    主流程：
    1. 归档普通热点
    2. 归档特殊项/置顶项
    3. 可选清理旧 snapshot / trend

    archive_date:
        - None：默认归档昨天
        - "2026-04-08"：手动归档指定日期
        - date(2026, 4, 8)：也支持

    interval_minutes:
        - 当前抓取频率
        - 用于计算 duration_minutes

    keep_days:
        - 清理实时层数据时，保留最近多少天

    do_cleanup:
        - False：只归档，不清理
        - True：归档后清理旧 snapshot / trend
    """
    archive_date_text = normalize_archive_date(archive_date)

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            normal_rows = archive_normal_hotspots(
                cursor,
                archive_date=archive_date_text,
                interval_minutes=interval_minutes
            )

            special_rows = archive_special_hotspots(
                cursor,
                archive_date=archive_date_text,
                interval_minutes=interval_minutes
            )

            snapshot_deleted = 0
            trend_deleted = 0

            if do_cleanup:
                snapshot_deleted = cleanup_old_snapshot(cursor, keep_days=keep_days)
                trend_deleted = cleanup_old_trend(cursor, keep_days=keep_days)

        conn.commit()

        target_date = archive_date_text if archive_date_text else "昨天"
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
        archive_date="2026-04-08",
        interval_minutes=5,
        keep_days=7,
        do_cleanup=False
    )