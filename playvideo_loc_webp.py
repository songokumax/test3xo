import os
import cv2
import pandas as pd
import numpy as np
import threading
import time
from moviepy import VideoFileClip

# ==== CẤU HÌNH ====
EXCEL_PATH = r"C:\phim\quatvn\ketqua.xlsx"
VIDEO_DIR  = r"C:\phim\quatvn\luuvideo\videos"
WEBP_DIR   = r"C:\phim\quatvn\luuvideo\webp_outputs"

COLUMN_VIDEO_NAME = "video_name"
COLUMN_CHON_LOC   = "chon_loc"
COLUMN_NAME_WEBP  = "name_webp"

if not os.path.exists(WEBP_DIR):
    os.makedirs(WEBP_DIR)

# Lock này cực kỳ quan trọng để các luồng xếp hàng ghi Excel, không tranh giành nhau
excel_lock = threading.Lock()
processing_threads = []
seek_to_frame = -1

def cut_webp_worker(video_path, output_path, start_time, end_time, video_name, idx):
    try:
        with VideoFileClip(video_path) as clip:
            sub = clip.subclipped(start_time, end_time)
            sub.resized(height=360).write_videofile(
                output_path, codec='libwebp', audio=False, logger=None,
                ffmpeg_params=['-preset', 'default', '-loop', '0']
            )
        
        # Ghi file WebP vào Excel một cách an toàn
        with excel_lock:
            time.sleep(0.5) # Nghỉ một chút để luồng chính rảnh tay
            df_sync = pd.read_excel(EXCEL_PATH, dtype=str).fillna("")
            df_sync.at[idx, COLUMN_NAME_WEBP] = os.path.basename(output_path)
            df_sync.to_excel(EXCEL_PATH, index=False)
            
        print(f"\n[Thread] XONG & DA LUU EXCEL: {os.path.basename(output_path)}")
    except Exception as e:
        print(f"\n[Thread] LOI: {e}")

def on_mouse(event, x, y, flags, param):
    global seek_to_frame
    if event == cv2.EVENT_LBUTTONDOWN or (event == cv2.EVENT_MOUSEMOVE and flags == cv2.EVENT_FLAG_LBUTTON):
        sw, total_frames = param
        seek_to_frame = int((x / sw) * total_frames)

def play_video_and_get_choice(video_path, video_name, idx):
    global seek_to_frame
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return None, None

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vw, vh = int(cap.get(3)), int(cap.get(4))

    import tkinter as tk
    root = tk.Tk(); root.withdraw()
    sw, sh = int(root.winfo_screenwidth()*0.8), int(root.winfo_screenheight()*0.8)
    root.destroy()

    scale = min(sw/vw, sh/vh)
    nw, nh = int(vw*scale), int(vh*scale)
    dx, dy = (sw-nw)//2, (sh-nh)//2

    cv2.namedWindow(video_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(video_name, sw, sh)
    cv2.setMouseCallback(video_name, on_mouse, param=(sw, total_frames))

    choice, start_time, is_ok, status_msg = '', None, False, "O: OK | K: KO | S: Bat dau | E: Cat"
    seek_to_frame = -1

    while True:
        if seek_to_frame != -1:
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(seek_to_frame, total_frames-1))
            seek_to_frame = -1

        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
            _, frame = cap.read()

        curr_f = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        curr_s = curr_f / fps
        
        canvas = np.zeros((sh, sw, 3), dtype=np.uint8)
        canvas[dy:dy+nh, dx:dx+nw] = cv2.resize(frame, (nw, nh))

        # Thanh tiến trình
        cv2.rectangle(canvas, (0, sh-15), (int(sw * (curr_f/total_frames)), sh), (0, 255, 0), -1)

        # Thông tin hiển thị
        info = f"{curr_s:.1f}s / {total_frames/fps:.1f}s"
        if start_time: info += f" | START: {start_time:.1f}s"
        cv2.putText(canvas, info, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(canvas, status_msg, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # Đếm luồng đang chạy
        active = sum(1 for t in processing_threads if t.is_alive())
        if active > 0:
            cv2.putText(canvas, f"Dang xu ly {active} WebP...", (sw-300, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        cv2.imshow(video_name, canvas)
        key = cv2.waitKey(20) & 0xFF
        
        if key in (ord('o'), ord('O')):
            choice, is_ok = 'OK', True
            status_msg = "DA CHON OK. Bam S de bat dau."
        elif key in (ord('k'), ord('K')): choice = 'KO'; break
        elif key in (ord('s'), ord('S')) and is_ok:
            start_time = curr_s
            status_msg = f"DA CHON S: {start_time:.1f}s. Bam E de cat."
        elif key in (ord('e'), ord('E')) and start_time is not None:
            out = os.path.join(WEBP_DIR, f"{os.path.splitext(video_name)[0]}_{int(start_time)}s.webp")
            t = threading.Thread(target=cut_webp_worker, args=(video_path, out, start_time, curr_s, video_name, idx))
            t.start()
            processing_threads.append(t)
            break
        elif key in (ord('a'), ord('A')): cap.set(cv2.CAP_PROP_POS_FRAMES, max(curr_f - int(5*fps), 0))
        elif key in (ord('d'), ord('D')): cap.set(cv2.CAP_PROP_POS_FRAMES, min(curr_f + int(5*fps), total_frames-1))
        elif key == 27: cap.release(); cv2.destroyAllWindows(); return None, None

    cap.release(); cv2.destroyAllWindows()
    return choice, "OK"

def main():
    if not os.path.exists(EXCEL_PATH): return
    while True:
        with excel_lock:
            df = pd.read_excel(EXCEL_PATH, dtype=str).fillna("")
        
        todo = df[df[COLUMN_CHON_LOC] == ""]
        if todo.empty: break
            
        idx = todo.index[0]
        v_name = str(df.loc[idx, COLUMN_VIDEO_NAME]).strip()
        v_path = os.path.join(VIDEO_DIR, v_name)
        
        if not os.path.exists(v_path):
            with excel_lock:
                df.at[idx, COLUMN_CHON_LOC] = "NOT_FOUND"
                df.to_excel(EXCEL_PATH, index=False)
            continue

        res, _ = play_video_and_get_choice(v_path, v_name, idx)
        if res is None: break

        with excel_lock:
            df_save = pd.read_excel(EXCEL_PATH, dtype=str).fillna("")
            df_save.at[idx, COLUMN_CHON_LOC] = res
            df_save.to_excel(EXCEL_PATH, index=False)

    for t in processing_threads: t.join()
    print("HOAN THANH!")

if __name__ == "__main__":
    main()
