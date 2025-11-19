# Pythonで日本語自然言語時刻パーサーを実装する

## はじめに

LINEリマインダーボットを開発する際、ユーザーが入力した日本語の自然言語テキストから時刻情報を抽出するパーサーを実装しました。本記事では、その中核となる `parse_natural_time()` 関数の内部実装を詳細に解説します。

## 関数のシグネチャ

```python
def parse_natural_time(text: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """
    Parse natural language time expressions.

    Args:
        text: Natural language time expression

    Returns:
        Tuple of (schedule dict, formatted description) or None if parsing fails.
    """
```

この関数は、入力テキストをパースして以下の2つの情報を返します：

1. **スケジュール辞書**: リマインダーの実行スケジュールを表すJSON互換の辞書
2. **フォーマット済み説明文**: ユーザーに表示する日時の説明文字列（例：「2025年11月20日 21:00」）

パースに失敗した場合は `None` を返します。

## 実装の全体構造

`parse_natural_time()` 関数は、以下の処理フローで動作します：

```python
def parse_natural_time(text: str) -> Optional[Tuple[Dict[str, Any], str]]:
    text = text.strip()
    now = get_current_time()  # Asia/Tokyo タイムゾーンの現在時刻

    # 内部ヘルパー関数の定義
    def parse_time_with_ampm(time_text: str) -> Tuple[int, int]:
        # ... (後述)

    # Pattern 0a: N分後
    match = re.match(r"(\d+)分後", text)
    if match:
        # ... 処理

    # Pattern 0b: N時間後
    match = re.match(r"(\d+)時間後", text)
    if match:
        # ... 処理

    # Pattern 0c-13: その他のパターン
    # ...

    return None  # どのパターンにもマッチしなかった場合
```

パターンマッチングは**上から順に試行**され、最初にマッチしたパターンで処理が確定します。そのため、より具体的なパターン（「N日後 HH:MM」）を、より一般的なパターン（「N日後」）よりも先に配置しています。

## 内部ヘルパー関数：parse_time_with_ampm

時刻表記のパース処理は、内部関数 `parse_time_with_ampm()` で集約されています。この関数は、以下の3種類の時刻表記に対応し、時刻の妥当性を検証します。

### バリデーション機能

抽出した時刻は、内部の `validate()` 関数で範囲チェックされます：

```python
def validate(hour: int, minute: int) -> Optional[Tuple[int, int]]:
    if not (0 <= minute < 60):
        return None
    if not (0 <= hour < 24):
        return None
    return (hour, minute)
```

**検証内容**：
- 時：0〜23の範囲
- 分：0〜59の範囲
- 範囲外の場合は `None` を返す

### 1. 午後表記

```python
match = re.match(r"午後\s*(\d{1,2})時?(\d{0,2})分?", time_text)
if match:
    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    if hour != 12:
        hour += 12
    return validate(hour, minute)
```

**変換ルール**：
- 午後1時 → 13時
- 午後3時30分 → 15時30分
- **午後12時 → 12時**（例外処理、12時はそのまま）

### 2. 午前表記

```python
match = re.match(r"午前\s*(\d{1,2})時?(\d{0,2})分?", time_text)
if match:
    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    if hour == 12:
        hour = 0
    return validate(hour, minute)
```

**変換ルール**：
- 午前9時 → 9時
- 午前11時30分 → 11時30分
- **午前12時 → 0時**（例外処理、午前12時は0時に変換）

### 3. 通常の時刻表記

```python
match = re.match(r"(\d{1,2})[時:](\d{0,2})分?", time_text)
if match:
    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    return validate(hour, minute)
```

**対応フォーマット**：
- `22:00` → (22, 0)
- `14時30分` → (14, 30)
- `9時` → (9, 0)

正規表現 `[時:]` により、`22:00` と `22時00分` の両方に対応しています。

## パターンマッチングの実装詳細

以下、各パターンの実装を詳細に解説します。

### Pattern 0a: N分後（相対分）

```python
match = re.match(r"(\d+)分後", text)
if match:
    minutes = int(match.group(1))
    if minutes <= 0 or minutes > 1440:  # Max 24 hours
        return None

    target_time = now + timedelta(minutes=minutes)

    schedule = {"type": "once", "run_at": target_time.isoformat()}
    desc = target_time.strftime("%Y年%m月%d日 %H:%M")
    return (schedule, desc)
```

**処理の流れ**：
1. 正規表現 `(\d+)分後` で数値部分を抽出
2. 範囲チェック（1〜1440分）
3. `timedelta` で現在時刻から加算
4. ISO 8601形式の文字列に変換して返却

