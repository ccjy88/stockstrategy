import requests
from requests.adapters import HTTPAdapter
import json
import configparser
import os
import sys
import logging
import time
import datetime
from threading import  Timer
from lxml import etree
import matplotlib.pyplot as plt
from PIL import  Image
from urllib import parse

'''需要安装升级'''
#pip install Pillow
#pip install Pillow -U
#pip install matplotlib==3.0.3
#--index https://pypi.tuna.tsinghua.edu.cn/simple

#import matplotlib.image as mpimg

class Config(object):
    def __init__(self):
        self.file='suning.ini'
        self.configer = configparser.RawConfigParser()
        self.configer.read(self.file)

    def getString(self,section,name):
        try:
            return self.configer.get(section,name,raw=True)
        except Exception as e:
            logger.error(e)
            return ''

    def getInt(self,section,name):
        try:
            return self.configer.getint(section,name)
        except Exception as e:
            logger.error(e)
            return -1


    def getBoolean(self,section,name):
        try:
            return self.configer.getboolean(section,name)
        except Exception as e:
            logger.error(e)
            return False


    def getFloat(self,section,name):
        try:
            return self.configer.getfloat(section,name)
        except Exception as e:
            logger.error(e)
            return 0

    def setString(self,section,option,value):
        self.configer.set(section,option,value)

    def save(self):
        with open(self.file,'w') as f:
            self.configer.write(f)

class SessionBuilder(object):
    def __init__(self):
        pass

    def buildSession(self, configer,section='head'):
        session = requests.Session()
        session.mount('http://', HTTPAdapter(max_retries=3))
        session.mount('https://', HTTPAdapter(max_retries=3))
        session.cookies =requests.utils.cookiejar_from_dict(cookiedict)
        headers={}
        headers['Accept']=configer.getString(section,'accept')
        headers['Accept-Encoding']=configer.getString(section,'accept-encoding')
        headers['Accept-Language']=configer.getString(section,'accept-language')
        headers['Connection']=configer.getString(section,'connection')
        headers['Referer']=configer.getString(section,'referer')
        headers['User-Agent']=configer.getString(section,'user-agent')
        session.headers = headers
        return session




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
        #formatter = logging.Formatter("%(asctime)s  %(message)s",'%Y-%m-%d %H:%M:%S')
        formatter = MSFormatter("%(asctime)s  %(message)s", datefmt=None)
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)
        if os.path.exists('logs')==False:
            os.mkdir("logs")
        fh = logging.FileHandler('logs/suning.log',encoding="utf-8")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def info(self,msg):
        self.logger.log(logging.INFO,msg)
    def error(self,msg):
        self.logger.log(logging.ERROR,msg)


'''预约'''
def appointment():
    resp = httpget('appointment')
    respstr=resp.text
    logger.info(respstr)
    issucess, errorcode, errormsg= parseJsonAppointment(respstr)
    if issucess==False:
        weixinmsg= '预约失败, errorcode={} {}'.format(errorcode,errormsg)
        logger.info(weixinmsg)
        sendweixin('预约失败', weixinmsg)
    else:
        weixinmsg= '预约成功, errorcode={} {}'.format(errorcode,errormsg)
        logger.info(weixinmsg)
        sendweixin('预约成功', weixinmsg)

def js2json(str):
    p1 = str.index("({") + 1
    p2 = str.index("})") + 1
    str = str[p1:p2]
    #logger.info('resp={}'.format(str))
    return json.loads(str)


def cookiedict2str(dict):
    s = ''
    for k,v in dict.items():
        s +='{}={}; '.format(k,v)
    if len(s)>2:
        s=s[:-2]
    return s

