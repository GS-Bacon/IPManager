import os


class Config:
    """アプリケーション設定"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')
    AUTO_CHECK_INTERVAL_SECONDS = 600  # 自動状態確認の間隔（秒）例: 600秒 = 10分
