#!/usr/bin/env python3
"""
APP評論爬取工具
支援 Google Play Store 和 Apple App Store 評論抓取
"""

import os
from datetime import datetime

# 從我們建立的模組中導入函式
from google_play_scraper_module import scrape_google_play_reviews
from app_store_scraper_module import scrape_app_store_reviews

def generate_structured_filename(platform, app_id, timestamp=None):
    """
    生成結構化檔案名稱
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_app_id = str(app_id).replace(".", "_").replace("/", "_")
    return f"{platform}_reviews_{clean_app_id}_{timestamp}.csv"


def main():
    """主程式"""

    # --- 設定參數 ---
    GOOGLE_APP_ID = "com.fubon.aibank"  # Google Play package name
    APPLE_APP_ID = 6479990131           # Apple App Store ID
    COUNTRY = "tw"                      # 台灣
    REVIEW_COUNT = 10000                 # 評論數量
    # ----------------

    # 建立輸出目錄
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 60)
    print("APP 評論爬取工具")
    print("=" * 60)
    print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目標評論數量: {REVIEW_COUNT}")
    print(f"輸出目錄: {output_dir}\n")

    # 抓取 Google Play 評論 (調用模組)
    google_df = scrape_google_play_reviews(
        app_id=GOOGLE_APP_ID,
        country=COUNTRY,
        count=REVIEW_COUNT
    )

    if not google_df.empty:
        google_filename = generate_structured_filename("google_play", GOOGLE_APP_ID, timestamp)
        google_filepath = os.path.join(output_dir, google_filename)
        google_df.to_csv(google_filepath, index=False, encoding="utf-8-sig")
        print(f"✓ Google Play 評論已儲存: {google_filepath}\n")
    else:
        print("✗ Google Play 評論抓取失敗\n")

    # 抓取 App Store 評論 (調用模組)
    apple_df = scrape_app_store_reviews(
        app_id=APPLE_APP_ID,
        country=COUNTRY,
        count=REVIEW_COUNT
    )

    if not apple_df.empty:
        apple_filename = generate_structured_filename("app_store", APPLE_APP_ID, timestamp)
        apple_filepath = os.path.join(output_dir, apple_filename)
        apple_df.to_csv(apple_filepath, index=False, encoding="utf-8-sig")
        print(f"✓ App Store 評論已儲存: {apple_filepath}\n")
    else:
        print("✗ App Store 評論抓取失敗\n")

    print("=" * 60)
    print("爬取完成總結:")
    print(f"Google Play 評論: {len(google_df)} 條")
    print(f"App Store 評論: {len(apple_df)} 條")
    print(f"完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
