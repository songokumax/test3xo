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
