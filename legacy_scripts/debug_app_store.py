#!/usr/bin/env python3
"""
App Store 評論抓取調試腳本
"""

from app_store_scraper import AppStore
import requests
import json

def test_app_id(app_id, country="tw"):
    """測試 App ID 是否有效"""
    print(f"測試 App ID: {app_id}")

    try:
        app = AppStore(country=country, app_name="", app_id=app_id)
        print(f"初始化成功: {app}")

        # 嘗試獲取評論
        app.review(how_many=5)
        print(f"獲取到 {len(app.reviews)} 條評論")

        if app.reviews:
            print("前 3 條評論:")
            for i, review in enumerate(app.reviews[:3]):
                print(f"  {i+1}. {review.get('userName', 'Unknown')}: {review.get('rating', 'N/A')}星")

        return len(app.reviews) > 0

    except Exception as e:
        print(f"錯誤: {str(e)}")
        return False

def search_app_store(query, country="tw"):
    """在 App Store 搜索應用"""
    print(f"搜索應用: {query}")

    # 使用 iTunes Search API
    url = "https://itunes.apple.com/search"
    params = {
        "term": query,
        "country": country,
        "entity": "software",
        "limit": 5
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if data.get("results"):
            print(f"找到 {len(data['results'])} 個應用:")
            for i, app in enumerate(data["results"][:3]):
                print(f"  {i+1}. {app['trackName']} (ID: {app['trackId']})")
                print(f"     開發者: {app['artistName']}")
                print(f"     類型: {app['primaryGenreName']}")
                print()
        else:
            print("未找到應用")

    except Exception as e:
        print(f"搜索失敗: {str(e)}")

def main():
    print("App Store 調試工具")
    print("=" * 50)

    # 測試當前使用的 App ID
    current_id = 6479990131
    print("1. 測試當前 App ID:")
    test_app_id(current_id)
    print()

    # 搜索富邦銀行相關應用
    print("2. 搜索富邦銀行相關應用:")
    search_terms = ["富邦銀行", "fubon bank", "富邦"]
    for term in search_terms:
        search_app_store(term)
        print()

    # 測試可能的其他 App ID
    print("3. 測試其他可能的 App ID:")
    possible_ids = [
        6479990131,  # 原來的
        1440750338,  # 富邦銀行 iOS App (可能)
        1440750339,  # 另一個可能
        1500000000   # 測試用
    ]

    for app_id in possible_ids:
        if app_id != current_id:  # 跳過已經測試過的
            print(f"測試 App ID {app_id}:")
            test_app_id(app_id)
            print()

if __name__ == "__main__":
    main()
