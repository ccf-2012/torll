from flask import Flask, render_template, jsonify, redirect
from flask import request, abort
import requests as pyrequests
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import logging
from flask_httpauth import HTTPBasicAuth
import myconfig
import argparse
from urllib.parse import urlparse
from wtforms import Form, StringField, RadioField, SubmitField, DecimalField, IntegerField, SelectField
from wtforms.validators import DataRequired, NumberRange
from wtforms.widgets import PasswordInput
import qbfunc
from apscheduler.schedulers.background import BackgroundScheduler
from torcp.tmdbparser import TMDbNameParser
import feedparser
import re
from http.cookies import SimpleCookie
from humanbytes import HumanBytes
import shutil
import lxml.html
import json
import siteconfig


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# app.config['SECRET_KEY'] = 'mykey'
db = SQLAlchemy(app)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
auth = HTTPBasicAuth()
scheduler = BackgroundScheduler(job_defaults={'max_instances': 2})


def genSiteLink(siteAbbrev, siteid, sitecat=''):
    SITE_URL_PREFIX = {
        'pter': 'https://pterclub.com/details.php?id=',
        'pterclub': 'https://pterclub.com/details.php?id=',
        'aud': 'https://audiences.me/details.php?id=',
        'audiences': 'https://audiences.me/details.php?id=',
        'chd': 'https://chdbits.co/details.php?id=',
        'chdbits': 'https://chdbits.co/details.php?id=',
        'lhd': 'https://lemonhd.org/',
        'hds': 'https://hdsky.me/details.php?id=',
        'ob': 'https://ourbits.club/details.php?id=',
        'ssd': 'https://springsunday.net/details.php?id=',
        'frds': 'https://pt.keepfrds.com/details.php?id=',
        'hh': 'https://hhanclub.top/details.php?id=',
        'ttg': 'https://totheglory.im/t/',
    }
    detailUrl = ''
    if siteAbbrev in SITE_URL_PREFIX:
        if siteAbbrev == 'lhd':
            if sitecat == 'movie':
                detailUrl = SITE_URL_PREFIX[siteAbbrev] + \
                    'details_movie.php?id=' + str(siteid)
            elif sitecat == 'tvseries':
                detailUrl = SITE_URL_PREFIX[siteAbbrev] + \
                    'details_tv.php?id=' + str(siteid)
        else:
            detailUrl = SITE_URL_PREFIX[siteAbbrev] + str(siteid)
    return detailUrl if detailUrl else ''


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

    def to_dict(self):
        return {
            'id': self.id,
            'torname': self.torname,
            'title': self.title,
            'addedon': self.addedon,
            'torabbrev': self.torsite,
            'torsite': genSiteLink(self.torsite, self.torsiteid),
            'torsitecat': self.torsitecat,
            'torimdb': self.torimdb,
            'tmdbid': str(self.tmdbid),
            'tmdbcat': self.tmdbcat,
            'location': self.location,
        }


def initDatabase():
    with app.app_context():
        db.create_all()


class TorcpItemDBObj:
    def __init__(self, torsite, torsiteid, torimdb, torhash, torsize):
        self.torsite = torsite
        self.torsiteid = torsiteid
        self.torimdb = torimdb
        self.torhash = torhash
        self.torsize = torsize

    def onOneItemTorcped(self, targetDir, mediaName, tmdbIdStr, tmdbCat, tmdbTitle):
        # print(targetDir, mediaName, tmdbIdStr, tmdbCat)
        t = TorMediaItem(torname=mediaName,
                         torsite=self.torsite,
                         title=tmdbTitle,
                         torsiteid=self.torsiteid,
                         torimdb=self.torimdb,
                         torhash=self.torhash,
                         torsize=self.torsize,
                         tmdbid=tryint(tmdbIdStr),
                         tmdbcat=tmdbCat,
                         location=targetDir)

        with app.app_context():
            db.session.add(t)
            db.session.commit()


class TorcpItemCallbackObj:
    def __init__(self):
        self.tmdbid = -1
        self.tmdbcat = ''
        self.mediaName = ''
        self.targetDir = ''
        self.tmdbTitle = ''

    def onOneItemTorcped(self, targetDir, mediaName, tmdbIdStr, tmdbCat, tmdbTitle):
        # print(targetDir, mediaName, tmdbIdStr, tmdbCat)
        self.tmdbid = int(tmdbIdStr)
        self.tmdbcat = tmdbCat
        self.mediaName = mediaName
        self.targetDir = targetDir
        self.tmdbTitle = tmdbTitle


def queryByHash(qbhash):
    with app.app_context():
        query = db.session.query(TorMediaItem).filter(
            TorMediaItem.torhash == qbhash).first()
        return query


@auth.verify_password
def verify_password(username, password):
    if username == myconfig.CONFIG.basicAuthUser and password == myconfig.CONFIG.basicAuthPass:
        return username


@app.route('/')
@auth.login_required
def index():
    return render_template('tortable.html')


class MediaItemForm(Form):
    # location = StringField('存储路径，如果是在本机上，修改此处将尝试改名', validators=[DataRequired()])
    # torimdb = StringField('修改IMDb以重新查询和生成硬链', validators=[DataRequired()])
    mbRootDir = StringField('媒体库根目录，如果是GD盘则将其mount到本地')
    tmdbcatid = StringField(
        '修改TMDb以重新查询和生成硬链, 分类和id的写法可以是：tv-12345，movie-12345或简写为m12345')
    # tmdbid = StringField('TMDb id')
    submit = SubmitField("执行修正")


def parseTMDbStr(tmdbstr):
    if tmdbstr.isnumeric():
        return '', tmdbstr
    m = re.search(r'(m(ovie)?|t(v)?)[-_]?(\d+)',
                  tmdbstr.strip(), flags=re.A | re.I)
    if m:
        catstr = 'movie' if m[1].startswith('m') else 'tv'
        return catstr, m[4]
    else:
        return '', ''


def torMediaEditFunc(mediaid, tmdbcatidstr, mbrootDir):
    tormedia = TorMediaItem.query.get(mediaid)

    tmdbcat, tmdbidstr = parseTMDbStr(tmdbcatidstr)
    myconfig.updateMediaRootDir(ARGS.config, mbrootDir)
    oldpath = os.path.join(myconfig.CONFIG.mbRootDir, tormedia.location)
    if os.path.exists(oldpath):
        import rcp
        targetLocation, tmdbTitle = rcp.runTorcpMove(
            sourceDir=oldpath,
            targetDir=myconfig.CONFIG.mbRootDir,
            tmdbcatidstr=tmdbcatidstr)

        if tormedia.location != targetLocation:
            tormedia.tmdbcat = tmdbcat
            tormedia.tmdbid = tryint(tmdbidstr)
            tormedia.location = targetLocation
            tormedia.title = tmdbTitle
            db.session.commit()
            warningstr = '影视内容已经移至：' + \
                os.path.join(myconfig.CONFIG.mbRootDir, targetLocation)
            shutil.rmtree(oldpath)
            moved = True
        else:
            warningstr = '影视内容位置没变：' + \
                os.path.join(myconfig.CONFIG.mbRootDir, targetLocation)
            moved = False
    else:
        warningstr = '目录不存在：' + oldpath
        moved = False

    return moved, warningstr