**制約**：
- 最小値：1分
- 最大値：1440分（24時間）

### Pattern 0b: N時間後（相対時間）

```python
match = re.match(r"(\d+)時間後", text)
if match:
    hours = int(match.group(1))
    if hours <= 0 or hours > 168:  # Max 7 days
        return None

    target_time = now + timedelta(hours=hours)

    schedule = {"type": "once", "run_at": target_time.isoformat()}
    desc = target_time.strftime("%Y年%m月%d日 %H:%M")
    return (schedule, desc)
```

Pattern 0a と同様の構造ですが、`timedelta(hours=hours)` を使用しています。最大値は168時間（7日間）です。

### Pattern 0c: N日後 HH:MM（相対日数 + 時刻指定）

```python
match = re.match(r"(\d+)日後\s+(.+)", text)
if match:
    days = int(match.group(1))
    time_part = match.group(2)

    if days <= 0 or days > 365:
        return None

    time_tuple = parse_time_with_ampm(time_part)
    if time_tuple is None:
        return None

    hour, minute = time_tuple
    target_time = now + timedelta(days=days)
    target_time = target_time.replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )

    schedule = {"type": "once", "run_at": target_time.isoformat()}
    desc = target_time.strftime("%Y年%m月%d日 %H:%M")
    return (schedule, desc)
```

**ポイント**：
- 正規表現 `\s+` で日数と時刻の間の空白を許容
- `parse_time_with_ampm()` を使用して時刻部分をパース
- `replace()` メソッドで時刻を上書き（秒・マイクロ秒は0にリセット）

### Pattern 0d: N日後（時刻なし、デフォルト9:00）

```python
match = re.match(r"(\d+)日後$", text)
if match:
    days = int(match.group(1))

    if days <= 0 or days > 365:
        return None

    target_time = now + timedelta(days=days)
    target_time = target_time.replace(hour=9, minute=0, second=0, microsecond=0)

    schedule = {"type": "once", "run_at": target_time.isoformat()}
    desc = target_time.strftime("%Y年%m月%d日 09:00")
    return (schedule, desc)
```

**注意点**：
- 正規表現末尾の `$` により、「3日後」のみにマッチ（「3日後 14:00」は Pattern 0c でマッチ）
- デフォルト時刻は9:00に固定

### Pattern 1: 毎週 曜日 時刻（週次繰り返し）

```python
match = re.match(r"毎週\s*([月火水木金土日]曜?日?)\s*(.+)", text)
if match:
    weekday_text = match.group(1)
    time_part = match.group(2)

    weekday = get_weekday_number(weekday_text)
    if weekday is None:
        return None

    time_tuple = parse_time_with_ampm(time_part)
    if time_tuple is None:
        return None

    hour, minute = time_tuple
    time_str = f"{hour:02d}:{minute:02d}"

    schedule = {"type": "weekly", "weekday": weekday, "time": time_str}
    desc = f"毎週{weekday_text} {time_str}"
    return (schedule, desc)
```

**スケジュールオブジェクトの構造**：
```json
{
  "type": "weekly",
  "weekday": 0,  // 0=月曜、1=火曜、...、6=日曜
  "time": "21:00"
}
```

**曜日の正規表現**：
- `[月火水木金土日]` で曜日文字を抽出
- `曜?日?` で「月」「月曜」「月曜日」のいずれにも対応

### Pattern 2: 毎月 DD日 時刻（月次繰り返し）

```python
match = re.match(r"毎月\s*(\d{1,2})日?\s*(.+)", text)
if match:
    day = int(match.group(1))
    time_part = match.group(2)

    if not 1 <= day <= 31:
        return None

    time_tuple = parse_time_with_ampm(time_part)
    if time_tuple is None:
        return None

    hour, minute = time_tuple
    time_str = f"{hour:02d}:{minute:02d}"

    schedule = {"type": "monthly", "day": day, "time": time_str}
    desc = f"毎月{day}日 {time_str}"
    return (schedule, desc)
```

**スケジュールオブジェクトの構造**：
```json
{
  "type": "monthly",
  "day": 15,
  "time": "20:00"
}
```

**範囲チェック**：
- 1〜31日の範囲でバリデーション
- 月によって存在しない日（2月31日など）は、別の関数 `calculate_initial_run_at()` で処理

### Pattern 3: 来週○曜日 時刻

