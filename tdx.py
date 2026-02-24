import os
import re
import sys
import requests
from datetime import datetime
from stations import stationIDs

TDX_AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TDX_BASE_URL = "https://tdx.transportdata.tw/api/basic"

# Map station name (Chinese) to TDX StationID
# TDX uses the same numeric IDs as stations.py
_STATION_NAME_TO_ID = stationIDs  # e.g. "松山" -> "0990"

TRAIN_TYPE_NAMES = {
    "1": "太魯閣",
    "2": "普悠瑪",
    "3": "自強(3000)",
    "4": "自強",
    "5": "莒光",
    "6": "復興",
    "7": "區間",
    "10": "普快",
    "11": "區間快",
}


def parse_date(s):
    """
    將各種日期格式統一解析成 YYYYMMDD 字串。
    支援：
      YYYYMMDD   → 原樣返回
      MMDD / MDD → 補上當前年份
      DD / D     → 補上當前年份與月份
    分隔符號 '-' '/' 會先被移除。
    """
    s = s.replace("-", "").replace("/", "").strip()
    if not s.isdigit():
        raise ValueError(f"無效的日期格式：{s!r}")
    now = datetime.now()
    if len(s) == 8:
        return s
    if len(s) in (3, 4):
        return f"{now.year}{s.zfill(4)}"
    if len(s) in (1, 2):
        return f"{now.year}{now.month:02d}{int(s):02d}"
    raise ValueError(f"無效的日期格式：{s!r}")


def parse_time(s):
    """
    將各種時間格式統一解析成 HH:MM 字串。
    支援：
      HH:MM / H:MM → 補零
      HHMM         → 加冒號
      HMM          → 補零加冒號（如 900 → 09:00）
    """
    s = s.replace(":", "").strip()
    if not s.isdigit():
        raise ValueError(f"無效的時間格式：{s!r}")
    if len(s) == 3:
        s = s.zfill(4)
    if len(s) == 4:
        return f"{s[:2]}:{s[2:]}"
    raise ValueError(f"無效的時間格式：{s!r}")


