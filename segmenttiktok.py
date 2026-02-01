import sys
import os
import subprocess
import threading
import requests
import pandas as pd
import time
import shutil
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLineEdit, QLabel, 
                             QFileDialog, QSpinBox, QPlainTextEdit)
from PyQt6.QtCore import pyqtSignal, QObject

# --- Cấu hình API TikTok từ dữ liệu của bạn ---
ORG_ID = "7567032608381337616"
UPLOAD_URL = f"https://business.tiktok.com/api/v3/bm/material/image/upload/?org_id={ORG_ID}"
CREATE_URL = f"https://business.tiktok.com/api/v3/bm/material/image/create/?org_id={ORG_ID}"

class Logger(QObject):
    log_signal = pyqtSignal(str)
    def log(self, message):
        self.log_signal.emit(f"[{time.strftime('%H:%M:%S')}] {message}")

class TikTokUploader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = Logger()
        self.initUI()
        self.logger.log_signal.connect(self.update_log)

    def initUI(self):
        self.setWindowTitle("TikTok Ads Segment to PNG - v2.3")
        self.setGeometry(100, 100, 950, 750)
        
        layout = QVBoxLayout()

        # 1. Chọn File Excel
        h_file = QHBoxLayout()
        self.path_input = QLineEdit()
        btn_browse = QPushButton("Chọn File Excel")
        btn_browse.clicked.connect(self.browse_file)
        h_file.addWidget(QLabel("File Excel:"))
        h_file.addWidget(self.path_input)
        h_file.addWidget(btn_browse)
        layout.addLayout(h_file)

        # 2. Nhập Cookie
        layout.addWidget(QLabel("Nhập Cookie (Session):"))
        self.cookie_input = QPlainTextEdit()
        self.cookie_input.setPlaceholderText("Dán chuỗi cookie bắt được từ DevTools vào đây...")
        self.cookie_input.setFixedHeight(120)
        layout.addWidget(self.cookie_input)

        # 3. Cấu hình luồng
        h_settings = QHBoxLayout()
        self.thread_count = QSpinBox()
        self.thread_count.setRange(1, 50)
        self.thread_count.setValue(10)
        h_settings.addWidget(QLabel("Số luồng Upload:"))
        h_settings.addWidget(self.thread_count)
        
        self.btn_run = QPushButton("BẮT ĐẦU XỬ LÝ")
        self.btn_run.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; height: 50px;")
        self.btn_run.clicked.connect(self.start_process)
        h_settings.addWidget(self.btn_run)
        layout.addLayout(h_settings)

        # 4. Ô Log (Đã sửa lỗi addLayout từ image_433dd9.png)
        layout.addWidget(QLabel("Log tiến trình:"))
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background-color: #000; color: #00ff00; font-family: 'Consolas';")
        layout.addWidget(self.log_box) # Thêm trực tiếp Widget vào Layout

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn file Excel", "", "Excel Files (*.xlsx *.xls)")
        if file_path: self.path_input.setText(file_path)

    def update_log(self, text):
        self.log_box.appendPlainText(text)
        self.log_box.ensureCursorVisible()

    def start_process(self):
        excel_path = self.path_input.text()
        cookie = self.cookie_input.toPlainText().strip()
        if not excel_path or not cookie:
            self.logger.log("LỖI: Thiếu Excel hoặc Cookie!")
            return
        self.btn_run.setEnabled(False)
        threading.Thread(target=self.main_worker, args=(excel_path, cookie), daemon=True).start()

    def main_worker(self, excel_path, cookie):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # Video nằm trong luuvideo/videos theo cấu trúc của bạn
            video_base_path = os.path.join(script_dir, "luuvideo", "videos") 
            
            df = pd.read_excel(excel_path)
            if 'number_segment_img' not in df.columns:
                df['number_segment_img'] = None

            # Lấy X-Csrftoken từ cookie
            csrf_token = "zegusHx7F0zHKxpInBgH1Y7tlsb96Av5"
            for item in cookie.split(';'):
                if 'X-Csrftoken' in item or 'csrftoken' in item:
                    csrf_token = item.split('=')[-1].strip()
            
            headers = {
                "Cookie": cookie,
                "X-Csrftoken": csrf_token,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
                "Content-Type": "application/json"
            }

            pending_videos = df[df['number_segment_img'].isna()]

            for index, row in pending_videos.iterrows():
                video_name = str(row['video_name']).strip()
                full_video_path = os.path.join(video_base_path, video_name)

                if not os.path.exists(full_video_path):
                    self.logger.log(f"Bỏ qua: Không thấy file {video_name}")
                    continue
                
                # Chỉ xử lý video >= 100MB
                file_size_mb = os.path.getsize(full_video_path) / (1024 * 1024)
                if file_size_mb < 100:
                    self.logger.log(f"Bỏ qua: {video_name} ({file_size_mb:.1f}MB) < 100MB")
                    continue

                task_dir = os.path.join(script_dir, video_name.replace(".mp4", ""))
                os.makedirs(task_dir, exist_ok=True)

                self.logger.log(f"--- Đang cắt video: {video_name} ---")
                cmd = [
                    'ffmpeg', '-i', full_video_path, '-c', 'copy', '-map', '0', 
                    '-f', 'segment', '-segment_time', '6', '-reset_timestamps', '1',
                    os.path.join(task_dir, f"{video_name.replace('.mp4', '')}_%d.ts")
                ]
                subprocess.run(cmd, capture_output=True)

                segments = [f for f in os.listdir(task_dir) if f.endswith('.ts')]
                self.logger.log(f"Cắt xong {len(segments)} đoạn. Bắt đầu upload...")

                with ThreadPoolExecutor(max_workers=self.thread_count.value()) as executor:
                    for seg in segments:
                        executor.submit(self.upload_flow, task_dir, seg, headers)

                df.at[index, 'number_segment_img'] = len(segments)
                df.to_excel(excel_path, index=False)
                
                # Tự động xóa thư mục tạm sau khi xong
                shutil.rmtree(task_dir)
                self.logger.log(f"Hoàn thành & Dọn dẹp: {video_name}")

            self.logger.log("HỆ THỐNG: Đã xử lý xong toàn bộ danh sách.")

        except Exception as e:
            self.logger.log(f"LỖI TOÀN CỤC: {str(e)}")
        finally:
            self.btn_run.setEnabled(True)

    def upload_flow(self, folder, seg_name, headers):
        try:
            path = os.path.join(folder, seg_name)
            png_file_path = path + ".png"

            # Tạo Header PNG 1x1 theo mã Hex bạn cung cấp
            png_header = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
            
            with open(path, 'rb') as f_ts:
                ts_data = f_ts.read()
            
            # Ghi file PNG "giả" chứa dữ liệu TS
            with open(png_file_path, 'wb') as f_png:
                f_png.write(png_header + ts_data)

            # Request 1: Upload
            with open(png_file_path, 'rb') as f:
                up_files = {'Filedata': (seg_name + ".png", f, 'image/png')}
                h_upload = headers.copy()
                if "Content-Type" in h_upload: del h_upload["Content-Type"]
                
                resp1 = requests.post(UPLOAD_URL, headers=h_upload, files=up_files)
                res_data = resp1.json()

            if res_data.get('code') == 0:
                img_info = res_data['data']['image_info']
                # Request 2: Create
                payload = {
                    "web_uri": img_info['web_uri'],
                    "original_web_uri": img_info['web_uri'],
                    "name": img_info['name'],
                    "show_error": False
                }
                resp2 = requests.post(CREATE_URL, headers=headers, json=payload)
                if resp2.json().get('code') == 0:
                    self.logger.log(f"Upload OK: {seg_name}")
                else:
                    self.logger.log(f"Lỗi Create {seg_name}: {resp2.text}")
            else:
                self.logger.log(f"Lỗi Upload {seg_name}: {res_data.get('msg')}")

        except Exception as e:
            self.logger.log(f"Lỗi luồng {seg_name}: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TikTokUploader()
    window.show()
    sys.exit(app.exec())
