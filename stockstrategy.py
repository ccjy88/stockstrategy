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

def calcEndmonth(endmonth,daysdir,delnegflag):
    printdetail = True
    print('打印{}个股'.format(daysdir))
    gp = GroupParse(endmonth, daysdir, printdetail, delnegflag)
    ct = gp.doParseGroup()
    print(ct)


if __name__ == '__main__':
    daysdir = r'D:\adatas\days'
    #daysdir = r'D:\adatas\近期强势'
    endmonth = 202011

    delnegflag = False
    calcEndmonth(endmonth, daysdir, delnegflag)


'''
    daysdir = r'D:\adatas\沪深'
    endmonth = 202011
    #删除回报差的
    delnegflag = True
    calcEndmonth(endmonth, daysdir, delnegflag)
'''