```python
match = re.match(r"来週\s*([月火水木金土日]曜?日?)\s*(.+)", text)
if match:
    weekday_text = match.group(1)
    time_part = match.group(2)

    weekday = get_weekday_number(weekday_text)
    if weekday is None:
        return None

    time_tuple = parse_time_with_ampm(time_part)
    if time_tuple is None:
        return None

    hour, minute = time_tuple

    # Calculate next week's target weekday
    days_ahead = weekday - now.weekday() + 7  # Always next week

    target_time = now + timedelta(days=days_ahead)
    target_time = target_time.replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )

    schedule = {"type": "once", "run_at": target_time.isoformat()}
    desc = (
        target_time.strftime("%Y年%m月%d日(%a) %H:%M")
        .replace("Mon", "月")
        .replace("Tue", "火")
        .replace("Wed", "水")
        .replace("Thu", "木")
        .replace("Fri", "金")
        .replace("Sat", "土")
        .replace("Sun", "日")
    )
    return (schedule, desc)
```

**ポイント**：
- `days_ahead = weekday - now.weekday() + 7` により、**必ず来週**の曜日を計算
- 例：今日が月曜日で「来週月曜」と指定 → 7日後
- `strftime("%a")` で英語の曜日名を取得し、`replace()` で日本語に変換

### Pattern 4: 明後日 時刻

```python
match = re.match(r"明後日\s*(.+)", text)
if match:
    time_part = match.group(1).replace("の", "").strip()

    time_tuple = parse_time_with_ampm(time_part)
    if time_tuple is None:
        return None

    hour, minute = time_tuple

    target_time = now + timedelta(days=2)
    target_time = target_time.replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )

    schedule = {"type": "once", "run_at": target_time.isoformat()}
    desc = target_time.strftime("%Y年%m月%d日 %H:%M")
    return (schedule, desc)
```

**前処理**：
- `.replace("の", "")` で「明後日の14:00」のような表記にも対応
- `.strip()` で前後の空白を除去

### Pattern 5: 明日 時刻

```python
match = re.match(r"明日\s*(.+)", text)
if match:
    time_part = match.group(1).replace("の", "").strip()

    time_tuple = parse_time_with_ampm(time_part)
    if time_tuple is None:
        return None

    hour, minute = time_tuple

    target_time = now + timedelta(days=1)
    target_time = target_time.replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )

    schedule = {"type": "once", "run_at": target_time.isoformat()}
    desc = target_time.strftime("%Y年%m月%d日 %H:%M")
    return (schedule, desc)
```

Pattern 4 と同様の構造で、`timedelta(days=1)` を使用しています。

### Pattern 6: 今日 時刻

```python
match = re.match(r"今日\s*(.+)", text)
if match:
    time_part = match.group(1).replace("の", "").strip()

    time_tuple = parse_time_with_ampm(time_part)
    if time_tuple is None:
        return None

    hour, minute = time_tuple

    target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # If time has passed today, move to tomorrow
    if target_time <= now:
        target_time += timedelta(days=1)

    schedule = {"type": "once", "run_at": target_time.isoformat()}
    desc = target_time.strftime("%Y年%m月%d日 %H:%M")
    return (schedule, desc)
```

**過去時刻の自動調整**：
- `if target_time <= now:` で時刻が既に過ぎているかチェック
- 過ぎている場合は `timedelta(days=1)` で翌日に自動調整
- 例：現在時刻が15:00で「今日14:00」と指定 → 明日14:00に調整

### Pattern 7: 時刻のみ（HH:MM, HH時, 午後3時など）

```python
time_tuple = parse_time_with_ampm(text)
if time_tuple is not None:
    hour, minute = time_tuple

    target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # If time has passed today, move to tomorrow
    if target_time <= now:
        target_time += timedelta(days=1)

    schedule = {"type": "once", "run_at": target_time.isoformat()}
    desc = target_time.strftime("%Y年%m月%d日 %H:%M")
    return (schedule, desc)
```

**処理の流れ**：
- `parse_time_with_ampm()` で時刻をパース
- 今日のその時刻に設定
- 既に過ぎている場合は明日に自動調整

Pattern 6 との違いは、「今日」という明示的なキーワードがない点です。

### Pattern 8: 日付のみ YYYY-MM-DD

```python
match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", text)
if match:
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    try:
        target_time = datetime(year, month, day, 9, 0, tzinfo=TZ)
        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 09:00")
        return (schedule, desc)
    except ValueError:
        return None
```

**ポイント**：
- ISO 8601形式（`YYYY-MM-DD`）の日付をパース
- 時刻は9:00に固定
- `datetime()` コンストラクタで `ValueError` が発生した場合（無効な日付）は `None` を返す

