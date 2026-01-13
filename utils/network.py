import ipaddress
import subprocess
import time


def is_valid_ipv4(ip_str):
    """IPv4アドレスの形式を検証する"""
    try:
        ipaddress.IPv4Address(ip_str)
        return True
    except ipaddress.AddressValueError:
        return False


def ping_host(ip_address):
    """指定されたIPアドレスにPingを実行し、到達可能性とレイテンシを返す"""
    try:
        # '-c 1': 1回だけpingを打つ
        # '-W 1': 1秒でタイムアウト (必要に応じて調整)
        start_time = time.time()
        # subprocess.runはtimeout引数で指定された秒数でタイムアウトが発生する
        result = subprocess.run(
            ['ping', '-c', '1', '-W', '1', ip_address],
            capture_output=True,
            text=True,
            timeout=2
        )
        end_time = time.time()

        if result.returncode == 0:
            output_lines = result.stdout.splitlines()
            for line in output_lines:
                if 'time=' in line:
                    rtt_str = line.split('time=')[1].split(' ')[0]
                    try:
                        return True, float(rtt_str)
                    except ValueError:
                        # 'time='はあったが数値に変換できない場合
                        pass
            # 'time='が見つからなかったが成功した場合（稀なケース）
            return True, (end_time - start_time) * 1000
        else:
            return False, None
    except subprocess.TimeoutExpired:
        # pingコマンドがタイムアウトした場合
        return False, None
    except Exception as e:
        # Ping実行時のその他のエラーを捕捉
        print(f"Pingエラー ({ip_address}): {e}")
        return False, None


def get_signal_strength(latency_ms):
    """レイテンシから信号強度（0-4）を計算する"""
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
