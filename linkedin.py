from simplebrowser import SimpleBrowser
import time
import random
import os
import logging
import pdb
import csv
import re
import click
from sheetfu import SpreadsheetApp
from sheetfu import Table
from selenium.common.exceptions import NoSuchElementException
from dateutil.parser import parse
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class LinkedIn:
    def __init__(self):
        self.b = SimpleBrowser(browser='chrome', width=1536, height=864)
    
    def sleep(self, min=600, max=8000):
        s = (random.randint(min, max) * 1.0) / 1000.0
        time.sleep(s)

    def login(self, username, password):
        self.b.get('https://www.linkedin.com/login?fromSignIn=true&trk=guest_homepage-basic_nav-header-signin')
        self.b.input(xpath='//input[@id="username"]', keys=username)
        self.b.input(xpath='//input[@id="password"]', keys=password)
        self.sleep()
        self.b.click(xpath='//button[contains(text(), "Sign in")]')
        self.sleep()

    def send_message(self, url, message):
        self.b.get(url)
        self.b.click(xpath='//a[text()="Message"]')
        self.b.input(xpath='//div[@aria-label="Write a message…"]', keys=message)
        self.b.click(xpath='//button[text()="Send"]')
        self.sleep()
        self.b.click(xpath='//button[@data-control-name="overlay.close_conversation_window"]')
        self.sleep()

    def connect(self, url, message):
        self.b.get(url)
        self.b.click(xpath='//button[contains(@aria-label, "Connect with")]')
        self.sleep()
        self.b.click(xpath='//button[contains(@aria-label, "Add a note")]')
        self.b.input(xpath='//textarea[@name="message"]', keys=message)
        self.b.click(xpath='//button[contains(@aria-label, "Done")]')

    @staticmethod
    def contact_id_from_url(url):
        g = re.match(r'https://.*/people/([^,]*),.*', url)
        if not g:
            return None
        return g[1]

    @staticmethod
    def company_id_from_url(url):
        g = re.match(r'https://.*/company/(.*)', url)
        if not g:
            return None
        return g[1]

    def __extract_search_results_from_page(self):
        dls = self.b.find_many(xpath='//section[@class="result-lockup"]//dl')
        res = []
        for dl in dls:
            data = {}
            a = dl.find_element_by_xpath('./dt/a')
            data['full_name'] = a.text
            data['full_name'] = (data['full_name'].split(',')[0]).lower().capitalize()
            words = data['full_name'].split(' ')
            data['first_name'] = words[0].lower().capitalize()
            data['last_name'] = words[-1].lower().capitalize() if len(words) > 1 else None
            link = a.get_attribute('href')
            id = LinkedIn.contact_id_from_url(url=link)
            data['sales_nav_url'] = link
            data['id'] = id
            dds = dl.find_elements_by_xpath('./dd')
            data['title'] = dds[1].find_elements_by_xpath('./span')[0].text
            data['company'] = dds[1].find_element_by_xpath('./span/span/a/span').text
            data['company_url'] = dds[1].find_element_by_xpath('./span/span/a').get_attribute('href')
            data['company_id'] = LinkedIn.company_id_from_url(url=data['company_url'])
            try:
                data['location'] = dds[3].find_element_by_xpath('./ul/li').text
                data['experience'] = dds[2].find_element_by_xpath('./span').text
            except NoSuchElementException as e:
                logger.exception('could not find element')
