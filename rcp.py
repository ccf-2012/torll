from app import TorcpItemDBObj, TorcpItemCallbackObj, initDatabase
import os
from torcp.torcp import Torcp
from myconfig import readConfig, CONFIG
import argparse
import re
import qbfunc
import logging

logger = logging.getLogger(__name__)


def extractIMDbFromTag(tagstr):
    tagList = []
    if tagstr:
        tagList = tagstr.split(',')
    imdbtag = next((x for x in tagList if x.startswith('tt')), '')
    return imdbtag


def parseSiteId(siteidStr, torimdb):
    site = ''
    siteid = ''
    m = re.search(r'(\w+)[_-](\d+)(_(tt\d+))?', siteidStr, re.I)
    if m:
        site = m[1]
        siteid = m[2]
        if not torimdb and m[4]:
            torimdb = m[4]
    return site, siteid, torimdb


def tryint(instr):
    try:
        string_int = int(instr)
    except ValueError:
        string_int = 0
    return string_int


def getSiteIdDirName(pathStr, savepath):
    npath = os.path.normpath(pathStr.strip())
    siteIdFolder = os.path.basename(os.path.normpath(savepath))
    relativePath = os.path.relpath(npath, savepath)
    l = relativePath.split(os.path.sep)
    torRootFolder = os.path.join(savepath, l[0]) if len(l) > 0 else npath
    return torRootFolder, siteIdFolder


def callNotifyPlex(hash):
    if CONFIG.plexServer and CONFIG.plexToken:
        import notify_plex
        notify_plex.notifyPlex(hash)


def runTorcpMove(sourceDir, targetDir, torimdb=None, tmdbcatidstr=None):
    if sourceDir:
        if not os.path.exists(sourceDir):
            logger.warning('File/Dir not exists: ' + sourceDir)
            return "", '', None
        # torimdb = extractIMDbFromTag(tortag)
        # rootdir, site_id_imdb = getSiteIdDirName(sourceDir, savepath)

        # site, siteid, torimdb = parseSiteId(site_id_imdb, imdbstr)
        # if insertHashDir:
        #     targetDir = os.path.join(CONFIG.linkDir, torhash)
        # else:
        #     targetDir = CONFIG.linkDir
        argv = [sourceDir, "-d", targetDir, "-s",
                "--tmdb-api-key", CONFIG.tmdb_api_key,
                "--tmdb-lang", CONFIG.tmdbLang,
                "--make-log",
                CONFIG.bracket,
                "-e", "srt",
                "--extract-bdmv",
                "--tmdb-origin-name"]
        if CONFIG.lang:
            argv += ["--lang", CONFIG.lang]
        if CONFIG.genre:
            argv += ["--genre", CONFIG.genre]
        if CONFIG.bracket == '--emby-bracket':
            argv += ["--filename-emby-bracket"]
        if torimdb:
            argv += ["--imdbid", torimdb]
        if tmdbcatidstr:
            argv += ["--tmdbid", tmdbcatidstr]
        argv += ["--move-run"]

        # print(argv)
        eo = TorcpItemCallbackObj()
        o = Torcp()
        o.main(argv, eo)
        return eo.targetDir, eo.tmdbTitle, eo.tmdbParser
    return '', '', None


def runTorcp(torpath, torhash, torsize, tortag, savepath, insertHashDir, tmdbcatidstr=None):
    if (CONFIG.dockerFrom != CONFIG.dockerTo):
        if torpath.startswith(CONFIG.dockerFrom) and savepath.startswith(CONFIG.dockerFrom):
            torpath = torpath.replace(
                CONFIG.dockerFrom, CONFIG.dockerTo, 1)
            savepath = savepath.replace(
                CONFIG.dockerFrom, CONFIG.dockerTo, 1)

    if torpath and torhash:
        if not os.path.exists(torpath):
            logger.warning('File/Dir not exists: ' + torpath)
            return 402
        logger.info("torpath: %s, torhash: %s, torsize: %s, tortag: %s, savepath: %s" %
            (torpath, torhash, torsize, tortag, savepath))
        torimdb = extractIMDbFromTag(tortag)
        rootdir, site_id_imdb = getSiteIdDirName(torpath, savepath)

        site, siteid, torimdb = parseSiteId(site_id_imdb, torimdb)
        if insertHashDir:
            targetDir = os.path.join(CONFIG.linkDir, torhash)
        else:
            targetDir = CONFIG.linkDir
        argv = [rootdir, "-d", targetDir, "-s",
                "--tmdb-api-key", CONFIG.tmdb_api_key,
                "--tmdb-lang", CONFIG.tmdbLang,
                "--make-log",
                CONFIG.bracket,
                "-e", "srt",
                "--extract-bdmv",
                "--tmdb-origin-name"]
        if CONFIG.lang:
            argv += ["--lang", CONFIG.lang]
        if CONFIG.genre:
            argv += ["--genre", CONFIG.genre]
        if CONFIG.bracket == '--emby-bracket':
            argv += ["--filename-emby-bracket"]
        if torimdb:
            argv += ["--imdbid", torimdb]
        if tmdbcatidstr:
            argv += ["--tmdbid", tmdbcatidstr]

        # print(argv)
        if not torsize:
            torsize = '0'
        eo = TorcpItemDBObj(site, siteid, torimdb,
                            torhash.strip(), tryint(torsize.strip()))
        o = Torcp()
        o.main(argv, eo)

        if CONFIG.notifyPlex:
            logger.info('callNotifyPlex')
            callNotifyPlex(torhash)

        return 200
    return 401


def torcpByHash(torhash):
    if torhash:
        torpath, torhash2, torsize, tortag, savepath = qbfunc.getTorrentByHash(torhash)
        r = runTorcp(torpath, torhash2, torsize, tortag,
                     savepath, insertHashDir=ARGS.hash_dir, tmdbcatidstr=ARGS.tmdbcatid)
        return r
    else:
        print("set -I arg")
        return 403


def loadArgs():
    parser = argparse.ArgumentParser(
        description='wrapper to TORCP to save log in sqlite db.')
    parser.add_argument('-F', '--full-path', help='full torrent save path.')
    parser.add_argument('-I', '--info-hash', help='info hash of the torrent.')
    parser.add_argument('-D', '--save-path', help='qbittorrent save path.')
    parser.add_argument('-G', '--tag', help='tag of the torrent.')
    parser.add_argument('-Z', '--size', help='size of the torrent.')
    parser.add_argument('--hash-dir', action='store_true', help='create hash dir.') 
    parser.add_argument('--tmdbcatid', help='specify TMDb as tv-12345/m-12345.')
    parser.add_argument('-C', '--config', help='config file.')

    global ARGS
    ARGS = parser.parse_args()
    if not ARGS.config:
        ARGS.config = os.path.join(os.path.dirname(__file__), 'config.ini')


def main():
    loadArgs()
    initDatabase()
    readConfig(ARGS.config)
    if ARGS.full_path and ARGS.save_path:
        runTorcp(ARGS.full_path, ARGS.info_hash, ARGS.size,
                 ARGS.tag, ARGS.save_path, 
                 insertHashDir=ARGS.hash_dir, tmdbcatidstr=ARGS.tmdbcatid)
    else:
        torcpByHash(ARGS.info_hash)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,  format='%(asctime)s %(levelname)s %(funcName)s %(message)s')
    main()
