import csv
import re
import time
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

BASE = "https://viet69.nu"
LIST_SELECTOR = "a.clip-link"
TITLE_SELECTORS = ["h1.entry-title", "h1.post-title", "article h1"]
TAGS_CONTAINER = "div.entry-tags"
VIDEO_API_RE = re.compile(r"https://emb\.cd-vs\.com/api/get-video\?")

# ==== Cấu hình ====
START_PAGE = 1
END_PAGE = 2            # số trang muốn quét
LIST_TIMEOUT_MS = 25000
WAIT_MEDIA_SECS = 25    # thời gian tối đa đợi request get-video
OUT_CSV = "viet69_scrape.csv"
HEADLESS = True
# ===================

def get_video_url_with_retries(page, url: str, max_tries: int = 3, delay_between: float = 1.5) -> Optional[str]:
    for attempt in range(1, max_tries + 1):
        video_url = capture_video_url_while_loading(page, url)
        if video_url:
            if attempt > 1:
                print(f"     • Lấy được URL sau lần thử {attempt}.")
            return video_url
        if attempt < max_tries:
            print(f"     • Không thấy URL, thử lại ({attempt}/{max_tries})…")
            try:
                page.reload(wait_until="domcontentloaded", timeout=LIST_TIMEOUT_MS)
            except Exception:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=LIST_TIMEOUT_MS)
                except Exception:
                    pass
            time.sleep(delay_between)
    return None

def extract_title(page) -> str:
    for sel in TITLE_SELECTORS:
        loc = page.locator(sel)
        if loc.count():
            try:
                t = loc.first.inner_text().strip()
                if t:
                    return t
            except Exception:
                pass
    try:
        return page.title().strip()
    except Exception:
        return ""

def extract_tags(page) -> List[str]:
    tags = []
    try:
        cont = page.locator(TAGS_CONTAINER)
        if cont.count():
            tags = [a.inner_text().strip() for a in cont.first.locator('a[rel="tag"]').all()]
    except Exception:
        pass
    return tags

def capture_video_url_while_loading(page, target_url: str) -> Optional[str]:
    import json, time, re
    context = page.context
    captured = {"url": None}
    VIDEO_API_RE = re.compile(r"https://emb\.cd-vs\.com/api/get-video\?")

    def on_response(resp):
        try:
            if VIDEO_API_RE.match(resp.url) and resp.status == 200 and not captured["url"]:
                try:
                    data = resp.json()
                except Exception:
                    data = json.loads(resp.text())
                captured["url"] = data.get("url")
        except Exception:
            pass

    context.on("response", on_response)
    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
        t0 = time.time()
        while time.time() - t0 < 25:
            if captured["url"]:
                break
            try:
                page.mouse.wheel(0, 600)  # kích lazy-load nếu có
            except Exception:
                pass
            time.sleep(0.3)
    finally:
        if hasattr(context, "remove_listener"):
            context.remove_listener("response", on_response)
        else:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

    return captured["url"]

def process_post(page, url, thumb_url) -> Dict:
    video_url = get_video_url_with_retries(page, url, max_tries=3, delay_between=1.5)
    title = extract_title(page)
    tags = extract_tags(page)
    return {
        "post_url": url,
        "thumb_url": thumb_url or "",
        "title": title,
        "video_url": video_url or "",
        "tags": ", ".join(tags),
    }

def _get_best_img_src(a_tag) -> Optional[str]:
    """Ưu tiên srcset (nếu có), rồi tới src, rồi data-src/data-lazy."""
    img = a_tag.locator("img").first
    if img.count() == 0:
        return None
    for attr in ["srcset", "data-srcset"]:
        try:
            val = img.get_attribute(attr)
            if val:
                # chọn URL có độ rộng lớn nhất trong srcset
                parts = [p.strip() for p in val.split(",")]
                best = None
                best_w = -1
                for p in parts:
                    # dạng: https://... 500w
                    bits = p.split()
                    if not bits:
                        continue
                    url = bits[0]
                    w = -1
                    if len(bits) > 1 and bits[1].endswith("w"):
                        try:
                            w = int(bits[1][:-1])
                        except:
                            pass
                    if w > best_w:
                        best_w = w
                        best = url
                if best:
                    return best
        except Exception:
            pass
    for attr in ["src", "data-src", "data-lazy", "data-original"]:
        try:
            val = img.get_attribute(attr)
            if val:
                return val
        except Exception:
            pass
    return None

def gather_post_cards_on_listing(page) -> List[Dict[str, str]]:
    """Trả về danh sách dict: {'href': ..., 'thumb_url': ...} theo thứ tự xuất hiện."""
    cards = []
    for a in page.locator(LIST_SELECTOR).all():
        try:
            href = a.get_attribute("href")
            if not href:
                continue
            # lấy ảnh ngay trên listing
            img_src = _get_best_img_src(a)
            if img_src:
                img_src = urljoin(BASE, img_src)
            href = urljoin(BASE, href)
            cards.append({"href": href, "thumb_url": img_src or ""})
        except Exception:
            continue

    # loại trùng, giữ thứ tự
    uniq, seen = [], set()
    for c in cards:
        key = (c["href"], c["thumb_url"])
        if key not in seen:
            uniq.append(c)
            seen.add(key)
    return uniq

def run():
    # thêm cột thumb_url
    Path(OUT_CSV).write_text("post_url,thumb_url,title,video_url,tags\n", encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--lang=vi-VN"])
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120 Safari/537.36"),
            ignore_https_errors=True,
        )
        page = context.new_page()
        writer = csv.DictWriter(
            open(OUT_CSV, "a", encoding="utf-8", newline=""),
            fieldnames=["post_url", "thumb_url", "title", "video_url", "tags"]
        )

        for page_no in range(START_PAGE, END_PAGE + 1):
            list_url = f"{BASE}/page/{page_no}/" if page_no > 1 else BASE
            print(f"=== Đang duyệt trang {page_no}: {list_url}")
            page.goto(list_url, wait_until="domcontentloaded", timeout=LIST_TIMEOUT_MS)

            post_cards = gather_post_cards_on_listing(page)
            print(f" Tìm thấy {len(post_cards)} bài.")

            for idx, card in enumerate(post_cards, 1):
                link = card["href"]; thumb = card["thumb_url"]
                print(f"  [{idx}/{len(post_cards)}] {link}")
                if thumb:
                    print(f"     • Ảnh (listing): {thumb}")
                try:
                    rec = process_post(page, link, thumb)
                    print(f'     • Tiêu đề: {rec["title"]}')
                    print(f'     • URL video (JSON): {rec["video_url"] or "(không thấy)"}')
                    print(f'     • Tags: {rec["tags"]}')
                    writer.writerow(rec)
                except Exception as e:
                    print(f"     ! Lỗi xử lý bài: {e}")

        print(f"\n✅ Xong. Kết quả lưu ở: {OUT_CSV}")
        context.close()
        browser.close()

if __name__ == "__main__":
    run()