def _load_config(config_path="tdx_config"):
    cfg = {}
    if not os.path.exists(config_path):
        return cfg
    with open(config_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def _get_token(client_id, client_secret):
    resp = requests.post(
        TDX_AUTH_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _tdx_get(token, path, params=None):
    headers = {"Authorization": f"Bearer {token}"}
    if params is None:
        params = {}
    params.setdefault("$format", "JSON")
    resp = requests.get(
        f"{TDX_BASE_URL}{path}",
        headers=headers,
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _short_type_name(name):
    """Strip verbose parenthetical descriptions, keep short ones like (3000)."""
    return re.sub(r'\(([^)]+)\)', lambda m: '' if (len(m.group(1)) > 4 or ' ' in m.group(1)) else m.group(0), name).strip()


def _parse_hhmm(time_str):
    """Parse 'HH:MM' or 'HH:MM:SS' into a comparable tuple (h, m)."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


def _time_diff_minutes(target_hhmm, train_hhmm):
    """Return signed minute difference: train_time - target_time."""
    t_h, t_m = target_hhmm
    r_h, r_m = train_hhmm
    return (r_h * 60 + r_m) - (t_h * 60 + t_m)


def _format_duration(dep_str, arr_str):
    """Return human-readable duration like '1時09分'."""
    d_h, d_m = _parse_hhmm(dep_str)
    a_h, a_m = _parse_hhmm(arr_str)
    total = (a_h * 60 + a_m) - (d_h * 60 + d_m)
    if total < 0:
        total += 24 * 60
    h, m = divmod(total, 60)
    if h:
        return f"{h}時{m:02d}分"
    return f"{m}分"


def query_trains(date_str, time_str, origin_name, dest_name=None, nearby=5):
    """
    查詢指定日期/時間/起站附近的台鐵班次。

    Args:
        date_str: 接受 YYYYMMDD / MMDD / DD，年月未填自動補當前
        time_str: 'HH:MM'
        origin_name: 起站中文名稱
        dest_name: 終站中文名稱（可為 None）
        nearby: 時間前後各幾班

    Returns:
        None（直接印出）
    """
    # Parse and normalise date / time
    try:
        date8 = parse_date(date_str)  # YYYYMMDD
    except ValueError as e:
        print(f"錯誤：{e}")
        sys.exit(1)
    try:
        time_str = parse_time(time_str)  # HH:MM
    except ValueError as e:
        print(f"錯誤：{e}")
        sys.exit(1)
    # TDX API requires YYYY-MM-DD
    api_date = f"{date8[:4]}-{date8[4:6]}-{date8[6:]}"
    display_date = f"{date8[:4]}/{date8[4:6]}/{date8[6:]}"

    # Validate stations
    if origin_name not in _STATION_NAME_TO_ID:
        print(f"錯誤：起站 '{origin_name}' 不存在")
        sys.exit(1)
    if dest_name and dest_name not in _STATION_NAME_TO_ID:
        print(f"錯誤：終站 '{dest_name}' 不存在")
        sys.exit(1)

    origin_id = _STATION_NAME_TO_ID[origin_name]

    # Load credentials
    cfg = _load_config()
    client_id = cfg.get("client_id", "")
    client_secret = cfg.get("client_secret", "")
    if not client_id or not client_secret:
        print("錯誤：請在 tdx_config 設定 client_id 和 client_secret")
        print("  前往 https://tdx.transportdata.tw 免費註冊")
        sys.exit(1)

    try:
        token = _get_token(client_id, client_secret)
    except Exception as e:
        print(f"TDX 認證失敗: {e}")
        sys.exit(1)

    target_hhmm = _parse_hhmm(time_str)
    trains = []

    try:
        if dest_name:
            dest_id = _STATION_NAME_TO_ID[dest_name]
            data = _tdx_get(
                token,
                f"/v3/Rail/TRA/DailyTrainTimetable/OD/{origin_id}/to/{dest_id}/{api_date}",
            )
            if isinstance(data, dict):
                data = next((v for v in data.values() if isinstance(v, list)), [])
            # Response: list of { TrainInfo: {...}, StopTimes: [...] }
            for item in data:
                info = item.get("TrainInfo", {})
                stops = item.get("StopTimes", [])
                dep_stop = next((s for s in stops if s["StationID"] == origin_id), None)
                arr_stop = next((s for s in stops if s["StationID"] == dest_id), None)
                if not dep_stop:
                    continue
                dep_time = dep_stop.get("DepartureTime", dep_stop.get("ArrivalTime", ""))
                arr_time = arr_stop.get("ArrivalTime", arr_stop.get("DepartureTime", "")) if arr_stop else ""
                trains.append({
                    "train_no": info.get("TrainNo", ""),
                    "type_id": str(info.get("TrainTypeCode", info.get("TrainTypeID", ""))),
                    "type_name": info.get("TrainTypeName", {}).get("Zh_tw", ""),
                    "dep_time": dep_time,
                    "arr_time": arr_time,
                })
        else:
            data = _tdx_get(
                token,
                f"/v3/Rail/TRA/DailyStationTimetable/Station/{origin_id}/{api_date}",
            )
            if isinstance(data, dict):
                data = next((v for v in data.values() if isinstance(v, list)), [])
            # Response: list of { TrainInfo: {...}, StopTime: {...} }
            for item in data:
                info = item.get("TrainInfo", {})
                stop = item.get("StopTime", {})
                dep_time = stop.get("DepartureTime", stop.get("ArrivalTime", ""))
                trains.append({
                    "train_no": info.get("TrainNo", ""),
                    "type_id": str(info.get("TrainTypeCode", info.get("TrainTypeID", ""))),
                    "type_name": info.get("TrainTypeName", {}).get("Zh_tw", ""),
                    "dep_time": dep_time,
                    "arr_time": "",
                })
    except requests.HTTPError as e:
        print(f"TDX API 錯誤: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"查詢失敗: {e}")
        sys.exit(1)

    if not trains:
        print("查無資料")
        return

    # Sort by departure time
    trains = [t for t in trains if t["dep_time"]]
    trains.sort(key=lambda t: _parse_hhmm(t["dep_time"]))

    # Find closest train index
    diffs = [abs(_time_diff_minutes(target_hhmm, _parse_hhmm(t["dep_time"]))) for t in trains]
    closest_idx = diffs.index(min(diffs))

    lo = max(0, closest_idx - nearby)
    hi = min(len(trains), closest_idx + nearby + 1)
    selected = trains[lo:hi]

    # Print header
    dest_label = f" → {dest_name}" if dest_name else ""
    print(f"\n查詢: {origin_name}{dest_label} | {display_date} {time_str} 附近班次\n")

    if dest_name:
        header = f"{'車次':<6} {'車種':<12} {'出發':<7} {'到達':<7} {'行駛時間'}"
        sep = "─" * 52
        print(header)
        print(sep)
        for t in selected:
            type_display = _short_type_name(t["type_name"]) or TRAIN_TYPE_NAMES.get(t["type_id"], t["type_id"])
            dep = t["dep_time"][:5] if t["dep_time"] else "─"
            arr = t["arr_time"][:5] if t["arr_time"] else "─"
            duration = _format_duration(dep, arr) if t["dep_time"] and t["arr_time"] else "─"
            marker = " ←" if t == trains[closest_idx] else ""
            print(f"{t['train_no']:<6} {type_display:<12} {dep:<7} {arr:<7} {duration}{marker}")
    else:
        header = f"{'車次':<6} {'車種':<12} {'出發'}"
        sep = "─" * 38
        print(header)
        print(sep)
        for t in selected:
            type_display = _short_type_name(t["type_name"]) or TRAIN_TYPE_NAMES.get(t["type_id"], t["type_id"])
            dep = t["dep_time"][:5] if t["dep_time"] else "─"
            marker = " ←" if t == trains[closest_idx] else ""
            print(f"{t['train_no']:<6} {type_display:<12} {dep}{marker}")

    print()
