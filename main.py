import time
import re
from seleniumbase import Driver
from stations import stationIDs

def load_from_file():
    data = {}
    try:
        with open('settings.txt', 'r', encoding='utf-8') as file:
            for line in file:
                key, value = line.strip().split('=', 1)
                data[key] = value
        return data
    except FileNotFoundError:
        print("File not found!")
        return None
    except UnicodeDecodeError as e:
        print(f"Error decoding file: {e}")
        return None

class Booker():
    def __init__(self):
        extension_path = r"./extension"
        self.cfg = load_from_file()
        self.driver = Driver(uc=True, headless2=True, extension_dir=extension_path)

    def checkRecaptcha(self):
        print("wait passing recaptcha...")
        if self.driver.is_element_visible('iframe[title="google recaptcha"]'):
            self.driver.switch_to_frame('iframe[title="google recaptcha"]')
            self.driver.click('#recaptcha-anchor')
            wait = False
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
        if wait:
            time.sleep(8)

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
        startStation = stationIDs[self.cfg["起站"]]+'-'+self.cfg["起站"]
        self.driver.type('#startStation', startStation)
        endStation = stationIDs[self.cfg["終站"]]+'-'+self.cfg["終站"]
        self.driver.type('#pid', self.cfg["帳號"])
        self.driver.type('#endStation', endStation)
        self.driver.type('#rideDate1', self.cfg["日期"])
        self.driver.type('#trainNoList1', self.cfg["車次"])
        self.checkRecaptcha()
        self.driver.click('#queryForm > div.btn-sentgroup > input.btn.btn-3d')
        time.sleep(5)
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
            if len(self.reserved) == 2 and self.reserved[0] == self.cfg["目標車廂"] and int(self.reserved[1]) < int(self.cfg["目標座號結束"]) and int(self.reserved[1]) > int(self.cfg["目標座號起始"]):
                success = True
                print("Found!!")
            else:
                self.cancel()

if __name__ == "__main__":
    newBooker = Booker()
    newBooker.startBookAndCheck()
