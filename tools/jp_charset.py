#!/usr/bin/env python3
"""
Character set definition for Japanese bitmap font generation.

Outputs a character code range string for font2bitmap.py -c option.

Usage:
    python3 tools/jp_charset.py          # print -c argument string
    python3 tools/jp_charset.py --count  # print character count
"""

import sys


def unique_chars(s):
    """Return de-duplicated characters preserving order."""
    seen = set()
    result = []
    for ch in s:
        if ch not in seen:
            seen.add(ch)
            result.append(ch)
    return result


# ---------------------------------------------------------------------------
# Character ranges (will be output in "start-end" or single "0xNN" format)
# ---------------------------------------------------------------------------
RANGES = [
    "0x20-0x7e",       # ASCII printable (space through tilde)
    "0xb0",            # ° degree sign
    "0x2014-0x2015",   # — ―
    "0x2026",          # …
    "0x3000-0x3003",   # Ideographic space 、。〃
    "0x300c-0x300f",   # 「」『』
    "0x3010-0x3011",   # 【】
    "0x3041-0x3096",   # Hiragana
    "0x30a1-0x30fc",   # Katakana + prolonged sound mark ー
    "0xff01",          # ！
    "0xff08-0xff09",   # （）
    "0xff0c",          # ，
    "0xff0e",          # ．
    "0xff1a-0xff1b",   # ：；
    "0xff1f",          # ？
]

# ---------------------------------------------------------------------------
# Common kanji - top ~500 by frequency in everyday Japanese text
# Source: newspaper / web corpus frequency analysis
# ---------------------------------------------------------------------------
_KANJI_RAW = (
    # Row 1-5: Top frequency kanji (政治・社会・一般)
    "日一国会人年大十二本中長出三同時政事自行社見月分議後前民生連"
    "五発間対上部東者党地合市業内相方四定今回新場金員九入選立開手"
    "米力学問高代明実円関決子動京全目表戦経通外最言氏現理調体化田"
    "当八六約主題下首意法不来作性的要用制治度務強気小七成期公持野"
    "協取都和統以機平総加山思家話世受区城北半記省西原村権心界品文"
    # Row 6-8: 報道・情報・日常
    "朝届報道変情特指示組有考正論必住建物使点保確英数識感覚基助各"
    "委付与件費求応真読判書第結果次満需給解利活資白案規女断改革配"
    "提条例交友好向増認多少反系列述均等含慮観察録別項号着限告際番"
    "所験程完了載構模類象格準備終教育想像放送"
    # 天気関連
    "晴曇雨雪雷風霧暑寒涼温湿乾快暖冷春夏秋冬"
    # 曜日・時間
    "火水木土曜週午夜朝昼夕刻秒"
    # タスク・仕事関連
    "予約束確認整頓掃除買購入届販売営業会議資料作成編集送信返信"
    "開始停止再起打電話連絡相談依頼承知完了済未着手進行中待機延期"
    # 日常生活
    "食事朝昼夕飯飲料理洗濯片付掃除散歩運動睡眠休憩外出帰宅"
    # 場所・方向
    "駅店校院園館場所東西南北左右上下前後近遠"
    # 数量・程度
    "万千百億兆個枚本台回件名人度分秒時間週月年"
    # 感情・状態
    "良悪楽苦難易忙暇元気病痛疲安危険急遅早速"
    # 色
    "赤青黄緑白黒茶紫橙灰"
    # その他よく使う漢字
    "書写真画音声映像電車道路空海川池花鳥犬猫魚"
    "親兄弟姉妹夫妻息娘祖父母友達先輩後輩同僚上司"
    "医者歯科薬病院銀郵局図書役届届届届届届届届届"
)

# De-duplicate kanji (removes trailing placeholders and any accidental repeats)
KANJI_CHARS = unique_chars(_KANJI_RAW)

# Convert kanji characters to hex codepoint strings
KANJI_CODES = [f"0x{ord(c):04x}" for c in KANJI_CHARS]


def count_chars_in_ranges(ranges):
    """Count the number of individual characters covered by range strings."""
    total = 0
    for part in ranges:
        if "-" in part and not part.startswith("-"):
            # Handle "0xAAAA-0xBBBB" ranges but not negative numbers
            halves = part.split("-")
            if len(halves) == 2:
                start = int(halves[0], 16)
                end = int(halves[1], 16)
                total += end - start + 1
            else:
                total += 1
        else:
            total += 1
    return total


def main():
    all_parts = RANGES + KANJI_CODES
    charset_arg = ",".join(all_parts)

    if "--count" in sys.argv:
        range_count = count_chars_in_ranges(RANGES)
        kanji_count = len(KANJI_CODES)
        total = range_count + kanji_count
        print(f"Range characters : {range_count}")
        print(f"Kanji characters : {kanji_count}")
        print(f"Total characters : {total}")
    else:
        print(charset_arg)


if __name__ == "__main__":
    main()
