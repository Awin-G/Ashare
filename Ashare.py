import os
import re
import sys
import urllib
import threading
import functools
import requests

# 可用alist地址，将会上传到第一个可用地址
available_urls = ['http://awin-x.top', 'http://awin.l2.ttut.cc', ]
# 可能的用户，将会使用第一个可用的用户
available_user = [{'name': 'admin', 'pass': '2038xY6677yy889'},
                  {'name': 'monitor', 'pass': '1973@QZWXECRVTBYNUMLKJHGFDSA1973'},
                  ]
# 将要被监视的文件夹
# source：文件夹  target：将要上传到的文件夹
# ext：将要备份的后缀名列表，判断逻辑是以该字符串结尾，包含'.*'时上传所有文件
watch_folders = [{'source': 'E:\\办公室\\笔记', 'target': '/家/备份1T/MAGIK', 'ext': ['.*']},
                 {'source': 'E:\\画廊\\漫画\\黄漫', 'target': '/家/图片/图片备份/来自magnet', 'ext': ['.*']},
                 ]
# 上传记录保存位置
data_file = 'c:\\菜单指令\\Ashare2.0\\upload_data.txt'
# 多线程信号，控制最多同时上传的文件数。
semaphore = threading.Semaphore(3)


class Connect:
    def __init__(self, url: str, name: str, password: str):
        self.url = url
        self.name = name
        self.password = password
        try:
            self.login = requests.post(url + '/api/auth/login', json={'username': self.name, 'password': self.password})
        except ConnectionError:
            raise ConnectionError("connection fail")
        try:
            message = self.login.json()['message']
        except requests.exceptions.JSONDecodeError:
            message = 'failed to connect alist'
        if self.login.status_code != 200 or message == 'failed to connect alist':
            print('状态码：' + str(self.login.status_code))
            raise ConnectionError('不是有效的alist链接')
        elif message == 'password is incorrect':
            print('密码错误')
            raise ConnectionError('密码错误')
        elif message == 'failed find user: record not found':
            print('用户名错误')
            raise ConnectionError('用户名错误')
        elif message == 'success':
            self.token = self.login.json()['data']['token']
            print('登陆成功：message=' + message)
            print('token: ' + self.login.json()['data']['token'])

    def mkdir(self, path):
        md = requests.post(self.url + '/api/fs/mkdir', json={'path': path}, headers={'Authorization': self.token})
        return md.status_code

    def ls(self, path):
        list = requests.post(self.url + '/api/fs/list', json={'path': path}, headers={'Authorization': self.token})
        for f in list.json()['data']['content']:
            print(f['name'] + '---大小：' + str(f['size']))
        return list.json()

    def upload(self, path, file):
        path = urllib.parse.quote(path)
        size = os.stat(file)
        headers = {'Authorization': self.token, 'File-Path': path,
                   'Content-Length': str(size)}
        binary_file = {'file': open(file, "rb")}
        up = requests.put(self.url + '/api/fs/form', files=binary_file, headers=headers)
        binary_file['file'].close()
        return up.json()['message']

    def rename(self, path, name):  # 尚未完成：：找不到储存？
        body = {'path': path, 'name': name}
        re = requests.post(self.url + '/api/fs/rename', data=body, headers={'Authorization': self.token})
        print(re.json())
        return re.status_code

    def dir(self, path, password=None):
        body = {'path': path, 'password': password}
        dirs = requests.post(self.url + '/api/fs/dirs', data=body, headers={'Authorization': self.token})
        return dirs.json()['data']

    def geturl(self, path, password=None):
        body = {'path': path, 'password': password}
        fileinfo = requests.post(self.url + '/api/fs/get', data=body, headers={'Authorization': self.token})
        url = fileinfo.json()['data']['raw_url']
        return url


def upload_thread(connection, path, file):
    with semaphore:
        print(file + '开始上传')
        try:
            message = connection.upload(path, file)
            if message == 'success':
                print(file + '上传成功')
                #return connection.geturl(path)
        except FileNotFoundError:
            print('无法打开' + file)
            print('文件打开失败')
        except ConnectionError:
            print('网络出现问题')
        except requests.exceptions.SSLError:
            print('ssl问题，请请尝试不使用https')
            print('退出')
            exit()


def upload(connection, path, file, name='origin name'):
    # 拼接路径
    if name == 'origin name':
        if re.match('.*/$', path) is None:
            path = path + '/'
        path = path + os.path.basename(file)
    elif name == 'given in path':
        pass
    else:
        path = path + name
    # 上传
    worker = functools.partial(upload_thread, connection, path, file)
    t = threading.Thread(target=worker)
    t.start()


def connect():
    for urls in available_urls:
        for user in available_user:
            try:
                connection = Connect(urls, user['name'], user['pass'])
                return connection
            except:
                print('失败：' + urls)
                continue
    raise ConnectionError('已尝试全部链接，失败。')


def match_ext(filename, ext):
    if '.*' in ext:
        return True
    return any(filename.endswith(extension) for extension in ext)


if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print('Awin-x')
        exit(0)
    else:
        sys.argv.pop(0)
        order = sys.argv.pop(0)
        # 更新监视的文件夹
        if order == 'U' or order == '-U':
            try:
                # 尝试连接
                alist = connect()
                # 读取上传信息
                with open(data_file, "r") as f:
                    last_times = eval(f.read())
                # 记录上传文件数
                upload_count = 0
                for folders in watch_folders:  # 遍历有哪些文件夹需要监控
                    if re.match('.*/$', folders['target']) is None:  # 保证目标路径以/结尾，方便拼接路径
                        folders['target'] = folders['target'] + '/'
                    for root, dirs, files in os.walk(folders['source']):  # 遍历文件夹
                        for filename in files:  # 选中文件文件
                            if match_ext(filename, folders['ext']):  # 选中指定后缀文件
                                file_path = os.path.join(root, filename)  # 拼接本地完整路径
                                current_time = os.path.getmtime(file_path)  # 获取文件修改时间
                                if file_path not in last_times or last_times[file_path] != current_time:  # 选中更新的文件
                                    # 创建上传任务
                                    upload(alist,
                                           folders['target'] + os.path.relpath(file_path, start=folders['source']),
                                           file_path,
                                           name='given in path')
                                    upload_count = upload_count + 1
                                    last_times[file_path] = current_time  # 更新修改时间
                                    if upload_count % 20 == 0:
                                        # 保存上传信息
                                        with open(data_file, "w") as f:
                                            f.write(str(last_times))
                with open(data_file, "w") as f:
                    f.write(str(last_times))
            except FileNotFoundError:
                print("上传数据文件打开失败，请尝试创建：" + data_file)
