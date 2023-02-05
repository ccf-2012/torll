import os
import json


def loadSiteConfig():
    site_json_file = os.path.join(os.path.dirname(__file__), 'siteconfig.json')
    f = open(site_json_file)

    site_config = json.load(f)
    f.close()
    return site_config