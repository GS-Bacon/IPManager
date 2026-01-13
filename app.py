from flask import Flask
from config import Config
from routes import register_routes

app = Flask(__name__)
app.config.from_object(Config)

# ルートを登録
register_routes(app)

if __name__ == '__main__':
    import threading
    from utils.scheduler import auto_checker_loop

    # サービス起動時に自動状態確認スレッドを開始
    checker_thread = threading.Thread(target=auto_checker_loop, args=(app,), daemon=True)
    checker_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=True)
