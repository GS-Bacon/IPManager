import os
import json
from config import Config


def load_data():
    """データファイルからデバイス情報を読み込む"""
    if not os.path.exists(Config.DATA_FILE):
        return {'devices': []}
    with open(Config.DATA_FILE, 'r') as f:
        data = json.load(f)
        # 初期状態のデバイスデータ構造を保証
        for device in data['devices']:
            device.setdefault('name', '未登録')
            device.setdefault('local_ip', None)
            device.setdefault('tailscale_ip', None)

            # 'port'フィールドがあれば'services'に変換（旧バージョンからの移行対応）
            if 'port' in device and isinstance(device['port'], (int, type(None))):
                if device['port'] is not None:
                    device['services'] = [{'name': 'Default Service', 'port': device['port']}]
                else:
                    # portがNoneの場合は、ポートなしサービスとして移行
                    device['services'] = [{'name': 'Default Service (No Port)', 'port': None}]
                del device['port']  # 古い'port'フィールドを削除

            # servicesリスト内の各サービスエントリの構造を保証
            # 古いservicesリストが空の辞書であった場合の対応
            if not isinstance(device.get('services'), list):
                device['services'] = []

            for svc in device['services']:
                svc.setdefault('name', 'Unnamed Service')
                svc.setdefault('port', None)  # ポートはNoneも許容

            device.setdefault('status', '不明')
            device.setdefault('ping_latency', None)
            device.setdefault('local_ip_status', 'unknown')
            device.setdefault('tailscale_ip_status', 'unknown')
            device.setdefault('local_ping_latency', None)
            device.setdefault('tailscale_ping_latency', None)
            device.setdefault('link_ip', None)
            device.setdefault('last_checked', None)  # 最終確認時刻
        return data


def save_data(data):
    """データファイルにデバイス情報を保存する"""
    with open(Config.DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)
