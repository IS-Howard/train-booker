# train-booker

台鐵自動訂票工具，支援訂票、排程重試、以及班次查詢。

## 需求

- Python 3.11+
- [SeleniumBase](https://github.com/seleniumbase/SeleniumBase)
- Google Chrome

```bash
pip install seleniumbase
```

查詢功能額外需要 [TDX 帳號](https://tdx.transportdata.tw)（免費）。

## 用法

### 訂票

```bash
python main.py <帳號> <起站> <終站> <日期> <車次> [座位偏好] [目標車廂]
```

| 參數 | 說明 |
|------|------|
| 帳號 | 台鐵會員身分證字號 |
| 起站／終站 | 中文站名，如 `松山`、`新竹` |
| 日期 | `YYYYMMDD` / `MMDD` / `DD`（年月未填自動補當前） |
| 車次 | 車次號碼，如 `131` |
| 座位偏好 | `n` 無偏好（預設）、`w` 靠窗、`a` 靠走道 |
| 目標車廂 | 指定車廂號，不符則自動取消重訂 |

```bash
python main.py C121568911 松山 新竹 20260301 131 a 5
```

### 排程重試

無票時每隔指定秒數重試，直到訂到為止：

```bash
python main.py schedule <間隔秒數> <帳號> <起站> <終站> <日期> <車次> [座位偏好] [目標車廂]
```

```bash
python main.py schedule 60 C121568911 松山 新竹 20260301 131 a 5
```

### 查詢班次

查詢指定時間附近的台鐵班次（需 TDX API 憑證）：

```bash
python main.py query <起站> <終站> <日期> <時間>
```

```bash
python main.py query 松山 新竹 20260301 0900
```

時間格式：`HH:MM`、`HHMM`、`HMM`（如 `900` → `09:00`）

## TDX 設定

查詢功能需要 TDX API 憑證，建立 `tdx_config` 檔案：

```
client_id=你的_client_id
client_secret=你的_client_secret
```

前往 [tdx.transportdata.tw](https://tdx.transportdata.tw) 免費註冊取得。

## Docker

```bash
docker build -t train-booker .
docker run train-booker C121568911 松山 新竹 20260301 131 a 5
```

## 結束代碼

| 代碼 | 說明 |
|------|------|
| 0 | 訂票成功 |
| 1 | 發生錯誤 |
| 2 | 無可用座位 |