#            pdb.set_trace()
            logger.info('adding data %s', data)
            res.append(data)
        return res

    def extract_search_results(self, saved_search_id):
        self.b.get(f'https://www.linkedin.com/sales/search/people?savedSearchId={saved_search_id}')
        self.sleep()
        self.b.scroll_down_page()
        n = self.b.find(xpath='//button[@class="search-results__pagination-next-button"]', scroll=True)
        disabled = n.get_attribute('disabled')
        index = 0
        results = []
        while not disabled:
            self.sleep()
            page_results = self.__extract_search_results_from_page()
            logger.info('found urls %s', len(page_results))
            results = results + page_results
            # extract info from this page
            n.click()
            self.sleep()
            logger.info('visiting next page')
            self.b.scroll_down_page()
            n = self.b.find(xpath='//button[@class="search-results__pagination-next-button"]', scroll=True)
            disabled = n.get_attribute('disabled')
            index = index + 1
        return results

    def __warm_up_page(self):
        self.b.scroll_down_page()
        self.b.scroll_up_page()

    def __goto_li_profile(self, sales_nav_url):
        self.b.get(sales_nav_url)
        self.sleep()
        # sometimes unlock profile button shows up.. click it to unlock
        # if re.search(r'OUT_OF_NETWORK', sales_nav_url):
        #     self.b.click(xpath='//button[@data-control-name="unlock"]')

        self.__warm_up_page()
        self.b.click(xpath='//button[contains(@class, "right-actions-overflow-menu-trigger")]')
        self.sleep(min=200, max=400)
        self.b.click(xpath='//div[@data-control-name="view_linkedin"]')
        self.sleep()
        # this is one weird thing.. linkedin.com opens in new tab so we need to switch to it
        self.b.driver.switch_to.window(self.b.driver.window_handles[1])
        self.__warm_up_page()
        self.sleep()

    def follow_contact(self, sales_nav_url):
        try:
            self.__goto_li_profile(sales_nav_url=sales_nav_url)
            self.b.click(xpath='//button/span[contains(text(), "More")]')
            self.sleep(min=200, max=400)
            self.b.click(xpath='//div[contains(@class, "pv-s-profile-actions--follow")]')
        except Exception as e:
            logger.exception('could not follow url %s', sales_nav_url)
        finally:
            self.b.close_windows()

    def connect_contact(self, sales_nav_url, message):
        try:
            self.__goto_li_profile(sales_nav_url=sales_nav_url)
            connected = False
            # sometimes there's a connect button and sometimes connect is in under More. First check if connect button exists
            try:

                self.b.click(xpath='//button[contains(@aria-label, "Connect with")]')
                connected = True
            except Exception as e:
                logger.error('did not find connect button will try more..')

            if not connected:
                self.b.click(xpath='//button/span[contains(text(), "More")]')
                self.sleep(min=200, max=400)
                self.b.click(xpath='//div[contains(@class, "pv-s-profile-actions--connect")]')

            if message:
                self.b.click(xpath='//button[contains(@aria-label, "Add a note")]')
                self.b.input(xpath='//textarea[@name="message"]', keys=message)
                self.b.click(xpath='//button[contains(@aria-label, "Done")]')
            else:
                self.b.click(xpath='//button[contains(@aria-label, "Send now")]')
        except Exception as e:
            logger.exception('could not connect url %s', sales_nav_url)
        finally:
            self.sleep()
            self.b.close_windows()


def random_greeting(name):
    greetings = [
        f'Hi {name}, thanks for connecting with me. You are awesome',
        f'It is a pleasure connecting with you, {name}',
        f'Thank you for accepting my LinkedIn invitation, {name}',
    ]
    index = random.randint(0, len(greetings)-1)
    return greetings[index]

def test_collect_contacts(saved_search_id):
    li = LinkedIn()
    li.login(username=os.getenv('LINKEDIN_USERNAME'), password=os.getenv('LINKEDIN_PASSWORD'))
    rows = li.extract_search_results(saved_search_id=saved_search_id)
    logger.info('search result urls = %s', len(rows))
    with open('/tmp/contacts.csv', 'w') as out:
        fieldnames = rows[0].keys()
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            logging.info('writing row %s', r)
            writer.writerow(r)

def read_contacts(filename):
    rows = []
    batches = set()
    with open(filename, 'r') as inp:
        reader = csv.DictReader(inp)
        rows = [ dict(r) for r in reader ]
    for r in rows:
        batches.add(r['batch'])
    if len(batches) > 1:
        logger.error('batch file has more than one batch id, please check the file')
        raise ValueError(f'batch file has multiple ids {batches}')
    if len(rows) > 200:
        logger.error('batch file is too large, cannot operate on more than 200 rows at a time')
        raise ValueError(f'batch file too large, has {len(rows)} rows')
    return rows

