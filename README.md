# TORDB aka TORCP UI w/ DB
* 以web ui形式设置torcp并监控下载的媒体文件被重新组织和处理
* **注意：若本服务在非私有的网络中运行，须万分注意防护**

## 安装
```sh
git clone https://github.com/ccf-2012/tordb.git
cd tordb
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

## 使用
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
# qbit 中设置完成后命令为：/home/ccf2013/tordb/rcp.sh "%I"
python3 /home/ccf2013/tordb/rcp.py  -I "$1" >>/home/ccf2013/rcp2.log 2>>/home/ccf2013/rcp2e.log
```

* 在暂存目录中建立硬链，上传 gd 盘后删除
```sh
#!/bin/bash
# qbit 中设置完成后命令为：/home/ccf2013/tordb/rcp.sh "%I"
python3 /home/ccf2013/tordb/rcp.py  --hash-dir -I "$1" >>/home/ccf2013/rcp2.log 2>>/home/ccf2013/rcp2e.log
sleep 5
gclone copy "/home/ccf2013/emby/$1/"  gd1:/media/148/emby/ 
sleep 100
rm -rf "/home/ccf2013/emby/$1/"
```
> 使用 `--hash-dir` 参数，将在目标目录，先建立一个以种子 hash 值为名的暂存目录，在其中生成目标链接，此目标在上传完成后将被删除
> 有一些 qbit 客户端在种子完成后输出参数时，会出现文件名丢失中文的现象，以 `rcp.py` 可仅使用 `%I` 参数完成任务，从而避免这一问题


## 对于原 torcp 用户
* 这个 tordb 要求 torcp 依赖，要求的版本是 >= 0.58，即 torcp 在 v0.58 改写了结构以支持外部代码传参及调用执行；
* 原有的功能和使用方式仍然不受影响，即如果原来有脚本在使用 torcp 跑，即使更新到了 v0.58，也应能继续完成任务；



---
to be cont.

