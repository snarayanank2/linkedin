# linkedin

This repository contains code to automate common tasks in LinkedIn. You will need sales navigator subscription to use this tool. This is under active development and is not ready for general use

# Disclaimer

LinkedIn will ban your account if you abuse this tool and do too many activities. We are not liable for any misuse of this tool. Use it wisely.

# Installation

## Create virtualenv and install requirements using:

```
virtualenv venv --python=python3.7
source venv/bin/activate
pip install -r requirements.txt
```

Next, you'll need to setup at webdriver for Chrome

## Setup Chrome WebDriver

Download and install Chrome webdriver from chromium site [here](https://chromedriver.chromium.org/downloads)

## Google Drive API credentials

Go to Google Cloud Console [here](https://console.cloud.google.com/)

Create or choose a project

Enable Google Sheets API in the project

Create credentials

Create service account and download json file

Copy the service account email

Create and download json keys and name it gsheets.json and save it in current directory

Do not share these credentials

# Usage

* Run a test to check connectivity to data sheet

```
linkedin test
```

* Save search results to google sheet. Will skip out of network

```
linkedin salesnav search --url=<search-url> --start-page=2 --num-pages=4
```

* Follow with LinkedIn profiles from salesnav data

```
linkedin salesnav follow --batch-size=100
```

* Connect with LinkedIn profiles from salesnav data

```
linkedin salesnav connect --batch-size=100 --message='Hi {first_name}, I would like to connect with you'
```

* Save search results on your network based on search url
```
linkedin network search --url=<search-url> --start-page=2 --num-pages=4
```

* Follow people in your network (TODO)

```
linkedin network follow --batch-size=100
```

* Connect with people in your network (2nd degree only)

```
linkedin network connect --batch-size=100 --message='Hi {first_name}, I would like to connect with you. Both of us know {common_name}'
```

* To withdraw old invitations to connect (TODO: This is currently broken)
```
linkedin invitations withdraw
```
