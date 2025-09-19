#!/usr/bin/env python3
"""
調試 App Store API 響應
"""

import requests
import json

def debug_api_response(app_id, country="tw", page=1):
    """檢查 App Store API 的實際響應"""
    url = f"https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy=mostRecent/page={page}/json"

    print(f"請求 URL: {url}")
    print("-" * 50)

    try:
        response = requests.get(url, timeout=10)
        print(f"狀態碼: {response.status_code}")
        print(f"響應長度: {len(response.text)} 字符")
        print()

        if response.status_code == 200:
            try:
                data = response.json()
                print("JSON 結構:")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])  # 只顯示前2000字符

                # 檢查 feed 結構
                if 'feed' in data:
                    feed = data['feed']
                    print(f"\nFeed 包含的鍵: {list(feed.keys())}")

                    if 'entry' in feed:
                        entries = feed['entry']
                        print(f"Entry 數量: {len(entries)}")

                        if entries:
                            print(f"\n第一個 entry 的鍵: {list(entries[0].keys())}")
                            if len(entries) > 1:
                                print(f"第二個 entry 的鍵: {list(entries[1].keys())}")

                                # 檢查第二個 entry (第一個評論) 的結構
                                review_entry = entries[1]
                                print("\n評論 entry 詳細結構:")
                                for key, value in review_entry.items():
                                    if isinstance(value, dict):
                                        print(f"  {key}: {list(value.keys())}")
                                    else:
                                        print(f"  {key}: {type(value).__name__}")

            except json.JSONDecodeError as e:
                print(f"JSON 解析失敗: {e}")
                print("原始響應內容 (前500字符):")
                print(response.text[:500])
        else:
            print(f"請求失敗: {response.status_code}")
            print(response.text[:500])

    except Exception as e:
        print(f"請求異常: {e}")

def main():
    APP_ID = 6479990131  # Fubon Bank
    COUNTRY = "tw"

    print("調試 App Store API 響應")
    print("=" * 50)

    debug_api_response(APP_ID, COUNTRY, page=1)

if __name__ == "__main__":
    main()
