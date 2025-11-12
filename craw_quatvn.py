#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Crawl quatvn.love:
- Mỗi trang listing lấy đúng 12 bài (ảnh thumb + title + url).
- Vào trang bài, đọc flowplayer[data-item] để lấy link media:
    + Nếu .mp4 => dùng trực tiếp
    + Nếu .m3u8 => tự map sang .mp4 (…/stream/<NAME>/output.m3u8 -> …/stream/<NAME>.mp4)
- Tải video (đặt Referer là trang bài), đặt tên file ngẫu nhiên .mp4.
- Ghi Excel: page, post_url, title, thumb_url, thumb_path, video_url, video_name, tags.

Usage:
    python crawl_quatvn.py --start 1 --end 3 --out luuvideo --excel ketqua.xlsx
"""

from __future__ import annotations
import argparse
import logging
import os
import random
import re
import string
from pathlib import Path
from urllib.parse import urlparse, urlsplit, urlunsplit

import html as ihtml
import json
import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

# ============ Config ============
BASE = "https://quatvn.love"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139 Safari/537.36"
}
LOG_FILE = "crawl_quatvn.log"
# ================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"),
              logging.StreamHandler()]
)
log = logging.getLogger("quatvn")

# ---------- Utils ----------
def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def rand_name(min_len=20, max_len=40) -> str:
    n = random.randint(min_len, max_len)
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))

def build_session() -> requests.Session:
    sess = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5,
                    status_forcelist=(429, 500, 502, 503, 504))
    adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=retries)
    sess.mount("http://", adapter)
    sess.mount("https://", adapter)
    sess.headers.update(HEADERS)
    return sess

def get_html(url: str, sess: requests.Session) -> str:
    r = sess.get(url, timeout=30)
    r.raise_for_status()
    return r.text

def save_file(url: str, out_path: Path, sess: requests.Session, referer: str | None = None) -> None:
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
        m = re.match(r"(https?://[^/]+)", referer)
        if m:
            headers["Origin"] = m.group(1)

    with sess.get(url, headers=headers, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)

# ---------- Parsers ----------
def list_posts(listing_html: str) -> list[dict]:
    """Trả về tối đa 12 item: {url, thumb, title}."""
    soup = BeautifulSoup(listing_html, "html.parser")
    items: list[dict] = []
    for li in soup.select(".g1-collection .g1-collection-items > li")[:12]:
        a = li.select_one(".entry-featured-media a.g1-frame[href]")
        img = li.select_one(".entry-featured-media img")
        title_a = li.select_one(".entry-header .entry-title a")
        if not a or not title_a:
            continue
        post_url = a["href"].strip()
        thumb_url = (img.get("data-src") or img.get("src") or "").strip() if img else ""
        title = title_a.get_text(strip=True)
        items.append({"url": post_url, "thumb": thumb_url, "title": title})
    return items

def m3u8_to_mp4(u: str) -> str:
    """.../stream/<NAME>/output.m3u8  =>  .../stream/<NAME>.mp4  (clear query/fragment, unescape quotes)."""
    if not u:
        return u
    u = ihtml.unescape(u).strip().strip('\'"')
    sp = urlsplit(u)
    new_path = re.sub(r"/([^/]+)/output\.m3u8$", r"/\1.mp4", sp.path)
    if new_path == sp.path:
        new_path = re.sub(r"/output\.m3u8$", r".mp4", sp.path)
    sp = sp._replace(path=new_path, query="", fragment="")
    return urlunsplit(sp)

def extract_media_from_post_html(html: str) -> tuple[str | None, str | None]:
    """
    Đọc flowplayer[data-item] → trả về (media_url, kind) với kind in {"mp4","mp4_from_m3u8"}.
    """
    soup = BeautifulSoup(html, "html.parser")
    fp = soup.select_one('div.flowplayer[data-item]')
    if not fp:
        return None, None

    raw = fp.get("data-item", "")
    try:
        data = json.loads(ihtml.unescape(raw))
    except Exception:
        return None, None

    # Ưu tiên mp4 gốc
    for s in (data.get("sources") or []):
        u = (s.get("src") or "").strip()
        t = (s.get("type") or "").lower()
        if "mp4" in t or u.lower().endswith(".mp4"):
            return u, "mp4"

    # Nếu chỉ có m3u8 → map sang mp4
    for s in (data.get("sources") or []):
        u = (s.get("src") or "").strip()
        t = (s.get("type") or "").lower()
        if "mpegurl" in t or u.lower().endswith(".m3u8"):
            return m3u8_to_mp4(u), "mp4_from_m3u8"

    return None, None

def get_post_meta(html: str) -> tuple[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.select_one("h1.entry-title, h1.g1-mega.entry-title")
    title = h1.get_text(strip=True) if h1 else ""
    tag_a = soup.select_one(".entry-categories a.entry-category")
    tags = [tag_a.get_text(strip=True)] if tag_a else []
    return title, tags

# ---------- Excel ----------
def excel_append_row(xlsx_path: Path, row: dict) -> None:
    """
    row: page, post_url, title, thumb_url, thumb_path, video_url, video_name, tags
    """
    from openpyxl import Workbook, load_workbook

    cols = ["page", "post_url", "title", "thumb_url", "thumb_path",
            "video_url", "video_name", "tags"]

    if not xlsx_path.exists():
        wb = Workbook()
        ws = wb.active
        ws.append(cols)
        wb.save(str(xlsx_path))

    wb = load_workbook(str(xlsx_path))
    ws = wb.active
    ws.append([row.get(c, "") for c in cols])
    wb.save(str(xlsx_path))

# ---------- Main crawl ----------
def crawl(args) -> None:
    sess = build_session()

    out_root = Path(args.out).resolve()
    thumb_dir = out_root / "thumbs"
    video_dir = out_root / "videos"
    ensure_dir(thumb_dir)
    ensure_dir(video_dir)

    all_rows: list[dict] = []

    for page_no in range(args.start, args.end + 1):
        page_url = BASE if page_no == 1 else f"{BASE}/page/{page_no}/"
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
        except Exception:
            pass
        log.info(f"=== Listing page {page_no}: {page_url}")

        try:
            listing_html = get_html(page_url, sess)
        except Exception as e:
            log.warning(f"Không tải được listing page {page_no}: {e}")
            continue

        posts = list_posts(listing_html)
        if not posts:
            log.warning("Không tìm thấy bài nào trên trang này.")
            continue

        for idx, post in enumerate(posts, 1):
            log.info(f"\n[{page_no}.{idx}] {post['title']}")
            try:
                # 1) Lưu thumbnail
                thumb_path = Path("")
                if post["thumb"]:
                    try:
                        ext = os.path.splitext(urlparse(post["thumb"]).path)[1] or ".jpg"
                        thumb_path = thumb_dir / (rand_name(10, 16) + ext)
                        save_file(post["thumb"], thumb_path, sess)
                    except Exception as e:
                        log.warning(f"  - Lỗi tải thumbnail: {e}")
                        thumb_path = Path("")

                # 2) Mở trang bài -> lấy media
                post_html = get_html(post["url"], sess)
                media_url, kind = extract_media_from_post_html(post_html)
                if not media_url:
                    log.warning("✗ Không tìm thấy nguồn media")
                    continue

                # 3) Tải mp4
                video_name = rand_name(20, 40) + ".mp4"
                out_mp4 = video_dir / video_name
                log.info(f"MP4 = {media_url}")
                try:
                    save_file(media_url, out_mp4, sess, referer=post["url"])
                except Exception as e:
                    log.warning(f"! Lỗi tải MP4: {e}")
                    continue

                # 4) Meta & Excel
                title, tags = get_post_meta(post_html)
                row = {
                    "page": page_no,
                    "post_url": post["url"],
                    "title": title or post["title"],
                    "thumb_url": post["thumb"],
                    "thumb_path": thumb_path.name if thumb_path else "",
                    "video_url": media_url,
                    "video_name": out_mp4.name,
                    "tags": ", ".join(tags),
                }
                excel_append_row(Path(args.excel), row)
                all_rows.append(row)

                log.info(f"✓ DONE: {row['title']}")
                log.info(f"   thumb: {row['thumb_path']}")
                log.info(f"   file : {row['video_name']}")
                log.info(f"   url  : {row['video_url']}")
                log.info(f"   tags : {row['tags']}")

            except Exception as e:
                log.warning(f"!! Lỗi bài [{post['url']}]: {e}")

    # Gộp Excel nếu muốn (nếu đã có file, append đã xử lý ở trên — phần này chỉ log tổng kết)
    excel_path = Path(args.excel).resolve()
    if all_rows:
        # đảm bảo file tồn tại (trong trường hợp không viết được ở trên vì lý do nào đó)
        if not excel_path.exists():
            pd.DataFrame(all_rows).to_excel(excel_path, index=False)
        log.info(f"\n==> Đã ghi {len(all_rows)} dòng vào: {excel_path}")
    else:
        # tạo file rỗng có header nếu chưa có
        if not excel_path.exists():
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.append(["page", "post_url", "title", "thumb_url", "thumb_path",
                       "video_url", "video_name", "tags"])
            wb.save(str(excel_path))
        log.warning(f"\n==> Không có bản ghi mới. Excel: {excel_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1, help="Trang bắt đầu")
    ap.add_argument("--end", type=int, default=1, help="Trang kết thúc (inclusive)")
    ap.add_argument("--out", type=str, default="luuvideo", help="Thư mục lưu file")
    ap.add_argument("--excel", type=str, default="ketqua.xlsx", help="Tên file Excel")
    args = ap.parse_args()
    crawl(args)

if __name__ == "__main__":
    main()
