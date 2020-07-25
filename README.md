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
python -m linkedin test
```

* Save search results to google sheet. Will skip out of network

```
python -m linkedin salesnav search --search-id=<search-id>
```

* Extract LinkedIn profiles from salesnav data

```
python -m linkedin salesnav get_profiles --batch-id=<batch-id>
```

* Connect with everybody in search result with templated message

```
python -m linkedin profiles connect --batch-id=<batch-id> --message-id=<message-id>
```

* To withdraw old invitations to connect
```
python -m linkedin withdraw
```

