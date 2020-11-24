from skhelper import  SkBrain as Agent
from skhelper import SkdayReader
from skhelper import setDaysdir

import numpy as np
import os
import re
import time

episodes = 400

globalagent = Agent('global', None)
agent = Agent('stocknet', globalagent)


'''板块分析。'''
class GroupParse(object):
    def __init__(self,endyyyymm,daysdir,printdetailflag,delnegflag = True):
        self.endyyyymm = endyyyymm
        self.daysdir = daysdir
        self.delnegflag = delnegflag
        self.printdetailflag = printdetailflag
        self.monthscores = []
        self.sumlabels = []

    def getyyyymm(self,yyyymm):
        yyyy = int(yyyymm/100)
        mm = int(yyyymm%100)
        return yyyy,mm

    def incyyyymm(self,yyyymm):
        yyyy,mm = self.getyyyymm(yyyymm)
        mm += 1
        if mm > 12:
            mm = 1
            yyyy += 1
        return yyyy,mm

    def decyyyymm(self,yyyymm):
        yyyy,mm = self.getyyyymm(yyyymm)
        mm -= 1
        if mm < 1:
            mm = 12
            yyyy -= 1
        return yyyy,mm

    def doParseWeekuprate(self,skid, removeafterdate, percent):
        setDaysdir(self.daysdir)
        y,m = self.getyyyymm(removeafterdate)
        reader = SkdayReader(skid)
        weekofyear = reader.day2weekofyear(int(y*10000+m*100+1))
        weeks = reader.toWeek()
        weeks = reader.removeWeekDateAfter(weeks, y * 100 + weekofyear)
        weeks = weeks[-12:, ]
        weeks = reader.calcNextweekHHV(weeks)

        #最后12周
        success= weeks[ weeks[:, -1] >= percent ]
        successrate = len(success) / len(weeks) * 100
        #print('{}周末上涨5成功率{:.1f}%'.format(skid, successrate))
        return successrate

    def doParseGroup(self):
        setDaysdir(self.daysdir)
        y,m = self.incyyyymm(self.endyyyymm)
        removeafterdate = y * 100 + m
        pattern = re.compile(r'^\d{6,6}.txt')
        for f in os.listdir(daysdir):
            if pattern.match(f):
                skid  = f[:6]
                agent.setParams()
                self.calcSkids(skid, removeafterdate)

        self.monthscores = np.array(self.monthscores)
        self.sumlabels = np.array(self.sumlabels)

        if (self.monthscores.shape[0] ==0):
            return -1

        #sum 5:end
        self.sumv = np.sum(self.monthscores[:, 5: -1], axis=1) + self.monthscores[:, -1] * 0.5

        #删除sumv小于4.1
        if self.delnegflag:
            delindex = np.where(self.sumv < 4.1)
            self.sumv = np.delete(self.sumv,delindex,axis=0)
            self.sumlabels = np.delete(self.sumlabels,delindex,axis=0)
            self.monthscores = np.delete(self.monthscores, delindex, axis=0)


        week5arr = []
        week10arr = []
        for skid in self.sumlabels:
            weekup10rate = self.doParseWeekuprate(skid, removeafterdate, 1.10)
            weekup5rate = self.doParseWeekuprate(skid, removeafterdate, 1.05)
            week10arr.append(weekup10rate)
            week5arr.append(weekup5rate)
        self.monthscores = np.hstack([self.monthscores, np.array(week10arr)[:, None]])
        self.monthscores = np.hstack([self.monthscores, np.array(week5arr)[:, None]])

        # del 周上涨5%概率小于25%
        if delnegflag:
            delindex = np.where(self.monthscores[:, -1] < 25)
            self.sumv = np.delete(self.sumv, delindex, axis=0)
            self.sumlabels = np.delete(self.sumlabels, delindex, axis=0)
            self.monthscores = np.delete(self.monthscores, delindex, axis=0)


        sortindex = np.argsort(-self.sumv)
        self.sumv = self.sumv[sortindex]
        self.sumlabels = self.sumlabels[sortindex]
        self.monthscores = self.monthscores[sortindex]


        if self.printdetailflag:
            print('日期:', self.endyyyymm)
            for i in range(self.sumlabels.shape[0]):
                print('{}\t{:.1f}\t{}\t{:.1f}\t{:.1f}'.format(self.sumlabels[i]
                                                              , self.sumv[i]
                                                              , self.monthscores[i][:-2]
                                                              , self.monthscores[i][-2]
                                                              , self.monthscores[i][-1]))

        return len(self.monthscores)

    def calcSkids(self, skid, removeafterdate):
        #print('begin calcSkids {}'.format(len(calcSkids)))
        sampletestrate = 1.0
        ret = agent.trainSkid(skid, sampletestrate, episodes, removeafterdate)
        if ret<0:
            return

        correctrate = agent.verifySkids( 0.0, removeafterdate)
        if self.printdetailflag:
            print('{}，自检正确率{:.1f}%'.format(skid,correctrate))

        futurevs = agent.predict( self.endyyyymm, removeafterdate)
        if len(futurevs) == 0:
             return
        self.monthscores.append(futurevs)
        self.sumlabels.append(skid)

    def totime(self,yyyymmdd):
        yyyy = int(yyyymmdd / 10000)
        mm  = int(yyyymmdd / 100 % 100)
        dd  = int(yyyymmdd % 100 )
        dt = time.strptime('{:04d}-{:02d}-{:02d}'.format(yyyy,mm,dd),'%Y-%m-%d')
        return dt


    def findgroupWeek20(self, endyyyymmdd, priorsweekcount, targetsuccessymd):
        setDaysdir(self.daysdir)
        pattern = re.compile(r'^\d{6,6}.txt')

        #要求endyyyymmdd这个日期加7
        yyyy = int(endyyyymmdd / 10000)
        mm  = int(endyyyymmdd / 100 % 100)
        dd  = int(endyyyymmdd % 100 )
        dt = time.strptime('{:4d}-{:02d}-{:02d}'.format(yyyy,mm,dd),'%Y-%m-%d')
        dt = time.mktime(dt)
        dt += 7 * 24 * 3600 + 8 * 3600
        dt = time.gmtime(dt)
        endyyyymmdd = dt.tm_year * 10000 + dt.tm_mon * 100 + dt.tm_mday

        #求开始日期
        dt = time.strptime('{:4d}-{:02d}-{:02d}'.format(yyyy,mm,dd),'%Y-%m-%d')
        dt = time.mktime(dt)
        dt = dt - ((priorsweekcount+1) * 7 * 24 + 8) * 3600
        dt = time.gmtime(dt)
        beginyyyymmdd = dt.tm_year * 10000 + dt.tm_mon * 100 + dt.tm_mday


        for f in os.listdir(daysdir):
            if pattern.match(f):
                skid  = f[:6]
                self.findWeekupdown20(skid,beginyyyymmdd, endyyyymmdd, priorsweekcount,targetsuccessymd)


    '''
    在周线上，取最近12周.
    当前Thhv比T+1的hhv更大。llv为T至T+3的最低价。
    hhv / llv >= 1.2
    T+1至 T+9之内，存在收盘close大于当前的close
    '''
    def findWeekupdown20(self, skid, beginyyyymmdd, endyyyymmdd , priorsweekcount,targetsuccessymd):
        setDaysdir(self.daysdir)
        yyyy = int(endyyyymmdd / 10000)
        mm  = int(endyyyymmdd / 100 % 100)
        dd  = int(endyyyymmdd % 100 )
        successymd = self.totime(targetsuccessymd)


        reader = SkdayReader(skid, beginyyyymmdd)
        weekofyear = reader.day2weekofyear(int(yyyy * 10000 + mm * 100 + dd))
        weeks = reader.toWeek()
        if len(weeks) < 6:
            return
        weeks = reader.removeWeekDateAfter(weeks, yyyy * 100 + weekofyear)
        weeks = weeks[- priorsweekcount:, ]

        OPEN_C = 1
        HIGH_C = 2
        LOW_C = 3
        CLOSE_C = 4

        fondweekcount = 0
        for i in range(0,len(weeks) - 3):
            if fondweekcount>0:
                #不要连续
                fondweekcount -= 1
                continue
            week = weeks[i]
            nextweek = weeks[i + 1]
            #currentclose = week[4]
            h = week[HIGH_C]
            nexth = nextweek[HIGH_C]
            if h >= nexth:
                #后面最低是哪周？

                llvarg = np.argmin(weeks[i+1: i+6, LOW_C])
                llvarg += i + 1
                llv = weeks[llvarg, LOW_C]

                llvclosearg = np.argmin(weeks[i+1: i+4, CLOSE_C])
                llvclosearg += i + 1
                llvclose = weeks[llvclosearg, CLOSE_C]

                if 1 - llv / h  >= 0.2 and llvarg+1 <= len(weeks) - 1: #下跌超20%
                    '''最低收盘价后面，大于20%的索引'''
                    successindexes = np.where(weeks[llvclosearg+1:,HIGH_C] / llvclose >= 1.2 )[0]

                    if len(successindexes)== 0:
                        fondweekcount = 0
                    else:
                        successindex = successindexes[0]+llvclosearg+1
                        #还必须上涨10%
                        if weeks[successindex,CLOSE_C] / weeks[successindex-1,CLOSE_C]>=1.1:
                            # 打印日期
                            fondweekcount = 2
                            weekindex = weeks[successindex,0]
                            targetmonday = weektomonday(weekindex)
                            if time.mktime(self.totime(targetmonday)) >= time.mktime(successymd):
                                print('week20%\t{}\t{}'.format(skid, targetmonday))
                        else:
                            fondweekcount = 0
                else:
                    fondweekcount = 0