@app.route('/mediaedit/<id>', methods=['POST', 'GET'])
@auth.login_required
def torMediaEdit(id):
    tormedia = TorMediaItem.query.get(id)
    form = MediaItemForm(request.form)
    form.tmdbcatid.data = "%s-%d" % (tormedia.tmdbcat, tormedia.tmdbid)
    if not myconfig.CONFIG.mbRootDir:
        myconfig.CONFIG.mbRootDir = myconfig.CONFIG.linkDir
    form.mbRootDir.data = myconfig.CONFIG.mbRootDir
    destDir = os.path.join(myconfig.CONFIG.mbRootDir, tormedia.location)
    if os.path.exists(destDir):
        warningstr = '此影视目录将被重新识别并移动：%s' % (destDir)
    else:
        warningstr = '%s : 目标不存在' % (destDir)

    if request.method == 'POST':
        form = MediaItemForm(request.form)
        moved, warningstr = torMediaEditFunc(
            id, form.tmdbcatid.data, form.mbRootDir.data)

        return render_template('mediaeditresult.html', msg=warningstr, moved=moved, mid=id)

    return render_template('mediaedit.html', form=form, msg=warningstr, mid=id)


@app.route('/api/mediaedit', methods=['POST'])
@auth.login_required
def apiTorMediaEdit():
    r = request.get_json()
    moved, msg = torMediaEditFunc(r["id"], r["tmdbcatid"], r["mbRootDir"])
    return json.dumps({'msg': msg, 'moved': moved}), 200, {'ContentType': 'application/json'}


@app.route('/mediadel/<id>')
@auth.login_required
def torMediaDel(id):
    tormedia = TorMediaItem.query.get(id)

    destDir = os.path.join(myconfig.CONFIG.linkDir, tormedia.location)
    if os.path.exists(destDir):
        print("Deleting ", destDir)
        try:
            shutil.rmtree(destDir)
        except:
            pass

    db.session.delete(tormedia)
    db.session.commit()
    return redirect("/")


class QBSettingForm(Form):
    qbhost = StringField('qBit 主机IP', validators=[DataRequired()])
    qbport = StringField('qBit 端口')
    qbuser = StringField('qBit 用户名', validators=[DataRequired()])
    qbpass = StringField('qBit 密码', widget=PasswordInput(
        hide_value=False), validators=[DataRequired()])
    submit = SubmitField("保存设置")
    qbapirun = RadioField('qBit 种子完成后调 API, 还是执行本地 rcp.sh 脚本？', choices=[
        ('True', '调用 API, 适用于 qBit 跑在docker里面的情况'),
        ('False', '直接执行本地 rcp.sh 脚本')])
    dockerFrom = StringField('若 qBit 在docker中，则须设置映射将docker中的路径：')
    dockerTo = StringField('转换为以下路径：')


@app.route('/qbsetting', methods=['POST', 'GET'])
@auth.login_required
def qbitSetting():
    form = QBSettingForm()
    form.qbhost.data = myconfig.CONFIG.qbServer
    form.qbport.data = myconfig.CONFIG.qbPort
    form.qbuser.data = myconfig.CONFIG.qbUser
    form.qbpass.data = myconfig.CONFIG.qbPass
    form.qbapirun.data = myconfig.CONFIG.apiRunProgram
    form.dockerFrom.data = myconfig.CONFIG.dockerFrom
    form.dockerTo.data = myconfig.CONFIG.dockerTo
    msg = ''
    if request.method == 'POST':
        form = QBSettingForm(request.form)
        myconfig.updateQBSettings(ARGS.config,
                                  form.qbhost.data,
                                  form.qbport.data,
                                  form.qbuser.data,
                                  form.qbpass.data,
                                  form.qbapirun.data,
                                  form.dockerFrom.data,
                                  form.dockerTo.data,
                                  )
        if form.qbapirun.data == 'True':
            authstr = '-u %s:%s ' % (myconfig.CONFIG.basicAuthUser,
                                     myconfig.CONFIG.basicAuthPass)
            apiurl = 'http://%s:5006/api/torcp2' % (form.qbhost.data)
            postargs = '-d torhash=%I '
            progstr = 'curl ' + authstr + postargs + apiurl
        else:
            fn = os.path.join(os.path.dirname(__file__), "rcp.sh")
            progstr = 'sh ' + fn + ' "%I" '
            scriptpath = os.path.dirname(__file__)
            with open(fn, 'w') as f:
                f.write(
                    f"#!/bin/sh\npython3 {os.path.join(scriptpath, 'rcp.py')}  -I $1 >>{os.path.join(scriptpath, 'rcp2.log')} 2>>{os.path.join(scriptpath, 'rcp2e.log')}\n")
                f.close()
            # import stat
            # os.chmod(fn, stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH)

        r = qbfunc.setAutoRunProgram(progstr)
        if r:
            msg = 'success'
        else:
            msg = 'failed'
    return render_template('qbsetting.html', form=form, msg=msg)


class SettingForm(Form):
    linkdir = StringField('目标目录位置', validators=[DataRequired()])
    symbolink = RadioField('硬链还是软链？如果目标目录与qbit的下载目录在不同分区，则需要使用软链', choices=[
        ('', '硬链，hardlink'),
        ('--symbolink', '软链，symbolink')],
        default='')
    tmdb_key = StringField('TMDb API key', validators=[DataRequired()])
    bracket = RadioField('使用括号后缀来向 Emby/Plex 指定媒体的TMDb id', choices=[
        ('--emby-bracket', 'Emby后缀，形如 [tmdbid=12345]'),
        ('--plex-bracket', 'Plex后缀，形如{tmdb-12345}'),
        ('', '无后缀')],
        default='')
    tmdb_lang = RadioField('TMDb 语言，生成英文或是中文目录名？', choices=[
        ('en-US', 'en-US'),
        ('zh-CN', 'zh-CN')],
        default='en-US')
    sep_lang = StringField('按语言分目录，以逗号分隔，如 cn,ja,ko 将不同语言的媒体分到不同目录中；留空表示不分')
    sep_genre = StringField('按类型分目录，以逗号分隔，使用TMDb语言对应的分类词；留空表示不分')
    submit = SubmitField("保存设置")


@app.route('/setting', methods=['POST', 'GET'])
@auth.login_required
def setting():
    form = SettingForm()
    form.linkdir.data = myconfig.CONFIG.linkDir
    form.tmdb_key.data = myconfig.CONFIG.tmdb_api_key
    form.bracket.data = myconfig.CONFIG.bracket
    form.tmdb_lang.data = myconfig.CONFIG.tmdbLang
    form.sep_lang.data = myconfig.CONFIG.lang
    form.sep_genre.data = myconfig.CONFIG.genre
    form.symbolink.data = myconfig.CONFIG.symbolink
    msg = ''
    if request.method == 'POST':
        form = SettingForm(request.form)
        myconfig.updateConfigSettings(ARGS.config,
                                      linkDir=form.linkdir.data,
                                      bracket=form.bracket.data,
                                      tmdbLang=form.tmdb_lang.data,
                                      lang=form.sep_lang.data,
                                      genre=form.sep_genre.data,
                                      tmdb_api_key=form.tmdb_key.data,
                                      symbolink=form.symbolink.data)
        msg = 'success'

    return render_template('settings.html', form=form, msg=msg)


