import os
import json
import ipaddress
import subprocess
import threading
import time
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import requests 

app = Flask(__name__)
# ★★★ ここを必ず変更してください ★★★
app.secret_key = 'your_secret_key_here' 

DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')
AUTO_CHECK_INTERVAL_SECONDS = 600
APP_VERSION = "3.5.0" # グループ表示・動的チェック機能追加

# ==============================================================================
# データ読み込み・保存関数
# ==============================================================================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {'services': [], 'last_updated': None, 'version': APP_VERSION, 'port_history': []}
    
    with open(DATA_FILE, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {'services': [], 'last_updated': None, 'version': APP_VERSION, 'port_history': []}

    data.setdefault('services', [])
    data.setdefault('version', APP_VERSION)
    data.setdefault('port_history', []) # 新しいポート履歴

    # 既存データの構造保証とマイグレーション
    for svc in data['services']:
        svc.setdefault('id', 0)
        svc.setdefault('service_name', 'Unnamed Service')
        svc.setdefault('ip_address', '0.0.0.0')
        svc.setdefault('port', 80)
        svc.setdefault('status', 'unknown') 
        if 'ping_latency' in svc:
            svc['http_latency'] = svc.pop('ping_latency') 
        svc.setdefault('http_latency', None)
        svc.setdefault('last_checked', None)
        svc.setdefault('ip_type', 'unknown') 
        
    # ポート履歴をセットで管理し、重複を防ぐ
    data['port_history'] = sorted(list(set(data['port_history'])))
        
    return data

def save_data(data):
    # IDの振り直し
    for i, svc in enumerate(data['services']):
        svc['id'] = i + 1
        
    data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data['version'] = APP_VERSION
    
    # ポート履歴を更新
    ports = {s['port'] for s in data['services'] if s.get('port') is not None}
    data['port_history'] = sorted(list(ports))
    
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# ==============================================================================
# HTTP疎通チェック関数とIP識別関数
# ==============================================================================
def is_valid_ipv4(ip_str):
    """有効なIPv4アドレスかチェック"""
    try:
        ipaddress.IPv4Address(ip_str)
        return True
    except ipaddress.AddressValueError:
        return False

def is_private_ip(ip_str):
    """プライベートIPアドレス (192.168/16, 10/8, 172.16/12) を識別"""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return ip_obj.is_private
    except ValueError:
        return False

def is_tailscale_ip(ip_str):
    """Tailscale IPアドレス (100.64.0.0/10, Carrier-Grade NAT) を識別"""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        # 100.64.0.0 - 100.127.255.255
        return ip_obj in ipaddress.ip_network('100.64.0.0/10')
    except ValueError:
        return False

def get_ip_type(ip_str):
    """IPアドレスのタイプを返す"""
    if is_tailscale_ip(ip_str):
        return 'tailscale'
    elif is_private_ip(ip_str):
        return 'private'
    else:
        return 'public'

def get_ip_rank(ip_str):
    """ソート用のIPアドレスのランク付け (ローカルIP優先: 192.168.x.x > その他private > Tailscale > public)"""
    if ip_str.startswith('192.168.'):
        return 1
    elif is_private_ip(ip_str):
        return 2
    elif is_tailscale_ip(ip_str):
        return 3
    return 4

def get_ip_group(ip_str):
    """IPアドレスのグループ名を取得（サブネット単位）"""
    if not is_valid_ipv4(ip_str):
        return "その他"

    parts = ip_str.split('.')
    if is_tailscale_ip(ip_str):
        return f"Tailscale ({parts[0]}.{parts[1]}.x.x)"
    elif ip_str.startswith('192.168.'):
        return f"192.168.{parts[2]}.x"
    elif ip_str.startswith('10.'):
        return f"10.{parts[1]}.{parts[2]}.x"
    elif is_private_ip(ip_str):
        return f"{parts[0]}.{parts[1]}.{parts[2]}.x"
    else:
        return "Public"

def group_services_by_ip(services):
    """サービスをIPグループ別に分類"""
    groups = {}
    for svc in services:
        group_name = get_ip_group(svc.get('ip_address', '0.0.0.0'))
        if group_name not in groups:
            groups[group_name] = []
        groups[group_name].append(svc)

    # グループをソート（ローカル優先）
    def group_sort_key(group_name):
        if group_name.startswith('192.168.'):
            return (0, group_name)
        elif group_name.startswith('10.'):
            return (1, group_name)
        elif group_name.startswith('Tailscale'):
            return (2, group_name)
        elif group_name == 'Public':
            return (3, group_name)
        return (4, group_name)

    sorted_groups = sorted(groups.items(), key=lambda x: group_sort_key(x[0]))
    return sorted_groups

def get_status_rank(status):
    """ソート用のステータスのランク付け (reachable > unreachable > unknown)"""
    if status == 'reachable':
        return 1
    elif status == 'unreachable':
        return 2
    return 3

def check_http_service(ip_address, port):
    """指定されたIPとポートへのHTTP(s) GETリクエストを試行"""
    url = f"http://{ip_address}:{port}"
    timeout = 5 
    try:
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        
        if 200 <= response.status_code < 300:
            latency_ms = response.elapsed.total_seconds() * 1000
            return True, latency_ms
        else:
            return False, None
            
    except requests.exceptions.Timeout:
        return False, None
    except requests.exceptions.RequestException:
        return False, None
    except Exception:
        return False, None

# ★★★ 欠落していた関数を再追加 ★★★
def get_signal_strength(latency_ms):
    """HTTP応答時間に基づいて信号強度を評価"""
    if latency_ms is None:
        return 0
    elif latency_ms < 300: 
        return 4
    elif latency_ms < 700: 
        return 3
    elif latency_ms < 1500: 
        return 2
    elif latency_ms < 3000: 
        return 1
    else:
        return 0

# ==============================================================================
# 状態確認ロジック
# ==============================================================================
def check_all_devices_status():
    data = load_data()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] HTTP状態確認を開始します。")
    updated = False

    for svc in data['services']:
        original_status = svc.get('status')
        original_latency = svc.get('http_latency')
        
        ip_address = svc.get('ip_address')
        port = svc.get('port')

        svc['ip_type'] = get_ip_type(ip_address)

        if not ip_address or not port:
            svc['status'] = 'unknown'
            svc['http_latency'] = None
        elif is_valid_ipv4(ip_address):
            reachable, latency = check_http_service(ip_address, port)
            svc['status'] = 'reachable' if reachable else 'unreachable'
            svc['http_latency'] = latency
        else:
            svc['status'] = 'unknown'
            svc['http_latency'] = None
        
        svc['last_checked'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if original_status != svc['status'] or original_latency != svc['http_latency']:
            updated = True

    if updated:
        save_data(data)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] HTTP状態確認が完了しました。")

