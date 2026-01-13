import threading
import time
import sys

from app import app, check_all_devices_status, AUTO_CHECK_INTERVAL_SECONDS

# 自動確認スレッドの制御変数
_auto_checker_thread = None
_thread_started = False
_thread_lock = threading.Lock()


def auto_checker_loop():
    """自動確認スレッドのメインループ。アプリケーションコンテキスト内で実行。"""
    while True:
        try:
            with app.app_context():
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
            _auto_checker_thread.daemon = True
            _auto_checker_thread.start()
            _thread_started = True
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 自動状態確認スレッドが起動しました。", file=sys.stderr)
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Gunicorn on_starting: 自動状態確認スレッドはすでに起動しています。", file=sys.stderr)


timeout = 120