@app.route('/editrcp', methods=['POST', 'GET'])
@auth.login_required
def editrcp():
    fn = myconfig.CONFIG.rcpshfile
    if os.path.isfile(fn):
        with open(fn, 'r') as f:
            rcpsh_txt = f.read()
    else:
        rcpsh_txt = ''
    msg = ''
    if request.method == 'POST':
        rcpsh_txt = request.form['config_file']

        with open(fn, 'w') as f:
            f.write("\n".join(rcpsh_txt.splitlines()))
        msg = "success"

    return render_template('editrcp.html', config_file=rcpsh_txt, msg=msg)


@app.route('/api/data')
@auth.login_required
def data():
    query = TorMediaItem.query

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            TorMediaItem.torname.like(f'%{search}%'),
            TorMediaItem.location.like(f'%{search}%'),
            TorMediaItem.title.like(f'%{search}%'),
        ))
    total_filtered = query.count()

    # sorting
    order = []
    i = 0
    while True:
        col_index = request.args.get(f'order[{i}][column]')
        if col_index is None:
            break
        col_name = request.args.get(f'columns[{col_index}][data]')
        if col_name not in ['torname', 'torsite', 'addedon']:
            col_name = 'addedon'
        descending = request.args.get(f'order[{i}][dir]') == 'desc'
        col = getattr(TorMediaItem, col_name)
        if descending:
            col = col.desc()
        order.append(col)
        i += 1
    if order:
        query = query.order_by(*order)

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    # response
    return {
        'data': [user.to_dict() for user in query],
        'recordsFiltered': total_filtered,
        'recordsTotal': TorMediaItem.query.count(),
        'draw': request.args.get('draw', type=int),
    }


@app.route('/api/torcp2', methods=['POST'])
@auth.login_required
def runTorcpByHash():
    if 'torhash' in request.form:
        torhash = request.form['torhash'].strip()
        print(torhash)
        torpath, torhash2, torsize, tortag, savepath = qbfunc.getTorrentByHash(
            torhash)
        r = runRcp(torpath, torhash2, torsize, tortag, savepath, None)
        if r == 200:
            return jsonify({'OK': 200}), 200
    return jsonify({'Error': 401}), 401


@app.route('/api/torcp', methods=['POST'])
@auth.login_required
def runTorcpApi():
    if 'torpath' in request.json and 'torhash' in request.json and 'torsize' in request.json:
        torpath = request.json['torpath'].strip()
        torhash = request.json['torhash'].strip()
        torsize = request.json['torsize'].strip()
        tortag = request.json['tortag'].strip(
        ) if 'tortag' in request.json else ''
        savepath = request.json['savepath'].strip(
        ) if 'savepath' in request.json else ''
        r = runRcp(torpath, torhash, torsize, tortag, savepath, None)
        if r == 200:
            return jsonify({'OK': 200}), 200
    return jsonify({'Error': 401}), 401


class RSSHistory(db.Model):
    __tablename__ = 'rss_history_table'
    id = db.Column(db.Integer, primary_key=True)
    site = db.Column(db.String(64))
    title = db.Column(db.String(255))
    accept = db.Column(db.Integer, default=0)
    imdbstr = db.Column(db.String(32))
    addedon = db.Column(db.DateTime, default=datetime.now)
    reason = db.Column(db.String(64))
    size = db.Column(db.BigInteger)
    infoLink = db.Column(db.String(255))
    downloadLink = db.Column(db.String(255))

    def to_dict(self):
        return {
            'id': self.id,
            'addedon': self.addedon,
            'site': self.site,
            'title': self.title,
            'imdbstr': self.imdbstr,
            'reason': self.reason,
            'size': HumanBytes.format(int(self.size)),
            'accept': self.accept,
            'infoLink': self.infoLink,
        }


@app.route('/api/rsslogdata')
@auth.login_required
def rssHistoryData():
    query = RSSHistory.query

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            RSSHistory.title.like(f'%{search}%'),
        ))
    total_filtered = query.count()

    # sorting
    order = []
    i = 0
    while True:
        col_index = request.args.get(f'order[{i}][column]')
        if col_index is None:
            break
        col_name = request.args.get(f'columns[{col_index}][data]')
        if col_name not in ['site', 'title', 'addedon', 'accept']:
            col_name = 'title'
        descending = request.args.get(f'order[{i}][dir]') == 'desc'
        col = getattr(RSSHistory, col_name)
        if descending:
            col = col.desc()
        order.append(col)
        i += 1
    if order:
        query = query.order_by(*order)

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    # response
    return {
        'data': [user.to_dict() for user in query],
        'recordsFiltered': total_filtered,
        'recordsTotal': RSSHistory.query.count(),
        'draw': request.args.get('draw', type=int),
    }


@app.route('/rsslog')
@auth.login_required
def rssLog():
    return render_template('rsslog.html')


class RSSTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site = db.Column(db.String(64))
    rsslink = db.Column(db.String(256))
    cookie = db.Column(db.String(1024))
    title_regex = db.Column(db.String(120))
    info_regex = db.Column(db.String(120))
    title_not_regex = db.Column(db.String(120))
    info_not_regex = db.Column(db.String(120))
    min_imdb = db.Column(db.Float, default=0.0)
    task_interval = db.Column(db.Integer)
    total_count = db.Column(db.Integer)
    accept_count = db.Column(db.Integer)
    last_update = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now)
    active = db.Column(db.SmallInteger, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'last_update': self.last_update,
            'site': self.site,
            'task_interval': self.task_interval,
            'accept_count': self.accept_count,
            'title_regex': self.title_regex,
            'title_not_regex': self.title_not_regex,
            'info_regex': self.info_regex,
            'info_not_regex': self.info_not_regex,
            'min_imdb': self.min_imdb,
            'active': self.active,
        }


class RSSTaskForm(Form):
    rsslink = StringField('RSS 链接', validators=[DataRequired()])
    cookie = StringField('Cookie', validators=[DataRequired()])
    title_regex = StringField('标题包含')
    title_not_regex = StringField('标题不含')
    info_regex = StringField('描述包含')
    info_not_regex = StringField('描述不含')
    min_imdb = DecimalField('IMDb 大于', validators=[NumberRange(min=0, max=10)])
    task_interval = IntegerField('执行间隔 (分钟)', validators=[DataRequired()])
    submit = SubmitField("保存设置")


def getSiteName(url):
    hostnameList = urlparse(url).netloc.split('.')
    if len(hostnameList) == 2:
        sitename = hostnameList[0]
    elif len(hostnameList) == 3:
        sitename = hostnameList[1]
    else:
        sitename = ''
    return sitename


def getAbbrevSiteName(url):
    sitename = getSiteName(url)
    SITE_ABBRES = [('chdbits', 'chd'), ('pterclub', 'pter'), ('audiences', 'aud'),
                   ('lemonhd', 'lhd'), ('keepfrds', 'frds'), ('ourbits', 'ob'),
                   ('springsunday', 'ssd')]
    # result = next((i for i, v in enumerate(SITE_ABBRES) if v[0] == sitename), "")
    abbrev = [x for x in SITE_ABBRES if x[0] == sitename]
    return abbrev[0][1] if abbrev else sitename


