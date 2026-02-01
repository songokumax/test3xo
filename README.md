# test3xo
cào dữ liệu trên viet69 lưu lại csv gồm url_viet69, url_anh, ten_phim, url_video_blogger, the_loai
mặc định 2 page, có thể sửa END_PAGE = 2 để tăng thêm

cài
pip install playwright pandas
pip install -U playwright && playwright install

craw trên fullcliphot cần:
- Cài https://www.gyan.dev/ffmpeg/builds/
- Cài gpac_latest_head_win64.exe từ https://gpac.io/downloads/gpac-nightly-builds/
- pip install playwright requests beautifulsoup4 pandas openpyxl tqdm
- python -m playwright install chromium
- Test chạy python crawl_fullcliphot.py --start 1 --end 5 --out luuvideo --excel ketqua.xlsx

Quatvn: chạy python crawl_quatvn.py --start 1 --end 5 --out luuvideo --excel ketqua.xlsx

playvideo_loc:
- Nên cài python 3.11.x để cài thư viện ko bị lỗi.
- pip install pandas opencv-python openpyxl (Nếu lỗi do dùng phiên bản python mới, gỡ ra, cài lại bản cũ hơn như 3.11.x, rồi chạy:

* py -3.11 -m ensurepip --upgrade
* py -3.11 -m pip install --upgrade pip
* py -3.11 -m pip install pandas opencv-python openpyxl

Trong đó:
- Phím O = OK, K = KO, N = bỏ qua, ESC = thoát chương trình
- Phím A = tua lùi 10s, D = tua tới 10s, khi hết video: Enter = phát lại

(nhớ sửa đường dẫn thư mục video và file execl, nếu file excel chưa có cột chon_loc, hãy thêm bằng tay trước)

*** Với segmenttiktok.py cần cài pip install PyQt6 requests pandas openpyxl
Và:

Bước 1: Tải bộ cài FFmpeg
Truy cập trang: gyan.dev/ffmpeg/builds (đây là nguồn phổ biến nhất cho Windows).

Tìm phần git full build, chọn link ffmpeg-git-full.7z để tải về.

Sử dụng WinRAR hoặc 7-Zip để giải nén file vừa tải.

Bước 2: Cố định vị trí thư mục
Sau khi giải nén, bạn sẽ thấy một thư mục kiểu ffmpeg-2026-01-xx.... Hãy đổi tên nó thành ngắn gọn là ffmpeg.

Copy thư mục ffmpeg này và dán vào ổ **C:**. Đường dẫn chuẩn lúc này sẽ là: C:\ffmpeg.

Bên trong thư mục này, bạn phải thấy thư mục con tên là bin (đây là nơi chứa file ffmpeg.exe).

Bước 3: Thêm vào biến môi trường (PATH)
Đây là bước quan trọng nhất để script Python không báo lỗi "FFmpeg not found".

Nhấn phím Windows, gõ tìm kiếm: "env" và chọn "Edit the system environment variables".

Trong cửa sổ hiện ra, nhấn nút Environment Variables... ở góc dưới bên phải.

Ở phần System variables (bảng bên dưới), tìm dòng có tên là Path, chọn nó rồi nhấn Edit....

Nhấn nút New, sau đó dán đường dẫn này vào: C:\ffmpeg\bin

Nhấn OK -> OK -> OK để đóng hết các cửa sổ.

Bước 4: Kiểm tra xem đã thành công chưa
Mở Command Prompt (CMD) hoặc PowerShell lên.

Gõ lệnh sau và nhấn Enter:

ffmpeg -version
Khi sử dụng, cần nhập cookie tiktok ads vào, và file excel có sẵn cột video_name, number_segment_img và video nằm trong luuvideo/videos
