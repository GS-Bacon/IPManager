# CLAUDE.md

このファイルはClaude Code（claude.ai/code）がこのリポジトリで作業する際のガイダンスを提供します。

## プロジェクト概要

IP Managerは、ネットワークデバイスのIPアドレスとサービスを管理するFlask製Webアプリケーションです。ローカルIPとTailscale IPのデュアルIP管理に対応し、Pingによる自動到達性確認機能を備えています。

## 技術スタック

- **バックエンド**: Flask (Python)
- **データストレージ**: JSON ファイル (`data.json`)
- **本番サーバー**: Gunicorn
- **フロントエンド**: Jinja2テンプレート + CSS（フレームワークなし）

## アーキテクチャ

```
app.py          → Flaskアプリ初期化、スレッド起動
config.py       → 設定クラス（SECRET_KEY, DATA_FILE, AUTO_CHECK_INTERVAL_SECONDS）
models.py       → データ永続化（load_data/save_data）、スキーマ移行ロジック含む
routes.py       → 全ルート定義（register_routes関数で一括登録）
utils/
├── network.py  → ping_host(), is_valid_ipv4(), get_signal_strength()
└── scheduler.py → auto_checker_loop(), check_all_devices_status()
```

## 重要な設計判断

### デュアルIP管理
- 各デバイスは `local_ip` と `tailscale_ip` を持つ
- 到達可能なIPを自動選択し `link_ip` に設定
- 両方到達可能な場合はレイテンシが低い方を優先

### サービス管理
- 1デバイスに複数サービス（`services`配列）を登録可能
- 各サービスは `name` と `port`（省略可）を持つ
- 旧バージョンからの移行：単一`port`フィールド → `services`配列

### 状態確認
- バックグラウンドスレッドで定期的にPing実行
- 開発環境: `app.py`直接実行時にスレッド起動
- 本番環境: `gunicorn_config.py`の`on_starting`フックで起動

## よく使うコマンド

```bash
# 開発サーバー起動
python app.py

# 本番サーバー起動
gunicorn -c gunicorn_config.py app:app
```

## コード変更時の注意点

1. **データスキーマ変更時**: `models.py`の`load_data()`に後方互換性のための`setdefault`処理を追加
2. **新規ルート追加時**: `routes.py`の`register_routes()`関数内に追加
3. **テンプレートのスタイル**: `base.html`に共通スタイル、各テンプレートに`{% block extra_styles %}`で固有スタイル
4. **Ping処理**: Linux前提（`-c`と`-W`オプション）、Windowsでは動作しない可能性あり
