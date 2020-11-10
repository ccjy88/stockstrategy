from skhelper import  SkBrain as Agent
from skhelper import setDaysdir

import numpy as np
import os
import re

episodes = 400

globalagent = Agent('global', None)
agent = Agent('stocknet', globalagent)


'''板块分析。'''
class GroupParse(object):
    def __init__(self,endyyyymm,daysdir,printdetailflag):
        self.endyyyymm = endyyyymm
        self.daysdir = daysdir
        self.delnegflag = True
        self.printdetailflag = printdetailflag
        self.sumscores = []
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

        self.sumscores = np.array(self.sumscores)
        self.sumlabels = np.array(self.sumlabels)

        if (self.sumscores.shape[0] ==0 ):
            return -1

        gamma = 0.90
        rate = [np.power(gamma, n) for n in range(self.sumscores.shape[1] - 2, -1, -1)]
        #折扣加权后的，按行求和。
        self.sumv = np.sum(self.sumscores[:,:-1] * rate,axis = 1) + self.sumscores[:, -1]*0.5

        #删除sumv小于4.0
        if self.delnegflag:
            delindex = np.where(self.sumv < 4.0)
            self.sumv = np.delete(self.sumv,delindex,axis=0)
            self.sumlabels = np.delete(self.sumlabels,delindex,axis=0)
            self.sumscores = np.delete(self.sumscores,delindex,axis=0)

        sortindex = np.argsort(-self.sumv)
        self.sumv = self.sumv[sortindex]
        self.sumlabels = self.sumlabels[sortindex]
        self.sumscores = self.sumscores[sortindex]

        if self.printdetailflag:
          for i in range(self.sumlabels.shape[0]):
                print('{} {:04d} {:.1f} {}'.format(self.sumlabels[i], self.endyyyymm,
                                                     self.sumv[i],self.sumscores[i]))
        return len(self.sumscores)

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
        self.sumscores.append(futurevs)
        self.sumlabels.append(skid)


if __name__ == '__main__':
    #daysdir = r'D:\PycharmProjects\a3c\汽车类'
    daysdir = r'.\days'
    #daysdir = r'D:\PycharmProjects\a3c\半导体'
    daysdir = r'D:\PycharmProjects\a3c\芯片板块'

    printdetail = True
    print('{}打印个股'.format(daysdir))
    gp = GroupParse(202011, daysdir, printdetail)
    ct = gp.doParseGroup()
    print(ct)
    exit(0)


    printdetail = False
    print('{}板块'.format(daysdir))
    for mm in np.arange(11, 1):
       yyyymm = 2019 * 100 + mm
       gp=GroupParse(yyyymm, daysdir, printdetail)
       ct = gp.doParseGroup()
       print(yyyymm,ct)

    for mm in np.arange(1, 11):
        yyyymm = 2020 * 100 + mm
        gp=GroupParse(yyyymm, daysdir, printdetail)
        ct = gp.doParseGroup()
        print(yyyymm,ct)

