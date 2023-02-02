

from myconfig import readConfig, CONFIG
# from app import TorMediaItem
from emby_client import EmbyClient
import re
import os
from torcp.tmdbparser import TMDbNameParser
import argparse

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from plexapi.server import PlexServer
import time



app = Flask(__name__)
app.config[
    'SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
db = SQLAlchemy(app)
# db.init_app(app)

MAX_RETRY = 5


class TorMediaItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    addedon = db.Column(db.DateTime, default=datetime.now)
    torname = db.Column(db.String(256), index=True)
    title = db.Column(db.String(256), index=True)
    torsite = db.Column(db.String(64))
    torsiteid = db.Column(db.Integer)
    torsitecat = db.Column(db.String(20))
    torimdb = db.Column(db.String(20), index=True)
    torhash = db.Column(db.String(120))
    torsize = db.Column(db.Integer)
    tmdbid = db.Column(db.Integer)
    tmdbcat = db.Column(db.String(20))
    location = db.Column(db.String(256))
    plexid = db.Column(db.String(120))


def tryFloat(fstr):
    try:
        f = float(fstr)
    except:
        f = 0.0
    return f


def isMediaExt(path):
    fn, ext = os.path.splitext(path)
    return ext in ['.mkv', '.mp4', '.ts', '.m2ts']


def loadEmbyLibrary():

    # configuration = embyapi.Configuration()
    # configuration.api_key['api_key'] = '9c78cfc58b10433e9504629d2d8d9ce5'
    # api_instance = embyapi.ActivityLogServiceApi(embyapi.ApiClient(configuration))

    if not (CONFIG.embyServer and CONFIG.embyUser):
        print("Set the EMBY section in config.ini")
        return
    print("Create Database....")
    with app.app_context():
        db.create_all()

    print("Connect to the Emby server: " + CONFIG.embyServer)
    ec = EmbyClient(CONFIG.embyServer, CONFIG.embyUser, CONFIG.embyPass)
    p = TMDbNameParser(CONFIG.tmdb_api_key, 'en')

    r = ec.getMediaList()
    for item in r:
        print(">> " + item["Name"])
        pi = TorMediaItem(title=item["Name"])

        guids = item["ProviderIds"]
        pi.torimdb = guids['IMDB'] if 'IMDB' in guids else ''
        pi.torimdb = guids['Imdb'] if 'Imdb' in guids else ''
        pi.tmdbid = guids['Tmdb'] if 'Tmdb' in guids else ''
        # pi.tvdb = guids['Tvdb'] if 'Tvdb' in guids else ''
        if item['Type'] == 'Series':
            pi.tmdbcat = 'tv'
            # pi.location = os.path.basename()
            pi.location = os.path.relpath(item["Path"], CONFIG.linkDir)
        elif item['Type'] == 'Movie':
            pi.tmdbcat = 'movie'
            pi.location = os.path.relpath(os.path.dirname(item["Path"]), CONFIG.linkDir)
            # pi.location = os.path.basename(os.path.dirname(item["Path"]))
        else:
            print("Unknow Type: " + item['Type'])

        pd = item["PremiereDate"] if "PremiereDate" in item else ""
        if 'Tmdb' not in guids:
            print("    TMDb Not Found: %s (%s) " % (item["Name"], pd))
            pi.tmdbid = searchTMDb(p, item["Name"], pi.torimdb)
        print("   %s: (TMDb: %s, IMDb: %s)\n    %s" % (pi.title, pi.tmdbid, pi.torimdb, pi.location))
        with app.app_context():
            db.session.add(pi)
            db.session.commit()
        # time.sleep(1)



def emptyTable():
    try:
        with app.app_context():
            num_rows_deleted = db.session.query(TorMediaItem).delete()
            db.session.commit()
            return num_rows_deleted
    except:
        db.session.rollback()
        return 0 


def plexKeyExists(videokey):
    with app.app_context():
        exists = db.session.query(db.exists().where(TorMediaItem.key == videokey)).scalar()
    #     exists = db.session.query(MediaItem.id).filter_by(key=videokey).first() is not None

    return exists


# @app.route('/sitetor/api/v1.0/init', methods=['GET'])
def loadPlexLibrary():
    if not (CONFIG.plexServer and CONFIG.plexToken):
        print("Set the 'server_token' and 'server_url' in config.ini")
        return
    print("Create Database....")
    with app.app_context():
        db.create_all()
    
    tstart = time.time()
    print("Connect to the Plex server: " + CONFIG.plexServer)
    baseurl = CONFIG.plexServer  # 'http://{}:{}'.format(ip, port)
    plex = PlexServer(baseurl, CONFIG.plexToken)
    # movies = plex.library.section(sectionstr)
    p = TMDbNameParser(CONFIG.tmdb_api_key, 'en')
    for idx, video in enumerate(plex.library.all()):
        for n in range(MAX_RETRY):
            try:
                pi = TorMediaItem(title=video.title)
                # pi.originalTitle = video.originalTitle
                # pi.librarySectionID = video.librarySectionID
                # pi.audienceRating = tryFloat(video.audienceRating)
                break
            except Exception as e:
                if n < MAX_RETRY:
                    print('Fail to reload the video' + str(e))
                    print('retry %d time.' % (n+1))
                    time.sleep(2)
                else:
                    print('Fail to reload the video MAX_RETRY(%d) times' % (MAX_RETRY))
                    os._exit(1)
            
        # pi.originalTitle = video.originalTitle
        # if plexKeyExists(video.key):
        #     continue

        if video.type == 'movie':
            pi.tmdbcat = 'movie'
        elif video.type == 'show':
            pi.tmdbcat = 'tv'
        else:
            pi.tmdbcat = video.type


        # pi.guid = video.guid
        # pi.key = video.key
        if len(video.locations) > 0:
            pi.location = ','.join(video.locations)
            if isMediaExt(video.locations[0]):
                pi.location = os.path.basename(
                    os.path.dirname(video.locations[0]))
            else:
                pi.location = os.path.basename(video.locations[0])
        else:
            print('No location: ', video.title)
        imdb = ''
        for guid in video.guids:
            imdbmatch = re.search(r'imdb://(tt\d+)', guid.id, re.I)
            if imdbmatch:
                pi.torimdb = imdbmatch[1]
                imdb = imdbmatch[1]
            tmdbmatch = re.search(r'tmdb://(\d+)', guid.id, re.I)
            if tmdbmatch:
                pi.tmdbid = tmdbmatch[1]
            # tvdbmatch = re.search(r'tvdb://(\d+)', guid.id, re.I)
            # if tvdbmatch:
            #     pi.tvdb = tvdbmatch[1]
        if not pi.tmdbid:
            pi.tmdbid = searchTMDb(p, video.title, imdb)
        with app.app_context():
            db.session.add(pi)
            db.session.commit()
        print("%d : %s , %s , %s, %s" % (idx, video.title,
              video.originalTitle, video.locations, video.guids))
    print(time.strftime("%H:%M:%S", time.gmtime(time.time()-tstart)))


def searchTMDb(tmdbParser, title, imdb):
    if imdb:
        tmdbParser.parse(title, useTMDb=True, hasIMDbId=imdb)
    else:
        tmdbParser.parse(title, useTMDb=True)
    return tmdbParser.tmdbid


def fillTMDbListDb():
    with app.app_context():
        query = db.session.query(TorMediaItem).filter(TorMediaItem.tmdbid == None)
        if not CONFIG.tmdb_api_key:
            print("Set the ['TMDB']['api_key'] in config.ini")
            return

        p = TMDbNameParser(CONFIG.tmdb_api_key, 'en')
        for row in query:
            row.tmdbid = searchTMDb(p, row.title, row.torimdb)
            # row.save()
            db.session.commit()


def loadArgs():
    global ARGS
    parser = argparse.ArgumentParser(
        description='A torrent handler does library dupe check, add qbit with tag, etc.'
    )
    parser.add_argument('--init-library', action='store_true',
                        help='init database with plex query.')
    parser.add_argument('--empty', action='store_true',
                        help='append to local database, without delete old data.')
    parser.add_argument('--fill-tmdb', action='store_true',
                        help='fill tmdb field if it miss.')
    parser.add_argument('-C', '--config', help='config file.')

    ARGS = parser.parse_args()
    if not ARGS.config:
        ARGS.config = os.path.join(os.getcwd(), 'config.ini')


def initDatabase():
    print("Init Database....")
    with app.app_context():
        db.create_all()
    if ARGS.empty:
        emptyTable()


def main():
    loadArgs()
    readConfig(ARGS.config)
    initDatabase()        
    if ARGS.init_library:
        if CONFIG.plexServer:
            loadPlexLibrary()
        if CONFIG.embyServer:
            loadEmbyLibrary()
    elif ARGS.fill_tmdb:
        fillTMDbListDb()


if __name__ == '__main__':
    main()
