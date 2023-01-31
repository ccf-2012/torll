# TORDB ARA TORCP ui w/ db
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
* 设置 qbit 完成后直接运行脚本，或者以 RESTful API 形式提交 torcp 处理；
  * 若 qbit 在 docker 中运行，则以API形式处理较简单；否则需要在 docker 中安装 requirements.txt 中的依赖；
  * 以 API 形式调用将在目标目录生成重组后媒体的硬链/软链，任务就此结束。

### 编辑 rcp.sh 脚本
* 若qbit 完成后直接运行脚本，则可以实现较为复杂的操作，例如上传gd以及通知Plex更新等，脚本名为 `rcp.sh`，webui中提供了在线编辑代码的功能


---
to be cont.

