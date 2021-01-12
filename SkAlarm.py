import numpy as np
import time
import os
import re
import configparser
import logging

'''
警告。读现价和周下跌-10 -20的关系。
'''

def getallstockid(daysdir):
    pattern = re.compile(r'^\d{6,6}.txt')

    skids=[]
    for f in os.listdir(daysdir):
        if pattern.match(f):
            skid = f[:6]
            skids.append(skid)
    return np.array(skids)

def getselfselect():
    pattern = re.compile(r'^\d{6,6}')
    skids=[]
    with open('自选.txt',mode='r', encoding="UTF-8") as f:
        ls = f.readlines()
        for l in ls:
            if pattern.match(l):
                skid = l[0:6]
                skids.append(skid)
    return np.array(skids)


def day2weekofyear(ymd):
    y = int(ymd/10000)
    m = int(int(ymd / 100) % 100)
    d = int(ymd % 100)
    strymd='{:4d}-{:02d}-{:02d}'.format(y, m, d)

    #dayofweek 0表示星期1，6表示星期天。
    dt = time.strptime(strymd,'%Y-%m-%d')
    swofy = time.strftime("%W", dt)
    return y*100+int(swofy)

def add_day(endyyyymmdd, dayinterval):
    yyyy = int(endyyyymmdd / 10000)
    mm = int(endyyyymmdd / 100 % 100)
    dd = int(endyyyymmdd % 100)
    dt = time.strptime('{:4d}-{:02d}-{:02d}'.format(yyyy, mm, dd), '%Y-%m-%d')
    dt = time.mktime(dt)
    dt += dayinterval * 24 * 3600 + 8 * 3600
    dt = time.gmtime(dt)
    endyyyymmdd = dt.tm_year * 10000 + dt.tm_mon * 100 + dt.tm_mday
    return endyyyymmdd


'''求年中某周的周五是哪天'''
def weektofriday(yyyyww):
    yy = int(yyyyww / 100)
    ww = int(yyyyww % 100)

    dt = time.strptime('{}-{}-0'.format(yy, ww), '%Y-%U-%w')
    yyyymmdd1 = dt.tm_year * 10000 + dt.tm_mon * 100 + dt.tm_mday

    t = time.mktime(dt)
    t = t + 5 * 24 * 3600 + 8 *3600 #加五天又8小时。北京东8区。
    dt = time.gmtime(t)
    yyyymmdd = dt.tm_year * 10000 + dt.tm_mon * 100 + dt.tm_mday
    #print("yyyyww={}{}, friday={} {}".format(yy,ww,yyyymmdd1,yyyymmdd))
    return yyyymmdd

def weektomonday(yyyyww):
    yy = int(yyyyww / 100)
    ww = int(yyyyww % 100)

    dt = time.strptime('{}-{}-0'.format(yy, ww), '%Y-%U-%w')
    yyyymmdd1 = dt.tm_year * 10000 + dt.tm_mon * 100 + dt.tm_mday

    t = time.mktime(dt)
    t = t +  8 *3600 #加五天又8小时。北京东8区。
    dt = time.gmtime(t)
    yyyymmdd = dt.tm_year * 10000 + dt.tm_mon * 100 + dt.tm_mday
    #print("yyyyww={}{}, friday={} {}".format(yy,ww,yyyymmdd1,yyyymmdd))
    return yyyymmdd


class SkfileReaderWeek(object):
    def __init__(self,DAYSDIR, skid, daybegin=0):
        self.skid = skid
        self.monthdatas=[]
        self.weekdatas=[]


        records=[]
        with open('{}\{}.txt'.format(DAYSDIR, skid),mode='r') as f:
            lines = f.readlines()
            for l in lines:
                if l.count('/') > 0:
                    words = l.split('\t')
                    yyyymmdd=int(words[0].strip().replace('/','')[0:8])
                    if daybegin!=0 and yyyymmdd < daybegin:
                        continue
                    yyyymm = int(yyyymmdd / 100)
                    #2000年前的不要了
                    if yyyymm <= 200000 :
                        continue
                    yyyymmdd=int(words[0].strip().replace('/','')[0:8])
                    openv=float(words[1].strip())
                    highv=float(words[2].strip())
                    lowv=float(words[3].strip())
                    closev=float(words[4].strip())
                    #print(yyyymm,openv,highv,lowv,closev)
                    records.append([yyyymmdd,openv,highv,lowv,closev])
            self.days=np.array(records)

    def toWeek(self):
        if len(self.weekdatas) > 0:
            return self.weekdatas

        weekofyear = -1
        weekdata=[]
        for i in range(self.days.shape[0]):
            daydata = self.days[i]
            tmpweekofyear = day2weekofyear(daydata[0])
            if (weekofyear != tmpweekofyear ):
                weekofyear = tmpweekofyear
                weekdata=[int(daydata[0]/10000)*100+weekofyear ,daydata[1],daydata[2],daydata[3],daydata[4]]
                self.weekdatas.append(weekdata)
            else:
                weekofyear = tmpweekofyear
                weekdata[2] = max(weekdata[2],daydata[2])
                weekdata[3] = min(weekdata[3],daydata[3])
                weekdata[4] = daydata[4]
        self.weekdatas = np.array(self.weekdatas)
        return self.weekdatas
    def removeWeekDateAfter(self, weekdatas, removedate):
        return np.delete(weekdatas, np.where(weekdatas[:, 0] >= removedate), axis=0)

buydate_col = 0
buyprice_col = 1
buyqty_col = 2
buymoney_col = 3
saledate_col = 4
saleprice_col = 5
salemoney_col = 6
closedprofit_col = 7
sumclosedprofit_col = 8
runningprofit_col = 9
pureprofit_col = 10

