# IP Manager

ネットワーク上のデバイスのIPアドレスとサービスを管理するFlask製Webアプリケーションです。ローカルIPとTailscale IPの両方に対応し、Pingによる到達性確認を自動で行います。

## 機能

- **デバイス管理**: デバイスの追加・編集・削除
- **デュアルIP対応**: ローカルIPとTailscale IPを同時に管理
- **複数サービス登録**: 1つのデバイスに複数のサービス（ポート）を登録可能
- **自動状態確認**: バックグラウンドで定期的にPingを実行し、到達性を監視
- **スマートリンク**: 到達可能なIPアドレスを自動選択してサービスにリンク
- **検索・ソート**: デバイス名、IP、サービス名、ポートで検索・並び替え
- **レスポンシブデザイン**: モバイル端末にも対応

## 必要条件

- Python 3.8+
- Flask 2.0+
- Gunicorn 20.0+ (本番環境用)

## インストール

```bash
# リポジトリをクローン
git clone https://github.com/yourusername/IPManager.git
cd IPManager

# 依存関係をインストール
pip install -r requirements.txt
```

## 起動方法

### 開発環境

```bash
python app.py
```

サーバーは `http://0.0.0.0:5000` で起動します。

### 本番環境 (Gunicorn)

```bash
gunicorn -c gunicorn_config.py app:app
```

## 設定

`config.py` で以下の設定を変更できます：

| 設定項目 | 説明 | デフォルト値 |
|---------|------|-------------|
| `SECRET_KEY` | セッション暗号化キー | 環境変数または `dev-key-change-in-production` |
| `DATA_FILE` | データ保存先 | `data.json` |
| `AUTO_CHECK_INTERVAL_SECONDS` | 自動状態確認の間隔（秒） | `600` (10分) |

## プロジェクト構成

```
IPManager/
├── app.py              # Flaskアプリケーションのエントリーポイント
├── config.py           # アプリケーション設定
├── models.py           # データの読み書き処理
├── routes.py           # ルーティング定義
├── gunicorn_config.py  # Gunicorn設定
├── requirements.txt    # 依存パッケージ
├── data.json           # デバイスデータ（自動生成）
├── utils/
│   ├── network.py      # ネットワークユーティリティ（Ping、IP検証）
│   └── scheduler.py    # 自動状態確認スケジューラー
└── templates/
    ├── base.html       # ベーステンプレート
    ├── index.html      # デバイス一覧画面
    ├── add_device.html # デバイス追加画面
    └── edit_device.html # デバイス編集画面
```

## 使い方

1. ブラウザで `http://localhost:5000` にアクセス
2. 「デバイスを追加」ボタンからデバイスを登録
3. ローカルIPまたはTailscale IP（または両方）を入力
4. サービス名とポート番号を登録（ポートは省略可能）
5. 自動的にPingが実行され、到達性が確認される
6. サービス名をクリックすると到達可能なIPでサービスにアクセス

## ライセンス

MIT License
