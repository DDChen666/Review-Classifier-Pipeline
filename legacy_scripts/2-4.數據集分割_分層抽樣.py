# --- START OF FILE 2-4.數據集分割(分層抽樣).py ---

#!/usr/bin/env python3
"""
數據集分割工具 (分層抽樣)

功能：
- 讀取已標註的評論 JSON 文件 (由 2-3.數據標註.py 生成)
- 基於 'primary' 類別進行分層抽樣
- 將數據集按 80:20 的比例分割為訓練集和測試集
- 輸出為 JSON 格式文件
"""

import os
import json
import pandas as pd
import glob
from datetime import datetime
from sklearn.model_selection import train_test_split

def find_latest_dataset_file(output_dir):
    """
    優先讀取 2-3 自動修復後的資料集：
      1) labeled_reviews_*_fixed.json
      2) labeled_reviews_*.json（回退）
    """
    try:
        fixed_pattern = os.path.join(output_dir, "labeled_reviews_*_fixed.json")
        fixed_files = glob.glob(fixed_pattern)
        if fixed_files:
            latest = max(fixed_files, key=os.path.getmtime)
            print(f"[OK] 找到最新的『已修復』資料集：{os.path.basename(latest)}")
            return latest

        labeled_pattern = os.path.join(output_dir, "labeled_reviews_*.json")
        labeled_files = glob.glob(labeled_pattern)
        if labeled_files:
            latest = max(labeled_files, key=os.path.getmtime)
            print(f"[OK] 未找到 *_fixed.json，回退使用：{os.path.basename(latest)}")
            return latest

        print("[WARN] 找不到任何 labeled_reviews 檔案")
        return None
    
    except Exception as e:
        print(f"[WARN] 查找文件失敗：{e}")
        return None

def save_as_json(df, file_path):
    """
    將 DataFrame 保存為指定的 JSON 格式

    Args:
        df (pd.DataFrame): 要保存的 DataFrame
        file_path (str): 文件路徑
    """
    try:
        # 使用 to_json 并设置 orient='records' 来生成所需的列表-字典格式
        df.to_json(file_path, orient='records', force_ascii=False, indent=2)
        print(f"[OK] 已保存 {len(df)} 條數據到 {os.path.basename(file_path)}")
    except Exception as e:
        print(f"[WARN] 保存 JSON 文件失敗：{e}")

def main():
    """主程式"""

    print("=" * 60)
    print("數據集分割工具 (分層抽樣)")
    print("=" * 60)

    # 設定路徑
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")

    print(f"工作目錄: {output_dir}")
    print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 1. 查找並加載數據
    print("1. 查找並加載最新資料集（優先 *_fixed.json）...")
    input_file = find_latest_dataset_file(output_dir)
    if not input_file:
        return

    try:
        with open(input_file, "r", encoding="utf-8-sig") as f:
            raw_data = json.load(f)
        if not isinstance(raw_data, list):
            print("[WARN] 檔案內容不是列表格式，請確認資料來源。")
            return
        df = pd.DataFrame(raw_data)
        print(f"[OK] 成功加載 {len(df)} 條已標註評論")
    except Exception as e:
        print(f"[WARN] 加載 JSON 文件失敗：{e}")
        return

    if df.empty:
        print("[WARN] 數據為空，無法進行分割")
        return

    # 檢查 'primary' 欄位是否存在
    if 'primary' not in df.columns or df['primary'].isnull().any():
        print("[WARN] 錯誤: 'primary' 欄位不存在或包含空值。請確保數據已完全標註。")
        return

    print()

    # 2. 顯示原始類別分佈
    print("2. 原始數據類別分佈:")
    class_distribution = df['primary'].value_counts(normalize=True).sort_index()
    print(class_distribution.to_string())
    print()
    
    # 檢查是否有類別樣本過少（小於2），這會導致分層抽樣失敗
    if (df['primary'].value_counts() < 2).any():
        print("警告: 存在樣本數小於 2 的類別，這可能導致分層抽樣失敗或不穩定。")
        print(df['primary'].value_counts())
        print()


    # 3. 執行分層抽樣分割 (80:20)
    print("3. 執行分層抽樣 (80:20)...")
    try:
        train_df, test_df = train_test_split(
            df,
            test_size=0.2,
            random_state=42,  # 確保每次分割結果都一樣，方便重現
            stratify=df['primary']  # 關鍵！指定依據 'primary' 欄位進行分層
        )
        print(f"[OK] 分割完成:")
        print(f"  - 訓練集: {len(train_df)} 條")
        print(f"  - 測試集: {len(test_df)} 條")
        print()
    except ValueError as e:
        print(f"[WARN] 分層抽樣失敗: {e}")
        print("  - 這通常是因為某些類別的樣本數太少（只有1個）。")
        return

    # 4. 驗證分割後的類別分佈
    print("4. 驗證分割後類別分佈:")
    train_dist = train_df['primary'].value_counts(normalize=True).sort_index()
    test_dist = test_df['primary'].value_counts(normalize=True).sort_index()
    
    comparison_df = pd.DataFrame({
        'Original': class_distribution,
        'Train Set': train_dist,
        'Test Set': test_dist
    })
    print(comparison_df.to_string(float_format="%.4f"))
    print("\n(可以看到，訓練集和測試集的類別比例與原始數據非常接近)\n")


    # 5. 保存文件
    print("5. 保存訓練集與測試集...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    train_file = os.path.join(output_dir, f"train_set_{timestamp}.json")
    test_file = os.path.join(output_dir, f"test_set_{timestamp}.json")

    save_as_json(train_df, train_file)
    save_as_json(test_df, test_file)

    print()
    print("=" * 60)
    print("處理完成！")
    print(f"完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    main()

# --- END OF FILE 2-4.數據集分割(分層抽樣).py ---
