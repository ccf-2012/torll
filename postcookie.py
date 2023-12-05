import requests
import sys
from loguru import logger
import siteconfig

TORLL_SERVER = 'http://ol.torll.com:5006'
TORLL_USER = 'admin'
TORLL_PASS = 'C4GssEIYnZktPsQm'

if __name__ == '__main__':
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | <level>{level: <8}</level> | - <level>{message}</level>")

    for sitehost in siteconfig.PT_SITES:
        # siteconfig.loadSiteIcon(sitehost)
        cookiestr = siteconfig.loadSavedCookies(sitehost)
        data = {
            'site': sitehost['site'],
            'auto_update': False,
            'update_interval': 30,
            'cookie': cookiestr,
            'newtorlink' : ''
        }
        logger.info(f"Post to {sitehost['site']}")
        serverUrl = f"{TORLL_SERVER}/api/sitesetting"
        response = requests.post(serverUrl, json=data, auth=(TORLL_USER, TORLL_PASS), headers={"Content-Type":"application/json"})
        logger.info(response)






