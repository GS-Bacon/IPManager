import os
import json
import ipaddress
import subprocess
import threading
import time
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here' # ★★★ ここを必ず変更してください ★★★

DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')
AUTO_CHECK_INTERVAL_SECONDS = 600 # ★★★ 自動状態確認の間隔（秒）例: 600秒 = 10分 ★★★

# ==============================================================================
# データ読み込み・保存関数
# ==============================================================================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {'devices': []}
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
        # 初期状態のデバイスデータ構造を保証
        for device in data['devices']:
            device.setdefault('name', '未登録')
            device.setdefault('local_ip', None)
            device.setdefault('tailscale_ip', None)
            device.setdefault('port', None)
            device.setdefault('status', '不明')
            device.setdefault('ping_latency', None)
            device.setdefault('local_ip_status', 'unknown')
            device.setdefault('tailscale_ip_status', 'unknown')
            device.setdefault('local_ping_latency', None)
            device.setdefault('tailscale_ping_latency', None)
            device.setdefault('link_ip', None)
            device.setdefault('link_port', None)
        return data

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# ==============================================================================
# Ping関連関数
# ==============================================================================
def is_valid_ipv4(ip_str):
    try:
        ipaddress.IPv4Address(ip_str)
        return True
    except ipaddress.AddressValueError:
        return False

def ping_host(ip_address):
    try:
        # '-c 1': 1回だけpingを打つ
        # '-W 1': 1秒でタイムアウト (必要に応じて調整)
        start_time = time.time()
        result = subprocess.run(['ping', '-c', '1', '-W', '1', ip_address], capture_output=True, text=True, timeout=2)
        end_time = time.time()
        
        if result.returncode == 0:
            output_lines = result.stdout.splitlines()
            for line in output_lines:
                if 'time=' in line:
                    rtt_str = line.split('time=')[1].split(' ')[0]
                    try:
                        return True, float(rtt_str)
                    except ValueError:
                        pass
            return True, (end_time - start_time) * 1000
        else:
            return False, None
    except subprocess.TimeoutExpired:
        return False, None
    except Exception as e:
        # Ping実行時のその他のエラーを捕捉
        print(f"Pingエラー ({ip_address}): {e}")
        return False, None

def get_signal_strength(latency_ms):
    if latency_ms is None:
        return 0
    elif latency_ms < 50:
        return 4
    elif latency_ms < 100:
        return 3
    elif latency_ms < 200:
        return 2
    elif latency_ms < 500:
        return 1
    else:
        return 0

# ==============================================================================
# 自動状態確認スレッド関連
# ==============================================================================
def check_all_devices_status():
    data = load_data()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 自動状態確認を開始します。")
    updated = False # データが更新されたかどうかを追跡

    for device in data['devices']:
        original_local_status = device['local_ip_status']
        original_tailscale_status = device['tailscale_ip_status']
        original_ping_latency = device['ping_latency']
        original_link_ip = device['link_ip']
        original_link_port = device['link_port']

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

        if local_ip_reachable or tailscale_ip_reachable:
            device['status'] = '到達可能'
            if local_ip_reachable and tailscale_ip_reachable:
                if local_latency is not None and tailscale_latency is not None:
                    if local_latency <= tailscale_latency:
                        device['link_ip'] = device['local_ip']
                    else:
                        device['link_ip'] = device['tailscale_ip']
                elif local_ip_reachable:
                    device['link_ip'] = device['local_ip']
                else:
                    device['link_ip'] = device['tailscale_ip']
            elif local_ip_reachable:
                device['link_ip'] = device['local_ip']
            else: # tailscale_ip_reachable
                device['link_ip'] = device['tailscale_ip']
            
            device['link_port'] = device['port']

        else:
            device['status'] = '到達不可'
            device['link_ip'] = None
            device['link_port'] = None
        
        valid_latencies = [l for l in [local_latency, tailscale_latency] if l is not None]
        device['ping_latency'] = min(valid_latencies) if valid_latencies else None
        
        # 変更があった場合にのみフラグを立てる
        if (original_local_status != device['local_ip_status'] or
            original_tailscale_status != device['tailscale_ip_status'] or
            original_ping_latency != device['ping_latency'] or
            original_link_ip != device['link_ip'] or
            original_link_port != device['link_port']):
            updated = True

    if updated: # 変更があった場合のみ保存
        save_data(data)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 自動状態確認が完了しました。")

# Gunicorn設定ファイルから呼び出されるスレッド関数
def auto_checker_loop():
    """自動確認スレッドのメインループ。アプリケーションコンテキスト内で実行。"""
    while True:
        try:
            with app.app_context(): # Flaskのコンテキストを確保
                check_all_devices_status()
        except Exception as e:
            # エラー発生時はstderrに出力
            import sys
            print(f"自動状態確認スレッドでエラーが発生しました: {e}", file=sys.stderr)
        time.sleep(AUTO_CHECK_INTERVAL_SECONDS)

# ==============================================================================
# Flask ルート
# ==============================================================================
@app.context_processor
def utility_processor():
    return dict(get_signal_strength=get_signal_strength)