def auto_checker_loop():
    while True:
        try:
            with app.app_context():
                check_all_devices_status()
        except Exception as e:
            import sys
            print(f"自動状態確認スレッドでエラーが発生しました: {e}", file=sys.stderr)
        time.sleep(AUTO_CHECK_INTERVAL_SECONDS)


# ==============================================================================
# Flask ルート
# ==============================================================================

@app.context_processor
def utility_processor():
    def format_last_checked(timestamp):
        if not timestamp: return "N/A"
        try:
            dt_obj = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            return dt_obj.strftime('%m/%d %H:%M')
        except ValueError:
            return "N/A"
    # utility_processor内でget_signal_strengthが定義されていることを確認
    return dict(get_signal_strength=get_signal_strength, format_last_checked=format_last_checked, app_version=APP_VERSION)

@app.route('/', methods=['GET', 'POST'])
def index():
    data = load_data()
    services = data['services']

    if request.method == 'POST':
        # サービス登録
        service_name = request.form['service_name'].strip()
        ip_address = request.form['ip_address'].strip()
        port_str = request.form.get('port', '').strip()
        
        # ポートの自動補完ロジック
        port = None
        if not port_str:
            # ポートが空欄の場合、80を自動設定
            port = 80 
            port_str = str(port)
        else:
            if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
                flash('ポートが無効です。1から65535の数字を入力してください。', 'error')
                return redirect(url_for('index'))
            port = int(port_str)
        
        # ポート補完後の必須チェック
        if not service_name or not ip_address: 
            flash('サービス名、IPアドレスは必須です。ポートが空欄の場合は80が自動設定されます。', 'error')
            return redirect(url_for('index'))
        
        if not is_valid_ipv4(ip_address):
            flash('IPアドレスが無効です。有効なIPv4アドレスを入力してください。', 'error')
            return redirect(url_for('index'))

        if any(s['ip_address'] == ip_address and s['port'] == port and s['service_name'] == service_name for s in services):
            flash('このサービスはすでに登録されています。', 'warning')
            return redirect(url_for('index'))

        new_id = len(services) + 1 
        
        services.append({
            'id': new_id,
            'service_name': service_name,
            'ip_address': ip_address,
            'port': port,
            'status': 'unknown',
            'http_latency': None, 
            'last_checked': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ip_type': get_ip_type(ip_address) 
        })
        save_data(data)
        flash('サービスが登録されました。', 'success')
        return redirect(url_for('index'))

    # GET リクエスト時の処理
    search_query = request.args.get('search', '').strip()
    if search_query:
        services = [
            s for s in services
            if (s['service_name'] and search_query.lower() in s['service_name'].lower()) or
               (s['ip_address'] and search_query in s['ip_address']) or
               (s['port'] is not None and search_query == str(s['port']))
        ]
        flash(f"「{search_query}」で検索しました。", 'info')

    # ソートロジック
    sort_by = request.args.get('sort_by', 'service_name') 
    sort_order = request.args.get('sort_order', 'asc')

    def get_sort_key(svc):
        if sort_by == 'service_name':
            # 優先順位: サービス名 (小文字) -> IPランク (ローカル優先) -> IPアドレス
            return (
                svc.get('service_name', '').lower(), 
                get_ip_rank(svc.get('ip_address', '0.0.0.0')),
                svc.get('ip_address', '0.0.0.0')
            )
        elif sort_by == 'id':
            return svc.get('id', 0)
        elif sort_by == 'ip_address':
            return svc.get('ip_address', '0.0.0.0')
        elif sort_by == 'port': 
            return svc.get('port') if svc.get('port') is not None else float('inf')
        elif sort_by == 'status':
            latency = svc.get('http_latency')
            # 優先順位: ステータスランク -> 応答速度 (Noneはinf)
            return (
                get_status_rank(svc.get('status', 'unknown')),
                latency if latency is not None else float('inf')
            )
        
        return (
            svc.get('service_name', '').lower(), 
            get_ip_rank(svc.get('ip_address', '0.0.0.0')),
            svc.get('ip_address', '0.0.0.0')
        )

    services.sort(key=get_sort_key, reverse=(sort_order == 'desc'))
    
    for svc in services:
        svc['ip_type'] = get_ip_type(svc['ip_address'])

    last_updated = data.get('last_updated', 'N/A')
    port_history = data.get('port_history', [])

    # グループ表示モード
    view_mode = request.args.get('view', 'list')  # 'list' or 'group'
    grouped_services = group_services_by_ip(services) if view_mode == 'group' else None

    return render_template(
        'index.html',
        services=services,
        grouped_services=grouped_services,
        view_mode=view_mode,
        sort_by=sort_by,
        sort_order=sort_order,
        search_query=search_query,
        last_updated=last_updated,
        port_history=port_history
    )

