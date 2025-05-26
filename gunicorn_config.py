import threading
import time
import sys

# app.py から自動確認関数をインポート
# app: Flaskアプリケーションインスタンス (Gunicornがロードするapp)
# check_all_devices_status: 全デバイスの状態を確認する関数
# auto_checker_thread_function: 自動確認スレッドが実行する関数
# AUTO_CHECK_INTERVAL_SECONDS: 自動確認の間隔
try:
    from app import app, check_all_devices_status, AUTO_CHECK_INTERVAL_SECONDS
except ImportError as e:
    print(f"Error importing app components in gunicorn_config: {e}", file=sys.stderr)
    sys.exit(1)

# 自動確認スレッドの制御変数
_auto_checker_thread = None
_thread_started = False
_thread_lock = threading.Lock()

def auto_checker_loop():
    """自動確認スレッドのメインループ。アプリケーションコンテキスト内で実行。"""
    while True:
        try:
            with app.app_context(): # アプリケーションコンテキストを確立
                check_all_devices_status()
        except Exception as e:
            print(f"自動状態確認スレッドでエラーが発生しました: {e}", file=sys.stderr)
        time.sleep(AUTO_CHECK_INTERVAL_SECONDS)

def on_starting(server):
    """Gunicornサーバーが起動する際に一度だけ実行されるフック。"""
    global _auto_checker_thread, _thread_started
    with _thread_lock:
        if not _thread_started:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Gunicorn on_starting: 自動状態確認スレッドを開始します。", file=sys.stderr)
            _auto_checker_thread = threading.Thread(target=auto_checker_loop)
            _auto_checker_thread.daemon = True # メインスレッドが終了したら、このスレッドも終了する
            _auto_checker_thread.start()
            _thread_started = True
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 自動状態確認スレッドが起動しました。", file=sys.stderr)
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Gunicorn on_starting: 自動状態確認スレッドはすでに起動しています。", file=sys.stderr)
timeout = 120
# Gunicorn設定にフックを登録
# on_starting: マスタープロセスが起動する際に呼び出される
# on_exit: マスタープロセスが終了する際に呼び出される (オプション)
# workers: ワーカープロセス数 (Systemdサービスファイルで指定済み)
# bind: アドレスとポート (Systemdサービスファイルで指定済み)
