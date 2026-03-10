import time
import re
import sys
from seleniumbase import Driver
from stations import stationIDs

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_NO_SEATS = 2
MAX_RETRIES = 5

def load_from_args():
    if len(sys.argv) not in (6, 7, 8):
        print("Usage: python main.py <帳號> <起站> <終站> <日期> <車次> [座位偏好(n/a/w)] [目標車廂]")
        print("       python main.py query <起站> <終站> <日期> <時間(HH:MM)>")
        print("  日期格式：YYYYMMDD / MMDD / DD（未填年月自動補當前）")
        sys.exit(EXIT_ERROR)

    起站 = sys.argv[2]
    終站 = sys.argv[3]
    if 起站 not in stationIDs:
        print(f"起站 '{起站}' 不存在")
        sys.exit(EXIT_ERROR)
    if 終站 not in stationIDs:
        print(f"終站 '{終站}' 不存在")
        sys.exit(EXIT_ERROR)

    from tdx import parse_date
    try:
        date8 = parse_date(sys.argv[4])
    except ValueError as e:
        print(f"錯誤：{e}")
        sys.exit(EXIT_ERROR)

    data = {
        "帳號": sys.argv[1],
        "起站": 起站,
        "終站": 終站,
        "日期": date8,
        "車次": sys.argv[5],
        "座位偏好": sys.argv[6] if len(sys.argv) >= 7 and sys.argv[6] in ('n', 'a', 'w') else 'n',
        "目標車廂": sys.argv[7] if len(sys.argv) == 8 else (sys.argv[6] if len(sys.argv) == 7 and sys.argv[6] not in ('n', 'a', 'w') else None),
    }
    return data

class Booker():
    def __init__(self):
        self.cfg = load_from_args()
        self.driver = Driver(uc=True)

    def waitForBlockUI(self):
        # Wait up to 2s for blockUI to appear (in case AJAX hasn't started yet)
        for _ in range(8):
            if self.driver.is_element_visible('.blockUI.blockOverlay'):
                break
            time.sleep(0.25)
        # Then wait for blockUI to disappear (up to 30s)
        for _ in range(120):
            if not self.driver.is_element_visible('.blockUI.blockOverlay'):
                return
            time.sleep(0.25)

    def waitForResults(self, timeout=30):
        """Wait for search results or no-seats message to appear. Returns True if results found."""
        for _ in range(timeout * 4):
            if self.driver.is_element_visible('tr.trip-column'):
                return True
            if self.driver.is_element_visible('.search-trip-mag'):
                return False
            if self.driver.is_element_visible('.info-error'):
                return None  # form validation error
            time.sleep(0.25)
        return None  # timeout

    def booking(self):
        """Returns: 'success', 'no_seats', or 'error'"""
        self.reserved = []
        self.bookID = ""
        try:
            # Navigate directly to the complete booking form (tip123)
            self.driver.open("https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip123/query")
            self.waitForBlockUI()
            self.driver.wait_for_element_visible('#startStation1')
            startStation = stationIDs[self.cfg["起站"]]+'-'+self.cfg["起站"]
            self.driver.type('#startStation1', startStation)
            endStation = stationIDs[self.cfg["終站"]]+'-'+self.cfg["終站"]
            self.driver.type('#endStation1', endStation)
            self.driver.type('#pid', self.cfg["帳號"])
            self.driver.type('#rideDate1', self.cfg["日期"])
            self.driver.type('#trainNoList1', self.cfg["車次"])
            if self.driver.is_element_visible('#queryForm > div:nth-child(3) > div.column.col3 > div.zone.pref > div.zone-group > div > .btn.btn-lg.btn-linear.active'):
                self.driver.click('#queryForm > div:nth-child(3) > div.column.col3 > div.zone.pref > div.zone-group > div > label')
            if self.cfg["座位偏好"] == 'w':
                self.driver.click("#queryForm > div:nth-child(3) > div.column.col3 > div:nth-child(2) > div.btn-group.seatPref > label:nth-child(2)")
            elif self.cfg["座位偏好"] == 'a':
                self.driver.click("#queryForm > div:nth-child(3) > div.column.col3 > div:nth-child(2) > div.btn-group.seatPref > label:nth-child(3)")
            elif self.cfg["座位偏好"] == 'n':
                self.driver.click("#queryForm > div:nth-child(3) > div.column.col3 > div:nth-child(2) > div.btn-group.seatPref > label:nth-child(1)")
            self.driver.wait_for_element_visible('#queryForm > div.btn-sentgroup > input.btn.btn-3d')
            self.driver.click('#queryForm > div.btn-sentgroup > input.btn.btn-3d')
            result = self.waitForResults(timeout=30)
            if result is None:
                print("查詢逾時或表單驗證失敗")
                return "error"
            if result is False:
                print("無可用座位")
                return "no_seats"
            self.driver.click('#queryForm > div.search-trip > table > tbody > tr.trip-column > td.check-way > label')
            self.waitForBlockUI()
            self.driver.wait_for_element_visible('#queryForm > div.btn-sentgroup > button.btn.btn-3d')
            self.driver.click('#queryForm > div.btn-sentgroup > button.btn.btn-3d')
            # Page navigates to /tip115/booking/modify — wait for it
            self.driver.wait_for_element_visible('.seat', timeout=20)
            seat = self.driver.get_text('.seat')
            self.reserved = re.findall(r'\d+', seat)
            self.bookID = self.driver.get_text('.font18', timeout=20)
            if len(self.reserved) != 2:
                print("booking error")
                return "error"
            print("Booked!!")
            return "success"
        except Exception as e:
            print(f"訂票過程發生錯誤: {e}")
            return "error"

    def cancel(self):
        for attempt in range(3):
            try:
                self.driver.open("https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip115/query")
                self.waitForBlockUI()
                self.driver.type('#pid', self.cfg["帳號"])
                self.driver.type('#bookingcode', self.bookID)
                self.driver.wait_for_element_visible('#queryForm > div.btn-sentgroup > button')
                self.driver.click('#queryForm > div.btn-sentgroup > button')
                self.waitForBlockUI()
                self.driver.wait_for_element_visible('#cancel', timeout=15)
                self.driver.click('#cancel')
                self.driver.wait_for_element_visible('.btn-danger', timeout=15)
                self.driver.click('.btn-danger')
                self.waitForBlockUI()
                print("Canceled!!")
                return
            except Exception as e:
                print(f"取消失敗 ({attempt+1}/3): {e}")
                time.sleep(2)
        print("取消失敗，請手動取消訂票代碼:", self.bookID)

    def startBookAndCheck(self):
        """Returns EXIT_SUCCESS, EXIT_NO_SEATS, or EXIT_ERROR."""
        target_car = self.cfg["目標車廂"]
        retries = 0
        try:
            while retries < MAX_RETRIES:
                result = self.booking()
                if result == "no_seats":
                    print("無座位")
                    return EXIT_NO_SEATS
                if result == "error":
                    retries += 1
                    print(f"重試 ({retries}/{MAX_RETRIES})...")
                    time.sleep(3)
                    continue
                # result == "success"
                retries = 0
                if target_car is None or self.reserved[0] == target_car:
                    print(f"訂票成功! 車廂:{self.reserved[0]} 座位:{self.reserved[1]}")
                    return EXIT_SUCCESS
                else:
                    print(f"車廂不符 (got {self.reserved[0]}, want {target_car})，取消重訂...")
                    self.cancel()
            print("重試次數已達上限")
            return EXIT_ERROR
        except Exception as e:
            print(f"發生錯誤: {e}")
            return EXIT_ERROR
        finally:
            self.driver.quit()

