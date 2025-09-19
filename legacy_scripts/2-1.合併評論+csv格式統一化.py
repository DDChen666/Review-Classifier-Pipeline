#!/usr/bin/env python3
"""
評論數據合併與格式統一化工具

功能：
- 讀取Google Play和App Store的評論CSV文件
- 統一字段格式，只保留兩個平台共有的字段
- 合併為單一CSV文件

統一字段設計：
- platform: 平台標識 ("google_play" 或 "app_store")
- reviewId: 評論ID
- userName: 用戶名稱
- rating: 評分 (1-5星)
- date: 評論時間
- content: 評論內容
"""

import os
import sys
import pandas as pd
from datetime import datetime
import glob


def load_google_play_reviews(csv_path):
    """
    加載Google Play評論數據

    Args:
        csv_path (str): CSV文件路徑

    Returns:
        pd.DataFrame: 統一格式的DataFrame
    """
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')

        # 檢查必要的字段
        required_columns = ['reviewId', 'userName', 'score', 'at', 'content']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"警告：Google Play CSV缺少字段：{missing_columns}")

        # 創建統一格式
        unified_data = []
        for _, row in df.iterrows():
            unified_row = {
                'platform': 'google_play',
                'reviewId': str(row.get('reviewId', '')),
                'userName': str(row.get('userName', '')),
                'rating': int(row.get('score', 0)) if pd.notna(row.get('score')) else 0,
                'date': str(row.get('at', '')),
                'content': str(row.get('content', ''))
            }
            unified_data.append(unified_row)

        return pd.DataFrame(unified_data)

    except Exception as e:
        print(f"讀取Google Play CSV失敗：{e}")
        return pd.DataFrame()


def load_app_store_reviews(csv_path):
    """
    加載App Store評論數據

    Args:
        csv_path (str): CSV文件路徑

    Returns:
        pd.DataFrame: 統一格式的DataFrame
    """
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')

        # 檢查必要的字段
        required_columns = ['reviewId', 'userName', 'rating', 'date', 'review']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"警告：App Store CSV缺少字段：{missing_columns}")

        # 創建統一格式
        unified_data = []
        for _, row in df.iterrows():
            # 合併標題和內容
            title = str(row.get('title', ''))
            review_content = str(row.get('review', ''))
            content = f"{title}\n{review_content}".strip() if title else review_content

            unified_row = {
                'platform': 'app_store',
                'reviewId': str(row.get('reviewId', '')),
                'userName': str(row.get('userName', '')),
                'rating': int(row.get('rating', 0)) if pd.notna(row.get('rating')) else 0,
                'date': str(row.get('date', '')),
                'content': content
            }
            unified_data.append(unified_row)

        return pd.DataFrame(unified_data)

    except Exception as e:
        print(f"讀取App Store CSV失敗：{e}")
        return pd.DataFrame()


def find_latest_csv_files(output_dir):
    """
    查找最新的評論CSV文件

    Args:
        output_dir (str): 輸出目錄路徑

    Returns:
        tuple: (google_play_path, app_store_path) 或 (None, None)
    """
    try:
        # 查找所有CSV文件
        csv_files = glob.glob(os.path.join(output_dir, "*.csv"))

        google_play_files = [f for f in csv_files if 'google_play' in os.path.basename(f)]
        app_store_files = [f for f in csv_files if 'app_store' in os.path.basename(f)]

        # 按修改時間排序，取最新的
        google_play_path = max(google_play_files, key=os.path.getmtime) if google_play_files else None
        app_store_path = max(app_store_files, key=os.path.getmtime) if app_store_files else None

        return google_play_path, app_store_path

    except Exception as e:
        print(f"查找CSV文件失敗：{e}")
        return None, None


