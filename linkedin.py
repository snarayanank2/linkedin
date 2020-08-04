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
from sdk import LinkedIn, pause

logger = logging.getLogger(__name__)


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
    network = Table.get_table_from_sheet(
        spreadsheet=spreadsheet,
        sheet_name='network'
    )
    li = LinkedIn()
    li.login(username=linkedin_username, password=linkedin_password)
    ctx.obj['li'] = li
    ctx.obj['salesnav'] = salesnav
    ctx.obj['network'] = network

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


@salesnav.command('search')
@click.pass_context
@click.option('--url', required=True, help='Search url')
@click.option('--start-page', required=True, help='Start page')
@click.option('--num-pages', default=1, required=True, help='Number of pages to extract from')
def salesnav_search(ctx, url, start_page, num_pages):
    salesnav = ctx.obj['salesnav']
    li = ctx.obj['li']
    for sr in li.salesnav_search(url=url, start_page=start_page, num_pages=num_pages):
        # TODO: check if this person is already in the table, if so, skip
        criterias = [{ 'salesnav_url': sr['salesnav_url']}]
        items = salesnav.select(criterias)
        if len(items) > 0:
            logger.info('item already exists.. skipping %s', sr)
        else:
            logger.info('adding sr %s', sr)
            salesnav.add_one(sr)
            salesnav.commit()


@salesnav.command('connect')
@click.pass_context
@click.option('--batch-size', default=100, required=True, help='Number of people to connect with')
@click.option('--message', required=True, help='Need a message to include when connecting')
def salesnav_connect(ctx, batch_size, message):
    salesnav = ctx.obj['salesnav']
    li = ctx.obj['li']
    for row in salesnav:
        if row.get_field_value('invited_at') or row.get_field_value('invite_failed_at'):
            logger.info('skipping row %s', row.get_field_value('id'))
            continue
        else:
            logger.info('processing %s %s', row.get_field_value('id'), row.get_field_value('full_name'))

        first_name = row.get_field_value('first_name')
        note = message.format(first_name=first_name)
        salesnav_url = row.get_field_value('salesnav_url')
        connected = False
        profile_url = None
        try:
            res = li.salesnav_connect(salesnav_url=salesnav_url, note=note)
            profile_url = res['profile_url']
            connected = True
        except Exception:
            logger.info('skipping %s', first_name)

        row.set_field_value('note', note)
        row.set_field_value('profile_url', profile_url)
        if connected:
            row.set_field_value('invited_at', dt_serialize(datetime.now()))
        else:
            row.set_field_value('invite_failed_at', dt_serialize(datetime.now()))
        salesnav.commit()
        batch_size = batch_size - 1
        if batch_size <= 0:
            break
    pause(min=4000, max=8000)


@salesnav.command('follow')
@click.pass_context
@click.option('--batch-size', default=100, required=True, help='Number of people to follow')
def salesnav_follow(ctx, batch_size):
    salesnav = ctx.obj['salesnav']
    li = ctx.obj['li']
    for row in salesnav:
        if row.get_field_value('followed_at') or row.get_field_value('follow_failed_at'):
            logger.info('skipping row %s', row.get_field_value('id'))
            continue
        else:
            logger.info('processing %s %s', row.get_field_value('id'), row.get_field_value('full_name'))

        salesnav_url = row.get_field_value('salesnav_url')

        followed = False
        profile_url = None
        try:
            res = li.salesnav_follow(salesnav_url=salesnav_url)
            profile_url = res['profile_url']
            followed = True
        except Exception:
            logger.info('skipping %s', first_name)


        row.set_field_value('profile_url', profile_url)

        if followed:
            row.set_field_value('followed_at', dt_serialize(datetime.now()))
        else:
            row.set_field_value('follow_failed_at', dt_serialize(datetime.now()))
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
    # TODO: this doesnt work
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

    # def send_message(self, url, message):
    #     self.b.get(url)
    #     self.b.click(xpath='//a[text()="Message"]')
    #     self.b.input(xpath='//div[@aria-label="Write a message…"]', keys=message)
    #     self.b.click(xpath='//button[text()="Send"]')
    #     self.sleep()
    #     self.b.click(xpath='//button[@data-control-name="overlay.close_conversation_window"]')
    #     self.sleep()

@cli.group()
@click.pass_context
def network(ctx):
    pass

@network.command('search')
@click.pass_context
@click.option('--url', required=True, help='Search url')
@click.option('--start-page', default=1, required=True, help='Start page')
@click.option('--num-pages', default=1, required=True, help='Number of pages to extract from')
def network_search(ctx, url, start_page, num_pages):
    network = ctx.obj['network']
    li = ctx.obj['li']
    for sr in li.network_search(url=url, start_page=start_page, num_pages=num_pages):
        # TODO: check if this person is already in the table, if so, skip
        criterias = [{ 'profile_url': sr['profile_url']}]
        items = network.select(criterias)
        if len(items) > 0:
            logger.info('item already exists.. updating action %s', sr['full_name'])
            items[0].set_field_value('action', sr['action'])
            items[0].set_field_value('degree', sr['degree'])
            network.commit()
        else:
            logger.info('adding sr %s', sr)
            network.add_one(sr)
            network.commit()


@network.command('connect')
@click.pass_context
@click.option('--batch-size', default=100, required=True, help='Number of people to connect with')
@click.option('--message', required=True, help='Need a message to include when connecting')
def network_connect(ctx, batch_size, message):
    network = ctx.obj['network']
    li = ctx.obj['li']
    for row in network:
        if row.get_field_value('action') == 'Invite Sent' or row.get_field_value('degree') != '2nd' or row.get_field_value('invited_at') or row.get_field_value('invite_failed_at'):
            logger.info('skipping row %s', row.get_field_value('full_name'))
            continue
        else:
            logger.info('processing %s', row.get_field_value('full_name'))

        first_name = row.get_field_value('first_name')
        common_name = row.get_field_value('common_name')
        assert first_name and common_name, 'names are missing, aborting'
        note = message.format(first_name=first_name, common_name=common_name)
        profile_url = row.get_field_value('profile_url')
        connected = False
        try:
            connected = li.profile_connect(profile_url=profile_url, note=note)
        except Exception:
            logger.exception('couldnt connect')
        row.set_field_value('note', note)
        if connected:
            row.set_field_value('invited_at', dt_serialize(datetime.now()))
        else:
            row.set_field_value('invite_failed_at', dt_serialize(datetime.now()))
        network.commit()
        batch_size = batch_size - 1
        if batch_size <= 0:
            break
    pause(min=4000, max=8000)