#下载二维码图片并显示，循环查询状态，直到手机扫描二维码并确认登录
class Login(object):
    def __init__(self):
        pass

    def doLogin(self):
        global cookiedict
        cookiedict={} #清cookie
        httpget('login')

        #需要得到图片qr uuid
        queryuuidresp = httpget('queryqr')

        #写文件
        with open('qr.jpg','wb') as f:
            f.write(queryuuidresp.content)
        logger.info('qr图片已存为qr.jpg')
        im = Image.open('qr.jpg')
        plt.imshow(im)
        plt.show()

        for i in range(60):
            time.sleep(1)
            headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}

            senddata = {}
            senddata['uuid'] = cookiedict['ids_qr_uuid']
            senddata['service'] = 'https://product.suning.com/0000000000/11001203841.html'
            senddata['terminal'] = 'PC'
            senddata = parse.urlencode(senddata)
            resp = httppost('querystate',senddata,otherheaders=headers)
            obj = js2json(resp.text)
            state=int(obj["state"])
            if state==2:
                self.popupLoginsuccess()
                self.loginservice()
                logger.info('手机已确认登录'.format(cookiedict))
                with open('requesthead.txt','w') as f:
                    f.write('Cookie:'+cookiedict2str(cookiedict))

                return True
            if state==3:
                logger.info('二维码超时了')
                break
            elif state==1:
                logger.info('手机已扫描')
            else:
                logger.info('等待手机扫描....')
        return False
    def popupLoginsuccess(self):
        resp = httpget('popuploginsuccess')
        logger.info('已执行popupLoginsuccess')
        return resp

    def loginservice(self):
        #这里千万千万不要重定向,否则得不到cookie
        resp = httpget('loginservice', allow_redirects=False)
        logger.info('已执行loginservice')

        resp = httpget('loginst')
        logger.info('已执行 loginst')

        return resp

'''立即购买 '''
def nowBuy():
    resp = httpget('nowbuy')
    respstr=resp.text
    logger.info(respstr)
    issucess,errorcode,errormsg = parseJsonBuy(respstr)
    if issucess==False:
        weixinmsg='购买失败, errorcode={} {}'.format(errorcode,errormsg)
        logger.info(weixinmsg)
        sendweixin('购买失败',weixinmsg)
    else:
        weixinmsg='issucess={}, errorcode={} {}'.format(issucess,errorcode,errormsg)
        logger.info(weixinmsg)
        sendweixin('购买成功',weixinmsg)

    return issucess,errorcode,errormsg

def parseJsonBuy(str):
    p1 = str.index("({")+1
    p2 = str.index("})")+1
    str = str[p1:p2]
    obj = json.loads(str)
    issuccess = "Y" == obj["isSuccess"]
    errorCode=0
    errorMessage=''
    #print("是否成功:",issuccess)
    resultErrorList=obj["resultErrorList"]
    for resulterror in resultErrorList:
        for edict in resulterror:
            if 'errorCode' in edict:
                errorCode = int(edict['errorCode'])
                errorMessage=edict['errorMessage']
                #print('错误代码:',edict['errorCode'])
    return  issuccess,errorCode,errorMessage

#分析预约结果
def parseJsonAppointment(str):
    p1 = str.index("({")+1
    p2 = str.index("})")+1
    str = str[p1:p2]
    obj = json.loads(str)
    errorCode=obj["code"]
    errorMessage=obj['message']
    issuccess = int(errorCode) == 0
    return  issuccess,errorCode,errorMessage

#成功后发送微信
def sendweixin(title,message):
    if message is None or len(message)==0:
        message='空消息'
    configer = Config()
    url = configer.getString("weixin","url")
    session = requests.Session()
    payload={"text": title,"desp": message}
    logger.info('开始发送weixin'+title)
    resp = session.post(url,data=payload).text
    logger.info('发送weixin结果:'+resp)


#循环启动定时任务，保持在线，并在预定时刻执行task
def scheduleStart(task,hour,minute,second,offsetmillisencd):
    t = time.localtime()
    target = time.strptime(
        '{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(t.tm_year, t.tm_mon, t.tm_mday, hour, minute, second),
        '%Y-%m-%d %H:%M:%S')
    target = time.mktime(target)
    login = Login()
    while True:
        differ = target - time.time() + offsetmillisencd/1000.0
        if differ>90:
            logger.info('等待60s......')
            time.sleep(60)
            while Orderlist().isLoginok() == False:
                logger.info("查询订单失败，需要重新登录,请用手机苏宁APP扫描确认")
                if login.doLogin(): break
        else:
            logger.info("准备启动任务=" + str(differ))
            timer = Timer(differ,task,[])
            timer.start()
            break


#从requesthead.txt中读取上次保存的cookie
def readCookiefile():
    with open('requesthead.txt','r') as f:
        lines = f.readlines()
        for l in lines:
            if l.startswith('Cookie'):break

        l = l[len('Cookie: '):]
        return l