@app.route('/rsstasks')
@auth.login_required
def rssTaskList():
    return render_template('rsstasks.html')


@app.route('/api/rsstasksdata')
@auth.login_required
def rssTaskData():
    query = RSSTask.query

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            RSSTask.site.like(f'%{search}%'),
        ))
    total_filtered = query.count()

    # sorting
    order = []
    i = 0
    while True:
        col_index = request.args.get(f'order[{i}][column]')
        if col_index is None:
            break
        col_name = request.args.get(f'columns[{col_index}][data]')
        if col_name not in ['site', 'min_imdb', 'last_update', 'accept_count']:
            col_name = 'site'
        descending = request.args.get(f'order[{i}][dir]') == 'desc'
        col = getattr(RSSTask, col_name)
        if descending:
            col = col.desc()
        order.append(col)
        i += 1
    if order:
        query = query.order_by(*order)

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    # response
    return {
        'data': [user.to_dict() for user in query],
        'recordsFiltered': total_filtered,
        'recordsTotal': RSSTask.query.count(),
        'draw': request.args.get('draw', type=int),
    }


@app.route('/rssnew', methods=['POST', 'GET'])
@auth.login_required
def rssNew():
    form = RSSTaskForm(request.form)
    if request.method == 'POST':
        form = RSSTaskForm(request.form)
        task = RSSTask()
        task.rsslink = form.rsslink.data
        task.site = getSiteName(task.rsslink)
        task.cookie = form.cookie.data
        task.title_regex = form.title_regex.data
        task.info_regex = form.info_regex.data
        task.title_not_regex = form.title_not_regex.data
        task.info_not_regex = form.info_not_regex.data
        task.min_imdb = form.min_imdb.data
        task.task_interval = form.task_interval.data
        task.total_count = 0
        task.accept_count = 0
        db.session.add(task)
        db.session.commit()

        job = scheduler.add_job(rssJob, 'interval', args=[
                                task.id], minutes=task.task_interval, id=str(task.id))
        return redirect("/rsstasks")

    return render_template('rssnew.html', form=form)


@app.route('/rssedit/<id>', methods=['POST', 'GET'])
@auth.login_required
def rssEdit(id):
    task = RSSTask.query.get(id)
    try:
        scheduler.remove_job(str(task.id))
    except:
        pass

    form = RSSTaskForm(request.form)
    form.rsslink.data = task.rsslink
    form.cookie.data = task.cookie
    form.title_regex.data = task.title_regex
    form.info_regex.data = task.info_regex
    form.title_not_regex.data = task.title_not_regex
    form.info_not_regex.data = task.info_not_regex
    form.min_imdb.data = task.min_imdb
    form.task_interval.data = task.task_interval

    if request.method == 'POST':
        form = RSSTaskForm(request.form)
        task.rsslink = form.rsslink.data
        task.site = getSiteName(task.rsslink)
        task.cookie = form.cookie.data
        task.title_regex = form.title_regex.data
        task.info_regex = form.info_regex.data
        task.title_not_regex = form.title_not_regex.data
        task.info_not_regex = form.info_not_regex.data
        task.min_imdb = form.min_imdb.data
        task.task_interval = form.task_interval.data
        # task.total_count = 0
        # task.accept_count = 0

        db.session.commit()

        job = scheduler.add_job(rssJob, 'interval', args=[
                                task.id], minutes=task.task_interval, id=str(task.id))
        return redirect("/rsstasks")

    return render_template('rssnew.html', form=form)


@app.route('/rssdel/<id>')
@auth.login_required
def rssDel(id):
    task = RSSTask.query.filter(RSSTask.id == id).first()
    try:
        scheduler.remove_job(str(task.id))
    except:
        pass

    db.session.delete(task)
    db.session.commit()
    return redirect("/rsstasks")


# @app.route('/rsspause/<id>')
# @auth.login_required
# def rssPause(id):
#     task = RSSTask.query.filter(RSSTask.id == id).first()
#     task.active = 2
#     db.session.commit()
#     return redirect("/rsstasks")


@app.route('/rssactivate/<id>')
@auth.login_required
def rssToggleActive(id):
    task = RSSTask.query.get(id)
    if task.active == 0:
        task.active = 2
        try:
            scheduler.pause_job(str(task.id))
        except:
            pass
    else:
        task.active = 0
        try:
            scheduler.resume_job(str(task.id))
        except:
            pass

    scheduler.print_jobs()
    db.session.commit()
    return redirect("/rsstasks")


@app.route('/rssrunonce/<id>')
@auth.login_required
def rssRunOnce(id):
    try:
        job = scheduler.get_job(str(id))
        if job:
            job.modify(next_run_time=datetime.now())
    except:
        pass
    return redirect("/rsstasks")


def validDownloadlink(downlink):
    keystr = ['passkey', 'downhash', 'totheglory.im/dl/',
              'totheglory.im/rssdd.php', 'download.php?hash=']
    return any(x in downlink for x in keystr)


def searchTMDb(tmdbParser, title, imdb):
    if imdb:
        tmdbParser.parse(title, useTMDb=True, hasIMDbId=imdb)
    else:
        tmdbParser.parse(title, useTMDb=True)
    return tmdbParser.tmdbid


def existsInRssHistory(torname):
    with app.app_context():
        # exists = db.session.query(RSSHistory.id).filter_by(title=torname).first() is not None
        exists = db.session.query(db.exists().where(
            RSSHistory.title == torname)).scalar()
    return exists


def saveRssHistory(site, item):
    with app.app_context():
        t = RSSHistory(site=site, title=item.title)
        if hasattr(item, 'link'):
            t.infoLink = item.link
        if hasattr(item, 'links') and len(item.links) > 1:
            t.downloadLink = item.links[1]['href']
        db.session.add(t)
        db.session.commit()
        return t


def checkMediaDbExistsTMDb(torTMDbid, torTMDbCat):
    with app.app_context():
        exists = db.session.query(TorMediaItem.id).filter_by(
            tmdbcat=torTMDbCat, tmdbid=torTMDbid).first() is not None
        return exists


def checkMediaDbNameDupe(torname):
    with app.app_context():
        exists = db.session.query(TorMediaItem.id).filter_by(
            torname=torname).first() is not None
        return exists


def genrSiteId(detailLink, imdbstr):
    siteAbbrev = getAbbrevSiteName(detailLink)
    if (siteAbbrev == "ttg"):
        m = re.search(r"t\/(\d+)", detailLink, flags=re.A)
    else:
        m = re.search(r"id=(\d+)", detailLink, flags=re.A)
    sid = m[1] if m else ""
    if imdbstr:
        sid = sid + "_" + imdbstr
    return siteAbbrev + "_" + sid


def tryFloat(fstr):
    try:
        f = float(fstr)
    except:
        f = 0.0
    return f


def tryint(instr):
    try:
        string_int = int(instr)
    except ValueError:
        string_int = 0
    return string_int


def fetchInfoPage(pageUrl, pageCookie):
    cookie = SimpleCookie()
    cookie.load(pageCookie)
    cookies = {k: v.value for k, v in cookie.items()}
    headers = {
        'User-Agent':
        'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36',
        'Content-Type': 'text/html; charset=UTF-8'
    }

    try:
        r = pyrequests.get(pageUrl, headers=headers, cookies=cookies)
        # r.encoding = r.apparent_encoding
        r.encoding = 'utf-8'
    except:
        return ''

    return r.text


