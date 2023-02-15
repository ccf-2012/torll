import os
import json


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

