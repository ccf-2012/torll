# TORLL aka TORCP ui
1. 以 web ui 形式设置 torcp，查看所处理的条目
2. 三类方式发起受管理的下载，即下载时收集管理种子的信息，以准确生成媒体库条目：
   1. `RSS` - 大家熟知的rss链接，后台运行，根据预设条件进行筛选下载
   2. 在torll `站点` 和 `搜索` 界面中，以统一的方式浏览各站种子，以TMDb/标题搜索，手动发起下载
   3. 在各pt站点页面以 torfilter 油猴插件对站点页面进行各类规则过滤、查重及发起下载
3. 管理媒体库中各条目信息，包括所有种子的源站链接、媒体条目入库位置等，如果有识别错误的条目，通过界面可以进行人工修正
   
* **注意：若本服务在非私有的网络中运行，须万分注意防护**



## 安装
### 下载及配环境
```sh
git clone https://github.com/ccf-2012/torll.git
cd torll
pip install -r requirements.txt
```

### 启动
* 首次使用需要加参数 `-G` 生成一个用户名密码
```sh
python3 app.py -G
```
* 记下用户名密码，再次以无参数启动
```sh
python3 app.py
```
> 你可以打开 `config.ini` 查看和修改密码。需要注意的是如果这里密码改了，在 qBit 中的种子完成后命令和 `torfilter` 代码中也要相应修改

* 启动成功后，浏览器打开 `http://server.ip:5006/` 以上面生成的用户名密码登录后使用。


### tocp相关的设置
#### 设置 torcp 参数

* 在影视种子下载完成后调用 torcp 进行处理时的参数，包括硬链/软链目标目录，TMDb的api key以及语言，Emby/Plex 括号后缀等；
* 软链(symbolink) 在Emby/Plex中播放以及在qBit中维持作种，都是可行的；但如果删除了源文件/目录，则链接就会失效，这一点与硬链不同，硬链就如同两个分别的文件，删掉任意一个都不影响；
* 括号后缀是指，生成的文件夹在交给 Emby/Plex 来收录库中时，通过后缀直接确定媒体；
* TMDb 语言决定生成的文件名是中文还是英文；


