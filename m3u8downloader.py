import logging
import requests
from requests.adapters import HTTPAdapter
import os
import configparser
from multiprocessing.pool import ThreadPool
from multiprocessing import cpu_count
import time
import datetime
#注：python3 安装 Crypto 是 pip install pycryptodome
from Crypto.Cipher import AES






class Config(object):
    def __init__(self):
        file='m3u8config.ini'
        self.configer = configparser.ConfigParser()
        self.configer.read(file,encoding="utf-8")

    def getString(self,section,name):
        return self.configer.get(section,name,raw=True)

    def getInt(self,section,name):
        return self.configer.getint(section,name,True)
    def getBoolean(self,section,name):
        return self.configer.getboolean(section,name,True)
    def getFloat(self,section,name):
        return self.configer.getfloat(section,name,True)

class SessionBuilder(object):
    def __init__(self):
        pass

    def buildSession(self, configer,section='head'):
        cookie=configer.getString(section,'cookie')
        cookiedict = self.str2dict(cookie)
        session = requests.Session()
        session.cookies =requests.utils.cookiejar_from_dict(cookiedict)
        headers={}
        headers['Accept']=configer.getString(section,'accept')
        headers['Accept-Encoding']=configer.getString(section,'accept-encoding')
        headers['Accept-Language']=configer.getString(section,'accept-language')
        headers['Connection']=configer.getString(section,'connection')
        headers['User-Agent']=configer.getString(section,'user-agent')
        session.headers = headers
        return session

    def buildPayload(self, configer):
        params = configer.getString('params', 'params')
        ws = params.split('&')
        paramdict={}
        for s in ws:
            nvs=s.split('=')
            paramdict[nvs[0].strip()] = nvs[1].strip()
        return paramdict


    def str2dict(self,cookie):
        if cookie is None or len(cookie.strip())==0:return {}
        ws = cookie.split(';')
        cookiedict={}
        for s in ws:
            nv = s.split('=')
            cookiedict[nv[0].strip()] = nv[1].strip()
        return cookiedict
class MSFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        if datefmt:
            s = time.strftime(datefmt, ct)
        else:
            # t = time.strftime("%Y-%m-%d %H:%M:%S", ct)
            # s = "%s,%03d" % (t, record.msecs)
            s = str(datetime.datetime.now())
        return s


class Logger(object):
    def __init__(self):
        self.logger = logging.getLogger("suning")
        self.logger.setLevel(logging.INFO)
        formatter = MSFormatter("%(asctime)s %(threadName)s  %(message)s", datefmt=None)
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)
        if os.path.exists('logs')==False:
            os.mkdir("logs")
        fh = logging.FileHandler('logs/m3u8.log',encoding="utf-8")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def info(self,msg):
        self.logger.log(logging.INFO,msg)
    def error(self,msg):
        self.logger.log(logging.ERROR,msg)


def aes_decode(data, key):
    """AES解密
    :param key:  密钥（16.32）一般16的倍数
    :param data:  要解密的数据
    :return:  处理好的数据
    """
    cryptor = AES.new(key,AES.MODE_CBC,key)
    plain_text = cryptor.decrypt(data)
    return plain_text.rstrip(b'\0')   #.decode("utf-8")


def executeDownloadts(param):
    url = param["url"]
    fileout=param["fileout"]
    xkey = param["xkey"]
    configer=param["configer"]
    logger=param["logger"]

    session = SessionBuilder().buildSession(configer, section='m3u8')
    session.mount('http://', HTTPAdapter(max_retries=3))
    session.mount('https://', HTTPAdapter(max_retries=3))
    logger.info("begin {}".format(url))
    try:
        content = session.get(url, timeout=30).content
    except Exception as e:
        logger.error(e)
        return False
    if len(xkey)>0 :
        content = aes_decode(content, xkey)
    with open(fileout, 'wb') as f:
        f.write(content)
    return True

