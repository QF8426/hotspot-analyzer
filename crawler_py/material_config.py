import os


def _get_positive_int(env_name: str, default: int) -> int:
    value = os.getenv(env_name, '').strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


# 三个平台统一保存标准：每个热点最多保存 3 条主体材料。
# 微博 = 3 条帖子；抖音/B站 = 3 条相关视频。
MATERIALS_PER_HOTSPOT = _get_positive_int('MATERIALS_PER_HOTSPOT', 3)

# 三个平台统一评论保存标准：每条主体材料最多保存 5 条高赞/热门评论。
# 如果平台实际返回不足 5 条，则按实际数量保存，不强行补假数据。
COMMENTS_PER_MATERIAL = _get_positive_int('COMMENTS_PER_MATERIAL', 5)

# 候选池可以按平台保留差异：候选池只是“先抓多少用于筛选”，最终入库数量仍受 COMMENTS_PER_MATERIAL 控制。
DOUYIN_COMMENT_FETCH_COUNT = _get_positive_int('DOUYIN_COMMENT_FETCH_COUNT', 30)
BILIBILI_COMMENT_CANDIDATE_SIZE = _get_positive_int('BILIBILI_COMMENT_CANDIDATE_SIZE', 50)
