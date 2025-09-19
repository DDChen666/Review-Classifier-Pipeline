#!/usr/bin/env python3
"""
數據清洗與待標註集生成工具

功能：
- 讀取合併評論CSV文件
- 數據清洗：轉換全形符號為半形、移除表情符號、移除短文本
- 輸出單一的JSON格式文件，用於後續的數據標註

JSON格式：
[
    {"text": "評論內容", "primary": "", "secondary": ""},
    ...
]
"""

import os
import sys
import pandas as pd
import json
import re
from datetime import datetime
import random
import glob
import unicodedata


def find_merged_reviews_file(output_dir):
    """
    查找最新的merged_reviews CSV文件

    Args:
        output_dir (str): 輸出目錄路徑

    Returns:
        str: CSV文件路徑，如果找不到則返回None
    """
    try:
        # 查找所有merged_reviews_*.csv文件
        pattern = os.path.join(output_dir, "merged_reviews_*.csv")
        files = glob.glob(pattern)

        if not files:
            print("✗ 找不到任何merged_reviews文件")
            return None

        # 如果有多個文件，按修改時間排序，取最新的
        latest_file = max(files, key=os.path.getmtime)
        print(f"✓ 找到最新的merged_reviews文件：{os.path.basename(latest_file)}")
        return latest_file

    except Exception as e:
        print(f"✗ 查找文件失敗：{e}")
        return None


def load_merged_reviews(csv_path):
    """
    加載合併評論CSV文件

    Args:
        csv_path (str): CSV文件路徑

    Returns:
        pd.DataFrame: 加載的DataFrame
    """
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        print(f"✓ 成功加載 {len(df)} 條評論數據")
        return df
    except Exception as e:
        print(f"✗ 加載CSV文件失敗：{e}")
        return pd.DataFrame()


def convert_fullwidth_to_halfwidth(text):
    """
    將全形字符轉換為半形字符

    Args:
        text (str): 輸入文本

    Returns:
        str: 轉換後的文本
    """
    if not isinstance(text, str):
        return ""

    fullwidth_chars = "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ！＂＃＄％＆＇（）＊＋，－．／：；＜＝＞？＠［＼］＾＿｀｛｜｝～　"
    halfwidth_chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ "
    trans_table = str.maketrans(fullwidth_chars, halfwidth_chars)
    return text.translate(trans_table)


def remove_emojis(text):
    """
    移除表情符號和特殊符號 - 改进版本
    使用更全面的Unicode范围来匹配各种表情符号

    Args:
        text (str): 輸入文本

    Returns:
        str: 移除表情符號後的文本
    """
    if not isinstance(text, str):
        return ""
    
    # 更全面的表情符号Unicode范围
    emoji_patterns = [
        # 基础表情符号
        r'[\U0001F600-\U0001F64F]',  # emoticons
        r'[\U0001F300-\U0001F5FF]',  # symbols & pictographs
        r'[\U0001F680-\U0001F6FF]',  # transport & map symbols
        r'[\U0001F1E0-\U0001F1FF]',  # flags (iOS)
        
        # 扩展表情符号范围
        r'[\U0001F900-\U0001F9FF]',  # supplemental symbols and pictographs
        r'[\U0001FA00-\U0001FA6F]',  # chess symbols
        r'[\U0001FA70-\U0001FAFF]',  # symbols and pictographs extended-A
        r'[\U00002600-\U000026FF]',  # miscellaneous symbols
        r'[\U00002700-\U000027BF]',  # dingbats
        
        # 其他相关符号
        r'[\U0001F004\U0001F0CF]',   # mahjong and playing cards
        r'[\U0001F170-\U0001F251]',  # enclosed characters
        r'[\U0000FE00-\U0000FE0F]',  # variation selectors
        r'[\U00002000-\U0000206F]',  # general punctuation (包括零宽字符)
        r'[\U0000200D]',             # zero width joiner
        r'[\U0000FE0F]',             # variation selector-16
        
        # 特殊字符
        r'[™©®]',                    # trademark, copyright, registered
        r'[\u2122\u00A9\u00AE]',     # 同上，不同编码
        
        # 其他可能的表情符号范围
        r'[\U0001F780-\U0001F7FF]',  # geometric shapes extended
        r'[\U0001F800-\U0001F8FF]',  # supplemental arrows-C
    ]
    
    result = text
    for pattern in emoji_patterns:
        result = re.sub(pattern, '', result, flags=re.UNICODE)
    
    # 额外处理：移除连续的修饰符和组合字符
    # 这些字符通常与表情符号一起出现
    modifiers_pattern = r'[\U0001F3FB-\U0001F3FF]+'  # skin tone modifiers
    result = re.sub(modifiers_pattern, '', result, flags=re.UNICODE)
    
    # 使用unicodedata来识别并移除其他可能的符号字符
    # 但要保留标点符号和其他有用字符
    cleaned_chars = []
    for char in result:
        # 获取字符的Unicode类别
        category = unicodedata.category(char)
        # 保留字母、数字、标点、空格、中文等有用字符
        if category[0] in ['L', 'N', 'P', 'Z', 'M'] or unicodedata.name(char, '').startswith('CJK'):
            # 但排除一些特殊符号类别
            if not (category == 'So' and ord(char) > 0x1F000):  # 排除高位符号字符
                cleaned_chars.append(char)
    
    result = ''.join(cleaned_chars)
    return result