class M3u8downloader:
    def __init__(self,url):
        self.url=url
        self.targetfilenameset=set()

    def start(self):
        global configer
        self.session = SessionBuilder().buildSession(configer,section='m3u8')
        logger.info("begin {}".format(self.url))
        resp = self.session.get(url)
        if resp.status_code != 200:
            logger.error('返回码错误:{} {}'.format(resp.status_code,self.url))
            return False
        m3u8text = resp.text
        self.parseM3u8(self.url,m3u8text)
        return True

    def parseM3u8(self,url, text):
        global  logger,tsdir
        dirpath = '/'.join(url.split('/')[:-1])+'/'
        sitepath = '/'.join(url.split('/')[:3])+'/'

        filelistfile=os.path.join(tsdir,'f.txt')
        with open(filelistfile, 'w') as listf:
            listf.write('')

        cmdfile=os.path.join(tsdir,'merge.cmd')
        with open(cmdfile, 'w') as listf:
            listf.write('ffmpeg -f concat -i f.txt -c copy -y {}.mp4'.format(tsdir))

        lines = text.split("\n")
        tsfileurls=[]
        xkey = ''
        extflag=False
        with open(filelistfile, 'a+') as listf:
            for line in lines:
                line=line.strip()
                if extflag:
                    extflag=False
                    if line.startswith("http"):
                        exturl =line
                        logger.info('外部url:{}'.format(exturl))
                        extm3u8text = self.session.get(exturl).text
                        self.parseM3u8(exturl, extm3u8text)
                    elif line.startswith("/"):
                        exturl =sitepath+line[1:]
                        logger.info('外部url:{}'.format(exturl))
                        extm3u8text = self.session.get(exturl).text
                        self.parseM3u8(exturl, extm3u8text)
                    else:
                        exturl =dirpath+line[1:]
                        logger.info('外部url:{}'.format(exturl))
                        extm3u8text = self.session.get(exturl).text
                        self.parseM3u8(exturl, extm3u8text)
                elif line.startswith("#EXT-X-KEY"):
                    p = line.find("URI=")
                    if p>=0:
                        xkeypath = dirpath + line[p + 1 + len("URI="):-1]
                        logger.info(xkeypath)
                        xkey = self.downloadContent(xkeypath)
                        logger.info('已下载xkey={}'.format(xkey.decode("utf-8")))

                elif line.endswith(".ts"):
                    words=line.split('/')
                    filename = words[-1]
                    self.targetfilenameset.add(filename)

                    listf.write('file {}\n'.format(filename))
                    fileout = os.path.join(tsdir, filename)
                    if os.path.exists(fileout):
                        continue
                    if line.startswith("/"):
                        fileurl = sitepath + line[1:]
                    else:
                        fileurl = dirpath+line[1:]
                    tsfileurls.append({'url': fileurl,'fileout': fileout,"configer":configer,"logger": logger,"xkey":xkey})
                elif line.startswith("#EXT-X-STREAM-INF"):
                    extflag=True



        while True:
            exists = True
            for filename in self.targetfilenameset:
                fileout = os.path.join(tsdir, filename)
                if os.path.exists(fileout)==False:
                    exists = False
                    break
            if exists:break

            logger.info("开始pool")
            pool = ThreadPool( 5 )
            pool.map(executeDownloadts, tsfileurls)
            logger.info("已结束pool")


    def downloadContent(self,url):
        global  logger
        logger.info("begin {}".format(url))
        return self.session.get(url).content



if __name__ == '__main__':

    configer = Config()
    logger=Logger()
    xkey=''

    logger.info('cpucount={}'.format(cpu_count()))
    #带AES
    tsdir='outdir'
    if os.path.exists(tsdir)==False:
        os.mkdir(tsdir)

    url=configer.getString('m3u8','url')
    down = M3u8downloader(url)
    down.start()
    logger.info("任务完成。")


