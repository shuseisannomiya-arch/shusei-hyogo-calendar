# 守成クラブ兵庫県会場カレンダー

兵庫県内の守成クラブ会場サイトから例会日程を取得し、Web表示用の `events.json` と Google カレンダー購読用の `events.ics` を生成します。

## 無料で公開する

無料運用は GitHub Pages + GitHub Actions を使います。詳しくは `FREE_DEPLOY.md` を見てください。

## 使い方

```sh
cd /Users/tsuwamonogura/Documents/Codex/守成クラブ三宮会場/calendar-sync
python3 scripts/fetch_events.py
```

生成物:

- `data/events.json`: iframe 表示ページが読む日程データ
- `data/events.ics`: Google カレンダーや Apple カレンダーで購読・ダウンロードできるICS
- `public/index.html`: WordPress や既存HPに iframe で貼る表示ページ

## WordPress / HP への貼り付け

`calendar-sync` フォルダをWeb公開できる場所へ置いた場合の例です。

```html
<iframe
  src="https://example.com/calendar-sync/public/index.html?publicIcs=https%3A%2F%2Fexample.com%2Fcalendar-sync%2Fdata%2Fevents.ics"
  style="width:100%;height:760px;border:0;"
  loading="lazy"
  title="守成クラブ兵庫県会場 例会カレンダー"
></iframe>
```

WordPressなら「カスタムHTML」ブロックにそのまま貼れます。

## Google カレンダーに表示する方法

1. `data/events.ics` をインターネットからアクセスできるURLに置きます。
2. Google カレンダーの「他のカレンダー」から「URLで追加」を選びます。
3. `https://example.com/calendar-sync/data/events.ics` を登録します。

iframe の `publicIcs=` に同じICS URLを指定すると、画面上に「Googleカレンダーに追加」ボタンが表示されます。

## 月1回の自動更新

サーバーの cron 例:

```cron
15 3 1 * * cd /path/to/calendar-sync && /usr/bin/python3 scripts/fetch_events.py
```

GitHub Pages などへ公開する場合は、月1回の GitHub Actions で `python3 scripts/fetch_events.py` を実行し、`data/events.json` と `data/events.ics` をコミットまたはデプロイしてください。

## 会場の追加・修正

`config/venues.json` に会場名、URL、標準開始・終了時刻を追加します。各サイトのHTML構造が変わっても、まずは「日程」「開催」「例会」の周辺テキストから自動抽出します。

抽出結果は `confidence` を付けています。初回公開前と月次更新後は、`data/events.json` の日付が公式ページと一致しているか確認してください。
