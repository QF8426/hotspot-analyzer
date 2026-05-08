from daily_archive import run_daily_archive


ARCHIVE_DATES = [
    "2026-04-08",
    "2026-04-26",
    "2026-04-28",
    "2026-05-05",
    "2026-05-06",
    "2026-05-07",
]


def main():
    for day_text in ARCHIVE_DATES:
        print("=" * 60)
        print(f"开始补归档：{day_text}")
        print("=" * 60)

        run_daily_archive(
            archive_date=day_text,
            interval_minutes=5,
            keep_days=9999,
            do_cleanup=False,
        )

        print(f"补归档完成：{day_text}")


if __name__ == "__main__":
    main()