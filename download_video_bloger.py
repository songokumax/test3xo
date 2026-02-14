import json
import requests
import time
import os
import pandas as pd
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright
from pynput import keyboard

# --- CẤU HÌNH ---
EXCEL_FILE = "viet69_final.xlsx"
DOWNLOAD_DIR = "videos_downloaded"
URL_COLUMN = "Video URL"
NAME_COLUMN = "video_name"
MAX_WORKERS = 5 

# Khởi tạo khóa đồng bộ và sự kiện dừng
excel_lock = threading.Lock()
stop_event = threading.Event()

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def on_press(key):
    """Lắng nghe phím Esc để dừng chương trình"""
    if key == keyboard.Key.esc:
        print("\n[!!!] Đã nhấn ESC. Đang dừng tất cả các luồng, vui lòng đợi giây lát...")
        stop_event.set()
        return False  # Dừng listener

def is_valid_blogger_url(url):
    if pd.isna(url): return False
    return "blogger.com/video.g?token=" in str(url)

def download_file(url, filepath, worker_no):
    if stop_event.is_set(): return False
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.blogger.com/"
    }
    try:
        with requests.get(url, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if stop_event.is_set(): return False
                    if chunk: f.write(chunk)
            return True
    except Exception as e:
        if not stop_event.is_set():
            print(f"    [Luồng {worker_no}][!] Lỗi tải file: {e}")
        return False

def worker_task(index, url, worker_no):
    if stop_event.is_set(): return

    random_name = f"{secrets.token_hex(16)}.mp4"
    file_path = os.path.join(DOWNLOAD_DIR, random_name)

    print(f"[*] Luồng {worker_no} đang xử lý hàng {index + 1}: {url[:40]}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        page = context.new_page()

        try:
            if stop_event.is_set(): return
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            if stop_event.is_set(): return
            page.wait_for_selector(".play-button", timeout=45000)
            
            time.sleep(2)
            if stop_event.is_set(): return

            video_config = page.evaluate("() => window.VIDEO_CONFIG")
            
            if video_config and "streams" in video_config:
                streams = video_config["streams"]
                if streams:
                    target_url = streams[-1].get("play_url")
                    if target_url:
                        if download_file(target_url, file_path, worker_no):
                            if stop_event.is_set(): return
                            with excel_lock:
                                df_temp = pd.read_excel(EXCEL_FILE)
                                df_temp[NAME_COLUMN] = df_temp[NAME_COLUMN].astype(str)
                                df_temp.at[index, NAME_COLUMN] = str(random_name)
                                df_temp.to_excel(EXCEL_FILE, index=False)
                                print(f"    [Luồng {worker_no}][OK] Đã lưu {random_name}")
        except Exception:
            pass
        finally:
            browser.close()

def main():
    if not os.path.exists(EXCEL_FILE):
        print(f"[!] Không tìm thấy file {EXCEL_FILE}")
        return

    # Bắt đầu lắng nghe bàn phím trong một luồng riêng
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    df = pd.read_excel(EXCEL_FILE)
    if NAME_COLUMN not in df.columns:
        df[NAME_COLUMN] = ""
    
    df[NAME_COLUMN] = df[NAME_COLUMN].astype(str)
    df.loc[df[NAME_COLUMN] == 'nan', NAME_COLUMN] = ""
    df.to_excel(EXCEL_FILE, index=False)

    mask = (df[URL_COLUMN].apply(is_valid_blogger_url)) & ((df[NAME_COLUMN] == "") | (df[NAME_COLUMN].isna()))
    tasks = [(idx, row[URL_COLUMN]) for idx, row in df[mask].iterrows()]

    if not tasks:
        print("[*] Không còn link nào cần tải.")
        return

    print(f"[*] Tổng {len(tasks)} link. Nhấn ESC bất cứ lúc nào để dừng chương trình.")

    # Sử dụng ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for i, (idx, url) in enumerate(tasks):
            worker_no = (i % MAX_WORKERS) + 1
            futures.append(executor.submit(worker_task, idx, url, worker_no))
            
            # Kiểm tra nếu đã nhấn Esc thì không gửi thêm task mới vào hàng đợi
            if stop_event.is_set():
                break

    # Đợi các luồng hiện tại đóng trình duyệt và thoát
    stop_event.set() 
    print("\n[*] ĐÃ DỪNG CHƯƠNG TRÌNH.")

if __name__ == "__main__":
    main()