def parseInfoPageIMDbval(doc):
    imdbval = 0
    m1 = re.search(r'IMDb.*?([0-9.]+)\s*/\s*10', doc, flags=re.A)
    if m1:
        imdbval = tryFloat(m1[1])
    doubanval = 0
    m2 = re.search(r'豆瓣评分.*?([0-9.]+)/10', doc, flags=re.A)
    if m2:
        doubanval = tryFloat(m2[1])
    if imdbval < 1 and doubanval < 1:
        ratelist = [x[1] for x in re.finditer(
            r'Rating:.*?([0-9.]+)\s*/\s*10\s*from', doc, flags=re.A)]
        if len(ratelist) >= 2:
            doubanval = tryFloat(ratelist[0])
            imdbval = tryFloat(ratelist[1])
        elif len(ratelist) == 1:
            #TODO: 不分辨douban/imdb了
            doubanval = tryFloat(ratelist[0])
            imdbval = doubanval
            # rate1 = re.search(r'Rating:.*?([0-9.]+)\s*/\s*10\s*from', doc, flags=re.A)
            # if rate1:
            #     imdbval = tryFloat(rate1[1])
        # print("   >> IMDb: %s, douban: %s" % (imdbval, doubanval))
    return imdbval, doubanval


def parseInfoPageIMDbId(doc):
    imdbstr = ''
    m1 = re.search(r'www\.imdb\.com\/title\/(tt\d+)', doc, flags=re.A)
    if m1:
        imdbstr = m1[1]
    return imdbstr


def checkMediaDbTMDbDupe(torname, imdbstr):
    if not torname:
        return 400
    if (not myconfig.CONFIG.tmdb_api_key):
        return 400

    p = TMDbNameParser(myconfig.CONFIG.tmdb_api_key, '')
    tmdbid = searchTMDb(p, torname, imdbstr)

    if tmdbid > 0:
        exists = checkMediaDbExistsTMDb(tmdbid, p.tmdbcat)
        if exists:
            return 202
        else:
            return 201
    else:
        return 203


def addTorrent(downloadLink, siteIdStr, imdbstr):
    if (not myconfig.CONFIG.qbServer):
        return 400

    if not validDownloadlink(downloadLink):
        return 402

    if not myconfig.CONFIG.dryrun:
        print("   >> Added: " + siteIdStr)
        if not qbfunc.addQbitWithTag(downloadLink.strip(), imdbstr, siteIdStr):
            return 400
    else:
        print("   >> DRYRUN: " + siteIdStr + "\n   >> " + downloadLink)

    return 201


def addTorrentViaPageDownload(downloadLink, sitecookie, siteIdStr, imdbstr):
    if (not myconfig.CONFIG.qbServer):
        return 400
    cookie = SimpleCookie()
    cookie.load(sitecookie)
    cookies = {k: v.value for k, v in cookie.items()}
    headers = {
        'User-Agent':
        'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36',
        'Content-Type': 'text/html; charset=UTF-8'
    }

    response = pyrequests.get(downloadLink, headers=headers, cookies=cookies)
    if not response.status_code == 200:
        return 402

    if not myconfig.CONFIG.dryrun:
        print("   >> Added: " + siteIdStr)
        if not qbfunc.addQbitFileWithTag(response.content, imdbstr, siteIdStr):
            return 400
    else:
        print("   >> DRYRUN: " + siteIdStr + "\n   >> " + downloadLink)

    return 201


def prcessRssFeeds(rsstask):
    feed = feedparser.parse(rsstask.rsslink)
    rssFeedSum = 0
    rssAccept = 0
    # with app.app_context():

    for item in feed.entries:
        rssFeedSum += 1
        if not hasattr(item, 'id'):
            print('RSS item: No id')
            continue
        if not hasattr(item, 'title'):
            print('RSS item:  No title')
            continue
        if not hasattr(item, 'link'):
            print('RSS item:  No info link')
            continue
        if not hasattr(item, 'links'):
            print('RSS item:  No download link')
            continue
        if len(item.links) <= 1:
            print('RSS item:  No download link')
            continue

        if existsInRssHistory(item.title):
            # print("   >> exists in rss history, skip")
            continue

        print("%d: %s (%s)" % (rssFeedSum, item.title,
                               datetime.now().strftime("%H:%M:%S")))

        dbrssitem = RSSHistory(site=rsstask.site,
                               title=item.title,
                               infoLink=item.link,
                               downloadLink=item.links[1]['href'],
                               size=item.links[1]['length'])

        db.session.add(dbrssitem)
        db.session.commit()

        if rsstask.title_regex:
            if not re.search(rsstask.title_regex, item.title, re.I):
                dbrssitem.reason = 'TITLE_REGEX'
                db.session.commit()
                continue

        if rsstask.title_not_regex:
            if re.search(rsstask.title_not_regex, item.title, re.I):
                dbrssitem.reason = 'TITLE_NOT_REGEX'
                db.session.commit()
                continue

        imdbstr = ''
        if rsstask.cookie:
            # Means: will dl wihout cookie, but no dl if cookie is wrong
            doc = fetchInfoPage(item.link, rsstask.cookie)
            if not doc:
                dbrssitem.reason = 'Fetch info page failed'
                db.session.commit()
                continue
            imdbstr = parseInfoPageIMDbId(doc)
            dbrssitem.imdbstr = imdbstr
            db.session.commit()

            if rsstask.info_regex:
                if not re.search(rsstask.info_regex, doc, flags=re.A):
                    dbrssitem.reason = 'INFO_REGEX'
                    db.session.commit()
                    continue
            if rsstask.info_not_regex:
                if re.search(rsstask.info_not_regex, doc, flags=re.A):
                    dbrssitem.reason = 'INFO_NOT_REGEX'
                    db.session.commit()
                    continue
            if rsstask.min_imdb:
                imdbval, doubanval = parseInfoPageIMDbval(doc)
                if (imdbval < rsstask.min_imdb) and (doubanval < rsstask.min_imdb):
                    # print("   >> MIN_IMDb not match")
                    dbrssitem.reason = "IMDb: %s, douban: %s" % (
                        imdbval, doubanval)
                    db.session.commit()
                    continue

        siteIdStr = genrSiteId(item.link, imdbstr)

        rssDownloadLink = item.links[1]['href']
        dbrssitem.accept = 2
        print('   %s (%s), %s' %
              (imdbstr, HumanBytes.format(int(dbrssitem.size)), rssDownloadLink))

        if checkMediaDbNameDupe(item.title):
            dbrssitem.reason = "Name dupe"
            db.session.commit()
            continue

        r = checkMediaDbTMDbDupe(item.title, imdbstr)
        if r != 201:
            dbrssitem.reason = 'TMDb dupe'
            db.session.commit()
            continue

        r = addTorrent(rssDownloadLink, siteIdStr, imdbstr)
        if r == 201:
            # Downloaded
            dbrssitem.accept = 3
            rssAccept += 1
        else:
            dbrssitem.reason = 'qBit Error'

        db.session.commit()

    # rtask = RSSTask.query.get(rsstask.id)
    rsstask.accept_count += rssAccept
    db.session.commit()

    print('RSS %s - Total: %d, Accepted: %d (%s)' %
          (rsstask.site, rssFeedSum, rssAccept, datetime.now().strftime("%H:%M:%S")))


