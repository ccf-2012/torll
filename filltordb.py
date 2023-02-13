from app import app, db, TorMediaItem
import sys, os
sys.path.insert(1, '../torcp/')

from torcp.tmdbparser import TMDbNameParser
import myconfig
import time


def fillTorMediaDb():
    with app.app_context():
        query = TorMediaItem.query
        for dbitem in query:
            if not dbitem.tmdbgenreids:
                # p.parse(dbitem.title, useTMDb=True, hasTMDbId=dbitem.tmdbid)
                if dbitem.tmdbid > 0:
                    p = TMDbNameParser(myconfig.CONFIG.tmdb_api_key, 'zh-CN')
                    # time.sleep(1)
                    attempts = 0
                    while attempts < 3:
                        try:
                            tmdbid, title, year = p.searchTMDbByTMDbId(dbitem.tmdbcat, str(dbitem.tmdbid))
                            break
                        except:
                            attempts += 1
                            print("TMDb connection failed. Trying %d " % attempts)
                            time.sleep(3)
                        
                    dbitem.tmdbposter = p.poster_path
                    dbitem.tmdbgenreids = ','.join(str(e) for e in p.genre_ids)
                    dbitem.tmdbyear = p.year
                    db.session.commit()


def main():
    myconfig.readConfig(os.path.join(os.path.dirname(__file__), 'config.ini'))
    fillTorMediaDb()


if __name__ == '__main__':
    main()
