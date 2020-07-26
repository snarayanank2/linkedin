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

def dt_deserialize(v):
    """
    s - representation from googlesheets

    Returns
    datetime object
    """
    return parse(v)

def dt_serialize(dt):
    """
    dt - datetime object

    Returns
    floating point representation that can be used by table
    """
    return dt.isoformat()

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
        # TODO: check if this person is already in the table, if so, skip
        criterias = [{ 'id': sr['id']}]
        items = salesnav.select(criterias)
        if len(items) > 0:
            logger.info('item already exists.. skipping %s', sr)
        else:
            logger.info('adding sr %s', sr)
            salesnav.add_one(sr)
            salesnav.commit()

def __connect_salesnav(sb, salesnav_url, note):
    sb.get(salesnav_url)
    sb.scroll_down_page()
    sb.scroll_up_page()
    sb.click(xpath='//button[contains(@class, "right-actions-overflow-menu-trigger")]')
    pause()
    sb.click(xpath='//div[@data-control-name="view_linkedin"]')
    pause()
    # this is one weird thing.. linkedin.com opens in new tab so we need to switch to it
    # TODO: move this functionality to simplebrowser
    sb.driver.switch_to.window(sb.driver.window_handles[1])
    profile_url = sb.get_current_url()
    sb.scroll_down_page()
    sb.scroll_up_page()
    connected = False
    # sometimes there's a connect button and sometimes connect is in under More. First check if connect button exists
    try:
        try:
            sb.click(xpath='//button[contains(@aria-label, "Connect with")]')
            connected = True
        except Exception as e:
            logger.error('did not find connect button will try more..')

        if not connected:
            try:
                sb.click(xpath='//button/span[contains(text(), "More")]')
                pause(min=200, max=400)
                sb.click(xpath='//div[contains(@class, "pv-s-profile-actions--connect")]//span[contains(text(),"Connect")]')
                connected = True
            except Exception as e:
                logger.error('could not connect.. failed')
                return profile_url, connected

        assert connected
        if note:
            sb.click(xpath='//button[contains(@aria-label, "Add a note")]')
            sb.input(xpath='//textarea[@name="message"]', keys=note)
            sb.click(xpath='//button[contains(@aria-label, "Done")]')
        else:
            sb.click(xpath='//button[contains(@aria-label, "Send now")]')
    except Exception as e:
        connected = False
        logger.exception('something unexpected happened at %s', salesnav_url)
        return profile_url, connected
    finally:
        pause()
        sb.close_windows()
    return profile_url, connected

@salesnav.command('connect')
@click.pass_context
@click.option('--batch-size', default=100, required=True, help='Number of people to connect with')
@click.option('--message', required=True, help='Need a message to include when connecting')
def salesnav_connect(ctx, batch_size, message):
    salesnav = ctx.obj['salesnav']
    sb = ctx.obj['sb']
    for row in salesnav:
        if row.get_field_value('invited_at') or row.get_field_value('failed_at'):
            logger.info('skipping row %s', row.get_field_value('id'))
            continue
        first_name = row.get_field_value('first_name')
        note = message.format(first_name=first_name)
        salesnav_url = row.get_field_value('salesnav_url')
        profile_url, connected = __connect_salesnav(sb=sb, salesnav_url=salesnav_url, note=note)
        row.set_field_value('note', note)
        row.set_field_value('profile_url', profile_url)
        if connected:
            row.set_field_value('invited_at', dt_serialize(datetime.now()))
        else:
            row.set_field_value('failed_at', dt_serialize(datetime.now()))
        salesnav.commit()
        batch_size = batch_size - 1
        if batch_size <= 0:
            break
    pause(min=4000, max=8000)


