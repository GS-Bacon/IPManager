import ipaddress
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash

from models import load_data, save_data
from utils.network import is_valid_ipv4, get_signal_strength


def register_routes(app):
    """Flaskアプリケーションにルートを登録する"""

    @app.context_processor
    def utility_processor():
        def format_last_checked(timestamp):
            if not timestamp:
                return "N/A"
            try:
                # 例: "2023-10-26 10:30:00" -> "10/26 10:30"
                dt_obj = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                return dt_obj.strftime('%m/%d %H:%M')
            except ValueError:
                return "N/A"
        return dict(get_signal_strength=get_signal_strength, format_last_checked=format_last_checked)

    @app.route('/')
    def index():
        data = load_data()
        devices = data['devices']

        # 検索機能
        search_query = request.args.get('search', '').strip()
        if search_query:
            devices = [
                d for d in devices
                if (d['name'] and search_query.lower() in d['name'].lower()) or
                   (d['local_ip'] and search_query in d['local_ip']) or
                   (d['tailscale_ip'] and search_query in d['tailscale_ip']) or
                   any(search_query in (str(s.get('port', '')) if s.get('port') is not None else '') or
                       search_query.lower() in s.get('name', '').lower() for s in d.get('services', []))
            ]
            flash(f"「{search_query}」で検索しました。", 'info')

        # 並び替え機能
        sort_by = request.args.get('sort_by', 'id')
        sort_order = request.args.get('sort_order', 'asc')

        def get_sort_key(device):
            if sort_by == 'id':
                return device.get('id', 0)
            elif sort_by == 'name':
                return device.get('name', '').lower()
            elif sort_by == 'local_ip':
                return ipaddress.IPv4Address(device.get('local_ip')) if device.get('local_ip') else ipaddress.IPv4Address('0.0.0.0')
            elif sort_by == 'tailscale_ip':
                return ipaddress.IPv4Address(device.get('tailscale_ip')) if device.get('tailscale_ip') else ipaddress.IPv4Address('0.0.0.0')
            elif sort_by == 'ping_latency':
                return device.get('ping_latency') if device.get('ping_latency') is not None else float('inf')
            elif sort_by == 'status':
                status_order = {'到達可能': 0, '不明': 1, '到達不可': 2}
                return status_order.get(device.get('status', '不明'), 99)
            elif sort_by == 'last_checked':
                return device.get('last_checked') if device.get('last_checked') else '0000-00-00 00:00:00'
            return device.get('name', '').lower()

        devices.sort(key=get_sort_key, reverse=(sort_order == 'desc'))

        return render_template('index.html', devices=devices, sort_by=sort_by, sort_order=sort_order, search_query=search_query)

    @app.route('/add', methods=['GET', 'POST'])
    def add_device():
        if request.method == 'POST':
            name = request.form['name'].strip()
            local_ip = request.form['local_ip'].strip() if request.form['local_ip'].strip() else None
            tailscale_ip = request.form['tailscale_ip'].strip() if request.form['tailscale_ip'].strip() else None

            # サービスとポートを複数取得
            service_names = request.form.getlist('service_name[]')
            service_ports = request.form.getlist('service_port[]')

            services = []
            has_at_least_one_service = False

            for i, svc_name_raw in enumerate(service_names):
                svc_name = svc_name_raw.strip()
                svc_port_str = service_ports[i].strip()

                if not svc_name and not svc_port_str:
                    continue

                if not svc_name:
                    flash(f'サービス {i+1} のサービス名が空です。', 'error')
                    return redirect(url_for('add_device'))

                svc_port = None
                if svc_port_str:
                    if not svc_port_str.isdigit():
                        flash(f'サービス「{svc_name}」のポートが無効です。数字を入力してください。', 'error')
                        return redirect(url_for('add_device'))
                    svc_port = int(svc_port_str)
                    if svc_port < 1 or svc_port > 65535:
                        flash(f'サービス「{svc_name}」のポートは1から65535の範囲で入力してください。', 'error')
                        return redirect(url_for('add_device'))

                services.append({'name': svc_name, 'port': svc_port})
                has_at_least_one_service = True

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

            if not has_at_least_one_service:
                flash('少なくとも一つのサービスを登録してください。', 'error')
                return redirect(url_for('add_device'))

            data = load_data()
            new_id = 1
            if data['devices']:
                new_id = max(d['id'] for d in data['devices']) + 1

            data['devices'].append({
                'id': new_id,
                'name': name,
                'local_ip': local_ip,
                'tailscale_ip': tailscale_ip,
                'services': services,
                'status': '不明',
                'ping_latency': None,
                'local_ip_status': 'unknown',
                'tailscale_ip_status': 'unknown',
                'local_ping_latency': None,
                'tailscale_ping_latency': None,
                'link_ip': None,
                'last_checked': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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

            # サービスとポートを複数取得
            service_names = request.form.getlist('service_name[]')
            service_ports = request.form.getlist('service_port[]')

            new_services = []
            has_at_least_one_service = False

            for i, svc_name_raw in enumerate(service_names):
                svc_name = svc_name_raw.strip()
                svc_port_str = service_ports[i].strip()

                if not svc_name and not svc_port_str:
                    continue

                if not svc_name:
                    flash(f'サービス {i+1} のサービス名が空です。', 'error')
                    return redirect(url_for('edit_device', device_id=device_id))

                svc_port = None
                if svc_port_str:
                    if not svc_port_str.isdigit():
                        flash(f'サービス「{svc_name}」のポートが無効です。数字を入力してください。', 'error')
                        return redirect(url_for('edit_device', device_id=device_id))
                    svc_port = int(svc_port_str)
                    if svc_port < 1 or svc_port > 65535:
                        flash(f'サービス「{svc_name}」のポートは1から65535の範囲で入力してください。', 'error')
                        return redirect(url_for('edit_device', device_id=device_id))

                new_services.append({'name': svc_name, 'port': svc_port})
                has_at_least_one_service = True

            device['services'] = new_services

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

            if not has_at_least_one_service:
                flash('少なくとも一つのサービスを登録してください。', 'error')
                return redirect(url_for('edit_device', device_id=device_id))

            save_data(data)
            flash('デバイスが更新されました。', 'success')
            return redirect(url_for('index'))
        return render_template('edit_device.html', device=device)

    @app.route('/delete/<int:device_id>')
    def delete_device(device_id):
        data = load_data()
        data['devices'] = [d for d in data['devices'] if d['id'] != device_id]
        for i, device in enumerate(data['devices']):
            device['id'] = i + 1
        save_data(data)
        flash('デバイスが削除されました。', 'success')
        return redirect(url_for('index'))
