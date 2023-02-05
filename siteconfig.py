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
        
    return site_config