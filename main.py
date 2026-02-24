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
        extension_path = r"./extension"
        self.cfg = load_from_args()
        self.driver = Driver(uc=True, headless2=True, extension_dir=extension_path)

    def waitForBlockUI(self):
        for _ in range(30):
            if not self.driver.is_element_visible('.blockUI.blockOverlay'):
                return
            time.sleep(1)

    def checkRecaptcha(self):
        print("wait passing recaptcha...")
        wait = False
        if self.driver.is_element_visible('iframe[title="google recaptcha"]'):
            self.driver.switch_to_frame('iframe[title="google recaptcha"]')
            time.sleep(1)
            self.driver.click('#recaptcha-anchor')
            while not self.driver.is_element_visible('.recaptcha-checkbox-checked'):
                self.driver.switch_to_default_window()
                if self.driver.is_element_visible('iframe[title="recaptcha challenge expires in two minutes"]'):
                    self.driver.switch_to_frame('iframe[title="recaptcha challenge expires in two minutes"]')
                    self.driver.wait_for_element('.help-button-holder', timeout=5)
                    self.driver.click('.help-button-holder')
                    print("Clicked reCAPTCHA solve button")
                    wait = True
                    break
                time.sleep(1)
                self.driver.switch_to_frame('iframe[title="google recaptcha"]')
        self.driver.switch_to_default_window()
        time.sleep(1)
        if wait:
            time.sleep(9)

    def login(self):
        self.driver.open("https://www.railway.gov.tw/tra-tip-web/tip/tip008/tip811/memberLogin")
        self.driver.type("#username", self.cfg["帳號"])
        self.driver.type("#password", self.cfg["密碼"])
        self.checkRecaptcha()
        self.driver.click('#submitBtn')
        time.sleep(3)
        print("Logged in!!")

    def booking(self):
        """Returns: 'success', 'no_seats', or 'error'"""
        self.reserved = []
        self.bookID = ""
        try:
            self.driver.open("https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip121/query")
            self.waitForBlockUI()
            self.driver.click('#tablist > li:nth-child(2) > a')
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
            self.checkRecaptcha()
            self.waitForBlockUI()
            self.driver.click('#queryForm > div.btn-sentgroup > input.btn.btn-3d')
            time.sleep(5)
            self.waitForBlockUI()
            if self.driver.is_element_visible('.search-trip-mag'):
                print("無可用座位")
                return "no_seats"
            self.driver.click('#queryForm > div.search-trip > table > tbody > tr.trip-column > td.check-way > label')
            self.checkRecaptcha()
            self.waitForBlockUI()
            self.driver.click('#queryForm > div.btn-sentgroup > button.btn.btn-3d')
            seat = self.driver.get_text('.seat')
            self.reserved = re.findall(r'\d+', seat)
            self.bookID = self.driver.get_text('.font18')
            if len(self.reserved) != 2:
                print("booking error")
                return "error"
            print("Booked!!")
            return "success"
        except Exception as e:
            print(f"訂票過程發生錯誤: {e}")
            return "error"

    def cancel(self):
        self.driver.get("https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip115/query")
        self.driver.type('#pid', self.cfg["帳號"])
        self.driver.type('#bookingcode', self.bookID)
        time.sleep(1)
        self.driver.click('#queryForm > div.btn-sentgroup > button')
        time.sleep(1)
        self.driver.click('#cancel')
        time.sleep(1)
        self.driver.click('.btn-danger')
        time.sleep(1)
        print("Canceled!!")

    def startBookAndCheck(self):
        """Returns EXIT_SUCCESS, EXIT_NO_SEATS, or EXIT_ERROR."""
        # self.login()
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