def test_follow_contacts(filename, batch):
    rows = read_contacts(filename=filename)
    li = LinkedIn()
    li.login(username=os.getenv('LINKEDIN_USERNAME'), password=os.getenv('LINKEDIN_PASSWORD'))
    for row in rows:
        url = row['sales_nav_url']
        logger.info('follow contact %s', row)
        li.follow_contact(sales_nav_url=url)

def test_connect_contacts(filename):
    rows = read_contacts(filename=filename)
    li = LinkedIn()
    li.login(username=os.getenv('LINKEDIN_USERNAME'), password=os.getenv('LINKEDIN_PASSWORD'))
    for row in rows:
        url = row['sales_nav_url']
        logger.info('connect contact %s', row)
        template = "Hi {}, I'm the founder of a startup (https://www.fylehq.com) that is building a new corporate card product. I'd be honored to connect with you and get your inputs to make sure we're solving the right problems."
        message = template.format(row['first_name'])
        li.connect_contact(sales_nav_url=url, message=message)

def split_names(input_filename, output_filename):
    inp = csv.DictReader(open(input_filename, 'r'))
    rows = [dict(row) for row in inp]
    for row in rows:
        row['full_name'] = (row['full_name'].split(',')[0]).lower().capitalize()
        words = row['full_name'].split(' ')
        row['first_name'] = words[0].lower().capitalize()
        row['last_name'] = words[-1].lower().capitalize() if len(words) > 1 else None
    out = csv.DictWriter(open(output_filename, 'w'), fieldnames=rows[0].keys())
    out.writeheader()
    for row in rows:
        out.writerow(row)

def pause(min=600, max=8000):
    s = (random.randint(min, max) * 1.0) / 1000.0
    time.sleep(s)

@click.group()
@click.option('--gsheets-credentials', default='gsheets.json', help='Credentials for gsheets access')
@click.option('--linkedin-username', default=lambda: os.environ.get('LINKEDIN_USERNAME', None), required=True, help='Linkedin username')
@click.option('--linkedin-password', default=lambda: os.environ.get('LINKEDIN_PASSWORD', None), required=True, help='Linkedin password')
@click.option('--spreadsheet-id', default=lambda: os.environ.get('GSHEETS_SPREADSHEET_ID', None), help='GSheets spreadsheet ID')
@click.pass_context
def cli(ctx, gsheets_credentials, linkedin_username, linkedin_password, spreadsheet_id):
    ctx.ensure_object(dict)
    logging.basicConfig(level=logging.INFO)
    sa = SpreadsheetApp(gsheets_credentials)
    spreadsheet = sa.open_by_id(spreadsheet_id=spreadsheet_id)
    salesnav = Table.get_table_from_sheet(
        spreadsheet=spreadsheet,
        sheet_name='salesnav'
    )
    sb = SimpleBrowser(browser='chrome', width=1536, height=864)
    sb.get('https://www.linkedin.com/login?fromSignIn=true&trk=guest_homepage-basic_nav-header-signin')
    sb.input(xpath='//input[@id="username"]', keys=linkedin_username)
    sb.input(xpath='//input[@id="password"]', keys=linkedin_password)
    pause()
    sb.click(xpath='//button[contains(text(), "Sign in")]')
    pause()
    ctx.obj['sb'] = sb
    ctx.obj['salesnav'] = salesnav

base_dt = parse('1900-01-01T00:00:00')

def dt_deserialize(v):
    """
    s - representation from googlesheets

    Returns
    datetime object
    """
    offset_ms = v * 24 * 60 * 60 * 1000
    return base_dt + timedelta(milliseconds=offset_ms)

def dt_serialize(dt):
    """
    dt - datetime object

    Returns
    floating point representation that can be used by table
    """
    td = (dt - base_dt)
    return td.days + (td.seconds * 1.0 / (60 * 60 * 24.0))