#查询历史订单用于验证是否登录了。
class Orderlist(object):
    def __init__(self):
        pass
    def isLoginok(self):
        logger.info('查询订单验证是否登录....')
        resp = httpget('queryorder')
        #logger.info(resp.text)
        xdata = etree.HTML(resp.text)
        inputs = xdata.xpath(r'//div[@class="my-appoint"]')
        #logger.info(len(inputs))
        loginok = len(inputs)>0 #如果登录成功，应该有多个input
        logger.info('已登录，查到了我的预约。')
        return loginok

def str2dict(cookie):
    ws = cookie.split(';')
    cookiedict={}
    for s in ws:
        if(len(s.strip())==0):continue
        nv = s.split('=')
        cookiedict[nv[0].strip()] = nv[1].strip()
    return cookiedict

def responseSetCookie(cookies):
    global cookiedict
    dict={k:v  for k, v in cookies.items()}
    cookiedict.update(dict)



def httpget(section,otherheads={},allow_redirects=True):
    configer = Config()
    url = configer.getString(section, 'url')
    session = SessionBuilder().buildSession(configer, section)
    session.headers.update(otherheads)
    resp = session.get(url,allow_redirects=allow_redirects,timeout=5)
    responseSetCookie(resp.cookies)
    return resp

def httppost(section,data,otherheaders={}):
    configer = Config()
    url = configer.getString(section, 'url')
    session = SessionBuilder().buildSession(configer, section)
    session.headers.update(otherheaders)
    resp = session.post(url,data,timeout=5)
    responseSetCookie(resp.cookies)
    return resp

cookiedict={}
bookActionID=''
partNumber='000000011001203841'

#生成新的预约URL，将URL中的活动ID替为最新的bookActionID
def buildappointmenturl():
    global bookActionID,partNumber
    resp = httpget('pcsale')
    pcdata = js2json(resp.text)
    salenetprice=pcdata['data']['price']['saleInfo'][0]['netPrice']
    bookActionID = pcdata['data']['price']['saleInfo'][0]['bookActionID']
    if len(bookActionID)==0:
        logger.error("没有活动，bookActionID={}".format(bookActionID))
        raise "没有活动，bookActionID={}".format(bookActionID)
    partNumber = pcdata['data']['price']['saleInfo'][0]['partNumber']
    logger.info('产品ID={} 价格={} 活动预订ID={}'.format(partNumber,salenetprice,bookActionID))
    appointmenturl = r'gotoAppoint_{}_{}_0000000000_P01_1_preBuyCallback.do'.format(bookActionID,partNumber)
    appointmenturl='https://yushou.suning.com/jsonp/appoint/'+appointmenturl+r'?callback=preBuyCallback&openId=&dfpToken=THwrjW176f4469b60DIKV3ad6___w7DDp8K5wrxJw6MZbMOxK27CrcOMBMOFw7lawqLCsMOm&appVersion=&detect=mmds_e66gdU6z666XdtDM666CzXDX666NzTDL666IN.DEj666SNyDX666XN-DM666v8Btj666W8utG666l8qtDs666Ol2tL666AlCtB666YGLEX6664GAEL666pMxE0B666RMyEB6663Xt0B666gXN0B666yBT0X666qBH0tL666jB30X666CLp0j6669LK0B666~LssX666SLMsDX666uLNsN666dLess666XLuss6660Lcsj666KjVstB666ojqsX666njrsL666wj1sX666HjHsL666fjasDX666SjQsL666gj2sB6668j3sX666jjysB6666josDL666UsYsX666YsPsL666vsCsX666ns_sL6663s-s67RFD63s-s7n73t3B2e3KbG0x3bE00Gbx6VrbeJre2eKx6E2e76DtE0sjLBX7eJ37n62E7e3E7nn66nJ62eEnkbJ3Vt6nn6J7nV23767n3n6Enr362er277eenrJ663ETD66-DST66lL7tJ272bxtwBc.pZJLPg1Bv7sED66666sED67tJ63eJ2Vtt7Jr2767nV237r7qA6696L6M666n6N6B666v6A6G666Y6q6G6666D266L6660Dp6X666XDtDj666NDMDL666gDFDX666VDTD6B666fDHDX666aDmDB666vD-DL666_DBtB666BtetDX666dtVtB666StrtL666QtatB666It2tB666DEmtEB666lEItB666gEYtB666VEPtB666qECtL666fEUt6X6661EUtX666~E_tZG66hE_tB666OE_tB666G0_tDX666ts_tB666Bj_tB6668LEEL666iBjEB666fXjEtB666rMNEB666cGdEB666LlAEB6663lcEX666i8cEEX66638cEj666dNcEB666bNcEX666PNcEL6668zcEDX666SzcEG666azcEX666ozcE0666jdcEG666RduEtsfErVnJrJne_._1eb18e1f-03ba-478c-b664-67c0a834f6ce_._&referenceURL=https%3A%2F%2Fproduct.suning.com%2F0000000000%2F11001203841.html&_=1610419603946'
    return appointmenturl

