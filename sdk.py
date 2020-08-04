from simplebrowser import SimpleBrowser
from typing import Generator, Dict
from selenium.common.exceptions import NoSuchElementException
import pdb
import re
import time
import random
import logging

logger = logging.getLogger(__name__)

SalesNavSearchResult = Dict[str, str]
NetworkSearchResult = Dict[str, str]
ProfileDetails = Dict[str, str]

def pause(min=600, max=8000):
    s = (random.randint(min, max) * 1.0) / 1000.0
    time.sleep(s)

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

    def __salesnav_search_results_page(self) -> Generator[SalesNavSearchResult, None, None]:
        self.sb.scroll_down_page()
        dls = self.sb.find_many(xpath='//section[@class="result-lockup"]//dl')
        for dl in dls:
            data: SalesNavSearchResult = {}
            a = dl.find_element_by_xpath('./dt/a')
            data['full_name'] = a.text
            data['full_name'] = (data['full_name'].split(',')[0]).lower().capitalize()
            words = data['full_name'].split(' ')
            data['first_name'] = words[0].lower().capitalize()
            data['last_name'] = words[-1].lower().capitalize() if len(words) > 1 else None
            link = a.get_attribute('href')
            data['salesnav_url'] = link
            dds = dl.find_elements_by_xpath('./dd')
            data['title'] = dds[1].find_elements_by_xpath('./span')[0].text
            data['company'] = dds[1].find_element_by_xpath('./span/span/a/span').text
            data['company_url'] = dds[1].find_element_by_xpath('./span/span/a').get_attribute('href')
            data['company_id'] = __company_id_from_url(url=data['company_url'])
            try:
                data['location'] = dds[3].find_element_by_xpath('./ul/li').text
                data['experience'] = dds[2].find_element_by_xpath('./span').text
            except NoSuchElementException as e:
                logger.exception('could not find element')
            yield data

    def salesnav_search_results(self, search_url: int, start_page: int, num_pages: int) -> Generator[SalesNavSearchResult, None, None]:
        assert num_pages > 0
        current_page = start_page
        self.sb.get(f'{search_url}&page={current_page}')
        while True:
            logger.info('processing page %s', current_page)
            for sr in self.__salesnav_search_results_page():
                yield sr
            current_page = current_page + 1
            if current_page > start_page + num_pages:
                break
            n = self.sb.find(xpath='//button[@class="search-results__pagination-next-button"]', scroll=True)
            disabled = n.get_attribute('disabled')
            if disabled:
                break
            else:
                n.click()

    def __network_search_results_page(self) -> Generator[NetworkSearchResult, None, None]:
        self.sb.scroll_down_page()
        infos = self.sb.find_many('//div[contains(@class, "search-result__wrapper")]')
        for info in infos:
            a = info.find_element_by_xpath('./div[2]/a')
            full_name = info.find_element_by_xpath('.//span[contains(@class, "actor-name")]').text
            full_name = (full_name.split(',')[0]).lower().capitalize()
            words = full_name.split(' ')
            first_name = words[0].lower().capitalize()
            last_name = words[-1].lower().capitalize() if len(words) > 1 else None
            profile_url = a.get_attribute('href')
            action = info.find_element_by_xpath('.//button[contains(@class, "search-result__actions--primary")]').text
            location = info.find_element_by_xpath('.//p[contains(@class, "subline-level-2")]').text   
            l1 = info.find_element_by_xpath('.//p[contains(@class, "subline-level-1")]').text
            l1s = re.split(' at | of ', l1)
            title = l1s[0]
            company_name = l1s[1] if len(l1s) > 1 else None
            degree = info.find_element_by_xpath('.//span[contains(@class, "dist-value")]').text
            try:
                common_name = info.find_element_by_xpath('.//span[contains(@class, "search-result__social-proof-count")]/span[1]').text
                sr: NetworkSearchResult = {
                    'profile_url': profile_url,
                    'full_name': full_name,
                    'first_name': first_name,
                    'last_name': last_name,
                    'title': title,
                    'company_name': company_name,
                    'location': location,
                    'common_name': common_name,
                    'action': action,
                    'degree': degree,
                }
                logger.info('adding sr %s', sr)
                yield sr
            except Exception:
                logger.error('skipping %s because no common name', full_name)

    def network_search_results(self, search_url: str, start_page: int, num_pages: int) -> Generator[NetworkSearchResult, None, None]:
        current_page = start_page
        self.sb.get(f'{search_url}&page={current_page}')
        while True:
            logger.info('processing page %s', current_page)
            for sr in self.__network_search_results_page():
                yield sr
            current_page = current_page + 1
            if current_page > start_page + num_pages:
                break
            n = self.sb.find(xpath='//button[contains(@class, "artdeco-pagination__button--next")]')
            disabled = n.get_attribute('disabled')
            if disabled:
                break
            else:
                n.click()

    def get_profile_details(self, salesnav_url: str, profile_url: str) -> ProfileDetails:
        res: ProfileDetails = {}
        return res
        raise NotImplementedError()

    def connect_profile(self, profile_url: str, note: str):
        raise NotImplementedError()

    def follow_profile(self, profile_url: str):
        raise NotImplementedError()
