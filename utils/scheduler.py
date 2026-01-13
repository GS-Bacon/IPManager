import time
from datetime import datetime

from config import Config
from models import load_data, save_data
from utils.network import ping_host


def check_all_devices_status(app=None):
    """全デバイスの状態を確認し、更新する"""
    data = load_data()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 自動状態確認を開始します。")
    updated = False  # データが更新されたかどうかを追跡

    for device in data['devices']:
        # オリジナルの状態を保存し、変更があったかチェックするため
        original_local_status = device.get('local_ip_status', 'unknown')
        original_tailscale_status = device.get('tailscale_ip_status', 'unknown')
        original_ping_latency = device.get('ping_latency')
        original_link_ip = device.get('link_ip')
        original_status = device.get('status', '不明')
        original_last_checked = device.get('last_checked')

        local_ip_reachable, local_latency = False, None
        tailscale_ip_reachable, tailscale_latency = False, None

        if device['local_ip']:
            local_ip_reachable, local_latency = ping_host(device['local_ip'])
            device['local_ip_status'] = 'reachable' if local_ip_reachable else 'unreachable'
            device['local_ping_latency'] = local_latency
        else:
            device['local_ip_status'] = 'unknown'
            device['local_ping_latency'] = None

        if device['tailscale_ip']:
            tailscale_ip_reachable, tailscale_latency = ping_host(device['tailscale_ip'])
            device['tailscale_ip_status'] = 'reachable' if tailscale_ip_reachable else 'unreachable'
            device['tailscale_ping_latency'] = tailscale_latency
        else:
            device['tailscale_ip_status'] = 'unknown'
            device['tailscale_ping_latency'] = None

        # 全体ステータスの決定とリンクIPの選択
        if local_ip_reachable or tailscale_ip_reachable:
            device['status'] = '到達可能'

            # リンクIPの決定ロジック（Tailscale優先）
            if tailscale_ip_reachable:
                if local_ip_reachable:
                    # 両方到達可能な場合
                    if tailscale_latency is not None and local_latency is not None:
                        # 両方Pingが通る場合、レイテンシが低い方を優先
                        if tailscale_latency <= local_latency:
                            device['link_ip'] = device['tailscale_ip']
                        else:
                            device['link_ip'] = device['local_ip']
                    elif tailscale_latency is not None:
                        device['link_ip'] = device['tailscale_ip']
                    elif local_latency is not None:
                        device['link_ip'] = device['local_ip']
                    else:
                        # 両方到達可能だが、どちらもPingレイテンシがNoneの場合
                        device['link_ip'] = device['tailscale_ip']
                else:
                    # Tailscale IPのみ到達可能な場合
                    device['link_ip'] = device['tailscale_ip']
            elif local_ip_reachable:
                # ローカルIPのみ到達可能な場合
                device['link_ip'] = device['local_ip']
            else:
                # ここに到達することは理論上ないはずだが、念のため
                device['status'] = '不明'
                device['link_ip'] = None

        else:  # どちらのIPも到達不可の場合
            device['status'] = '到達不可'
            device['link_ip'] = None

        # 全体のPingレイテンシは、到達可能なIPのPingレイテンシのうち最小のもの
        valid_latencies = [lat for lat in [local_latency, tailscale_latency] if lat is not None]
        device['ping_latency'] = min(valid_latencies) if valid_latencies else None

        # 最終確認時刻を更新
        device['last_checked'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 変更があった場合にのみフラグを立てる
        if (original_local_status != device['local_ip_status'] or
            original_tailscale_status != device['tailscale_ip_status'] or
            original_ping_latency != device['ping_latency'] or
            original_link_ip != device['link_ip'] or
            original_status != device['status'] or
            original_last_checked != device['last_checked']):
            updated = True

    if updated:  # 変更があった場合のみ保存
        save_data(data)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 自動状態確認が完了しました。")


def auto_checker_loop(app=None):
    """自動確認スレッドのメインループ"""
    import sys
    while True:
        try:
            if app is not None:
                with app.app_context():
                    check_all_devices_status(app)
            else:
                check_all_devices_status()
        except Exception as e:
            print(f"自動状態確認スレッドでエラーが発生しました: {e}", file=sys.stderr)
        time.sleep(Config.AUTO_CHECK_INTERVAL_SECONDS)
