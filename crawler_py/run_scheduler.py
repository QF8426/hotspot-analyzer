import time
from datetime import datetime

from weibo_sync import sync_weibo_hot_search
from douyin_sync import sync_douyin_hot_search
from bilibili_sync import sync_bilibili_hot_search

from daily_archive import run_daily_archive
from ai_summary_worker import run_ai_summary_worker
from material_worker_playwright import run_material_worker
from douyin_material_worker import run_douyin_material_worker
from bilibili_material_worker import run_bilibili_material_worker


SYNC_INTERVAL_MINUTES = 5

AI_WORKER_INTERVAL_MINUTES = 1
AI_WORKER_BATCH_SIZE = 3

MATERIAL_WORKER_INTERVAL_MINUTES = 2
MATERIAL_WORKER_BATCH_SIZE = 2
MATERIAL_WORKER_HEADLESS = False

ARCHIVE_HOUR = 0
ARCHIVE_MINUTE = 15
KEEP_DAYS = 7
DO_CLEANUP_AFTER_ARCHIVE = True


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def should_run_sync(now: datetime, last_sync_key: str | None) -> tuple[bool, str]:
    if now.minute % SYNC_INTERVAL_MINUTES != 0:
        return False, last_sync_key or ""

    current_key = now.strftime("%Y-%m-%d %H:%M")
    if current_key == last_sync_key:
        return False, current_key

    return True, current_key


def should_run_ai_worker(now: datetime, last_ai_worker_key: str | None) -> tuple[bool, str]:
    if now.minute % AI_WORKER_INTERVAL_MINUTES != 0:
        return False, last_ai_worker_key or ""

    current_key = now.strftime("%Y-%m-%d %H:%M")
    if current_key == last_ai_worker_key:
        return False, current_key

    return True, current_key


def should_run_material_worker(now: datetime, last_material_worker_key: str | None) -> tuple[bool, str]:
    if now.minute % MATERIAL_WORKER_INTERVAL_MINUTES != 0:
        return False, last_material_worker_key or ""

    current_key = now.strftime("%Y-%m-%d %H:%M")
    if current_key == last_material_worker_key:
        return False, current_key

    return True, current_key


def should_run_archive(now: datetime, last_archive_date: str | None) -> tuple[bool, str]:
    if now.hour != ARCHIVE_HOUR or now.minute != ARCHIVE_MINUTE:
        return False, last_archive_date or ""

    today_key = now.strftime("%Y-%m-%d")
    if today_key == last_archive_date:
        return False, today_key

    return True, today_key


def run_hotspot_sync() -> None:
    """
    同步平台热榜。

    微博：
    - 热点/快照/趋势
    - 材料任务
    - AI 简介任务

    抖音：
    - 热点/快照/趋势
    - 前 10 入队抖音材料任务
    - 前 10 入队 AI 简介任务

    B站：
    - 热搜词条
    - 热点/快照/趋势
    - 前 10 入队 B站材料任务
    - 前 10 入队 AI 简介任务
    - AI worker 会等待材料任务完成后再生成简介
    """
    print(f"[{now_text()}] 开始执行微博同步...")
    try:
        sync_weibo_hot_search()
        print(f"[{now_text()}] 微博同步完成")
    except Exception as e:
        print(f"[{now_text()}] 微博同步失败：{e}")

    print(f"[{now_text()}] 开始执行抖音同步...")
    try:
        sync_douyin_hot_search()
        print(f"[{now_text()}] 抖音同步完成")
    except Exception as e:
        print(f"[{now_text()}] 抖音同步失败：{e}")

    print(f"[{now_text()}] 开始执行 B站同步...")
    try:
        sync_bilibili_hot_search()
        print(f"[{now_text()}] B站同步完成")
    except Exception as e:
        print(f"[{now_text()}] B站同步失败：{e}")