def __follow_salesnav(sb, salesnav_url):
    sb.get(salesnav_url)
    sb.click(xpath='//button[contains(@class, "right-actions-overflow-menu-trigger")]')
    pause(min=200, max=400)
    sb.click(xpath='//div[@data-control-name="view_linkedin"]')
    pause(min=500, max=1000)
    # this is one weird thing.. linkedin.com opens in new tab so we need to switch to it
    # TODO: move this functionality to simplebrowser
    sb.driver.switch_to.window(sb.driver.window_handles[1])
    profile_url = sb.get_current_url()
    followed = False
    # sometimes there's a connect button and sometimes connect is in under More. First check if connect button exists
    try:
        sb.click(xpath='//button/span[contains(text(), "More")]')
        pause(min=200, max=400)
        sb.click(xpath='//div[contains(@class, "pv-s-profile-actions--follow")]//span[contains(text(),"Follow")]')
        followed = True
    except Exception as e:
        logger.error('could not follow.. failed')
        return profile_url, followed
    finally:
        pause()
        sb.close_windows()
    return profile_url, followed

@salesnav.command('follow')
@click.pass_context
@click.option('--batch-size', default=100, required=True, help='Number of people to follow')
def salesnav_follow(ctx, batch_size):
    salesnav = ctx.obj['salesnav']
    sb = ctx.obj['sb']
    for row in salesnav:
        if row.get_field_value('followed_at') or row.get_field_value('failed_at'):
            logger.info('skipping row %s', row.get_field_value('id'))
            continue
        salesnav_url = row.get_field_value('salesnav_url')
        profile_url, followed = __follow_salesnav(sb=sb, salesnav_url=salesnav_url)
        row.set_field_value('profile_url', profile_url)
        if followed:
            row.set_field_value('followed_at', dt_serialize(datetime.now()))
        else:
            row.set_field_value('failed_at', dt_serialize(datetime.now()))
        salesnav.commit()
        batch_size = batch_size - 1
        if batch_size <= 0:
            break
    pause(min=4000, max=8000)

@cli.group()
@click.pass_context
def invitations(ctx):
    pass

@invitations.command('withdraw')
@click.pass_context
@click.option('--start-page', default=4, required=True, help='Start withdrawing invitations from this page')
def invitations_withdraw(ctx, start_page):
    sb = ctx.obj['sb']
    sb.get(f'https://www.linkedin.com/mynetwork/invitation-manager/sent/?invitationType=&page={start_page}')
    while True:
        pause()
        lis = sb.find_many(xpath='//li[contains(@class, "invitation-card")]')
        liw = None
        for li in lis:
            t = li.find_element_by_xpath('.//time').text
            if 'week' in t:
                liw = li
                break
        if liw:
            logger.info('withdrawing invitation %s', liw.text)
            b = liw.find_element_by_xpath('.//button[contains(@data-control-name, "withdraw_single")]')
            b.click()
            pause()
            sb.click(xpath='//button[contains(@class, "artdeco-button--primary")]')
            pause()
        else:
            n = sb.find(xpath='//button[contains(@class, "artdeco-pagination__button--next")]')
            if n.get_attribute('disabled'):
                break
            else:
                n.click()

    # def follow_contact(self, sales_nav_url):
    #     try:
    #         self.__goto_li_profile(sales_nav_url=sales_nav_url)
    #         self.b.click(xpath='//button/span[contains(text(), "More")]')
    #         self.sleep(min=200, max=400)
    #         self.b.click(xpath='//div[contains(@class, "pv-s-profile-actions--follow")]')
    #     except Exception as e:
    #         logger.exception('could not follow url %s', sales_nav_url)
    #     finally:
    #         self.b.close_windows()

    # def send_message(self, url, message):
    #     self.b.get(url)
    #     self.b.click(xpath='//a[text()="Message"]')
    #     self.b.input(xpath='//div[@aria-label="Write a message…"]', keys=message)
    #     self.b.click(xpath='//button[text()="Send"]')
    #     self.sleep()
    #     self.b.click(xpath='//button[@data-control-name="overlay.close_conversation_window"]')
    #     self.sleep()