@cli.command()
@click.pass_context
def test(ctx):
    credentials = ctx.obj['credentials']
    spreadsheet_id = ctx.obj['spreadsheet_id']
    logger.info('test called with credentials %s', credentials)
    sa = SpreadsheetApp(credentials)
    spreadsheet = sa.open_by_id(spreadsheet_id=spreadsheet_id)
    table = Table.get_table_from_sheet(
        spreadsheet=spreadsheet,
        sheet_name='salesnav'
    )
    logger.info('header is %s', table.header)
    for row in table:
        logger.info('row %s', row.values)
        logger.info('name %s', row.get_field_value('first_name'))
        logger.info('invited_at %s', dt_deserialize(row.get_field_value('invited_at')))
    #test_collect_contacts(saved_search_id=10331)
    #test_connect_contacts(filename='/tmp/batch.csv')
    #time.sleep(10)

@cli.group()
@click.pass_context
def salesnav(ctx):
    pass

@salesnav.command('list')
@click.pass_context
def salesnav_list(ctx):
    salesnav = ctx.obj['salesnav']
    logger.info('header is %s', salesnav.header)
    for row in salesnav:
        logger.info('row %s', row.values)
        logger.info('name %s', row.get_field_value('first_name'))
        logger.info('invited_at %s', dt_deserialize(row.get_field_value('invited_at')))

def __salesnav_id_from_url(url):
    g = re.match(r'https://.*/people/([^,]*),.*', url)
    if not g:
        return None
    return g[1]

def __company_id_from_url(url):
    g = re.match(r'https://.*/company/(.*)', url)
    if not g:
        return None
    return g[1]

def __search_results_page_generator(sb):
    dls = sb.find_many(xpath='//section[@class="result-lockup"]//dl')
    for dl in dls:
        data = {}
        a = dl.find_element_by_xpath('./dt/a')
        data['full_name'] = a.text
        data['full_name'] = (data['full_name'].split(',')[0]).lower().capitalize()
        words = data['full_name'].split(' ')
        data['first_name'] = words[0].lower().capitalize()
        data['last_name'] = words[-1].lower().capitalize() if len(words) > 1 else None
        link = a.get_attribute('href')
        id = __salesnav_id_from_url(url=link)
        data['sales_nav_url'] = link
        data['id'] = id
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

def __search_results_generator(sb, search_id):
    sb.get(f'https://www.linkedin.com/sales/search/people?savedSearchId={search_id}')
    pause()
    sb.scroll_down_page()
    n = sb.find(xpath='//button[@class="search-results__pagination-next-button"]', scroll=True)
    disabled = n.get_attribute('disabled')
    index = 0
    results = []
    while not disabled:
        pause()
        search_results = __search_results_page_generator(sb=sb)
        for sr in search_results:
            sr['search_id'] = search_id
            yield sr
        n.click()
        pause()
        sb.scroll_down_page()
        n = sb.find(xpath='//button[@class="search-results__pagination-next-button"]', scroll=True)
        disabled = n.get_attribute('disabled')

@salesnav.command('search')
@click.pass_context
@click.option('--search-id', required=True, help='Saved search ID')
def salesnav_search(ctx, search_id):
    salesnav = ctx.obj['salesnav']
    sb = ctx.obj['sb']
    for sr in __search_results_generator(sb=sb, search_id=search_id):
        logger.info('adding sr %s', sr)
        salesnav.add_one(sr)
    salesnav.commit()

@salesnav.command('get_profiles')
@click.pass_context
def get_profiles(ctx):
    credentials = ctx.obj['credentials']
    logger.info('salesnav get_profiles called with credentials %s', credentials)

@cli.group()
@click.pass_context
def profiles(ctx):
    pass

@profiles.command('connect')
@click.pass_context
def profiles_connect(ctx):
    credentials = ctx.obj['credentials']
    logger.info('profiles connect called with credentials %s', credentials)