if __name__ == "__main__":
    # query subcommand: python main.py query <起站> <日期> <時間> [終站]
    if len(sys.argv) >= 2 and sys.argv[1] == "query":
        if len(sys.argv) != 6:
            print("Usage: python main.py query <起站> <終站> <日期> <時間(HH:MM)>")
            print("  日期格式：YYYYMMDD / MMDD / DD（未填年月自動補當前）")
            sys.exit(EXIT_ERROR)
        from tdx import query_trains
        origin = sys.argv[2]
        dest = sys.argv[3]
        date = sys.argv[4]
        time_s = sys.argv[5]
        query_trains(date, time_s, origin, dest)
        sys.exit(EXIT_SUCCESS)

    # schedule subcommand: python main.py schedule <間隔秒數> <帳號> <起站> ...
    if len(sys.argv) >= 2 and sys.argv[1] == "schedule":
        if len(sys.argv) < 8:
            print("Usage: python main.py schedule <間隔秒數> <帳號> <起站> <終站> <日期> <車次> [座位偏好(n/a/w)] [目標車廂]")
            sys.exit(EXIT_ERROR)
        try:
            interval = int(sys.argv[2])
        except ValueError:
            print("錯誤：間隔秒數必須為整數")
            sys.exit(EXIT_ERROR)
        sys.argv = [sys.argv[0]] + sys.argv[3:]
        attempt = 0
        while True:
            attempt += 1
            print(f"\n===== 第 {attempt} 次嘗試 =====")
            code = Booker().startBookAndCheck()
            if code == EXIT_SUCCESS:
                sys.exit(EXIT_SUCCESS)
            elif code == EXIT_NO_SEATS:
                print(f"{interval} 秒後重試...")
                time.sleep(interval)
            else:
                print("發生錯誤，停止排程")
                sys.exit(EXIT_ERROR)

    try:
        sys.exit(Booker().startBookAndCheck())
    except Exception as e:
        print(f"啟動失敗: {e}")
        sys.exit(EXIT_ERROR)
