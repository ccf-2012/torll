import requests
import sys
from loguru import logger
import siteconfig

TORLL_SERVER = 'http://127.0.0.1:5006'
TORLL_USER = 'admin'
TORLL_PASS = 'server_pass'

if __name__ == '__main__':
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | <level>{level: <8}</level> | - <level>{message}</level>")

    for sitehost in siteconfig.PT_SITES:
        # siteconfig.loadSiteIcon(sitehost)
        cookiestr = siteconfig.loadSavedCookies(sitehost)
        data = {
            'site': sitehost['site'],
            'autoupdate': False,
            'cookie': cookiestr,
            'newtorlink' : ''
        }
        logger.info(f"Posting {sitehost['site']}")
        serverUrl = f"{TORLL_SERVER}/api/sitesetting"
        response = requests.post(serverUrl, json=data, auth=(TORLL_USER, TORLL_PASS), headers={"Content-Type":"application/json"})
        logger.info(response)






