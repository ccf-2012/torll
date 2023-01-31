
import qbittorrentapi
import myconfig


def getTorrentByHash(torhash):
    qbClient = qbittorrentapi.Client(
        host=myconfig.CONFIG.qbServer, port=myconfig.CONFIG.qbPort, username=myconfig.CONFIG.qbUser, password=myconfig.CONFIG.qbPass)

    try:
        qbClient.auth_log_in()
    except qbittorrentapi.LoginFailed as e:
        print(e)
        return '', '', '', '', ''
    except:
        return '', '', '', '', ''

    if not qbClient:
        return '', '', '', '', ''

    try:
        # torrent = qbClient.torrents_properties(torrent_hash=torhash)
        torrent = qbClient.torrents_trackers(torrent_hash=torhash)
    except:
        print('Torrent hash NOT found.')
        return '', '', '', '', ''

    torlist = qbClient.torrents_info(torrent_hashes=torhash, limit=3)
    if len(torlist) != 1:
        print('Torrent hash NOT found.')
        return '', '', '', '', ''

    torrent = torlist[0]
    return torrent.content_path, torrent.hash, str(torrent.size), torrent.tags, torrent.save_path


def getAutoRunProgram():
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

    prefs = qbClient.app_preferences()
    autoprog = prefs["autorun_program"]
    return autoprog



def setAutoRunProgram(prog):
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

    qbClient.app_set_preferences(prefs={"autorun_enabled": True, "autorun_program": prog})
    return True


def addQbitWithTag(downlink, imdbtag, siteIdStr=None):
    qbClient = qbittorrentapi.Client(
        host=myconfig.CONFIG.qbServer, port=myconfig.CONFIG.qbPort, username=myconfig.CONFIG.qbUser, password=myconfig.CONFIG.qbPass)

    try:
        qbClient.auth_log_in()
    except qbittorrentapi.LoginFailed as e:
        print(e)
        return False

    if not qbClient:
        return False

    try:
        # curr_added_on = time.time()
        if siteIdStr:
            result = qbClient.torrents_add(
                urls=downlink,
                save_path=siteIdStr,
                # download_path=download_location,
                # category=timestamp,
                tags=[imdbtag],
                use_auto_torrent_management=False)
        else:
            result = qbClient.torrents_add(
                urls=downlink,
                tags=[imdbtag],
                use_auto_torrent_management=False)
        # breakpoint()
        if 'OK' in result.upper():
            pass
            # print('   >> Torrent added.')
        else:
            print('   >> Torrent not added! something wrong with qb api ...')
    except Exception as e:
        print('   >> Torrent not added! Exception: '+str(e))
        return False

    return True
