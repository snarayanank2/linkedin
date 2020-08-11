from simplebrowser import SimpleBrowser
from typing import Generator, Dict
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pdb
import re
import time
import random
import logging
from lxml import html, etree

logger = logging.getLogger(__name__)

def pause(min=600, max=8000):
    s = (random.randint(min, max) * 1.0) / 1000.0
    time.sleep(s)

def parse_salesnav_search(page_source: str):
    tree = html.fromstring(page_source)
    sections = tree.xpath('//section[contains(@class, "result-lockup")]')
    res = []
    for section in sections:
        full_name = section.xpath('.//dt[contains(@class, "result-lockup__name")]/a/text()')[0].strip()
        logger.info('%s', full_name)
        words = full_name.split(' ')
        first_name = words[0].lower().capitalize()
        last_name = words[-1].lower().capitalize() if len(words) > 1 else None
        salesnav_url = 'https://www.linkedin.com' + section.xpath('.//dt[contains(@class, "result-lockup__name")]/a/@href')[0]
        logger.info('%s', salesnav_url)
        company = section.xpath('.//dl//span[contains(@class, "result-lockup__position-company")]/a/span/text()')[0].strip()
        title = section.xpath('.//dl//dd[2]//span/text()')[0].strip()
        degree_c = section.xpath('.//dl//span[contains(@class, "label-16dp")]/text()')
        degree = degree_c[0].strip() if len(degree_c) > 0 else None
        location_c = section.xpath('.//dl//dd[4]/ul/li/text()')
        location = location_c[0].strip() if len(location_c) > 0 else None
        d = {
            'full_name': full_name,
            'first_name': first_name,
            'last_name': last_name,
            'salesnav_url': salesnav_url,
            'title': title,
            'company': company,
            'location': location,
            'degree': degree
        }
#        logger.info('d = %s', d)
        res.append(d)
    return res

def parse_salesnav_details(page_source: str):
    tree = html.fromstring(page_source)
    degree_c = tree.xpath('//span[contains(@class, "label-16dp")]/text()')
    degree = degree_c[0].strip() if len(degree_c) > 0 else None
    common_name_a = tree.xpath('//li[contains(@class, "best-path-in")]//div[contains(@class, "best-path-in-entity__spotlight")]//a/text()')
    common_name = common_name_a[0].strip() if len(common_name_a) > 0 else None
    return {
        'degree': degree,
        'common_name': common_name
    }

def parse_profile_details(page_source: str):
    connect_status = None
    follow_status = None
    degree = None
    tree = html.fromstring(page_source)
    degree = tree.xpath('.//li[contains(@class, "pv-top-card__distance-badge")]//span[@class="dist-value"]/text()')[0]
    top_card = tree.xpath('.//section[contains(@class, "pv-top-card")]')[0]
    a1 = top_card.xpath('.//div[contains(@class, "ph5")]//div[contains(@class, "mt1")]//span[contains(@class, "artdeco-button__text")]')[0].text.strip()
    if degree == '1st':
        connect_status = 'connected'
    elif a1 == 'Pending':
        connect_status = 'requested'
    else:
        connect_status = 'not_requested'
    a2 = top_card.xpath('.//div[contains(@class, "pv-s-profile-actions--follow")]//span[contains(@class, "pv-s-profile-actions__label")]/text()')
    if len(a2) > 0 and a2[0] == 'Follow':
        follow_status = 'not_followed'
    else:
        follow_status = 'followed'
    return {
        'connect_status': connect_status,
        'follow_status': follow_status,
        'degree': degree
    }

class LinkedIn:

    def __init__(self):
        self.sb = SimpleBrowser(browser='chrome', width=1920, height=1080)

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
            pass
#            logger.error('did not find connect button will try more..')

        if not connected:
            self.sb.click(xpath='//button/span[contains(text(), "More")]')
            pause(min=200, max=400)
            self.sb.click(xpath='//div[contains(@class, "pv-s-profile-actions--connect")]//span[contains(text(),"Connect")]')
            connected = True

        assert connected
        if note and len(note) > 10:
            self.sb.click(xpath='//button[contains(@aria-label, "Add a note")]')
            self.sb.input(xpath='//textarea[@name="message"]', keys=note)
            self.sb.click(xpath='//button[contains(@aria-label, "Done")]')
        else:
            self.sb.click(xpath='//button[contains(@aria-label, "Send now")]')
        pause(min=500, max=1000)

    def __profile_follow(self):
        # TODO: assert that we are in a profile page
        followed = False
        try:
            self.sb.click(xpath='//button[contains(@aria-label, "Follow")]')
            followed = True
        except Exception as e:
            pass
#            logger.error('did not find follow button will try more..')

        if not followed:
            self.sb.click(xpath='//button/span[contains(text(), "More")]')
            pause(min=200, max=400)
            self.sb.click(xpath='//div[contains(@class, "pv-s-profile-actions--follow")]//span[contains(text(),"Follow")]')


    def salesnav_connect(self, salesnav_url: str, note: str):
        self.sb.get(salesnav_url)
        pause(min=2000, max=3000)
        res = parse_salesnav_details(page_source=self.sb.driver.page_source)
        self.__salesnav_goto_profile()
        res['profile_url'] = self.sb.get_current_url()
        res2 = parse_profile_details(page_source=self.sb.driver.page_source)
        res = {**res, **res2}
        try:
            if res['connect_status'] == 'not_requested':
                logger.info('trying to connect %s', res['profile_url'])
                self.__profile_connect(note=note)
                logger.info('successfully requested')
            else:
                logger.info('already connected.. skipping')
        except Exception as e:
            logger.exception('connect %s failed', res['profile_url'])
            raise e
        finally:
            self.sb.close_windows()
        return res

    def salesnav_follow(self, salesnav_url: str):
        self.sb.get(salesnav_url)
        pause(min=1000, max=3000)
        res = parse_salesnav_details(page_source=self.sb.driver.page_source)
        self.__salesnav_goto_profile()
        res['profile_url'] = self.sb.get_current_url()
        res2 = parse_profile_details(page_source=self.sb.driver.page_source)
        res = {**res, **res2}
        try:
            if res['follow_status'] == 'not_followed':
                logger.info('trying to follow %s', res['profile_url'])
                self.__profile_follow()
                logger.info('followed successfully')
            else:
                logger.info('already followed.. skipping')
        except Exception as e:
            logger.exception('following %s failed', res['profile_url'])
            raise e
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
