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
    li = LinkedIn()
    li.login(username=linkedin_username, password=linkedin_password)
    ctx.obj['li'] = li
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


@salesnav.command('search')
@click.pass_context
@click.option('--url', required=True, help='Search url')
@click.option('--start-page', default=1, required=True, help='Start page')
@click.option('--num-pages', default=1, required=True, help='Number of pages to extract from')
def salesnav_search(ctx, url, start_page, num_pages):
    salesnav = ctx.obj['salesnav']
    li = ctx.obj['li']
    for sr in li.salesnav_search(url=url, start_page=start_page, num_pages=num_pages):
        # TODO: check if this person is already in the table, if so, skip
        criterias = [{ 'salesnav_url': sr['salesnav_url']}]
        items = salesnav.select(criterias)
        if len(items) > 0:
            logger.info('item already exists.. skipping %s', sr['full_name'])
        else:
            logger.info('adding sr %s', sr['full_name'])
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
            logger.info('skipping row %s', row.get_field_value('full_name'))
            continue
        else:
            logger.info('processing %s', row.get_field_value('full_name'))

        first_name = row.get_field_value('first_name')
        note = message.format(first_name=first_name)
        salesnav_url = row.get_field_value('salesnav_url')
        row.set_field_value('note', note)
        try:
            res = li.salesnav_connect(salesnav_url=salesnav_url, note=note)
            row.set_field_value('profile_url', res.get('profile_url', None))
            row.set_field_value('common_name', res.get('common_name', None))
            row.set_field_value('degree', res.get('degree', None))
            row.set_field_value('connect_status', res.get('connect_status', None))
            row.set_field_value('invited_at', dt_serialize(datetime.now()))
        except Exception:
            row.set_field_value('invite_failed_at', dt_serialize(datetime.now()))
            logger.exception('connect failed for %s', row.get_field_value('full_name'))

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
            logger.info('skipping row %s', row.get_field_value('full_name'))
            continue
        else:
            logger.info('processing %s ', row.get_field_value('full_name'))

        salesnav_url = row.get_field_value('salesnav_url')

        try:
            res = li.salesnav_follow(salesnav_url=salesnav_url)
            row.set_field_value('profile_url', res.get('profile_url', None))
            row.set_field_value('common_name', res.get('common_name', None))
            row.set_field_value('degree', res.get('degree', None))
            row.set_field_value('follow_status', res.get('follow_status', None))
            row.set_field_value('followed_at', dt_serialize(datetime.now()))
        except Exception:
            row.set_field_value('follow_failed_at', dt_serialize(datetime.now()))
            logger.exception('follow failed for %s', row.get_field_value('full_name'))

        salesnav.commit()
        batch_size = batch_size - 1
        if batch_size <= 0:
            break
        pause(min=600, max=2000)
    pause(min=4000, max=6000)

@cli.group()
@click.pass_context
def invitations(ctx):
    pass

@invitations.command('withdraw')
@click.pass_context
@click.option('--page', default=4, required=True, help='Withdraw all invitations in page')
def invitations_withdraw(ctx, page):
    li = ctx.obj['li']
    li.invitations_withdraw(page=page)
    pause(min=4000, max=6000)

