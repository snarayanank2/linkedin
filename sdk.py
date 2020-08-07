from simplebrowser import SimpleBrowser
from typing import Generator, Dict
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pdb
import re
import time
import random
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def pause(min=600, max=8000):
    s = (random.randint(min, max) * 1.0) / 1000.0
    time.sleep(s)

def parse_salesnav_search(page_source: str):
    soup = BeautifulSoup(page_source, 'html.parser')
    sections = soup.find_all("section", "result-lockup")
    res = []
    for section in sections:
        full_name = section.dl.find("dt", "result-lockup__name").a.string.strip()
        words = full_name.split(' ')
        first_name = words[0].lower().capitalize()
        last_name = words[-1].lower().capitalize() if len(words) > 1 else None
        salesnav_url = "https://www.linkedin.com" + section.dl.find("dt", "result-lockup__name").a["href"]
        company = section.dl.find("span", "result-lockup__position-company").a.span.string.strip()
        title = section.dl.find_all("dd")[1].span.string.strip()
        location = None
        degree = None
        try:
            location = section.dl.find_all("dd")[3].ul.li.string.strip()
            degree = section.dl.find("span", "label-16dp").string.strip()
        except Exception:
            pass
        res.append({
            'full_name': full_name,
            'first_name': first_name,
            'last_name': last_name,
            'salesnav_url': salesnav_url,
            'title': title,
            'company': company,
            'location': location,
            'degree': degree
        })
    return res

def parse_salesnav_details(page_source: str):
    soup = BeautifulSoup(page_source, 'html.parser')
    degree = soup.find("span", "label-16dp").string.strip()
    common_name = None
    if soup.find("li", "best-path-in"):
        common_div = soup.find("li", "best-path-in").find("div", "best-path-in-entity__spotlight")
        if common_div:
            common_name = common_div.find("a").string.strip()
    connect_status_li = soup.find("div", "profile-topcard-actions__overflow-dropdown").div.ul.li
    if connect_status_li.div:
        connect_status = 'Connect'
    else:
        connect_status = 'Pending'
    return {
        'degree': degree,
        'common_name': common_name,
        'connect_status': connect_status
    }

def parse_profile_details(page_source: str):
    # TODO: implement this
    return {}

class LinkedIn:

    def __init__(self):
        self.sb = SimpleBrowser(browser='chrome', width=1536, height=864)

    def login(self, username: str, password: str):
        self.sb.get('https://www.linkedin.com/login?fromSignIn=true&trk=guest_homepage-basic_nav-header-signin')
        self.sb.input(xpath='//input[@id="username"]', keys=username)
        self.sb.input(xpath='//input[@id="password"]', keys=password)
        pause()
        self.sb.click(xpath='//button[contains(text(), "Sign in")]')
        pause()

    def __salesnav_search_page(self):
        pause()
        self.sb.scroll_down_page()
        res = parse_salesnav_search(self.sb.driver.page_source)
        return res

    def salesnav_search(self, url: str, start_page: int, num_pages: int):
        assert num_pages > 0
        current_page: int = start_page
        self.sb.get(f'{url}&page={current_page}')
        while True:
            logger.info('processing page %s', current_page)
            pause()
            self.sb.scroll_down_page()
            res = parse_salesnav_search(self.sb.driver.page_source)
            for sr in res:
                yield sr
            current_page = current_page + 1
            if current_page >= start_page + num_pages:
                break
            n = self.sb.find(xpath='//button[@class="search-results__pagination-next-button"]', scroll=True)
            disabled = n.get_attribute('disabled')
            if disabled:
                break
            else:
                n.click()

    def __salesnav_goto_profile(self):
        self.sb.click(xpath='//button[contains(@class, "right-actions-overflow-menu-trigger")]')
        pause(min=200, max=300)
        self.sb.click(xpath='//div[@data-control-name="view_linkedin"]')
        pause(min=500, max=1000)
        # this is one weird thing.. linkedin.com opens in new tab so we need to switch to it
        # TODO: move this functionality to simplebrowser
        self.sb.driver.switch_to.window(self.sb.driver.window_handles[1])


    def __profile_connect(self, note: str):
        # TODO: assert that we are in a profile page
        self.sb.scroll_down_page()
        self.sb.scroll_up_page()
        connected = False
        try:
            self.sb.click(xpath='//button[contains(@aria-label, "Connect with")]')
            connected = True
        except Exception as e:
            logger.error('did not find connect button will try more..')

        if not connected:
            self.sb.click(xpath='//button/span[contains(text(), "More")]')
            pause(min=200, max=400)
            self.sb.click(xpath='//div[contains(@class, "pv-s-profile-actions--connect")]//span[contains(text(),"Connect")]')
            connected = True

        assert connected
        if note:
            self.sb.click(xpath='//button[contains(@aria-label, "Add a note")]')
            self.sb.input(xpath='//textarea[@name="message"]', keys=note)
            self.sb.click(xpath='//button[contains(@aria-label, "Done")]')
        else:
            self.sb.click(xpath='//button[contains(@aria-label, "Send now")]')

    def __profile_follow(self):
        # TODO: assert that we are in a profile page
        followed = False
        try:
            self.sb.click(xpath='//button[contains(@aria-label, "Follow")]')
            followed = True
        except Exception as e:
            logger.error('did not find follow button will try more..')

        if not followed:
            self.sb.click(xpath='//button/span[contains(text(), "More")]')
            pause(min=200, max=400)
            self.sb.click(xpath='//div[contains(@class, "pv-s-profile-actions--follow")]//span[contains(text(),"Follow")]')


    def salesnav_connect(self, salesnav_url: str, note: str):
        self.sb.get(salesnav_url)
        pause(min=2000, max=3000)
        res = parse_salesnav_details(page_source=self.sb.driver.page_source)
        if res['connect_status'] == 'Pending':
            return res
        self.__salesnav_goto_profile()
        res['profile_url'] = self.sb.get_current_url()
        res2 = parse_profile_details(page_source=self.sb.driver.page_source)
        res = {**res, **res2}
        try:
            self.__profile_connect(note=note)
        finally:
            self.sb.close_windows()
        return res

    def salesnav_follow(self, salesnav_url: str):
        self.sb.get(salesnav_url)
        pause(min=1000, max=3000)
        res = parse_salesnav_details(page_source=self.sb.driver.page_source)
        if res['connect_status'] == 'Pending':
            return res
        self.__salesnav_goto_profile()
        res['profile_url'] = self.sb.get_current_url()
        res2 = parse_profile_details(page_source=self.sb.driver.page_source)
        res = {**res, **res2}
        try:
            self.__profile_follow()
        finally:
            self.sb.close_windows()
        return res

    def invitations_withdraw(self, page: int):
        self.sb.get(f'https://www.linkedin.com/mynetwork/invitation-manager/sent/?invitationType=&page={page}')
        self.sb.scroll_down_page()
        lis = self.sb.find_many(xpath='//li[contains(@class, "invitation-card")]')
        liws = reversed(lis)

        # for li in reversed(lis):
        #     t = li.find_element_by_xpath('.//time').text
        #     if 'week' in t and li.is_displayed():
        #         liws.append(li)

        for liw in liws:
            self.sb.scroll_down_page()
            logger.info('withdrawing invitation %s', liw.text)
            b = liw.find_element_by_xpath('.//button[contains(@data-control-name, "withdraw_single")]')
            b.click()
            pause(min=500, max=1000)
            self.sb.click(xpath='//button[contains(@class, "artdeco-button--primary")]')
            pause(min=1000, max=2000)
