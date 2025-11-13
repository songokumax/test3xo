import os
import cv2
import pandas as pd
from datetime import datetime

# ==== CẤU HÌNH ====
EXCEL_PATH = r"C:\code\quatvn\ketqua.xlsx"   # đường dẫn file excel (can sua)
VIDEO_DIR  = r"C:\code\quatvn\luuvideo\videos"          # thư mục chứa video (can sua)
LOG_PATH   = r"C:\code\quatvn\luuvideo\log_chon_loc.txt"  # file log txt

COLUMN_VIDEO_NAME = "video_name"  # tên cột trong excel chứa tên file video
COLUMN_CHON_LOC   = "chon_loc"    # tên cột chọn lọc

# ==================


def play_video_and_get_choice(video_path, window_name="Video"):
    """
    Phát video bằng OpenCV.
    Điều khiển:
      O  -> chọn OK
      K  -> chọn KO
      N  -> bỏ qua (để trống)
      ESC -> thoát chương trình chính
      A  -> tua lùi 10s
      D  -> tua tới 10s
      Enter -> khi đã hết video: phát lại từ đầu

    Trả về:
      'OK', 'KO', '', hoặc None (ESC).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Không mở được video: {video_path}")
        return ''

    # ---- thông tin video ----
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    ret, frame = cap.read()
    if not ret:
        cap.release()
        return ''

    h, w = frame.shape[:2]

    # ---- kích thước màn hình (tkinter, chạy được win/macos/linux) ----
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        root.destroy()
    except Exception:
        screen_w, screen_h = 1920, 1080

    # scale vừa 80% màn hình, giữ tỉ lệ
    scale = min(screen_w * 0.8 / w, screen_h * 0.8 / h, 1.0)
    disp_w = int(w * scale)
    disp_h = int(h * scale)

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, disp_w, disp_h)
    cv2.moveWindow(window_name,
                   int((screen_w - disp_w) / 2),
                   int((screen_h - disp_h) / 2))

    # quay lại frame đầu
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    choice = ''

    jump_frames = int(10 * fps)  # 10s

    while True:
        ret, frame = cap.read()

        # ---- hết video: dừng lại, chờ phím ----
        if not ret:
            if total_frames > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(total_frames - 1, 0))
                ret_last, frame_last = cap.read()
                if ret_last:
                    frame_disp = cv2.resize(frame_last, (disp_w, disp_h))
                    cv2.imshow(window_name, frame_disp)

            while True:
                key = cv2.waitKey(0) & 0xFF  # ở đây chỉ cần 8-bit

                if key in (ord('o'), ord('O')):
                    choice = 'OK'
                    cap.release()
                    cv2.destroyAllWindows()
                    return choice
                elif key in (ord('k'), ord('K')):
                    choice = 'KO'
                    cap.release()
                    cv2.destroyAllWindows()
                    return choice
                elif key in (ord('n'), ord('N')):
                    choice = ''
                    cap.release()
                    cv2.destroyAllWindows()
                    return choice
                elif key == 27:  # ESC
                    cap.release()
                    cv2.destroyAllWindows()
                    return None
                elif key == 13:  # Enter: phát lại
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    break  # thoát vòng chờ phím, quay lại loop phát
                # phím khác thì tiếp tục chờ

            continue  # quay lại vòng while lớn (phát lại)

        # ---- còn frame: hiển thị ----
        # ----- tính thời gian -----
        current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        current_sec = current_frame / fps
        total_sec = total_frames / fps

        def format_time(sec):
            sec = int(sec)
            return f"{sec//60:02d}:{sec%60:02d}"

        time_text = f"{format_time(current_sec)} / {format_time(total_sec)}"

        # ----- resize frame -----
        frame_disp = cv2.resize(frame, (disp_w, disp_h))

        # ----- vẽ thời gian lên góc trái phía trên -----
        cv2.putText(
            frame_disp,
            time_text,
            (10, 30),  # vị trí
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,        # size chữ
            (255, 255, 255),   # màu trắng
            2,          # độ dày
            cv2.LINE_AA
        )

        cv2.imshow(window_name, frame_disp)


        wait_ms = int(1000 / fps)
        key = cv2.waitKey(wait_ms) & 0xFF
        if key == 255:  # không có phím
            continue

        # --- phím chọn ---
        if key in (ord('o'), ord('O')):
            choice = 'OK'
            break
        elif key in (ord('k'), ord('K')):
            choice = 'KO'
            break
        elif key in (ord('n'), ord('N')):
            choice = ''
            break
        elif key == 27:  # ESC
            choice = None
            break

        # --- tua bằng A / D ---
        if key in (ord('a'), ord('A')):
            current = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            new_pos = max(current - jump_frames, 0)
            cap.set(cv2.CAP_PROP_POS_FRAMES, new_pos)
        elif key in (ord('d'), ord('D')):
            current = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            new_pos = min(current + jump_frames, max(total_frames - 1, 0))
            cap.set(cv2.CAP_PROP_POS_FRAMES, new_pos)

    cap.release()
    cv2.destroyAllWindows()
    return choice



def append_log(video_name, choice):
    """
    Ghi 1 dòng log vào file txt
    """
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{time_str}\t{video_name}\t{choice}\n")


def main():
    # đọc file excel
    df = pd.read_excel(EXCEL_PATH)

    # đảm bảo có 2 cột cần thiết
    if COLUMN_VIDEO_NAME not in df.columns or COLUMN_CHON_LOC not in df.columns:
        print("Không tìm thấy cột 'video_name' hoặc 'chon_loc' trong file Excel.")
        return

    # lặp qua từng dòng
    for idx, row in df.iterrows():
        chon_loc_value = str(row[COLUMN_CHON_LOC]).strip() if not pd.isna(row[COLUMN_CHON_LOC]) else ""

        # bỏ qua những dòng đã có chọn lọc
        if chon_loc_value != "":
            continue

        video_name = str(row[COLUMN_VIDEO_NAME]).strip()
        video_path = os.path.join(VIDEO_DIR, video_name)

        if not os.path.isfile(video_path):
            print(f"KHÔNG TÌM THẤY FILE VIDEO: {video_path}")
            append_log(video_name, "FILE_NOT_FOUND")
            continue

        print(f"\nĐang phát: {video_name}")
        print("Phím O = OK, K = KO, N = bỏ qua, ESC = thoát chương trình")
        print("Phím A = tua lùi 10s, D = tua tới 10s, khi hết video: Enter = phát lại")

        choice = play_video_and_get_choice(video_path, window_name=video_name)

        if choice is None:
            # người dùng bấm ESC → thoát luôn
            print("Bạn đã bấm ESC. Thoát chương trình.")
            break

        # cập nhật vào dataframe
        df.at[idx, COLUMN_CHON_LOC] = choice

        # lưu lại excel sau mỗi video để không mất dữ liệu
        df.to_excel(EXCEL_PATH, index=False)

        # ghi log
        append_log(video_name, choice)

        print(f"Đã ghi '{choice}' cho video {video_name}")

    print("Hoàn thành.")


if __name__ == "__main__":
    main()
