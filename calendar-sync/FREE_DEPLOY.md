# 無料運用ガイド

この構成は、GitHub の無料枠で動かす前提です。

## 無料で使う構成

- GitHub public repository: コード置き場
- GitHub Actions: 週1回 `fetch_events.py` を自動実行
- GitHub Pages: カレンダー表示ページ、`events.json`、`events.ics` を公開
- WordPress: GitHub Pages のURLを iframe で貼る
- Google カレンダー: 公開された `events.ics` URLを購読

GitHub Pages は GitHub Free の public repository で利用できます。private repository で無料利用したい場合は制限が出る可能性があるため、無料運用では public repository 推奨です。

## 初回設定

1. GitHub に public repository を作ります。
2. このフォルダ一式を repository に push します。
3. GitHub の repository で `Settings` → `Pages` を開きます。
4. `Build and deployment` の `Source` を `GitHub Actions` にします。
5. `Actions` タブから `Update and publish calendar` を手動実行します。

成功すると、Pages URL が発行されます。

例:

```text
https://ユーザー名.github.io/リポジトリ名/
```

## WordPress に貼る iframe

Pages URL が `https://ユーザー名.github.io/リポジトリ名/` の場合:

```html
<iframe
  src="https://ユーザー名.github.io/リポジトリ名/?publicIcs=https%3A%2F%2Fユーザー名.github.io%2Fリポジトリ名%2Fdata%2Fevents.ics"
  style="width:100%;height:760px;border:0;"
  loading="lazy"
  title="守成クラブ兵庫県会場 例会カレンダー"
></iframe>
```

WordPress の「カスタムHTML」ブロックに貼ってください。

## Google カレンダーに出す

Google カレンダーで「他のカレンダー」→「URLで追加」を選び、以下のURLを入れます。

```text
https://ユーザー名.github.io/リポジトリ名/data/events.ics
```

## 間違い報告ボタン

一覧ページの各日程には「報告」ボタンがあります。クリックすると、対象の日程情報を含んだ報告用モーダルが開きます。

メール送信先を指定したい場合は、iframe のURLに `reportEmail=` を追加します。

```html
<iframe
  src="https://ユーザー名.github.io/リポジトリ名/?publicIcs=https%3A%2F%2Fユーザー名.github.io%2Fリポジトリ名%2Fdata%2Fevents.ics&reportEmail=info%40example.com"
  style="width:100%;height:760px;border:0;"
  loading="lazy"
  title="守成クラブ兵庫県会場 例会カレンダー"
></iframe>
```

報告内容で日程を完全自動書き換えする運用は、誤報やいたずらでカレンダーが壊れる可能性があるため、標準では無効にしています。無料運用では「報告を受ける → 公式ページを確認 → 設定や抽出を修正」が安全です。

## Google カレンダーをHPに表示する

Google カレンダーそのものを表示し、その下にICSダウンロードなどのボタンを出す場合は `google-calendar.html` を使います。

流れ:

1. Google カレンダーで `events.ics` を「URLで追加」します。
2. 追加したカレンダーを必要に応じて公開設定にします。
3. Google カレンダーの設定画面で、そのカレンダーの `カレンダーID` をコピーします。
4. WordPress に以下の iframe を貼ります。

```html
<iframe
  src="https://ユーザー名.github.io/リポジトリ名/google-calendar.html?calendarId=ここにGoogleカレンダーID&publicIcs=https%3A%2F%2Fユーザー名.github.io%2Fリポジトリ名%2Fdata%2Fevents.ics"
  style="width:100%;height:820px;border:0;"
  loading="lazy"
  title="守成クラブ兵庫県会場 Googleカレンダー"
></iframe>
```

Google カレンダーの「埋め込みコード」に入っているURLをそのまま使いたい場合は、`calendarId=` の代わりに `googleEmbed=` を使えます。

```html
<iframe
  src="https://ユーザー名.github.io/リポジトリ名/google-calendar.html?googleEmbed=ここにGoogle埋め込みURL&publicIcs=https%3A%2F%2Fユーザー名.github.io%2Fリポジトリ名%2Fdata%2Fevents.ics"
  style="width:100%;height:820px;border:0;"
  loading="lazy"
  title="守成クラブ兵庫県会場 Googleカレンダー"
></iframe>
```

このページの下部には以下のボタンが出ます。

- Googleカレンダーに追加
- ICSダウンロード
- 一覧で見る

## 週1回の自動更新

`.github/workflows/deploy-calendar-pages.yml` が毎週月曜日 09:20（日本時間）に動きます。

処理内容:

1. 各会場HPを取得
2. `events.json` と `events.ics` を生成
3. GitHub Pages に公開

手動で更新したい場合は、GitHub の `Actions` タブから `Update and publish calendar` → `Run workflow` を押します。

## 無料運用の注意点

- GitHub Pages は公開サイトなので、リポジトリや生成物に非公開情報を入れないでください。
- public repository の scheduled workflow は、長期間リポジトリ活動がないと自動停止されることがあります。その場合は Actions タブから再有効化します。
- 会場HP側のHTML構造が大きく変わると、日程抽出の微調整が必要になることがあります。
