import os
import json
import requests
import browser_cookie3
import sys
from loguru import logger
from urllib.parse import urlparse


def loadSiteConfig():
    site_json_file = os.path.join(os.path.dirname(__file__), 'siteconfig.json')
    try:
        f = open(site_json_file)
        site_config = json.load(f)
    except:
        logger.error('Can NOT found file: siteconfig.json')
        return []
    f.close()
    
    return site_config["sites"] if site_config else []


# 图标缓存目录
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'static', "icon_cache")
PT_SITES = loadSiteConfig()


def getSiteIcoPath(sitename):
    return '/static/' + f"{sitename}.ico"

def fetchSiteIcon(siteid):
    r = False
    siteJson = getSiteConfig(siteid)
    if siteJson:
        logger.info(f"fetch site ico : {siteJson['site']}")
        r = loadSiteIcon(siteJson)
    return r

def loadSiteIcon(siteJson):
    # cursite = getSiteConfig(sitehost)
    icourl = siteJson['baseurl'] + 'favicon.ico'
    # 创建图标缓存目录
    r = False
    os.makedirs(CACHE_DIR, exist_ok=True)
    icon_path = os.path.join(CACHE_DIR, f"{siteJson['site']}.ico")
    if not os.path.exists(icon_path):
        response = requests.get(icourl, timeout=5)
        if response:
            logger.info(f"success, save ico in: {icon_path}")
            with open(icon_path, "wb") as f:
                f.write(response.content)
                r = True
        else:
            r = False
    else:
        r = True
        logger.info(f"exists ico : {icon_path}")
    return r   

def loadSavedCookies(siteJson):
    cookieStr = ''
    # siteJson = getSiteConfig(siteid)
    if siteJson:
        domain = urlparse(siteJson["baseurl"]).netloc
        cookieJar = browser_cookie3.edge(domain_name=domain)
        cookieDict = requests.utils.dict_from_cookiejar(cookieJar)
        cookieDict.pop('filterParam', None)
        pairs = ['%s=%s' % (name, value) for (name, value) in cookieDict.items()]
        cookieStr =  ';'.join(pairs)
        logger.debug(f"Load cookie for : {domain}")
    # logger.debug(cookieStr)
    return cookieStr


def getSiteConfig(sitename):
    cursite = next((x for x in PT_SITES if x["site"] == sitename), None)
    return cursite

if __name__ == '__main__':
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | <level>{level: <8}</level> | - <level>{message}</level>")

    # PT_SITES = loadSiteConfig()
    # for sitehost in PT_SITES:
    #     loadSiteIcon(sitehost)
