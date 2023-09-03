import os
import json
import requests


# 图标缓存目录
cache_dir = os.path.join(os.path.dirname(__file__), 'static', "icon_cache")

def getSiteIcoPath(sitename):
    return '/static/' + f"{sitename}.ico"


def loadSiteIcon(sitehost):
    # cursite = getSiteConfig(sitehost)
    icourl = sitehost['baseurl'] + 'favicon.ico'
    # 创建图标缓存目录
    os.makedirs(cache_dir, exist_ok=True)
    icon_path = os.path.join(cache_dir, f"{sitehost['site']}.ico")
    if not os.path.exists(icon_path):
        response = requests.get(icourl, timeout=5)
        with open(icon_path, "wb") as f:
            f.write(response.content)


def loadSiteConfig():
    site_json_file = os.path.join(os.path.dirname(__file__), 'siteconfig.json')
    try:
        f = open(site_json_file)
        site_config = json.load(f)
    except:
        return []
    f.close()
    
    return site_config["sites"] if site_config else []


PT_SITES = loadSiteConfig()

def getSiteConfig(sitename):
    cursite = next((x for x in PT_SITES if x["site"] == sitename), None)
    return cursite

if __name__ == '__main__':
    # PT_SITES = loadSiteConfig()
    for sitehost in PT_SITES:
        loadSiteIcon(sitehost)