def merge_reviews(google_df, app_store_df):
    """
    合併兩個平台的評論數據

    Args:
        google_df (pd.DataFrame): Google Play評論
        app_store_df (pd.DataFrame): App Store評論

    Returns:
        pd.DataFrame: 合併後的DataFrame
    """
    if google_df.empty and app_store_df.empty:
        print("沒有有效的評論數據")
        return pd.DataFrame()

    # 合併DataFrame
    merged_df = pd.concat([google_df, app_store_df], ignore_index=True)

    # 按時間排序（最新的在前）
    try:
        merged_df['date'] = pd.to_datetime(merged_df['date'], errors='coerce')
        merged_df = merged_df.sort_values('date', ascending=False)
        merged_df['date'] = merged_df['date'].dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"時間排序失敗：{e}")

    return merged_df


def clean_reviews(df):
    """
    清理評論數據

    Args:
        df (pd.DataFrame): 要清理的DataFrame

    Returns:
        pd.DataFrame: 清理後的DataFrame
    """
    if df.empty:
        return df

    # 移除重複的評論（基於reviewId）
    df = df.drop_duplicates(subset=['reviewId'], keep='first')

    # 移除無效數據
    df = df[df['rating'].between(1, 5)]  # 評分應在1-5之間
    df = df[df['content'].str.len() > 0]  # 內容不為空

    # 清理內容文本
    df['content'] = df['content'].str.strip()
    df['userName'] = df['userName'].str.strip()

    return df


def generate_output_filename():
    """
    生成輸出文件名

    Returns:
        str: 輸出文件名
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"merged_reviews_{timestamp}.csv"


def main():
    """主程式"""

    # 設定路徑
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    input_dir = os.path.join(project_root, "1.爬蟲", "output")
    output_dir = os.path.join(project_root, "2.數據篩選+格式統一+合併+清洗+標註", "output")

    # 確保輸出目錄存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("=" * 60)
    print("評論數據合併與格式統一化工具")
    print("=" * 60)
    print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"輸入目錄: {input_dir}")
    print(f"輸出目錄: {output_dir}")
    print()

    # 查找最新的CSV文件
    google_path, app_store_path = find_latest_csv_files(input_dir)

    if not google_path and not app_store_path:
        print("錯誤：找不到任何評論CSV文件")
        return

    print("找到的CSV文件：")
    if google_path:
        print(f"✓ Google Play: {os.path.basename(google_path)}")
    else:
        print("✗ 未找到Google Play評論文件")

    if app_store_path:
        print(f"✓ App Store: {os.path.basename(app_store_path)}")
    else:
        print("✗ 未找到App Store評論文件")

    print()

    # 加載數據
    google_df = pd.DataFrame()
    app_store_df = pd.DataFrame()

    if google_path:
        print("加載Google Play評論...")
        google_df = load_google_play_reviews(google_path)
        print(f"✓ 加載 {len(google_df)} 條Google Play評論")

    if app_store_path:
        print("加載App Store評論...")
        app_store_df = load_app_store_reviews(app_store_path)
        print(f"✓ 加載 {len(app_store_df)} 條App Store評論")

    print()

    # 合併數據
    print("合併評論數據...")
    merged_df = merge_reviews(google_df, app_store_df)
    print(f"✓ 合併後總計 {len(merged_df)} 條評論")

    # 清理數據
    print("清理數據...")
    cleaned_df = clean_reviews(merged_df)
    print(f"✓ 清理後剩餘 {len(cleaned_df)} 條評論")

    # 保存結果
    if not cleaned_df.empty:
        output_filename = generate_output_filename()
        output_path = os.path.join(output_dir, output_filename)

        cleaned_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"✓ 合併評論已保存: {output_path}")
    else:
        print("✗ 沒有有效的評論數據，跳過保存")

    print()
    print("=" * 60)
    print("處理完成總結:")
    print(f"Google Play 評論: {len(google_df)} 條")
    print(f"App Store 評論: {len(app_store_df)} 條")
    print(f"合併後總計: {len(merged_df)} 條")
    print(f"清理後有效: {len(cleaned_df)} 條")
    print(f"完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
