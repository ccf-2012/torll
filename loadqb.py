import argparse
import qbittorrentapi
import urllib.parse
from humanbytes import HumanBytes
import myconfig
import re
import os
import requests


def printTorrent(torrent, trackMessage=''):
    print(f'{torrent.hash[:6]}: \033[32m{torrent.name}\033[0m' +
          f' ({HumanBytes.format(torrent.total_size, True)})' +
          f' - \033[31m {abbrevTracker(torrent.tracker)}\033[0m' +
          f'    \033[34m  {trackMessage} \033[0m')


def abbrevTracker(trackerstr):
    hostnameList = urllib.parse.urlparse(trackerstr).netloc.split('.')
    if len(hostnameList) == 2:
        abbrev = hostnameList[0]
    elif len(hostnameList) == 3:
        abbrev = hostnameList[1]
    else:
        abbrev = ''
    return abbrev


def pathHasSiteId(savepath):
    lastfn = os.path.basename(os.path.normpath(savepath))
    if re.search(r'(\w+)[_-](\d+)(_(tt\d+))?', lastfn, re.I):
        return True
    return False


def postToTorcp(hashstr):
    url = f'http://{myconfig.CONFIG.qbServer}:5006/api/torcp2'

    r = requests.post(url, data={'torhash': hashstr}, auth=(
        myconfig.CONFIG.basicAuthUser, myconfig.CONFIG.basicAuthPass))

    return r


def iterSiteIdPath():
    qbClient = qbittorrentapi.Client(
        host=myconfig.CONFIG.qbServer, port=myconfig.CONFIG.qbPort, username=myconfig.CONFIG.qbUser, password=myconfig.CONFIG.qbPass)

    try:
        qbClient.auth_log_in()
    except qbittorrentapi.LoginFailed as e:
        print(e)
        return False
    except:
        return False

    if not qbClient:
        return False

    for torrent in qbClient.torrents_info(sort='added_on', reverse=False):
        if pathHasSiteId(torrent.save_path):
            printTorrent(torrent)
            postToTorcp(torrent.hash)


def loadArgs():
    global ARGS
    parser = argparse.ArgumentParser(description='a qbittorrent utils')
    parser.add_argument('-C', '--config', help='config file.')

    ARGS = parser.parse_args()
    if not ARGS.config:
        ARGS.config = os.path.join(os.path.dirname(__file__), 'config.ini')


def main():
    loadArgs()
    myconfig.readConfig(ARGS.config)
    iterSiteIdPath()


if __name__ == '__main__':
    main()