@app.route('/rssmanual/<rsslogid>')
@auth.login_required
def manualDownload(rsslogid):
    dbrssitem = RSSHistory.query.get(rsslogid)
    # TODO: count download number on 1st site of the name
    taskitem = RSSTask.query.filter(RSSTask.site == dbrssitem.site).first()

    imdbstr = ''
    if taskitem:
        doc = fetchInfoPage(dbrssitem.infoLink, taskitem.cookie)
        if doc:
            imdbstr = parseInfoPageIMDbId(doc)
            dbrssitem.imdbstr = imdbstr
        siteIdStr = genrSiteId(dbrssitem.infoLink, imdbstr)

        if not checkMediaDbNameDupe(dbrssitem.title):
            r = addTorrent(dbrssitem.downloadLink, siteIdStr, imdbstr)
            if r == 201:
                dbrssitem.accept = 3
                taskitem.accept_count += 1
                db.session.commit()
    return redirect("/rsslog")


@app.route('/api/dupedownload', methods=['POST'])
@auth.login_required
def jsApiDupeDownload():
    if not request.json or 'torname' not in request.json:
        abort(jsonify(message="torname not found"))

    if checkMediaDbNameDupe(request.json['torname']):
        return jsonify({'Dupe': 'name'}), 202

    imdbstr = ''
    if 'imdbid' in request.json and request.json['imdbid']:
        imdbstr = request.json['imdbid'].strip()
    siteIdStr = ''
    if 'siteid' in request.json and request.json['siteid']:
        siteIdStr = request.json['siteid'].strip()
    forceDownload = False
    if 'force' in request.json:
        forceDownload = request.json['force']

    if 'downloadlink' in request.json and validDownloadlink(request.json['downloadlink']):
        downloadlink = request.json['downloadlink'].strip()
    else:
        return jsonify({'no download link': True}), 205

    if not forceDownload:
        r = checkMediaDbTMDbDupe(request.json['torname'], imdbstr)
        if r != 201:
            return jsonify({'TMDb Dupe': False}), r

    if not myconfig.CONFIG.dryrun:
        print("Added: " + request.json['torname'])
        r = addTorrent(downloadlink, siteIdStr, imdbstr)
        if r == 201:
            return jsonify({'Download': True}), 201
        else:
            abort(jsonify(message="failed add qbit"))            
    else:
        # print("DRYRUN: " + request.json['torname'])
        print("DRYRUN: " + request.json['torname'] +
              "\n" + request.json['downloadlink'])
        return jsonify({'DRYRUN': True}), 205


@app.route('/api/checkdupeonly', methods=['POST'])
@auth.login_required
def jsApiCheckDupe():
    if not request.json or 'torname' not in request.json:
        abort(jsonify(message="torname not found"))
    if checkMediaDbNameDupe(request.json['torname']):
        return jsonify({'Dupe': 'name'}), 202
    imdbstr = ''
    if 'imdbid' in request.json and request.json['imdbid']:
        imdbstr = request.json['imdbid'].strip()

    r = checkMediaDbTMDbDupe(request.json['torname'], imdbstr)
    if r != 201:
        return jsonify({'TMDb Dupe': False}), r
    return jsonify({'No Dupe': True}), 201


def requestPtPage(pageUrl, pageCookie):
    cookie = SimpleCookie()
    cookie.load(pageCookie)
    cookies = {k: v.value for k, v in cookie.items()}
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        'User-Agent':
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36 Edg/109.0.1518.78",
        'Content-Type': 'text/html; charset=UTF-8'
    }

    try:
        r = pyrequests.get(pageUrl, headers=headers, cookies=cookies, timeout=15)
        # print(r.encoding, r.apparent_encoding)
        # utf-8 Windows-1254
        # 'ISO-8859-1' utf-8
        r.encoding = 'utf-8'
        # r.encoding = r.apparent_encoding
    except:
        return ''

    return r.text


class TorrentCache(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    addedon = db.Column(db.DateTime, default=datetime.now)
    site = db.Column(db.String(32))
    searchword = db.Column(db.String(64))
    tortitle = db.Column(db.String(256))
    infolink = db.Column(db.String(256))
    subtitle = db.Column(db.String(256))
    downlink = db.Column(db.String(256))
    taggy = db.Column(db.Boolean)
    tagzz = db.Column(db.Boolean)
    imdbstr = db.Column(db.String(16))
    imdbval = db.Column(db.Float, default=0.0)
    doubanval = db.Column(db.Float, default=0.0)
    doubanid = db.Column(db.String(16))
    seednum = db.Column(db.Integer)
    downnum = db.Column(db.Integer)
    torsizestr = db.Column(db.String(16))
    tordate = db.Column(db.DateTime)
    dlcount = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'addedon': self.addedon,
            'site': self.site,
            'searchword': self.searchword,
            'tortitle': self.tortitle,
            'infolink': getfulllink(self.site, self.infolink),
            'subtitle': self.subtitle,
            'downlink': self.downlink,
            'taggy': self.taggy,
            'tagzz': self.tagzz,
            'imdbstr': self.imdbstr,
            'imdbval': self.imdbval,
            'doubanval': self.doubanval,
            'seednum': self.seednum,
            'downnum': self.downnum,
            'torsizestr': self.torsizestr,
            'tordate': self.tordate,
            'dlcount': self.dlcount,
        }


@app.route('/api/searchresult')
@auth.login_required
def searchResultData():
    query = TorrentCache.query

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            TorrentCache.tortitle.like(f'%{search}%'),
            TorrentCache.subtitle.like(f'%{search}%'),
        ))
    else:
        col1search = request.args.get('columns[1][search][value]')
        if col1search:
            query = query.filter(TorrentCache.searchword == col1search)
    total_filtered = query.count()

    # sorting
    order = []
    i = 0
    while True:
        col_index = request.args.get(f'order[{i}][column]')
        if col_index is None:
            break
        col_name = request.args.get(f'columns[{col_index}][data]')
        if col_name not in ['tortitle', 'site', 'seednum', 'tordate']:
            col_name = 'id'
        descending = request.args.get(f'order[{i}][dir]') == 'desc'
        col = getattr(TorrentCache, col_name)
        if descending:
            col = col.desc()
        order.append(col)
        i += 1
    if order:
        query = query.order_by(*order)

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    # response
    return {
        'data': [tor.to_dict() for tor in query],
        'recordsFiltered': total_filtered,
        'recordsTotal': TorrentCache.query.count(),
        'draw': request.args.get('draw', type=int),
    }


def remove_non_ascii(string):
    return ''.join(char for char in string if ord(char) < 128)


def striptag(titlestr):
    s = titlestr.replace('\n', '').strip()
    # s = re.sub(r'\[?(国语|中字|官方|禁转|原创)\]?', '', s)
    s = re.sub(r'\[?Checked by \w+\]?', '', s)
    return s


# xpath method