![torcp setting](https://ptpimg.me/tl68x6.png)


> 还有一些设置仅在`config.ini` 中体现，比如在生成媒体库时生成一个年份目录

#### 设置 qBittorrent 
* 设置 qbit 的 主机ip，端口，用户名，密码
* 设置 qbit 完成后直接运行脚本，有两种方式运行torcp，1. 直接以 API 调用方式 2. 调用rcp.sh脚本方式；
![qb setting](https://ptpimg.me/otvack.png)

* 两种方式作一下解说：
##### API 方式
* 若 qbit 在 docker 中运行，则以 API 形式处理较简单；
* 以 API 形式调用的将在 torll 所理解的目录中进行处理，若 qBit 在docker中，则须设置映射将docker中的路径转换为 torll 所识别的路径；
* 在保存设置时，软件会在 qbit 中设置种子完成后执行的命令；形如：
```sh
curl -u admin:password -d torhash=%I http://192.168.5.6:5006/api/torcp2 
```
> 其中的 admin 和 password 就是前面安装时所设的用户名密码
* torll 的 API 将完成对种子文件的链接处理，任务就此结束。
##### rcp.sh 方式
* 若设置 qBit 完成后运行脚本，则可以实现较为复杂的操作，例如上传 gd 盘以及通知 Plex 更新等，脚本名为 `rcp.sh`，webui 中提供了在线编辑代码的功能
* 在脚本中通常使用 `rcp.py` 完成对 qBit 中种子文件的处理，其中会使用 torcp 的处理机制和 torll 中的设置；调用 `rcp.sh` 所需要的参数可以只是一个 `-I` 指向 qBit 中种子的 hash;
* 若 qBit 在 docker 中运行，要使用脚本方式进行处理，需要在 docker 中安装 requirements.txt 中的依赖；参考 [torcp中的介绍](https://github.com/ccf-2012/torcp/blob/main/qb%E8%87%AA%E5%8A%A8%E5%85%A5%E5%BA%93.md#3-qbit%E4%BB%A5docker%E5%AE%89%E8%A3%85)

1. 简单的例子，种子完成后直接在本地硬盘上作硬链：
```sh
#!/bin/bash
# qbit 中设置完成后命令为：/home/ccf2013/torll/rcp.sh "%I"
python3 /home/ccf2013/torll/rcp.py  -I "$1" >>/home/ccf2013/rcp2.log 2>>/home/ccf2013/rcp2e.log
```

2. 种子完成后，在暂存目录中建立硬链，调用 rclone 上传 gd 盘，之后删除
```sh
#!/bin/bash
# qbit 中设置完成后命令为：/home/ccf2013/torll/rcp.sh "%I"
python3 /home/ccf2013/torll/rcp.py  --hash-dir -I "$1" >>/home/ccf2013/rcp2.log 2>>/home/ccf2013/rcp2e.log
sleep 5
gclone copy "/home/ccf2013/emby/$1/"  gd1:/media/148/emby/ 
sleep 100
rm -rf "/home/ccf2013/emby/$1/"
```
* 使用 `--hash-dir` 参数，将在目标目录，先建立一个以种子 hash 值为名的暂存目录，在其中生成目标链接，此目标在上传完成后将被删除
* 有一些 qbit 客户端在种子完成后输出参数时，会出现文件名丢失中文的现象，以 `rcp.py` 可仅使用 `%I` 参数完成任务，从而避免这一问题

----
## 浏览、查找站点种子及下载
* 主要有3种方式下载种子并完成整体的刮削处理流程
   1. `RSS` - 大家熟知的rss链接，长期后台运行，根据预设条件进行筛选下载
   2. 在torll `站点` 和 `搜索` 界面中，以统一的方式浏览各站种子，通过TMDb/标题搜索，手动点击发起下载
   3. 在各站点页面以 torfilter 油猴插件对站点页面进行各类规则过滤、查重及发起下载

* 以上述这些方式添加种子时，会在qBit中生成一些特征数据，以便在后续进行准确的处理：
  1. 生成 site_id 形式的保存目录： torll 在处理 qBit 中的种子，对 `site_id_imdb` 形式目录保存的种子，如 'pter_87424_tt0075329'，将会识别其中的源站信息和IMDb。这样的目录，有利于追溯查阅信息和保种续种(Credit to @boomPa)。
  2. 可以在 `config.ini` 设置 `[AUTO_CATEGORY]` ，对不同特征的种子标题，按正则进行分类；不同的分类可以依 `[CATEGORY_DIR]` 分存到不同目录; （示例见后）


### RSS 方式下载
* 在RSS任务列表，新建RSS任务，填写 rss 链接、站点cookie，运行间隔
* 可以设置过滤标题，内容包含或不含哪些内容，以正则表示
* 在RSS记录列表，可以看到各rss条目，哪些接收，哪些未收，未收会有原因
* 未收的可以点击下载手工加入下载器
* 任务列表中，可以对单条任务手工发起检查，可以暂停任务


### 在 torll 中浏览站点种子列表
* 站点-站点配置，选择站点，设置 cookie 和 种子列表链接 (站新链接)
* 当前支持 pter, chd, aud, ob, rl, hds, frds, ssd, ttg, ~~mteam~~, tlf, hdh, pth, tju, hh, ~~beitai~~, ~~hdc~~, ~~hares~~, hdfans, soulvoice, hdtime, discfan, btschool, ptsbao, piggo, ~~hddolby~~ 站
* 可以在自己本地的PC机上运行 postcookie  从本地机器上获取cookie，并上传到运行 torll 的 server
* 在站点配置中，可以设置自动定时获取各站新种
* 获取过各站新种 ( `站新` )后，即可在站点页面中浏览和发起下载
![站新](https://ptpimg.me/4q6430.png)

### 在 torll 中查找下载
* 在上述站点配置完成后，可以直接选取某几个站点，输入关键字，发起搜索
* 搜索结果可以发起下载


### 通过 torfilter 下载
使用 [github 上的代码](https://github.com/ccf-2012/torfilter)，修改 `torfilter.js` 以下2部分：
1. 在头部的 `@connect` 部分，大约在12行：
```js
// @connect      192.168.5.6
```

2. 代码 UserScript 一开始，约在44行，设置地址、用户名和密码：
```js
const API_SERVER = 'http://192.168.5.6:5006';
const API_AUTH_USER = "admin";
const API_AUTH_PASS = "password";
```

即可定向到所设地址，如上例中的 192.168.5.6，去进行查重和发起下载，其中用户名密码为 torll 中的登陆密码。

----
## RSS CLI 
> 命令行形式运行 rss 命令，在 web 页面观察记录

### 设置 RSS
* 以 `rssconfig.json.sample` 为样本编辑形成 `rssconfig.json` 文件
```sh
cp rssconfig.json.sample rssconfig.json
```
* 其中条目形如:
```json
{
  "rsstasks": [
    {
      "name": "华语最佳", // 用于标识，要求本配置文件内唯一
      "site": "expample",  // 站点id 应于siteconfig.json名字对应
      "rss_url": "https://example.club/torrentrss.php?rows=10&linktype=dl&passkey=somepasskey",
      "cookie": "c_secure_pass=....",
      "qb_category": "", // 此rss收进下载器的种子全部添加某特定标识
      "filters": [
        {
          "detail_regex": "最佳男主角",  // 要求在种子信息详情页中能匹配 字串 或 正则
          "title_not_regex": "Hello",   // 要求在种标题中 不 匹配 字串 或 正则
          "subtitle_not_regex": "Test",  // 要求在种子副标题 不 匹配 字串 或 正则
          "size_gb_min": "2",       // 要求种子大小大于 2GB
          "size_gb_max": "12"       // 要求种子大小小于 12GB
        }
      ]
    }, // 可以写多个
    {
      "name": "Another动漫专线",
      "rss_url": "https://another.top/torrentrss.php?passkey=abcdefgh&rows=30&linktype=dl",
      "site": "another",
      "cookie": "c_secure_uid=;",
      "qb_category": "动漫专线",
      "filters": [
        {
          "title_regex": "S\\d+E\\d+",
          "subtitle_regex": "第\\d+集"
        }
      ]
    }
  ]
}
```

### 运行
* 直接运行
```sh
python3 rsscli.py
```
* 也可放入 crontab 中定时运行

### 观察记录
* 在 torll 上 RSS 页面可观察到 rss 的记录，收录的和未收的，未收的会显示原因

  
----
## 影视库
* 当积累了较多种子，toll 可以方便在查找种子标题，存储路径，可以点击链接到源站查看信息，也可以方便地查看TMDb, IMDb
![影视库](https://ptpimg.me/6538cc.png)

### 修正

* 如果发现匹配错误的条目，可以点击 `修正` ，以新输入的 TMDb 分类和 id 作 torcp `--move-run` 
* 如果所下载的种子已经传到 GD 盘，可以将 GD 盘 mount 到本地，这里输入 mount 后的媒体库的根目标路径，其在 `config.ini` 中对应
```ini
[TORCP]
mbrootdir = /gd124/media/148/emby
```
![修正匹配](https://ptpimg.me/218uav.png)

### 删除
* 从torll 中删除当前的记录
* 如果媒体文件是在本地的，链接目录存在，则同时**删除所链接的目录**
* 如果媒体文件在gd盘，则不会删除
* 注意`config.ini` 中 `[TORCP]`段中，`linkdir` 指向的是本地链接目录，而 `mbrootdir` 指向云盘 mount 在本地的位置
> 初始时这两值为一样，因此在第一次修改前或手工修改 config.ini 前，媒体指向的位置是不对的


# 一些辅助工具

## postcookie  从本地机器上获取cookie，并上传到自己的 server
* 修改 `postcookie.py` 中以下几行
```
TORLL_SERVER = 'http://127.0.0.1:5006'
TORLL_USER = 'admin'
TORLL_PASS = 'server_pass'
```
* 然后运行：
```sh
python3 postcookie.py
```

## 手工将qBit中的种子提交torll处理
* 在 torll 中已正确设置 qBit 的情况下，可以手工将 qBit 中的种子提交 torll 处理。此命令可在任何能连上 torll 的机器上发起，即所有操作是由 torll 完成。
* torll 接收网络API请求，到 qBit 中找到种子，取出所需信息进行处理，例：
```sh
curl -u admin:password -d torhash=种子hash_bc9f857cc8d721ed5d8ea672d http://192.168.5.6:5006/api/torcp2 
```

* 也可以在控制台上手工运行 `rcp.py` 完成任务。
  * 若种子还在 qBit 中，则在 torll 中已正确设置的情况下，仅接收种子的 `%I` (种子hash) 即可工作，通过到 qbit 上查找相关种子取得所需的信息，调用 torcp 完成处理。
  * 手工运行 rcp.py 的种子，信息也会存入数据库中，torll 中可以查看。 例：
```sh
python3 rcp.py -I hashcode_bc9f857cc8d721ed5d8ea672d
```

> 对于原 torcp 用户，这个 torll 要求 torcp 版本 >= 0.60 的依赖，torcp 在此版后改写了结构以支持外部代码传参及调用执行；原有的功能和使用方式仍然不受影响，即如果原来有脚本在使用 torcp 跑，即使更新到了新版，也应能继续完成任务；


----

## 通知Plex更新 notify_plex.py 
* 对于 gd 盘，Plex 无法感知有文件变动
* 所以当新的文件（夹）添加进了媒体库时，可以使用 `notify_plex.py` 通知Plex Server进行更新
* 所需要的参数也同样，仅需要用种子的 hash 值即可
* 在 `config.ini` 中应有 Plex Server 的相应设置，即：
```ini
[PLEX]
server_url = http://192.168.5.6:32400
; 取得Plex token的步骤： https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/
server_token = your-PLEX_token
rootdir = /gd1/media/plex/
```


* 在 `config.ini` 中编辑 Plex Section和文件路径的对应，如：
* 一个section可以包含多个目录，如：
```ini
[PLEX_SECTION]
剧集 = TV/other, TV/cn, TV/ja, TV/ko
电影 = Movie/other, Movie/cn, Movie/ja, Movie/ko
儿童剧集 = TV/动画
纪录剧集 = TV/纪录
纪录电影 = Movie/纪录
动画电影 = Movie/动画
```

* 使用
```
$ python3 notify_plex.py -h
usage: notify_plex.py [-h] -I INFO_HASH [-C CONFIG]

Notify plex server to add a file/folder.

optional arguments:
  -h, --help            show this help message and exit
  -I INFO_HASH, --info-hash INFO_HASH
                        info hash of the torrent.
  -C CONFIG, --config CONFIG
                        config file.
```

* 例：
```
$ python3 notify_plex.py -I 5c23a9a2e36145f994029bf2871ce63e37d59ea5
Movie/ko/Fukuoka (2020) {tmdb-576112}
```


## 满足不同规则，分存到不同目录
* 在各种下载发起的方式（torfilter推送、搜索、RSS）下，可以设置自动分类，在启动下载时给种子设置不同category 并针对不同category，可以设置存储到不同目录
* 其规则和对应目录，可在 `config.ini` 中设置，形如：

```ini
[AUTO_CATEGORY]
单集 = S\d+E\d+

[CATEGORY_DIR]
单集 = /volume1/video/downloads/tv_未完结
```

----

## 导入 Emby/Plex库中原有的影视条目
* 导入现有Emby/Plex媒体库中的条目，可以便于查重。
* 即：如果一个片子已经在库中有了，在 rss 以及 torfilter 中批量处理时碰到其它同 TMDb 种子，即使名字不同，也将跳过不下载；

1. 在 `config.ini` 中加入 Emby 或 Plex 的设置，如：
* Emby
```ini
[EMBY]
server_url = http://192.168.5.6:8096
user = test
pass = test
```
> Emby 当前假设媒体根目录为 torcp 的目标根目录，即直接链接的场景，后续再看

* Plex
```ini
[PLEX]
server_url=http://192.168.5.6:32400
; 取得Plex token的步骤： https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/
server_token=your-PLEX_token
rootdir = /gd1/media/plex/
```

2. 运行 `loadmb.py` 
```sh
python3 loadmb.py --init-library
```
* 如果要清除库中条目，全部新建，则加 `--empty` 参数

## 使用 loadqb.py 将 qBit 中的种子导入库中
* 如果 qBit 中已经有一些以 site-id 形式存储的种子，将它们导入库中，可便于查重和管理
* 同样，要求在 torll 中已正确设置 qBit
* 当前代码是仅找出保存路径带有 site_id 特征的种子进行处理，可根据自己需要作调整

```sh
python3 loadqb.py
```

----

# sqlite table
```sh
# upload db.sqlite to server as db3.sqlite
sqlite3 db.sqlite "drop table pt_site; drop table site_torrent; drop table  torrent_cache;"
sqlite3 db3.sqlite ".dump pt_site" | sqlite3 db.sqlite
sqlite3 db3.sqlite ".dump site_torrent" | sqlite3 db.sqlite
sqlite3 db3.sqlite ".dump torrent_cache" | sqlite3 db.sqlite
```

---
to be cont.

