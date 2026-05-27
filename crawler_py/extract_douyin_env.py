import re
from urllib.parse import urlparse, parse_qs

CURL_FILE = "douyin_curl.txt"
OUT_FILE = "douyin_env_output.txt"

def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def find_first(pattern, text, default=""):
    m = re.search(pattern, text, flags=re.S)
    return m.group(1).strip() if m else default

def main():
    text = read_text(CURL_FILE)

    # 1. 提取 URL
    url = find_first(r"curl\s+'([^']+)'", text)
    if not url:
        raise RuntimeError("没有找到 curl 后面的 URL，请确认复制的是 bash cURL。")

    qs = parse_qs(urlparse(url).query)

    def q(name):
        return qs.get(name, [""])[0]

    # 2. 提取 cookie：bash cURL 一般是 -b '...'
    cookie = find_first(r"\s-b\s+'([^']+)'", text)

    # 如果不是 -b，而是 -H 'cookie: ...'
    if not cookie:
        cookie = find_first(r"-H\s+'cookie:\s*([^']+)'", text)

    # 3. 提取请求头
    bd_client_data = find_first(r"-H\s+'bd-ticket-guard-client-data:\s*([^']+)'", text)
    bd_public_key = find_first(r"-H\s+'bd-ticket-guard-ree-public-key:\s*([^']+)'", text)
    bd_version = find_first(r"-H\s+'bd-ticket-guard-version:\s*([^']+)'", text, "2")
    bd_web_sign_type = find_first(r"-H\s+'bd-ticket-guard-web-sign-type:\s*([^']+)'", text, "1")
    bd_web_version = find_first(r"-H\s+'bd-ticket-guard-web-version:\s*([^']+)'", text, "2")

    env = f"""# ===== Douyin cookie / comment api params =====
DOUYIN_COOKIE="{cookie}"

# 评论接口关键参数
DOUYIN_WEBID={q("webid")}
DOUYIN_UIFID={q("uifid")}
DOUYIN_VERIFY_FP={q("verifyFp")}
DOUYIN_FP={q("fp")}
DOUYIN_MS_TOKEN={q("msToken")}
DOUYIN_A_BOGUS={q("a_bogus")}
DOUYIN_X_SECSIG={q("x-secsdk-web-signature")}

# bd-ticket-guard 请求头
DOUYIN_BD_TICKET_GUARD_CLIENT_DATA={bd_client_data}
DOUYIN_BD_TICKET_GUARD_REE_PUBLIC_KEY={bd_public_key}
DOUYIN_BD_TICKET_GUARD_VERSION={bd_version}
DOUYIN_BD_TICKET_GUARD_WEB_SIGN_TYPE={bd_web_sign_type}
DOUYIN_BD_TICKET_GUARD_WEB_VERSION={bd_web_version}
"""

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(env)

    print(f"已生成：{OUT_FILE}")
    print("把 douyin_env_output.txt 里的内容复制到 crawler_py/.env 中替换原来的 DOUYIN_* 配置。")
    print("注意：不要提交 .env 到 GitHub。")

if __name__ == "__main__":
    main()