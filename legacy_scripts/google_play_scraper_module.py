#!/usr/bin/env python3
"""
Google Play Store 評論爬取模組
"""

import pandas as pd
from google_play_scraper import Sort, reviews

def scrape_google_play_reviews(app_id, lang="zh_TW", country="tw", count=200):
    """
    抓取 Google Play Store 評論

    Args:
        app_id (str): App package name
        lang (str): 語言代碼
        country (str): 國家代碼
        count (int): 評論數量

    Returns:
        pd.DataFrame: 評論數據
    """
    print(f"開始抓取 Google Play 評論: {app_id}")

    try:
        result, _ = reviews(
            app_id,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=count
        )

        df = pd.DataFrame(result, columns=[
            "reviewId", "userName", "score", "at", "content",
            "replyContent", "thumbsUpCount"
        ])

        print(f"成功抓取 {len(df)} 條 Google Play 評論")
        return df

    except Exception as e:
        print(f"Google Play 評論抓取失敗: {str(e)}")
        return pd.DataFrame()

# (可選) 加上獨立測試的區塊
if __name__ == '__main__':
    print("--- 測試 Google Play 爬蟲模組 ---")
    test_app_id = "com.google.android.apps.maps"
    test_df = scrape_google_play_reviews(test_app_id, count=10)
    if not test_df.empty:
        print("\n測試成功，獲取到評論樣本：")
        print(test_df.head(3))
    else:
        print("\n測試失敗。")