@app.route('/')
def index():
    data = load_data()
    devices = data['devices']

    # 検索機能
    search_query = request.args.get('search', '').strip()
    if search_query:
        devices = [
            d for d in devices
            if (d['local_ip'] and search_query in d['local_ip']) or
               (d['tailscale_ip'] and search_query in d['tailscale_ip'])
        ]
        flash(f"IPアドレス「{search_query}」で検索しました。", 'info')

    # 並び替え機能
    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('sort_order', 'asc') # asc:昇順, desc:降順

    def get_sort_key(device):
        if sort_by == 'name':
            return device.get('name', '').lower()
        elif sort_by == 'local_ip':
            # IPアドレス文字列を直接比較するとおかしくなるため、ipaddressオブジェクトに変換して比較
            return ipaddress.IPv4Address(device.get('local_ip')) if device.get('local_ip') else ipaddress.IPv4Address('0.0.0.0')
        elif sort_by == 'tailscale_ip':
            return ipaddress.IPv4Address(device.get('tailscale_ip')) if device.get('tailscale_ip') else ipaddress.IPv4Address('0.0.0.0')
        elif sort_by == 'ping_latency':
            # Ping速度はNoneの場合を考慮して最大値か無限大を返す
            return device.get('ping_latency') if device.get('ping_latency') is not None else float('inf')
        elif sort_by == 'status':
            # 状態は文字列比較だが、到達可能/到達不可で優先順位を付ける
            status_order = {'到達可能': 0, '不明': 1, '到達不可': 2}
            return status_order.get(device.get('status', '不明'), 99)
        return device.get('name', '').lower() # デフォルト

    devices.sort(key=get_sort_key, reverse=(sort_order == 'desc'))

    return render_template('index.html', devices=devices, sort_by=sort_by, sort_order=sort_order, search_query=search_query)

@app.route('/add', methods=['GET', 'POST'])
def add_device():
    if request.method == 'POST':
        name = request.form['name'].strip()
        local_ip = request.form['local_ip'].strip()
        tailscale_ip = request.form['tailscale_ip'].strip()
        port = request.form['port'].strip()

        if not name:
            flash('名前は必須です。', 'error')
            return redirect(url_for('add_device'))

        if not local_ip and not tailscale_ip:
            flash('ローカルIPまたはTailscale IPの少なくとも一つを入力してください。', 'error')
            return redirect(url_for('add_device'))

        if local_ip and not is_valid_ipv4(local_ip):
            flash('ローカルIPが無効です。有効なIPv4アドレスを入力してください。', 'error')
            return redirect(url_for('add_device'))
        
        if tailscale_ip and not is_valid_ipv4(tailscale_ip):
            flash('Tailscale IPが無効です。有効なIPv4アドレスを入力してください。', 'error')
            return redirect(url_for('add_device'))
        
        if port and not port.isdigit():
            flash('ポートが無効です。数字を入力してください。', 'error')
            return redirect(url_for('add_device'))
        port = int(port) if port else None
        if port and (port < 1 or port > 65535):
            flash('ポートは1から65535の範囲で入力してください。', 'error')
            return redirect(url_for('add_device'))

        data = load_data()
        new_id = 1
        if data['devices']:
            new_id = max(d['id'] for d in data['devices']) + 1

        data['devices'].append({
            'id': new_id,
            'name': name,
            'local_ip': local_ip if local_ip else None,
            'tailscale_ip': tailscale_ip if tailscale_ip else None,
            'port': port,
            'status': '不明', # 初期値
            'ping_latency': None, # 初期値
            'local_ip_status': 'unknown',
            'tailscale_ip_status': 'unknown',
            'local_ping_latency': None,
            'tailscale_ping_latency': None,
            'link_ip': None,
            'link_port': None
        })
        save_data(data)
        flash('デバイスが追加されました。', 'success')
        return redirect(url_for('index'))
    return render_template('add_device.html')

@app.route('/edit/<int:device_id>', methods=['GET', 'POST'])
def edit_device(device_id):
    data = load_data()
    device = next((d for d in data['devices'] if d['id'] == device_id), None)

    if device is None:
        flash('デバイスが見つかりません。', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        device['name'] = request.form['name'].strip()
        device['local_ip'] = request.form['local_ip'].strip() if request.form['local_ip'].strip() else None
        device['tailscale_ip'] = request.form['tailscale_ip'].strip() if request.form['tailscale_ip'].strip() else None
        device['port'] = int(request.form['port'].strip()) if request.form['port'].strip() else None

        if not device['name']:
            flash('名前は必須です。', 'error')
            return redirect(url_for('edit_device', device_id=device_id))
        
        if not device['local_ip'] and not device['tailscale_ip']:
            flash('ローカルIPまたはTailscale IPの少なくとも一つを入力してください。', 'error')
            return redirect(url_for('edit_device', device_id=device_id))

        if device['local_ip'] and not is_valid_ipv4(device['local_ip']):
            flash('ローカルIPが無効です。有効なIPv4アドレスを入力してください。', 'error')
            return redirect(url_for('edit_device', device_id=device_id))

        if device['tailscale_ip'] and not is_valid_ipv4(device['tailscale_ip']):
            flash('Tailscale IPが無効です。有効なIPv4アドレスを入力してください。', 'error')
            return redirect(url_for('edit_device', device_id=device_id))
        
        if device['port'] and (device['port'] < 1 or device['port'] > 65535):
            flash('ポートは1から65535の範囲で入力してください。', 'error')
            return redirect(url_for('edit_device', device_id=device_id))

        save_data(data)
        flash('デバイスが更新されました。', 'success')
        return redirect(url_for('index'))
    return render_template('edit_device.html', device=device)

@app.route('/delete/<int:device_id>')
def delete_device(device_id):
    data = load_data()
    data['devices'] = [d for d in data['devices'] if d['id'] != device_id]
    for i, device in enumerate(data['devices']): # IDを振り直す
        device['id'] = i + 1
    save_data(data)
    flash('デバイスが削除されました。', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
