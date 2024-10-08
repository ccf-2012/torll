from app import queryByHash
from plexapi.server import PlexServer
from myconfig import CONFIG, readConfig
import argparse
import os
import sys
import time
from loguru import logger


MAX_RETRY = 5

# sectionMatchList = [('TV/cn', '中文剧集'), ('TV/ja', '日韩剧集'), ('TV/ko', '日韩剧集'), ('TV/other', '剧集'), ('Movie/cn', '中文电影'), ('Movie', '电影')]

def notifyPlex(hash):
    plexSrv = PlexServer(CONFIG.plexServer, CONFIG.plexToken)
    mediaItem = queryByHash(hash)

    if mediaItem and plexSrv:
        mediaPath = mediaItem.location.strip()
        libtup = next((g for g in CONFIG.plexSectionList if mediaPath.startswith(g[1])), None)
        if libtup:
            try:
                lib = plexSrv.library.section(libtup[0])
            except:
                logger.info("Plex: no library names: " + libtup[0])
        else:
            logger.info("Plex: Can't match any library: " + mediaPath)
            return 

        if lib:
            for n in range(MAX_RETRY):
                try:
                    logger.info(mediaPath)
                    lib.update(path=os.path.join(CONFIG.plexRootDir, mediaPath))
                    break
                except Exception as e:
                    if n < MAX_RETRY:
                        logger.info('Fail: lib.update' + str(e))
                        logger.info('retry %d time.' % (n+1))
                        time.sleep(30)
                    else:
                        logger.info('Error: MAX_RETRY(%d) times' % (MAX_RETRY))
                        os._exit(1)
                
        else:
            logger.info("Can't find the library section: " + ARGS.library)
    else:
        logger.info("Info hash not found/Plex server not connected. ")    


def loadArgs():
    parser = argparse.ArgumentParser(description='Notify plex server to add a file/folder.')
    parser.add_argument('-I', '--info-hash', type=str, required=True, help='info hash of the torrent.')
    parser.add_argument('-C', '--config', help='config file.')

    global ARGS
    ARGS = parser.parse_args()
    if not ARGS.config:
        ARGS.config = os.path.join(os.path.dirname(__file__), 'config.ini')


def main():
    loadArgs()
    readConfig(ARGS.config)
    notifyPlex(ARGS.info_hash)


if __name__ == '__main__':
    logger.remove()
    formatstr = "{time:YYYY-MM-DD HH:mm:ss} | <level>{level: <8}</level> | - <level>{message}</level>"
    logger.add(sys.stdout, format=formatstr)

    main()