def xpathGetElement(row, siteJson, key):
    if not siteJson:
        return ''
    if key not in siteJson:
        return ''
    eleJson = siteJson[key]
    if not isinstance(eleJson, str):
        elestring = row.xpath(eleJson["path"])
        if elestring and "method" in eleJson:
            if eleJson["method"] == "re_imdb":
                m = re.search(r'title/(tt\d+)', elestring, re.I)
                return m[1] if m else ''
            elif eleJson["method"] == "re_douban":
                m = re.search(r'subject/(\d+)', elestring, re.I)
                return m[1] if m else ''
            elif eleJson["method"] == "ssd_imdb":
                m = re.search(r'search=(\d+)&search_area=4', elestring, re.I)
                return m[1] if m else ''
            elif eleJson["method"] == "ssd_douban":
                m = re.search(r'search=(\d+)&search_area=5', elestring, re.I)
                return m[1] if m else ''
            elif eleJson["method"] == "ttg_seednum":
                m = re.search(r'(\d+)\s*/\s*\d+', elestring, re.I)
                return m[1] if m else ''
            elif eleJson["method"] == "ttg_downum":
                m = re.search(r'\d+\s*/\s*(\d+)', elestring, re.I)
                return m[1] if m else ''

        return ''
    else:
        if not eleJson.strip():
            return ''
        return row.xpath(eleJson)



def matchIMDbid(str):
    return True if re.match(r'tt\d+', str.strip(), re.I) else False

def xpathSearchPtSites(sitehost, siteCookie, seachWord):
    r = siteconfig.loadSiteConfig()
    if r:
        PT_SITES = r["sites"]
    else:
        return -1  # site not configured

    cursite = next((x for x in PT_SITES if x["site"] == sitehost), None)
    if not cursite:
        return -1  # site not configured

    if matchIMDbid(seachWord):
        pturl = cursite['searchIMDburl']+seachWord
    else:    
        pturl = cursite['searchurl']+seachWord

    hosturl = '{uri.scheme}://{uri.netloc}/'.format(uri=urlparse(pturl))
    passkey = ''
    # if "passkey" in cursite:
    #     ucpJson = cursite["passkey"]
    #     if "usercp" in ucpJson and "keypath" in ucpJson:
    #         usercpurl = hosturl + ucpJson["usercp"]
    #         usercpdoc = requestPtPage(usercpurl, siteCookie)
    #         if not usercpdoc:
    #             return 404
    #         usercplh = lxml.html.fromstring(usercpdoc)
    #         passkey = usercplh.xpath(ucpJson["keypath"])
    #         passkey = remove_non_ascii(passkey)

    doc = requestPtPage(pturl, siteCookie)
    if not doc:
        return -1  # page not fetched

    htmltree = lxml.html.fromstring(doc)
    torlist = htmltree.xpath(cursite["torlist"])
    count = 0
    for row in reversed(torlist):
        title = xpathGetElement(row, cursite, "tortitle")
        if not title:
            continue
        dbitem = TorrentCache()
        dbitem.tortitle = title
        dbitem.infolink = xpathGetElement(row, cursite, "infolink")

        # TODO: add passkey for downlink
        dbitem.downlink = xpathGetElement(row, cursite, "downlink")

        dbitem.subtitle = xpathGetElement(row, cursite, "subtitle")
        if dbitem.subtitle:
            # dbitem.subtitle = dbitem.subtitle.removeprefix(dbitem.tortitle)
            dbitem.subtitle = striptag(dbitem.subtitle)

        dbitem.tagzz = True if xpathGetElement(
            row, cursite, "tagzz") else False
        dbitem.taggy = True if xpathGetElement(
            row, cursite, "taggy") else False
        dbitem.doubanval = tryFloat(xpathGetElement(row, cursite, "doubanval"))
        dbitem.imdbval = tryFloat(xpathGetElement(row, cursite, "imdbval"))
        dbitem.imdbstr = xpathGetElement(row, cursite, "imdbstr")
        if dbitem.imdbstr and not dbitem.imdbstr.startswith('tt'):
            dbitem.imdbstr = 'tt' + dbitem.imdbstr.zfill(7)
        dbitem.doubanid = xpathGetElement(row, cursite, "doubanid")
        dbitem.seednum = tryint(xpathGetElement(row, cursite, "seednum"))
        dbitem.downnum = tryint(xpathGetElement(row, cursite, "downnum"))
        dbitem.torsizestr = xpathGetElement(row, cursite, "torsize")
        tordatestr = xpathGetElement(row, cursite, "tordate")
        dbitem.tordate = datetime.strptime(tordatestr, "%Y-%m-%d %H:%M:%S")

        dbitem.site = sitehost
        dbitem.searchword = seachWord

        # print(dbitem.__dict__)
        count += 1
        db.session.add(dbitem)
        db.session.commit()

    return count


@app.route('/ptsearch', methods=['GET'])
@auth.login_required
def ptSearch():
    # form = PtSearchForm(request.form)
    sitelist = PtSite.query
    MAX_SEARCH_WORD = 100

    wordlist = []
    for idx, x in enumerate(db.session.query(TorrentCache.searchword).distinct()):
        if idx < MAX_SEARCH_WORD:
            wordlist.append(x.searchword)
        else:
            clearOldResults(x.searchword)
            x.delete()
            db.session.commit()

    return render_template('ptsearch.html', sites=sitelist, wordlist=wordlist)

def clearOldResults(searchword):
    ds = db.session.query(TorrentCache).filter(TorrentCache.searchword == searchword)
    ds.delete(synchronize_session=False)
    db.session.commit()
    # d = TorrentCache.delete().where(TorrentCache.searchword == searchword)
    # d.execute()

@app.route('/api/ptsearch', methods=['POST'])
def apiPtSearch():
    if request.method == 'POST':
        r = request.get_json()

        sitehost = r["site"]
        ptcookie = getSiteCookie(sitehost)
        clearOldResults(r["searchword"])
        resultCount = xpathSearchPtSites(sitehost, ptcookie, r["searchword"])
        if resultCount > 0:
            dbsite = PtSite.query.filter(PtSite.site == sitehost).first()
            dbsite.lastResultCount = resultCount
            db.session.commit()

    return json.dumps({'site':sitehost, 'resultCount': resultCount}), 200, {'ContentType': 'application/json'}


def getSiteCookie(sitehost):
    dbsiteitem = PtSite.query.filter(PtSite.site == sitehost).first()
    if not dbsiteitem:
        return ''
    return dbsiteitem.cookie


def getfulllink(sitehost, rellink):
    if rellink.startswith('http'):
        return rellink
    if rellink.startswith('/'):
        rellink = rellink[1:]

    r = siteconfig.loadSiteConfig()
    if r:
        PT_SITES = r["sites"]
    else:
        return ''  # site not configured

    cursite = next((x for x in PT_SITES if x["site"] == sitehost), None)
    if not cursite:
        return ''  # site not configured

    hosturl = '{uri.scheme}://{uri.netloc}/'.format(
        uri=urlparse(cursite['searchurl']))
    return hosturl + rellink


