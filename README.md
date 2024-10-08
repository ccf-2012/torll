# TORLL aka TORCP ui
1. 以 web ui 形式设置 torcp，查看所处理的条目
2. 如果有识别错误的条目，可在 ui 中修正
3. 可作为 torfilter 的后端，即在 pt 站上提交查重下载到 torll
4. 可设置 rss 任务，进行日常的下载，支持 TMDb 查重
5. 可搜索 pt 站上种子发起下载
* **注意：若本服务在非私有的网络中运行，须万分注意防护**


## 安装
```sh
git clone https://github.com/ccf-2012/torll.git
cd torll
pip install -r requirements.txt
```

## 启动
* 首次使用需要加参数 `-G` 生成一个用户名密码
```sh
python3 app.py -G
```
* 记下用户名密码，再次以无参数启动
```sh
python3 app.py
```
> 你可以打开 `config.ini` 查看和修改密码。需要注意的是如果这里密码改了，在 qBit 中的命令和 `torfilter` 中也要相应修改

* 启动成功后，浏览器打开 `http://server.ip:5006/` 登录后使用。


## 设置
### 设置 torcp 参数

* 在影视种子下载完成后调用 torcp 进行处理时的参数，包括硬链/软链目标目录，TMDb的api key以及语言，Emby/Plex 括号后缀等；
* 软链(symbolink) 在Emby/Plex中播放以及在qBit中维持作种，都是可行的；但如果删除了源文件/目录，则链接就会失效，这一点与硬链不同，硬链就如同两个分别的文件，删掉任意一个都不影响；
* 括号后缀是指，生成的文件夹在交给 Emby/Plex 来收录库中时，通过后缀直接确定媒体；
* TMDb 语言决定生成的文件名是中文还是英文；


![torcp setting](https://ptpimg.me/tl68x6.png)


### 设置 qBittorrent 
* 设置 qbit 的 主机ip，端口，用户名，密码
* 设置 qbit 完成后直接运行脚本，或者以 API 形式提交 torcp 处理；
![qb setting](https://ptpimg.me/otvack.png)



* 两种方式作一下解说：
#### API 方式
* 若 qbit 在 docker 中运行，则以 API 形式处理较简单；
* 以 API 形式调用的将在 torll 所理解的目录中进行处理，若 qBit 在docker中，则须设置映射将docker中的路径转换为 torll 所识别的路径；
* 在保存设置时，软件会在 qbit 中设置种子完成后执行的命令；形如：
```sh
curl -u admin:password -d torhash=%I http://192.168.5.6:5006/api/torcp2 
```
> 其中的 admin 和 password 就是前面安装时所设的用户名密码
* torll 的 API 将完成对种子文件的链接处理，任务就此结束。

#### rcp.sh 方式
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


## 在添加种子时，生成 site_id 形式的保存目录
* torll 在处理 qBit 中的种子，对 `site_id_imdb` 形式目录保存的种子，如 'pter_87424_tt0075329'，将会识别其中的源站信息和IMDb。这样的目录，有利于追溯查阅信息和保种续种(Credit to @boomPa)。
* 有三种方式可以在下载种子时生成 site_id 目录：
1. rss
2. torfilter 
3. 在torll中查找种子，发起下载

## 设置 RSS
* 在RSS任务列表，新建RSS任务，填写 rss 链接、站点cookie，运行间隔
* 可以设置过滤标题，内容包含或不含哪些内容，以正则表示
* 在RSS记录列表，可以看到各rss条目，哪些接收，哪些未收，未收会有原因
* 未收的可以点击下载手工加入下载器
* 任务列表中，可以对单条任务手工发起检查，可以暂停任务


## 使用 torfilter
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


## 在 torll 中查找
* 当前支持 pter, chd, aud, ob, hds, frds, ssd, ttg, mteam, tlf, hdh, pth, tju, hh, beitai, hdc, hares, hdfans, soulvoice, hdtime, discfan, btschool, ptsbao 站


## 各站新种
![站新](https://ptpimg.me/4q6430.png)


---
# 一些辅助工具


## 手工将qBit中的种子提交torll处理
* 在 torll 中已正确设置 qBit 的情况下，可以手工将 qBit 中的种子提交 torll 处理。此命令可在任何能连上 torll 的机器上发起，即所有操作是由 torll 完成。
* torll 接收网络API请求，到 qBit 中找到种子，取出所需信息进行处理，例：
```sh
curl -u admin:password -d torhash=种子hash_bc9f857cc8d721ed5d8ea672d http://192.168.5.6:5006/api/torcp2 
```

* 也可以在控制台上手工运行 `rcp.py` 完成任务，例：
```sh
python3 rcp.py -I hashcode_bc9f857cc8d721ed5d8ea672d
```


----

## rcp.py  
上面的脚本示例中，使用了 `rcp.py`，这是一个对 torcp 的包装，主要功能为：
1. 若种子还在 qBit 中，则在 torll 中已正确设置的情况下，仅接收种子的 `%I` (种子hash) 即可工作，通过到 qbit 上查找相关种子取得所需的信息，调用 torcp 完成处理
2. 手工运行 rcp.py 的种子，信息也会存入数据库中，torll 中可以查看


```
python3 rcp.py -h 

usage: rcp.py [-h] [-F FULL_PATH] [-I INFO_HASH] [-D SAVE_PATH] [-G TAG] [-Z SIZE] [--hash-dir] [--tmdbcatid TMDBCATID] [-C CONFIG]

wrapper to TORCP to save log in sqlite db.

options:
  -h, --help            show this help message and exit
  -F FULL_PATH, --full-path FULL_PATH
                        full torrent save path.
  -I INFO_HASH, --info-hash INFO_HASH
                        info hash of the torrent.
  -D SAVE_PATH, --save-path SAVE_PATH
                        qbittorrent save path.
  -G TAG, --tag TAG     tag of the torrent.
  -Z SIZE, --size SIZE  size of the torrent.
  --hash-dir            create hash dir.
  --tmdbcatid TMDBCATID
                        specify TMDb as tv-12345/m-12345.
  -C CONFIG, --config CONFIG
                        config file.
```

> 对于原 torcp 用户，这个 torll 要求 torcp 版本 >= 0.60 的依赖，torcp 在此版后改写了结构以支持外部代码传参及调用执行；原有的功能和使用方式仍然不受影响，即如果原来有脚本在使用 torcp 跑，即使更新到了新版，也应能继续完成任务；


## notify_plex.py 
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
; rootdir = /volume1/downloads/NAS8/
```

* 在 `config.ini` 中编辑 Plex Section和文件路径的对应，如：
```ini
[PLEX_SECTION]
中文剧集 = TV/cn
日韩剧集 = TV/ja, TV/ko
剧集 = TV/other
中文电影 = Movie/cn
电影 = Movie
动画剧集 = TV/animation
```

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
----

## 导入Emby/Plex库中的影视条目
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

# postcookie  从本地机器上获取cookie，并上传到自己的 server
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

