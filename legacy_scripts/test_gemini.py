#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_gemini.py - 簡單測試 Gemini API 連接和功能（新版 google-genai 寫法）
"""

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types


def test_gemini_api() -> bool:
    """測試 Gemini API 基本功能（非串流版本，回傳 text）"""

    # 載入環境變數
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        print("❌ 錯誤: 未找到 GEMINI_API_KEY/GOOGLE_API_KEY 環境變數")
        print("請在 .env 文件中設置您的 API key，例如：GEMINI_API_KEY=xxxxx")
        return False

    try:
        print("🔄 初始化 Gemini 客戶端...")
        client = genai.Client(api_key=api_key)

        # 測試模型（可改 gemini-2.5-flash）
        model = "gemini-2.5-pro"
        print(f"🔄 測試模型: {model}")

        # 推薦：直接用字串當 contents；避免舊版 Content/Part 寫法混淆
        user_prompt = "請用中文回答：今天的天氣如何？只需要簡短回答，不要多說。"

        # 新版設定：關閉 thinking、使用純文字輸出
        config = types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.95,
            max_output_tokens=1024,
            response_mime_type="text/plain",
            thinking_config=types.ThinkingConfig(thinking_budget=0),  # 關閉思考，避免空回覆
            # 如需放寬安全門檻，可取消註解：
            # safety_settings=[
            #     types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            #     types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            #     types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            #     types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            # ],
        )

        print("🔄 發送請求到 Gemini API...")
        resp = client.models.generate_content(
            model=model,
            contents=user_prompt,   # ✅ 直接字串
            config=config,          # ✅ 新版設定
        )

        text = (resp.text or "").strip() if resp else ""
        if text:
            print("✅ API 調用成功！")
            print("📝 Gemini 回應：")
            print(f"   {text}")
            return True

        print("❌ API 返回空響應")
        # 額外除錯資訊（若 SDK 有提供就印出）
        try:
            print("  - prompt_feedback:", getattr(resp, "prompt_feedback", None))
            print("  - candidates:", len(getattr(resp, "candidates", []) or []))
            print("  - usage_metadata:", getattr(resp, "usage_metadata", None))
        except Exception:
            pass
        return False

    except Exception as e:
        error_message = str(e)
        print(f"❌ API 調用失敗: {error_message}")

        # 常見錯誤建議
        em = error_message.lower()
        if "api_key" in em or "unauthorized" in em or "permission" in em:
            print("💡 建議檢查:")
            print("   - API key 是否正確/有效（專案/金鑰權限是否包含 Gemini）")
            print("   - 是否放在 GEMINI_API_KEY 或 GOOGLE_API_KEY")
        elif "quota" in em or "rate limit" in em:
            print("💡 建議:")
            print("   - 檢查配額或計費狀態")
            print("   - 降低呼叫頻率稍後重試")
        elif "503" in em or "unavailable" in em or "timeout" in em:
            print("💡 建議:")
            print("   - 可能是暫時性問題，稍後重試")
            print("   - 檢查網路/代理設定")
        return False


def main():
    print("=== Gemini API 測試工具（新版） ===")
    ok = test_gemini_api()
    print()
    if ok:
        print("🎉 測試通過！Gemini API 可以正常使用")
    else:
        print("❌ 測試失敗，請檢查配置與網路或上方錯誤提示")
    print("=== 測試完成 ===")


if __name__ == "__main__":
    main()