@app.route('/manual_check')
def manual_check():
    check_all_devices_status()
    flash('全サービスのHTTP疎通チェックを手動で実行しました。テーブルが更新されます。', 'info')
    return redirect(url_for('index'))

@app.route('/json_data')
def json_data():
    data = load_data()
    services_data = []
    for svc in data['services']:
        s = svc.copy()
        s['latency'] = s.pop('http_latency')
        services_data.append(s)

    serializable_data = {
        'version': data.get('version', APP_VERSION),
        'last_updated': data.get('last_updated', 'N/A'),
        'services': services_data,
        'port_history': data.get('port_history', [])
    }
    
    return jsonify(serializable_data)


@app.route('/edit/<int:service_id>', methods=['POST'])
def edit_service(service_id):
    data = load_data()
    svc = next((s for s in data['services'] if s['id'] == service_id), None)

    if svc is None:
        flash('サービスが見つかりません。', 'error')
        return redirect(url_for('index'))

    svc['service_name'] = request.form['service_name'].strip()
    svc['ip_address'] = request.form['ip_address'].strip()
    port_str = request.form.get('port', '').strip()

    if not svc['service_name'] or not svc['ip_address'] or not port_str:
        flash('サービス名、IPアドレス、ポートはすべて必須です。', 'error')
        return redirect(url_for('index'))
    
    if not is_valid_ipv4(svc['ip_address']):
        flash('IPアドレスが無効です。有効なIPv4アドレスを入力してください。', 'error')
        return redirect(url_for('index'))

    svc['port'] = None
    if port_str:
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            flash('ポートが無効です。1から65535の数字を入力してください。', 'error')
            return redirect(url_for('index'))
        svc['port'] = int(port_str)

    svc['ip_type'] = get_ip_type(svc['ip_address'])
    svc['status'] = 'unknown'
    svc['http_latency'] = None 

    save_data(data) 
    flash('サービスが更新されました。', 'success')
    return redirect(url_for('index'))