@app.route('/dlresult/<cacheid>')
@auth.login_required
def resultDownload(cacheid):
    dbcacheitem = TorrentCache.query.get(cacheid)

    infolink = getfulllink(dbcacheitem.site, dbcacheitem.infolink)
    downlink = getfulllink(dbcacheitem.site, dbcacheitem.downlink)
    sitecookie = getSiteCookie(dbcacheitem.site)
    if not dbcacheitem.imdbstr:
        imdbstr = ''
        if sitecookie:
            doc = fetchInfoPage(infolink, sitecookie)
            if doc:
                imdbstr = parseInfoPageIMDbId(doc)
                dbcacheitem.imdbstr = imdbstr
    siteIdStr = genrSiteId(infolink, dbcacheitem.imdbstr)

    # if not checkMediaDbNameDupe(dbcacheitem.title):
    r = addTorrentViaPageDownload(downlink, sitecookie, siteIdStr, dbcacheitem.imdbstr)
    if r == 201:
        dbcacheitem.dlcount += 1
        db.session.commit()
    return redirect("/ptsearch")


class PtSite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    addedon = db.Column(db.DateTime, default=datetime.now)
    last_update = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now)
    site = db.Column(db.String(32))
    cookie = db.Column(db.String(1024))
    siteNewLink = db.Column(db.String(256))
    siteNewCheck = db.Column(db.Boolean)
    lastSearchCheck = db.Column(db.Boolean)
    lastResultCount = db.Column(db.Integer)

    def to_dict(self):
        return {
            'id': self.id,
            'last_update': self.last_update,
            'site': self.site,
            'cookie': self.cookie,
            'lastResultCount': self.lastResultCount,
        }


class PtSiteForm(Form):
    site = SelectField(u'选择站点', choices=[
                       ('pterclub', 'PTerClub'), ('chdbits', 'CHDBits'), ('audiences', 'Audiences')])
    cookie = StringField('Cookie')
    internlink = StringField('官种链接')
    submit = SubmitField("添加")


@app.route('/sites',  methods=['POST', 'GET'])
@auth.login_required
def sitesConfig():
    r = siteconfig.loadSiteConfig()
    if r:
        PT_SITES = r["sites"]
    else:
        abort(403)

    form = PtSiteForm(request.form)
    form.site.choices = [(row["site"], row["site"]) for row in PT_SITES]
    return render_template('ptsites.html', form=form)


@app.route('/api/savesearch',  methods=['POST', 'GET'])
@auth.login_required
def apiSaveSearch():
    if request.method == 'POST':
        r = request.get_json()
        sitelist = r['sitelist']
        dbsitelist = PtSite.query
        for dbsite in dbsitelist:
            dbsite.lastSearchCheck = dbsite.site in sitelist
            db.session.commit()
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


@app.route('/api/sitesetting/',  methods=['GET', 'POST'])
def apiGetSiteSetting():
    if request.method == 'POST':
        r = request.get_json()
        sitehost = r['site']
        if '选择站点' in sitehost:
            abort(jsonify(message="not for this"))

        exists = db.session.query(PtSite.id).filter_by(
            site=sitehost).first() is not None
        if not exists:
            dbsite = PtSite(site=r['site'], cookie=r['cookie'])
        else:
            dbsite = PtSite.query.filter(PtSite.site == sitehost).first()
            dbsite.cookie = r['cookie']
        db.session.add(dbsite)
        db.session.commit()
        return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}

    if request.method == 'GET':
        sitehost = request.args.get('site')
        op = request.args.get('op')
        if not sitehost:
            abort(jsonify(message="site not found"))

        if sitehost.isdigit():
            dbsite = PtSite.query.get(sitehost)
        else:
            dbsite = PtSite.query.filter(PtSite.site == sitehost).first()
        if not dbsite:
            return json.dumps({'cookie': ''}), 200, {'ContentType': 'application/json'}

        if op == 'delete':
            db.session.delete(dbsite)
            db.session.commit()
        
        return json.dumps({'site': dbsite.site, 'cookie': dbsite.cookie}), 200, {'ContentType': 'application/json'}



@app.route('/api/sitelistdata')
@auth.login_required
def apiSitesData():
    query = PtSite.query

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            PtSite.site.like(f'%{search}%'),
        ))
    total_filtered = query.count()

    # sorting
    order = []
    i = 0
    while True:
        col_index = request.args.get(f'order[{i}][column]')
        if col_index is None:
            break
        col_name = request.args.get(f'columns[{col_index}][data]')
        if col_name not in ['site', 'last_update']:
            col_name = 'last_update'
        descending = request.args.get(f'order[{i}][dir]') == 'desc'
        col = getattr(PtSite, col_name)
        if descending:
            col = col.desc()
        order.append(col)
        i += 1
    if order:
        query = query.order_by(*order)

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    # response
    return {
        'data': [x.to_dict() for x in query],
        'recordsFiltered': total_filtered,
        'recordsTotal': PtSite.query.count(),
        'draw': request.args.get('draw', type=int),
    }



def rssJob(id):
    with app.app_context():
        task = RSSTask.query.filter(RSSTask.id == id).first()
        if task:
            # print('Runing task: ' + task.rsslink)
            prcessRssFeeds(task)


def startApsScheduler():
    with app.app_context():
        tasks = RSSTask.query
        for t in tasks:
            if not scheduler.get_job(str(t.id)):
                print(t.rsslink)
                job = scheduler.add_job(rssJob, 'interval',
                                        args=[t.id],
                                        minutes=t.task_interval,
                                        next_run_time=datetime.now(),
                                        id=str(t.id))
                if t.active == 2:
                    job.pause()

    scheduler.start()
    scheduler.print_jobs()


def runRcp(torpath, torhash, torsize, tortag, savepath, tmdbcatid):
    if (myconfig.CONFIG.apiRunProgram == 'True') and (myconfig.CONFIG.dockerFrom != myconfig.CONFIG.dockerTo):
        if torpath.startswith(myconfig.CONFIG.dockerFrom) and savepath.startswith(myconfig.CONFIG.dockerFrom):
            torpath = torpath.replace(
                myconfig.CONFIG.dockerFrom, myconfig.CONFIG.dockerTo, 1)
            savepath = savepath.replace(
                myconfig.CONFIG.dockerFrom, myconfig.CONFIG.dockerTo, 1)

    import rcp
    return rcp.runTorcp(torpath, torhash, torsize, tortag, savepath, insertHashDir=False, tmdbcatidstr=tmdbcatid)


def loadArgs():
    parser = argparse.ArgumentParser(
        description='TORCP web ui.')
    parser.add_argument('-C', '--config', help='config file.')
    parser.add_argument('-G', '--init-password',
                        action='store_true', help='init pasword.')
    parser.add_argument('--no-rss',
                        action='store_true', help='do not start rss tasks')

    global ARGS
    ARGS = parser.parse_args()
    if not ARGS.config:
        ARGS.config = os.path.join(os.path.dirname(__file__), 'config.ini')


def main():
    loadArgs()
    initDatabase()
    if not ARGS.no_rss:
        startApsScheduler()
    myconfig.readConfig(ARGS.config)
    if ARGS.init_password:
        myconfig.generatePassword(ARGS.config)
        return
    if not myconfig.CONFIG.basicAuthUser or not myconfig.CONFIG.basicAuthPass:
        print('set user/pasword in config.ini or use "-G" argument')
        return
# https://stackoverflow.com/questions/14874782/apscheduler-in-flask-executes-twice
    app.run(host='0.0.0.0', port=5006, debug=True, use_reloader=False)


if __name__ == '__main__':
    main()