### Pattern 9: 日付のみ MM/DD

```python
match = re.match(r"(\d{1,2})/(\d{1,2})$", text)
if match:
    month = int(match.group(1))
    day = int(match.group(2))
    year = now.year

    # If the date has passed this year, use next year
    try:
        target_time = datetime(year, month, day, 9, 0, tzinfo=TZ)
        if target_time <= now:
            target_time = datetime(year + 1, month, day, 9, 0, tzinfo=TZ)

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 09:00")
        return (schedule, desc)
    except ValueError:
        return None
```

**年の自動補完**：
- 年の指定がないため、現在年を使用
- **既に過ぎている場合は翌年に自動調整**
- 例：現在が2025年12月で「5/3」と指定 → 2026年5月3日

### Pattern 10: 日付のみ M月D日

```python
match = re.match(r"(\d{1,2})月(\d{1,2})日?$", text)
if match:
    month = int(match.group(1))
    day = int(match.group(2))
    year = now.year

    # If the date has passed this year, use next year
    try:
        target_time = datetime(year, month, day, 9, 0, tzinfo=TZ)
        if target_time <= now:
            target_time = datetime(year + 1, month, day, 9, 0, tzinfo=TZ)

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 09:00")
        return (schedule, desc)
    except ValueError:
        return None
```

Pattern 9 と同様の処理で、正規表現が `(\d{1,2})月(\d{1,2})日?` に変更されています。

### Pattern 11: YYYY年M月D日（時刻なし）

```python
match = re.match(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日?$", text)
if match:
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    # Block dates more than 5 years in the future
    max_year = now.year + 5
    if year > max_year:
        return None

    try:
        target_time = datetime(year, month, day, 9, 0, tzinfo=TZ)

        # Check if time is in the past
        if is_past_time(target_time):
            return None

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 09:00")
        return (schedule, desc)
    except ValueError:
        return None
```

**追加の制約**：
- `max_year = now.year + 5` で5年以上先の日付を拒否
- `is_past_time()` で過去の日付をチェック（翌年への自動調整なし）

### Pattern 12: YYYY年M月D日 時刻付き

```python
match = re.match(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日?\s+(.+)", text)
if match:
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    time_part = match.group(4)

    # Block dates more than 5 years in the future
    max_year = now.year + 5
    if year > max_year:
        return None

    time_tuple = parse_time_with_ampm(time_part)
    if time_tuple is None:
        return None

    hour, minute = time_tuple

    try:
        target_time = datetime(year, month, day, hour, minute, tzinfo=TZ)

        # Check if time is in the past
        if is_past_time(target_time):
            return None

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)
    except ValueError:
        return None
```

Pattern 11 と同様ですが、時刻部分を `parse_time_with_ampm()` でパースしています。

### Pattern 13: YYYY-MM-DD HH:MM（ISO 8601形式 + 時刻）

```python
match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})", text)
if match:
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    hour = int(match.group(4))
    minute = int(match.group(5))

    # Block dates more than 5 years in the future
    max_year = now.year + 5
    if year > max_year:
        return None

    try:
        target_time = datetime(year, month, day, hour, minute, tzinfo=TZ)

        # Check if time is in the past
        if is_past_time(target_time):
            return None

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)
    except ValueError:
        return None
```

**特徴**：
- 正規表現で時刻部分も直接抽出（`parse_time_with_ampm()` を使用しない）
- ISO 8601形式に準拠した最も構造化されたフォーマット

### Pattern 14: MM/DD HH:MM（スラッシュ区切り + コロン時刻）

```python
match = re.match(r"(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{1,2})", text)
if match:
    month = int(match.group(1))
    day = int(match.group(2))
    hour = int(match.group(3))
    minute = int(match.group(4))
    year = now.year

    try:
        target_time = datetime(year, month, day, hour, minute, tzinfo=TZ)

        # If the date has passed this year, use next year
        if is_past_time(target_time):
            target_time = datetime(year + 1, month, day, hour, minute, tzinfo=TZ)

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)
    except ValueError:
        return None
```

**対応例**：
- `11/25 18:00` → 2025年11月25日 18:00
- `3/14 09:30` → 2026年3月14日 09:30（既に過ぎている場合）

**年の自動補完**：
- 年の指定がないため、現在年を使用
- 既に過ぎている場合は翌年に自動調整

### Pattern 15: MM/DD 時刻（スラッシュ区切り + 日本語時刻）