def count_chinese_characters(text):
    """
    計算中文字符數量

    Args:
        text (str): 輸入文本

    Returns:
        int: 中文字符數量
    """
    if not isinstance(text, str):
        return 0
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    return len(chinese_pattern.findall(text))


def clean_text(text):
    """
    清理文本：轉換全形為半形、移除表情符號

    Args:
        text (str): 輸入文本

    Returns:
        str: 清理後的文本
    """
    if not isinstance(text, str):
        return ""
    text = convert_fullwidth_to_halfwidth(text)
    text = remove_emojis(text)
    # 清理多余的空白字符，但保留单个空格
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def filter_short_texts(data_list, min_chinese_chars=2):
    """
    過濾掉中文字符數量不足的文本

    Args:
        data_list (list): 數據列表
        min_chinese_chars (int): 最少中文字符數

    Returns:
        list: 過濾後的數據列表
    """
    filtered_data = []
    removed_count = 0

    for item in data_list:
        text = item.get('text', '')
        chinese_count = count_chinese_characters(text)
        if chinese_count > min_chinese_chars:
            filtered_data.append(item)
        else:
            removed_count += 1

    print(f"✓ 移除了 {removed_count} 條短文本（中文字符 ≤ {min_chinese_chars}）")
    return filtered_data


def save_json_file(data, file_path):
    """
    保存數據為JSON文件

    Args:
        data (list): 要保存的數據
        file_path (str): 文件路徑
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ 已保存 {len(data)} 條數據到 {file_path}")
    except Exception as e:
        print(f"✗ 保存JSON文件失敗：{e}")


def test_emoji_removal():
    """
    测试表情符号移除功能
    """
    test_cases = [
        "这是测试文本😀😃😄😁😆😅😂🤣😊😇",
        "好棒👍👎👌👊✊🤛🤜🤞✌️🤟🤘👏",
        "心情💕💖💗💘💝💟💜🖤💛💚💙💔❤️",
        "天气☀️⛅⛈️🌧️⌨️📱💻🖥️🖨️⌚📷📹🎥📞☎️📠",
        "食物🍎🍊🍋🍌🍉🍇🍓🫐🍈🍒🍑🥭🍍🥥🥝",
        "普通标点符号：，。！？；：""''（）【】《》",
        "这里有™版权©符号和®注册商标",
        "混合内容😀这是中文🎉English😊123数字！@#$%符号"
    ]
    
    print("表情符号清除测试：")
    print("-" * 50)
    for i, test_text in enumerate(test_cases, 1):
        cleaned = remove_emojis(test_text)
        print(f"{i}. 原始: {test_text}")
        print(f"   清理: {cleaned}")
        print()


def main():
    """主程式"""

    print("=" * 60)
    print("數據清洗與待標註集生成工具")
    print("=" * 60)

    # 可选：运行表情符号清除测试
    # test_emoji_removal()
    # return

    # 設定路徑
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"輸出目錄: {output_dir}")
    print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 1. 查找並加載合併後的CSV文件
    input_file = find_merged_reviews_file(output_dir)
    if not input_file:
        return
    df = load_merged_reviews(input_file)
    if df.empty:
        print("✗ 沒有有效的評論數據")
        return
    print()

    # 2. 數據清洗
    print("2. 數據清洗...")
    cleaned_data = []
    for _, row in df.iterrows():
        original_text = str(row.get('content', ''))
        if not original_text.strip():
            continue
        cleaned_text = clean_text(original_text)
        data_item = {
            "text": cleaned_text,
            "primary": "",
            "secondary": ""
        }
        cleaned_data.append(data_item)
    print(f"✓ 原始數據: {len(df)} 條，清洗後剩餘: {len(cleaned_data)} 條")
    print()

    # 3. 過濾短文本
    print("3. 過濾短文本...")
    filtered_data = filter_short_texts(cleaned_data, min_chinese_chars=2)
    print(f"✓ 過濾後數據: {len(filtered_data)} 條")
    print()

    if not filtered_data:
        print("✗ 沒有足夠的數據可供標註，程序終止。")
        return

    # 4. 保存為待標註文件
    print("4. 保存為待標註的JSON文件...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"unlabeled_reviews_{timestamp}.json"
    output_path = os.path.join(output_dir, output_filename)
    save_json_file(filtered_data, output_path)
    print()

    # 顯示樣例
    print("5. 數據樣例:")
    for i, item in enumerate(filtered_data[:3]):
        print(f"  {i+1}. {item}")
    print()

    # 總結
    print("=" * 60)
    print("處理完成總結:")
    print(f"原始評論數量: {len(df)}")
    print(f"清洗後數量: {len(cleaned_data)}")
    print(f"最終有效數據: {len(filtered_data)}")
    print(f"輸出文件: {output_filename}")
    print(f"完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    main()