import feedparser
import re
import os
import sys
import json
import argparse
import lxml.html
from myconfig import readConfig, CONFIG
from loguru import logger
import app
from humanbytes import HumanBytes


def tryint(instr):
    try:
        string_int = int(instr)
    except ValueError:
        string_int = 0
    return string_int


def removePasskeyUrl(url):
    return re.sub(r'&(passkey|rsskey|downhash)=[^&]*', '', url)


def checkAutoCategory(title):
    for category, pattern in CONFIG.autoCategory:
        if re.search(pattern, title):
            return category
    return ''


class TorDetail:
    def __init__(self, imdbstr, subtitle, infopage):
        self.imdbstr = imdbstr
        self.subtitle = subtitle
        self.infopage = infopage


class RssFeed:
    def __init__(self, taskconfig):
        self.name = taskconfig.get("name", "none")
        self.rssUrl = taskconfig.get("rss_url")
        self.filters = taskconfig.get("filters", [])
        self.site = taskconfig.get("site")
        self.cookie = taskconfig.get("cookie")
        self.qbCategory = taskconfig.get("qb_category", "")

    def fetchRss(self):
        """Fetch and parse the RSS feed."""
        return feedparser.parse(self.rssUrl)

    def fetchInfoPage(self, detailLink):
        if self.cookie:
            doc = app.fetchInfoPage(detailLink, self.cookie)
            if doc:
                imdbstr = app.parseInfoPageIMDbId(doc)
                subtitle = self.parseSubtitle(doc)
                return TorDetail(imdbstr, subtitle, doc)
        return None

    def parseSubtitle(self, doc):
        parser = lxml.html.HTMLParser(recover=True, encoding='utf-8')
        htmltree = lxml.html.fromstring(doc, parser=parser)
        subtitle = htmltree.xpath(
            "//td[text()='副标题']/following-sibling::td[1]/text()")
        return subtitle[0] if subtitle else ''

    def existsInRssHistory(self, torname):
        with app.app.app_context():
            # exists = db.session.query(RSSHistory.id).filter_by(title=torname).first() is not None
            exists = app.db.session.query(app.db.exists().where(
                app.RSSHistory.title == torname)).scalar()
        return exists

    def saveRssHistory(self, entry):
        with app.app.app_context():
            size_item = tryint(entry.links[1]['length'])
            dbrssitem = app.RSSHistory(site=self.site,
                                       title=entry.title,
                                       infoLink=entry.link,
                                       downloadLink=entry.links[1]['href'],
                                       size=size_item)
            app.db.session.add(dbrssitem)
            app.db.session.commit()
            return dbrssitem

    def commitDbSession(self, dbrssitem, reason):
        with app.app.app_context():
            dbrssitem.reason = reason
            app.db.session.commit()

    def addDownload(self, entry, detail ):
        rssDownloadLink = entry.links[1]['href']
        logger.info(f'   >> {removePasskeyUrl(rssDownloadLink)}')

        qbCategory = self.qbCategory if self.qbCategory else ''
        if not qbCategory:
            qbCategory = checkAutoCategory(entry.title)

        r = app.addTorrent(rssDownloadLink, detail.imdbstr, qbCategory)
        return True if r == 201 else False

    def applyFilters(self, entry, detail):
        """Apply configured filters to a single RSS entry."""
        for filter in self.filters:
            if 'title_regex' in filter:
                if not re.search(filter['title_regex'], entry.title, re.I):
                    return 'TITLE_REGEX'
            if 'title_not_regex' in filter:
                if re.search(filter['title_not_regex'], entry.title, re.I):
                    return 'TITLE_NOT_REGEX'
            if 'subtitle_regex' in filter:
                if not re.search(filter['subtitle_regex'], entry.get('subtitle', '')):
                    return 'SUBTITLE_REGEX'
            if 'subtitle_not_regex' in filter:
                if re.search(filter['subtitle_not_regex'], entry.get('subtitle', '')):
                    return 'SUBTITLE_NOT_REGEX'
            if 'detail_regex' in filter:
                if re.search(filter['detail_regex'], detail.infopage):
                    return 'DETAIL_REGEX'
            if 'size_min' in filter:
                size_gb = tryint(entry.links[1]['length']) / 1024 / 1024 / 1024
                if size_gb < filter['size_gb_min']:
                    return 'SIZE_MIN'
            if 'size_max' in filter:
                size_gb = tryint(entry.links[1]['length']) / 1024 / 1024 / 1024
                if size_gb > filter['size_gb_max']:
                    return 'SIZE_MAX'
        return 'HIT'

    def missFields(self, entry):
        fields = ['id', 'title', 'link', 'links']
        mislist = [z for z in fields if not hasattr(entry, z)]
        return len(mislist) > 0

    def processRssFeeds(self):
        """Get filtered RSS entries based on configured filters."""
        feed = self.fetchRss()
        rssFeedSum = len(feed.entries)
        rssAccept = 0
        for i, entry in enumerate(feed.entries):
            if self.missFields(entry):
                logger.warning('miss field in rssitem ')
                continue
            if self.existsInRssHistory(entry.title):
                continue
            with app.app.app_context():
                # dbrssitem = self.saveRssHistory(entry)
                size_item = tryint(entry.links[1]['length'])
                dbrssitem = app.RSSHistory(site=self.site,
                                        title=entry.title,
                                        infoLink=entry.link,
                                        downloadLink=entry.links[1]['href'],
                                        size=size_item)
                app.db.session.add(dbrssitem)
                app.db.session.commit()

                detail = self.fetchInfoPage(entry.link)
                logger.info(
                    f'   {i}  {entry.title}, {detail.imdbstr}, {detail.subtitle}')
                reason = self.applyFilters(entry, detail)
                if reason == 'HIT':
                    rssAccept += 1
                    r = self.addDownload(entry, detail)
                    dbrssitem.accept = 2 if r else 0
                # self.commitDbSession(dbrssitem, reason)
                dbrssitem.reason = reason
                app.db.session.commit()

        logger.info(
            f'RSS {self.name} {self.site} - Total: {rssFeedSum}, Accepted: {rssAccept}')


def loadConfig(configFile):
    """Load the entire configuration from a JSON file."""
    # with open(configFile, 'r') as file:
    #     return json.load(file)
    rss_json_file = os.path.join(os.path.dirname(__file__), configFile)
    try:
        f = open(rss_json_file)
        rss_config = json.load(f)
    except:
        logger.error(f'json file error: {rss_json_file}')
        return []
    f.close()
    return rss_config


def rssTask():
    readConfig("config.ini")
    configFile = "rssconfig.json"  # Path to the filters configuration file
    config = loadConfig(configFile)
    tasks = config.get("rsstasks", [])
    for i, task in enumerate(tasks):
        rssfeed = RssFeed(task)
        logger.info(f'RSS Task {i}: {rssfeed.name} {removePasskeyUrl(rssfeed.rssUrl)}')
        rssfeed.processRssFeeds()


if __name__ == "__main__":
    logger.remove()
    formatstr = "{time:YYYY-MM-DD HH:mm:ss} | <level>{level: <8}</level> | - <level>{message}</level>"
    logger.add(sys.stdout, format=formatstr)
    rssTask()
