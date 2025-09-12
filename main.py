import time
import re
import sys
from seleniumbase import Driver
from stations import stationIDs

def load_from_args():
    if len(sys.argv) != 9:
        print("Usage: python main.py <帳號> <密碼> <起站> <終站> <日期> <車次> <座位偏好(n/a/w)> <目標車廂>")
        sys.exit(1)
    
    data = {
        "帳號": sys.argv[1],
        "密碼": sys.argv[2],
        "起站": sys.argv[3],
        "終站": sys.argv[4],
        "日期": sys.argv[5],
        "車次": sys.argv[6],
        "座位偏好": sys.argv[7],
        "目標車廂": sys.argv[8],
    }
    return data

class Booker():
    def __init__(self):
        extension_path = r"./extension"
        self.cfg = load_from_args()
        self.driver = Driver(uc=True, headless2=True, extension_dir=extension_path)

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
        self.driver.open("https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip121/query")
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
        self.driver.click('#queryForm > div.btn-sentgroup > input.btn.btn-3d')
        time.sleep(5)
        self.driver.click('#queryForm > div.search-trip > table > tbody > tr.trip-column > td.check-way > label')
        self.checkRecaptcha()
        self.driver.click('#queryForm > div.btn-sentgroup > button.btn.btn-3d')
        seat = self.driver.get_text('.seat')
        self.reserved = re.findall(r'\d+', seat)
        self.bookID = self.driver.get_text('.font18')
        if len(self.reserved) != 2:
            print("booking error")
        print("Booked!!")

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
        success = False
        self.login()
        while(not success):
            self.booking()
            if len(self.reserved) == 2 and self.reserved[0] == self.cfg["目標車廂"]:
                success = True
                print("Found!!")
            else:
                self.cancel()

if __name__ == "__main__":
    newBooker = Booker()
    newBooker.startBookAndCheck()