#生成新的立即购买URL，替掉其中的参数activityId为新的bookActionID
def buildnowbuyurl():
    global bookActionID,partNumber
    url = c.getString('nowbuy','url')
    p = url.find('&') + 1
    url=url[p:]
    ws = url.split('&')
    newurl='https://shopping.suning.com/nowBuy.do?callback=jQuery17209281810946284754_1610432762062'

    subreq=''
    for s in ws:
        if s.startswith('cartVO'):
            v=s[len('cartVO='):]
            v = parse.unquote(v)
            obj = json.loads(v)
            #订购ID为obj['cmmdtyVOList'][0]['activityId']
            obj['cmmdtyVOList'][0]['activityId']=bookActionID
            subreq+='&cartVO='+parse.quote(json.dumps(obj))
        else:
            subreq+='&'+s
    newurl +=subreq
    return newurl

#从shop主页找飞天maotai
def searchFeitianURL():
    resp = httpget('shop')
    xdata = etree.HTML(resp.text)
    controls = xdata.xpath('//*[a="飞天茅台"]/a[1]')
    if len(controls)>0:
        href = controls[0].attrib['href']
        return href
    return None



if __name__ == '__main__':

    flagdict={'预约':1, '购买':2}
    logger=Logger()
    logger.info('begin....')

    #commodity = searchFeitianURL()
    #logger.info('飞天茅台主页:'+commodity)

    #生成查询产品销售信息，包括产品价格、预约活动ID.
    # 生成url,替换产品ID=partNumber
    c = Config()
    partNumber='000000011001203841'
    urltemp = c.getString('pcsale', 'urltemp')
    url = urltemp.format(partNumber, partNumber)
    c.setString('pcsale','url', url)
    c.save()
    appointmenturl = buildappointmenturl()
    c.setString('appointment','url',appointmenturl)

    #生成活动购买URL
    nowbuyurl = buildnowbuyurl()
    c.setString('nowbuy','url',nowbuyurl)
    c.save()

    #全局的cookie，从上次登录成功的文件读取。cookie不超时就不需要重新登录。
    cookiedict.update(str2dict(readCookiefile()))
    login = Login()

    while Orderlist().isLoginok() == False:
        logger.info("查询订单失败，需要重新登录,请用手机扫描确认")
        if login.doLogin()==True:
            break

    action = c.getInt('main','action')
    if action==1:
        flag=flagdict['预约']
    elif action==2:
        flag=flagdict['购买']
    else:
        logger.error('不明白action选项{},1=预约，2=购买'.format(action))
        sys.exit(-1)

    if flag == flagdict['预约']:


        #预约
        schedulehour = c.getInt('appointmenttime','h')
        schedulemin = c.getInt('appointmenttime','m')
        schedulesecond = c.getInt('appointmenttime','s')
        offsetmillisecond = c.getInt('appointmenttime','ms')

        logger.info('准备定时预约，时间{}:{}:{},提前{}毫秒'.format(schedulehour,schedulemin,schedulesecond, offsetmillisecond))
        scheduleStart(appointment,schedulehour, schedulemin, schedulesecond, offsetmillisecond)

    elif flag == flagdict['购买']:
        #立即买
        schedulehour = c.getInt('nowbuytime','h')
        schedulemin = c.getInt('nowbuytime','m')
        schedulesecond = c.getInt('nowbuytime','s')
        offsetmillisecond = c.getInt('nowbuytime','ms')

        logger.info('准备定时购买，时间{}:{}:{},提前{}毫秒'.format(schedulehour,schedulemin,schedulesecond,offsetmillisecond))
        scheduleStart(nowBuy,schedulehour, schedulemin, schedulesecond, offsetmillisecond)

