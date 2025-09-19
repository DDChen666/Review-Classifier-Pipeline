#!/usr/bin/env python3
"""
測試環境設置的簡單腳本
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

def test_env():
    """測試環境變數載入"""
    # 載入環境變數
    script_dir = Path(__file__).parent
    env_path = script_dir / '.env'

    if env_path.exists():
        load_dotenv(env_path)
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and api_key != "your_gemini_api_key_here":
            print("✓ GEMINI_API_KEY 已設置")
        else:
            print("✗ GEMINI_API_KEY 未設置或使用預設值")
    else:
        print("✗ .env 文件不存在")

def test_imports():
    """測試依賴包導入"""
    try:
        import google.genai
        print("✓ google-genai 導入成功")
    except ImportError:
        print("✗ google-genai 導入失敗")

    try:
        from dotenv import load_dotenv
        print("✓ python-dotenv 導入成功")
    except ImportError:
        print("✗ python-dotenv 導入失敗")

def test_files():
    """測試文件存在性"""
    script_dir = Path(__file__).parent
    output_dir = script_dir / "output"

    if output_dir.exists():
        print("✓ output 目錄存在")
        json_files = list(output_dir.glob("*.json"))
        if json_files:
            print(f"✓ 找到 {len(json_files)} 個 JSON 文件:")
            for f in json_files:
                if f.name.startswith(("test_reviews", "train_reviews")):
                    print(f"  - {f.name}")
                    # 檢查文件內容
                    try:
                        with open(f, 'r', encoding='utf-8') as file:
                            data = json.load(file)
                            print(f"    包含 {len(data)} 條評論")
                    except Exception as e:
                        print(f"    ✗ 讀取失敗: {e}")
        else:
            print("✗ output 目錄中沒有 JSON 文件")
    else:
        print("✗ output 目錄不存在")

if __name__ == "__main__":
    print("=== 環境測試 ===")
    test_env()
    test_imports()
    test_files()
    print("=== 測試完成 ===")