```python
match = re.match(r"(\d{1,2})/(\d{1,2})\s+(.+)", text)
if match:
    month = int(match.group(1))
    day = int(match.group(2))
    time_part = match.group(3)
    year = now.year

    time_tuple = parse_time_with_ampm(time_part)
    if time_tuple is None:
        return None

    hour, minute = time_tuple

    try:
        target_time = datetime(year, month, day, hour, minute, tzinfo=TZ)

        # If the date has passed this year, use next year
        if is_past_time(target_time):
            target_time = datetime(year + 1, month, day, hour, minute, tzinfo=TZ)

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)
    except ValueError:
        return None
```

**対応例**：
- `11/24 18時` → 2025年11月24日 18:00
- `12/31 午後3時` → 2025年12月31日 15:00
- `1/1 午前9時30分` → 2026年1月1日 09:30（既に過ぎている場合）

**ポイント**：
- `parse_time_with_ampm()` を使用して柔軟な時刻表記に対応
- `18時`、`午後3時`、`14:00` などすべてパース可能

### Pattern 16: MM月DD日 時刻（月日 + 日本語時刻）

**注意**: このパターンは Pattern 10 と重複しているため、実際の実装ではコメントとして記載されています。

```python
# Pattern 16: MM月DD日 時刻 (e.g., "11月25日 18時", "11月25日 午後3時")
# Note: This pattern is already handled by Pattern 10 above
```

Pattern 10 が `r"(\d{1,2})月(\d{1,2})日?\s*(.+)"` で時刻付きの形式も処理するため、明示的なパターン定義は不要です。

**対応例（Pattern 10 で処理）**：
- `11月25日 18時` → 2025年11月25日 18:00
- `12月31日 午後3時` → 2025年12月31日 15:00

## 過去時刻の検出と調整

過去時刻の判定には、専用の関数 `is_past_time()` を使用しています：

```python
def is_past_time(target_time: datetime) -> bool:
    """
    Check if the target time is in the past.

    Args:
        target_time: Target datetime to check

    Returns:
        True if target time is in the past, False otherwise.
    """
    now = get_current_time()
    return target_time < now
```

**調整ロジックの違い**：

| パターン | 過去時刻の扱い |
|---------|---------------|
| 今日 時刻 | 翌日に自動調整 |
| 時刻のみ | 翌日に自動調整 |
| MM/DD | 翌年に自動調整 |
| M月D日 | 翌年に自動調整 |
| YYYY年M月D日 | エラー（`None` を返す） |
| YYYY-MM-DD HH:MM | エラー（`None` を返す） |

明示的に年が指定されている場合は、ユーザーの意図を尊重し、過去の日時であればエラーとして扱います。

## タイムゾーン処理

すべての日時計算は、`zoneinfo.ZoneInfo` を使用して **Asia/Tokyo (JST, UTC+9)** タイムゾーンで行われます：

```python
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tokyo")

def get_current_time() -> datetime:
    """Get current time in configured timezone."""
    return datetime.now(TZ)
```

生成される ISO 8601 文字列には、必ずタイムゾーンオフセットが含まれます：

```python
target_time = datetime(2025, 11, 20, 21, 0, tzinfo=TZ)
print(target_time.isoformat())
# 出力: '2025-11-20T21:00:00+09:00'
```

## 返り値の形式

成功時の返り値は、以下の構造を持つタプルです：

```python
(
    {
        "type": "once",  # または "weekly", "monthly"
        "run_at": "2025-11-20T21:00:00+09:00"  # type="once" の場合
        # または
        "weekday": 0,  # type="weekly" の場合（0=月曜、6=日曜）
        "time": "21:00"
        # または
        "day": 15,  # type="monthly" の場合
        "time": "20:00"
    },
    "2025年11月20日 21:00"  # ユーザー向け表示文字列
)
```

## まとめ

本記事では、日本語自然言語時刻パーサーの実装を詳細に解説しました。実装のポイントは以下の通りです：

1. **パターンマッチングの順序**: より具体的なパターンを先に配置
2. **内部ヘルパー関数の活用**: `parse_time_with_ampm()` で時刻パース処理を集約
3. **時刻バリデーション**: 0-23時、0-59分の範囲チェック
4. **過去時刻の自動調整**: パターンに応じて柔軟に対応
5. **タイムゾーン対応**: `zoneinfo` を使用した正確な時刻計算
6. **エラーハンドリング**: 範囲チェックと `ValueError` のキャッチ

この実装により、「明日9時」「毎週月曜20時」「2025年5月3日 14:00」「11/24 18時」など、16種類以上の自然言語表現に対応した柔軟なパーサーを実現しました。