def calcEndmonth(endmonth,daysdir,delnegflag):
    printdetail = True
    print('打印{}个股'.format(daysdir))
    gp = GroupParse(endmonth, daysdir, printdetail, delnegflag)
    ct = gp.doParseGroup()
    print(ct)



'''求年中某周的周五是哪天'''
def weektomonday(yyyyww):
    yy = int(yyyyww / 100)
    ww = int(yyyyww % 100)

    dt = time.strptime('{}-{}-0'.format(yy, ww), '%Y-%U-%w')
    dt = time.mktime(dt)
    dt = dt + 5 * 24 * 3600 + 8 *3600 #加五天又8小时。北京东8区。
    dt = time.gmtime(dt)
    yyyymmdd = dt.tm_year * 10000 + dt.tm_mon * 100 + dt.tm_mday
    return yyyymmdd


if __name__ == '__main__':
    #daysdir = r'D:\adatas\days'
    #daysdir = r'D:\adatas\近期强势'
    endmonth = 202010

    delnegflag = False
#    calcEndmonth(endmonth, daysdir, delnegflag)

    daysdir = r'D:\adatas\沪深'
    #daysdir = r'D:\adatas\days'
    gp = GroupParse(endmonth, daysdir, True, delnegflag)
    priorsweekcount = 6
    # 这周数据保留，从这一周的事面开始删除
    endyyyymmdd = 20200807
    targetyyyymmdd = endyyyymmdd
    gp.findgroupWeek20(endyyyymmdd, priorsweekcount,targetyyyymmdd)



'''
    daysdir = r'D:\adatas\沪深'
    endmonth = 202011
    #删除回报差的
    delnegflag = True
    calcEndmonth(endmonth, daysdir, delnegflag)
'''