@app.route('/delete/<int:service_id>')
def delete_service(service_id):
    data = load_data()
    data['services'] = [s for s in data['services'] if s['id'] != service_id]
    save_data(data)
    flash('サービスが削除されました。', 'success')
    return redirect(url_for('index'))

@app.route('/check_single/<int:service_id>')
def check_single_service(service_id):
    """単一サービスの疎通チェック（Ajax用）"""
    data = load_data()
    svc = next((s for s in data['services'] if s['id'] == service_id), None)

    if svc is None:
        return jsonify({'error': 'Service not found'}), 404

    ip_address = svc.get('ip_address')
    port = svc.get('port')

    if ip_address and port and is_valid_ipv4(ip_address):
        reachable, latency = check_http_service(ip_address, port)
        svc['status'] = 'reachable' if reachable else 'unreachable'
        svc['http_latency'] = latency
    else:
        svc['status'] = 'unknown'
        svc['http_latency'] = None

    svc['ip_type'] = get_ip_type(ip_address)
    svc['last_checked'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_data(data)

    return jsonify({
        'id': svc['id'],
        'status': svc['status'],
        'latency': svc['http_latency'],
        'ip_type': svc['ip_type'],
        'last_checked': svc['last_checked']
    })

@app.route('/check_all_async')
def check_all_async():
    """全サービス疎通チェック（Ajax用・結果を返す）"""
    data = load_data()
    results = []

    for svc in data['services']:
        ip_address = svc.get('ip_address')
        port = svc.get('port')

        if ip_address and port and is_valid_ipv4(ip_address):
            reachable, latency = check_http_service(ip_address, port)
            svc['status'] = 'reachable' if reachable else 'unreachable'
            svc['http_latency'] = latency
        else:
            svc['status'] = 'unknown'
            svc['http_latency'] = None

        svc['ip_type'] = get_ip_type(ip_address)
        svc['last_checked'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        results.append({
            'id': svc['id'],
            'status': svc['status'],
            'latency': svc['http_latency'],
            'ip_type': svc['ip_type'],
            'last_checked': svc['last_checked']
        })

    save_data(data)
    return jsonify({'results': results, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

if __name__ == '__main__':
    with app.app_context():
        check_all_devices_status()

    checker_thread = threading.Thread(target=auto_checker_loop, daemon=True)
    checker_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=True)