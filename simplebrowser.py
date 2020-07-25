from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import SessionNotCreatedException
from selenium.webdriver.chrome.options import Options
import os
import time
import logging
import random

logger = logging.getLogger(__name__)


class SimpleBrowser:

    @classmethod
    def __create_chrome_driver(cls, width, height):
        assert width
        assert height
        options = Options()
        options.add_argument(f'--window-size={width},{height}')
        # if width < 450:
        #     mobile_emulation = {
        #         'deviceMetrics': 
        #             { 'width': width, 'height': height, 'pixelRatio': 3.0}
        #     }
        #     options.add_experimental_option("mobileEmulation", mobile_emulation)
        driver = webdriver.Chrome(options=options)
        return driver

    @classmethod
    def __create_safari_driver(cls, width, height):
        driver = webdriver.Safari()
        driver.set_window_size(width, height)
        return driver

    @classmethod
    def __create_driver(cls, browser, width, height):
        assert browser in ['chrome', 'safari',
                           'firefox', None], 'unsupported browser'
        driver = None
        for i in range(0, 3):
            try:
                if browser == 'safari':
                    driver = SimpleBrowser.__create_safari_driver(
                        width=width, height=height)
                if browser == 'chrome' or not browser:
                    driver = SimpleBrowser.__create_chrome_driver(
                        width=width, height=height)
            except SessionNotCreatedException as e:
                logger.exception('couldnt create session properly')
                time.sleep(4)
            if driver:
                break
        return driver

    def __init__(self, browser, width, height):
        self.browser = browser
        self.driver = SimpleBrowser.__create_driver(
            browser=browser, width=width, height=height)
        assert self.driver, 'unable to initialize browser properly'
        self.timeout = 5
        self.wait = WebDriverWait(self.driver, self.timeout)

    def close(self):
        time.sleep(1)
        driver = self.driver
        self.driver = None
        if driver:
            driver.close()
        time.sleep(2)

    def __del__(self):
        logger.debug('destructor called')
        self.close()

    def get(self, url):
        return self.driver.get(url)

    def checkbox_click(self, elem):
        self.driver.execute_script("arguments[0].click();", elem)

    def current_height(self):
        return self.driver.execute_script("return document.body.scrollHeight")

    def current_scroll_position(self):
        return self.driver.execute_script("return window.pageYOffset")

    def scroll_down_page(self, max_speed=300):
        current_scroll_position, new_height= 0, 1
        while current_scroll_position <= new_height:
            delta = random.randint(1, max_speed)
            current_scroll_position += delta
            self.driver.execute_script(f'window.scrollTo(0, {current_scroll_position});')
            time.sleep(random.uniform(0.0, 1.0))
            new_height = self.current_height()

    def scroll_up_page(self, max_speed=300):
        pos = self.current_scroll_position()
        while pos > 0:
            delta = random.randint(1, max_speed)
            pos -= delta
            if pos < 0:
                pos = 0
            self.driver.execute_script(f'window.scrollTo(0, {pos});')
            time.sleep(random.uniform(0.0, 1.0))
 
    def find(self, xpath, scroll=False):
        l = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        if scroll:
            self.driver.execute_script("arguments[0].scrollIntoView(true);", l)
            time.sleep(1)
            l = self.wait.until(
                EC.presence_of_element_located((By.XPATH, xpath)))
        return l

    def find_many(self, xpath):
        m = self.wait.until(EC.presence_of_all_elements_located((By.XPATH, xpath)))
        return m

    def click(self, xpath, scroll=False):
        l = self.find(xpath, scroll)
        ltag = l.tag_name.lower() if l.tag_name else None
        assert ltag in ['input', 'li', 'button', 'span',
                        'a', 'div', 'textarea'], 'xpath did not return proper element'
        l = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath)))
        l.click()
        return l

    def input(self, xpath, keys, scroll=False):
        l = self.find(xpath, scroll)
        ltag = l.tag_name.lower() if l.tag_name else None
        # logger.info('found element with tag %s', ltag)
        assert ltag in ['input', 'li', 'button', 'span',
                        'a', 'div', 'textarea'], 'xpath did not return proper element'
        l = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        l.click()
        time.sleep(0.1)
        l.send_keys(keys)
        time.sleep(0.1)
        return l

    def close_windows(self):
        # close all windows except 0
        while len(self.driver.window_handles) > 1:
            w = self.driver.window_handles[-1]
            self.driver.switch_to.window(w)
            self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])

    def mark_divs(self):
        for d in self.driver.find_elements_by_xpath("//div"):
            self.driver.execute_script(
                "arguments[0]['style']['border']='1px solid black';", d)

    def get_width(self):
        return self.driver.get_window_size()['width']

    def get_height(self):
        return self.driver.get_window_size()['height']

    def is_desktop(self):
        return self.get_width() >= 1024

    def is_mobile(self):
        return self.get_width() < 425

    def is_tablet(self):
        return self.get_width() >= 425 and self.get_width() < 1024

    def get_current_url(self):
        return self.driver.current_url

    def set_window_size(self, width, height):
        self.driver.set_window_size(width, height)