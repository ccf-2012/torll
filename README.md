# TORLL aka TORCP list
* 以web ui形式设置torcp，查看所处理的条目
* **注意：若本服务在非私有的网络中运行，须万分注意防护**

## 安装
```sh
git clone https://github.com/ccf-2012/torll.git
cd torll
pip install -r requirements.txt
```

## 启动
* 首次使用需要生成一个用户名密码
```sh
python3 app.py -G
```
* 记下用户名密码，再次以无参数启动
```sh
python3 app.py
```
* 启动成功后，浏览器打开 `http://server.ip:5006/` 登录后使用

## 设置
### 设置 torcp 参数
* 在影视种子下载完成后调用 torcp 进行处理时的参数，包括硬链/软链目标目录，TMDb的api key以及语言，Emby/Plex 括号后缀等；

### 设置 qBittorrent 
* 设置 qbit 的 主机ip，端口，用户名，密码
* 设置 qbit 完成后直接运行脚本，或者以 RESTful API 形式提交 torcp 处理；
  * 若 qbit 在 docker 中运行，则以API形式处理较简单；否则需要在 docker 中安装 requirements.txt 中的依赖；
  * 以 API 形式调用将在目标目录生成重组后媒体的硬链/软链，任务就此结束；
  * 直接运行脚本则是运行 `rcp.sh` ；
  * 在保存设置时，软件会在 qbit 中设置相应的命令；
* 若 qBit 在docker中，则须设置映射将docker中的路径转换为脚本所识别的路径；


### 编辑 rcp.sh 脚本
* 若qbit 完成后直接运行脚本，则可以实现较为复杂的操作，例如上传gd以及通知Plex更新等，脚本名为 `rcp.sh`，webui中提供了在线编辑代码的功能
* 简单的示例，仅作硬链：
```sh
#!/bin/bash
# qbit 中设置完成后命令为：/home/ccf2013/torll/rcp.sh "%I"
python3 /home/ccf2013/torll/rcp.py  -I "$1" >>/home/ccf2013/rcp2.log 2>>/home/ccf2013/rcp2e.log
```

* 在暂存目录中建立硬链，上传 gd 盘后删除
```sh
#!/bin/bash
# qbit 中设置完成后命令为：/home/ccf2013/torll/rcp.sh "%I"
python3 /home/ccf2013/torll/rcp.py  --hash-dir -I "$1" >>/home/ccf2013/rcp2.log 2>>/home/ccf2013/rcp2e.log
sleep 5
gclone copy "/home/ccf2013/emby/$1/"  gd1:/media/148/emby/ 
sleep 100
rm -rf "/home/ccf2013/emby/$1/"
```
> 使用 `--hash-dir` 参数，将在目标目录，先建立一个以种子 hash 值为名的暂存目录，在其中生成目标链接，此目标在上传完成后将被删除
> 有一些 qbit 客户端在种子完成后输出参数时，会出现文件名丢失中文的现象，以 `rcp.py` 可仅使用 `%I` 参数完成任务，从而避免这一问题

## 种子列表
* 当积累了较多种子，toll 可以方便在查找种子标题，存储路径，可以点击链接到源站查看信息，也可以方便地查看TMDb, IMDb
* 如果发现匹配错误的条目，可以点击 `修正` ，输入 TMDb 分类和 id ，即会重新生成目标链接
* torll 中积累的种子条目，还可以作为查重的基础，即如果一个片子已经在库中有了，碰到其它种子，即使名字不同，也将跳过不下载；配合 torfilter 可以查看站上有哪些种子自己的库中还没有



## rcp.py 
上面的脚本示例中，使用了 `rcp.py`，这是一个对 torcp 的包装，主要功能为：
1. 在 torll 中已正确设置 qBit 的情况下，仅接收种子的 `%I` (种子hash) 即可工作，通过到qb上查找相关种子取得所需的信息，调用torcp完成处理
2. 种子作了硬链处理后，信息会存在本地数据库中，torll 中可以查看


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

## API 形式
在 torll 中已正确设置 qBit 的情况下，torll 还可以接收网络API请求，到qbit中找到种子，取出所需信息进行处理，例：
```sh
curl -u admin:password -d torhash=种子hash_bc9f857cc8d721ed5d8ea672d http://192.168.5.6:5006/api/torcp2 
```


## 对于原 torcp 用户
* 这个 torll 要求 torcp 版本 >= 0.59 的依赖，即 torcp 在 v0.59 改写了结构以支持外部代码传参及调用执行；
* 原有的功能和使用方式仍然不受影响，即如果原来有脚本在使用 torcp 跑，即使更新到了 v0.58，也应能继续完成任务；


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
即可定向在所设地址上进行查重和发起下载，其中用户名密码为torll中的登陆密码。


## 导入Emby/Plex库中的影视条目
1. 在 `config.ini` 中加入 Emby 或 Plex 的设置，如：
* Emby
```ini
[EMBY]
server_url = http://192.168.5.6:8096
user = test
pass = test
```
* Plex
```ini
[PLEX]
server_url=http://192.168.5.6:32400
; 取得Plex token的步骤： https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/
server_token=your-PLEX_token
rootdir = /gd1/media/plex/
```

2. 运行 `loadmedia.py` 
```sh
python3 loadmedia.py --init-library
```


## 使用 qbpost.py 将 qBit 中的种子导入库中
* 如果 qBit 中已经有一些以site-id这样形式生成的种子，将它们导入库中，可便于查重和管理
* 同样，要求在 torll 中已正确设置 qBit
```sh
python3 qbpost.py
```

---
to be cont.

