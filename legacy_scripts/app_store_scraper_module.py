#!/usr/bin/env python3
"""
Apple App Store 評論爬取模組
"""

import requests
import json
import time
from datetime import datetime
import pandas as pd

def scrape_app_store_reviews(app_id, country="tw", count=200):
    """
    抓取 Apple App Store 評論 (使用 RSS Feed API)

    Args:
        app_id (int): App ID
        country (str): 國家代碼
        count (int): 評論數量

    Returns:
        pd.DataFrame: 評論數據
    """
    print(f"開始抓取 App Store 評論: {app_id}")

    reviews_list = []
    page = 1
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    try:
        while len(reviews_list) < count:
            try:
                url = f"https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy=mostRecent/page={page}/json"
                response = session.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()

                feed = data.get('feed', {})
                entries = feed.get('entry', [])

                if not entries or len(entries) <= 1:
                    break

                for entry in entries[1:]:
                    if len(reviews_list) >= count:
                        break
                    review = _parse_app_store_review_entry(entry)
                    if review:
                        reviews_list.append(review)

                print(f"第 {page} 頁: 獲取到 {len(entries)-1} 條評論")
                page += 1
                time.sleep(1)

            except requests.RequestException as e:
                print(f"請求錯誤 (頁面 {page}): {e}")
                break
            except json.JSONDecodeError as e:
                print(f"JSON 解析錯誤 (頁面 {page}): {e}")
                break

        if reviews_list:
            df = pd.DataFrame(reviews_list)
            print(f"成功抓取 {len(df)} 條 App Store 評論")
            return df
        else:
            print("未獲取到任何評論")
            return pd.DataFrame()

    except Exception as e:
        print(f"App Store 評論抓取失敗: {str(e)}")
        return pd.DataFrame()

def _parse_app_store_review_entry(entry):
    """解析單條 App Store 評論 (內部輔助函式)"""
    try:
        author_name = entry.get('author', {}).get('name', {}).get('label', 'Unknown')
        content = entry.get('content', {}).get('label', '')
        rating = int(entry.get('im:rating', {}).get('label', '0'))
        title = entry.get('title', {}).get('label', '')
        review_id = entry.get('id', {}).get('label', '')
        updated = entry.get('updated', {}).get('label', '')
        review_date = datetime.fromisoformat(updated.replace('Z', '+00:00'))

        return {
            'reviewId': review_id,
            'userName': author_name,
            'rating': rating,
            'date': review_date.strftime('%Y-%m-%d %H:%M:%S'),
            'title': title,
            'review': content,
            'isEdited': False
        }
    except Exception:
        return None

# (可選) 獨立測試區塊
if __name__ == '__main__':
    print("--- 測試 App Store 爬蟲模組 ---")
    test_app_id = 585027354 # Line App ID
    test_df = scrape_app_store_reviews(test_app_id, count=10)
    if not test_df.empty:
        print("\n測試成功，獲取到評論樣本：")
        print(test_df.head(3))
    else:
        print("\n測試失敗。")