runningcolcount = 11

OPEN_COLINDEX = 1
HIGH_COLINDEX = 2
LOW_COLINDEX = 3
CLOSE_COLINDEX = 4


def getnow():
    #now = time.gmtime(time.time()+8*3600)
    now = time.strftime('%Y%m%d')
    return now

class Skalarm(object):
    def __init__(self, daysdir):
        self.daysdir = daysdir

    #最近5个周线高点下跌-20%
    def weekHighDown20(self):
        global  exportdir,logger
        pattern = re.compile(r'^\d{6,6}')
        pricerecords={}

        #找文件
        today = int(getnow())
        for i in range(-1,-4,-1):
            path=r'{}\自选股{}.txt'.format(exportdir,today)
            if os.path.isfile(path):
                break
            today = add_day(today,i)
        logger.info('当前数据文件：{}'.format(path))
        with open(path,mode='r',encoding="GBK") as f:
            ls = f.readlines()
            for l in ls:
                if pattern.match(l):
                    words = l.split('\t')
                    skid = words[0]
                    skname = words[1]
                    currentprice=float(words[3])
                    startymd = add_day(today,-260)
                    reader=SkfileReaderWeek(daysdir,skid,daybegin=startymd)
                    weeks = reader.toWeek()
                    hhvyear = np.max( weeks[:,HIGH_COLINDEX])
                    if len(weeks)==0:
                        continue
                    hhv = np.max( weeks[-5:,HIGH_COLINDEX])
                    if hhv >= hhvyear * 0.9 and currentprice<=hhv * 0.82:
                        percent = (currentprice / hhv - 1)*100
                        logger.info("回调-20% {} {}  高点{:.2f} 现价{:.2f},下跌{:.2f}%".format(skid,skname,hhv,
                                                                                 currentprice,percent))



    #读取文件,周线收盘跌-10%
    def weekcloseDown10(self):
        global  exportdir,config,logger
        pattern = re.compile(r'^\d{6,6}')
        pricerecords={}
        sknames={}

        #找文件
        today = int(getnow())
        for i in range(-1,-4,-1):
            path=r'{}\自选股{}.txt'.format(exportdir,today)
            if os.path.isfile(path):
                break
            today = add_day(today,i)
        logger.info('当前数据文件：{}'.format(path))
        with open(path,mode='r',encoding="GBK") as f:
            ls = f.readlines()
            for l in ls:
                if pattern.match(l):
                    words = l.split('\t')
                    #print(words[0],words[1],words[3])
                    pricerecords[words[0]] =  float(words[3])
                    sknames[words[0]] = words[1]
        for skid,skname in pricerecords.items():
            try:
                ymd = int(config.get('week',skid))
                currentprice = pricerecords[skid]
                weekindex = day2weekofyear(ymd)

                daybegin = weektomonday(weekindex)
                reader = SkfileReaderWeek(daysdir, skid, daybegin)
                weeks = reader.toWeek()
                if len(weeks) == 0:
                    logger.error("xxx错误{} 没有数据".format(skid))
                    return
                weekclose = weeks[0, CLOSE_COLINDEX]

                alarmprice = weekclose * 0.9
                percent = (1 - alarmprice / currentprice) * 100
                skname = sknames[skid]
                if currentprice <= weekclose * 0.9:
                    logger.info('{} {} !!! 到达!!! {}周-10% {:.2f}% 现价{:.2f} 埋点{:.2f}'.format(skid, skname, ymd, percent,
                                                                                     currentprice, alarmprice))
                elif currentprice <= weekclose * 0.93:
                    logger.info('{} {} 接近{}周-10% {:.2f}% 现价{:.2f} 埋点{:.2f}'.format(skid, skname, ymd, percent, currentprice,
                                                                             alarmprice))
            except Exception:
                pass

        #60分钟
        for skid,skname in pricerecords.items():
            try:
                price60min = float(config.get('60min',skid))
                currentprice = pricerecords[skid]

                alarmprice = price60min * 0.93
                percent = (1 - alarmprice / currentprice) * 100
                skname = sknames[skid]
                if currentprice <= alarmprice:
                    logger.info('{} {} !!! 到达!!! 60min-7% {:.2f}% 现价{:.2f} 埋点{:.2f}'.format(skid, skname, percent,
                                                                                     currentprice, alarmprice))
                elif currentprice <= price60min * 0.95:
                    logger.info('{} {} 接近60min-7% {:.2f}% 现价{:.2f} 埋点{:.2f}'.format(skid, skname,percent, currentprice,
                                                                             alarmprice))
            except Exception as e:
                #print(e)
                pass


class Logger(object):
    def __init__(self):
        self.logger = logging.getLogger("skalarm")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s  %(message)s", '%Y-%m-%d %H:%M:%S')
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)
        if os.path.exists('logs')==False:
            os.mkdir("logs")
        fh = logging.FileHandler('logs/skalarm.log',encoding="utf-8")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def info(self,msg):
        self.logger.log(logging.INFO,msg)
    def error(self,msg):
        self.logger.log(logging.ERROR,msg)


if __name__ == '__main__':
    config = configparser.RawConfigParser()
    logger = Logger()
    logger.info("开始...")
    config.read('skalarm.ini',encoding='utf-8')
    daysdir = config.get('skalarm','daysdir')
    exportdir = config.get('skalarm','exportdir')


    alarmer = Skalarm(daysdir)
    alarmer.weekcloseDown10()

    #高点回调
    #alarmer.weekHighDown20()