def run_all_material_workers() -> None:
    """
    处理材料任务。

    微博材料任务：
    - 由 material_worker_playwright.py 处理
    - 处理 status = pending 的微博任务

    抖音材料任务：
    - 由 douyin_material_worker.py 处理
    - 处理 status = pending_douyin 的抖音任务

    B站材料任务：
    - 由 bilibili_material_worker.py 处理
    - 处理 status = pending_bilibili 的 B站任务

    注意：
    材料 worker 必须先于 AI worker 执行。
    这样 AI worker 执行时才能读取到帖子/视频材料和评论材料。
    """
    print(f"[{now_text()}] 开始处理微博材料任务...")
    try:
        run_material_worker(
            limit=MATERIAL_WORKER_BATCH_SIZE,
            headless=MATERIAL_WORKER_HEADLESS,
        )
        print(f"[{now_text()}] 微博材料任务处理完成")
    except Exception as e:
        print(f"[{now_text()}] 微博材料任务处理失败：{e}")

    print(f"[{now_text()}] 开始处理抖音材料任务...")
    try:
        run_douyin_material_worker(limit=MATERIAL_WORKER_BATCH_SIZE)
        print(f"[{now_text()}] 抖音材料任务处理完成")
    except Exception as e:
        print(f"[{now_text()}] 抖音材料任务处理失败：{e}")

    print(f"[{now_text()}] 开始处理 B站材料任务...")
    try:
        run_bilibili_material_worker(limit=MATERIAL_WORKER_BATCH_SIZE)
        print(f"[{now_text()}] B站材料任务处理完成")
    except Exception as e:
        print(f"[{now_text()}] B站材料任务处理失败：{e}")


def main() -> None:
    print("调度器启动")
    print(f"微博/抖音/B站同步间隔：每 {SYNC_INTERVAL_MINUTES} 分钟一次")
    print(f"材料任务处理间隔：每 {MATERIAL_WORKER_INTERVAL_MINUTES} 分钟一次")
    print(f"材料任务每批处理：每个平台最多 {MATERIAL_WORKER_BATCH_SIZE} 条")
    print(f"AI 简介处理间隔：每 {AI_WORKER_INTERVAL_MINUTES} 分钟一次")
    print(f"AI 简介每批处理：最多 {AI_WORKER_BATCH_SIZE} 条")
    print(f"日归档时间：每天 {ARCHIVE_HOUR:02d}:{ARCHIVE_MINUTE:02d}")
    print(f"归档后清理旧数据：{'开启' if DO_CLEANUP_AFTER_ARCHIVE else '关闭'}")
    print("-" * 50)

    last_sync_key = None
    last_material_worker_key = None
    last_ai_worker_key = None
    last_archive_date = None

    while True:
        now = datetime.now()

        sync_ready, sync_key = should_run_sync(now, last_sync_key)
        if sync_ready:
            run_hotspot_sync()
            # 无论某个平台是否失败，本分钟都不重复触发，避免失败后 20 秒循环反复打接口。
            last_sync_key = sync_key
            print("-" * 50)

        now = datetime.now()
        material_ready, material_worker_key = should_run_material_worker(now, last_material_worker_key)
        if material_ready:
            print(f"[{now_text()}] 开始处理材料任务...")
            try:
                run_all_material_workers()
                last_material_worker_key = material_worker_key
                print(f"[{now_text()}] 材料任务处理完成")
            except Exception as e:
                print(f"[{now_text()}] 材料任务处理失败：{e}")

            print("-" * 50)

        now = datetime.now()
        ai_ready, ai_worker_key = should_run_ai_worker(now, last_ai_worker_key)
        if ai_ready:
            print(f"[{now_text()}] 开始处理 AI 简介任务...")
            try:
                run_ai_summary_worker(limit=AI_WORKER_BATCH_SIZE)
                last_ai_worker_key = ai_worker_key
                print(f"[{now_text()}] AI 简介任务处理完成")
            except Exception as e:
                print(f"[{now_text()}] AI 简介任务处理失败：{e}")

            print("-" * 50)

        now = datetime.now()
        archive_ready, archive_date_key = should_run_archive(now, last_archive_date)
        if archive_ready:
            print(f"[{now_text()}] 开始执行日归档...")
            try:
                run_daily_archive(
                    archive_date=None,
                    interval_minutes=SYNC_INTERVAL_MINUTES,
                    keep_days=KEEP_DAYS,
                    do_cleanup=DO_CLEANUP_AFTER_ARCHIVE,
                )
                last_archive_date = archive_date_key
                print(f"[{now_text()}] 日归档完成")
            except Exception as e:
                print(f"[{now_text()}] 日归档失败：{e}")

            print("-" * 50)

        time.sleep(20)


if __name__ == "__main__":
    main()