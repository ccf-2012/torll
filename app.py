# curl -i -H "Content-Type: application/json" -X POST -d '{"torpath" : "~/torccf/frds_10018_tt6710716/真探S03.2019.1080p.WEB-DL.x265.AC3￡cXcY@FRDS", "torhash": "289256b0918c3dccea51a194a3e834664b17eafd", "torsize": "11534336"}' http://localhost:5000/api/torcp

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
from wtforms import Form, StringField, RadioField, SubmitField, DecimalField, IntegerField
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
            'title' : self.title,
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
                         tmdbid=int(tmdbIdStr),
                         tmdbcat=tmdbCat,
                         location=targetDir)
        
        with app.app_context():
            db.session.add(t)
            db.session.commit()


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
    tmdbcatid = StringField('修改TMDb以重新查询和生成硬链, 分类和id的写法可以是：tv-12345，movie-12345，m12345')
    # tmdbid = StringField('TMDb id')
    submit = SubmitField("保存设置")


def parseTMDbStr(tmdbstr):
    if tmdbstr.isnumeric():
        return '', tmdbstr
    m = re.search(r'(m(ovie)?|t(v)?)[-_]?(\d+)', tmdbstr.strip(), flags=re.A | re.I)
    if m:
        catstr = 'movie' if m[1].startswith('m') else 'tv'
        return catstr, m[4]
    else:
        return '', ''


@app.route('/mediaedit/<id>', methods=['POST', 'GET'])
@auth.login_required
def torMediaEdit(id):
    tormedia = TorMediaItem.query.get(id)
    destDir = os.path.join(myconfig.CONFIG.linkDir, tormedia.location)

    if os.path.exists(destDir):
        warningstr = '此影视种子所链目录将被删除：%s' % (destDir)
    else:
        warningstr = '%s : 目标不存在' % (destDir)

    form = MediaItemForm(request.form)
    form.tmdbcatid.data = "%s-%d" % (tormedia.tmdbcat, tormedia.tmdbid)

    if request.method == 'POST':
        form = MediaItemForm(request.form)
        # cat, tmdbstr = parseTMDbStr(form.tmdbcatid.data)

        if os.path.exists(destDir):
            print("Deleting ", destDir)
            try:
                shutil.rmtree(destDir)
            except:
                pass
        # print("Delete complete")

        torpath, torhash2, torsize, tortag, savepath = qbfunc.getTorrentByHash(
            tormedia.torhash)
        r = runRcp(torpath, torhash2, torsize, tortag, savepath, form.tmdbcatid.data)
        
        db.session.delete(tormedia)
        db.session.commit()
        return redirect("/")

    return render_template('mediaedit.html', form=form, msg=warningstr)


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
    qbpass = StringField('qBit 密码', widget=PasswordInput(hide_value=False), validators=[DataRequired()])
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
            progstr =  'sh ' + fn + ' "%I" '
            scriptpath = os.path.dirname(__file__)
            with open(fn, 'w') as f:
                f.write(f"#!/bin/bash\npython3 {os.path.join(scriptpath, 'rcp.py')}  -I $1 >>{os.path.join(scriptpath, 'rcp2.log')} 2>>{os.path.join(scriptpath, 'rcp2e.log')}\n")
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
    sep_lang = StringField('分语言目录，以逗号分隔，将不同语言的媒体分别存在不同目录中；留空表示不分语言')
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
    form.symbolink.data = myconfig.CONFIG.symbolink
    msg = ''
    if request.method == 'POST':
        form = SettingForm(request.form)
        myconfig.updateConfigSettings(ARGS.config,
                                      linkDir=form.linkdir.data,
                                      bracket=form.bracket.data,
                                      tmdbLang=form.tmdb_lang.data,
                                      lang=form.sep_lang.data,
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
            rcpsh_file = f.read()
    else:
        rcpsh_file = ''
    msg = ''
    if request.method == 'POST':
        rcpsh_file = request.form['config_file']
        with open(fn, 'w') as f:
            f.write(str(rcpsh_file))
        msg = "success"

    return render_template('editrcp.html', config_file=rcpsh_file, msg=msg)


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
        r.encoding = r.apparent_encoding
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
                        infoLink = item.link,
                        downloadLink = item.links[1]['href'],
                        size = item.links[1]['length'])

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
                    dbrssitem.reason = "IMDb: %s, douban: %s" % (imdbval, doubanval)
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
        abort(400)

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
            abort(400)
    else:
        # print("DRYRUN: " + request.json['torname'])
        print("DRYRUN: " + request.json['torname'] + "\n" + request.json['downloadlink'])
        return jsonify({'DRYRUN': True}), 205


@app.route('/api/checkdupeonly', methods=['POST'])
@auth.login_required
def jsApiCheckDupe():
    if not request.json or 'torname' not in request.json:
        abort(400)
    if checkMediaDbNameDupe(request.json['torname']):
        return jsonify({'Dupe': 'name'}), 202
    imdbstr = ''
    if 'imdbid' in request.json and request.json['imdbid']:
        imdbstr = request.json['imdbid'].strip()

    r = checkMediaDbTMDbDupe(request.json['torname'], imdbstr)
    if r != 201:
        return jsonify({'TMDb Dupe': False}), r
    return jsonify({'No Dupe': True}), 201


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
