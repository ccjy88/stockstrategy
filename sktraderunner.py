import numpy as np
import os
import time

'''
模拟交易策略进行买卖，已全部卖掉为结束
可以设置下跌多少买，上涨多少卖。
'''

class StfileReader(object):
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
    def day2weekofyear(self,ymd):
        y = int(ymd/10000)
        m = int(int(ymd / 100) % 100)
        d = int(ymd % 100)
        strymd='{:4d}-{:02d}-{:02d}'.format(y, m, d)

        #dayofweek 0表示星期1，6表示星期天。
        dt = time.strptime(strymd,'%Y-%m-%d')
        swofy = time.strftime("%W", dt)
        return int(swofy)

    def toWeek(self):
        if len(self.weekdatas) > 0:
            return self.weekdatas

        weekofyear = -1
        weekdata=[]
        for i in range(self.days.shape[0]):
            daydata = self.days[i]
            tmpweekofyear = self.day2weekofyear(daydata[0])
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

class SktradeRunner(object):
    def __init__(self, daysdir):
        self.daysdir = daysdir


    '''运行'''
    def run(self,skid, startymd, buyqty, buyprice, endymd, buypricerate, salepricerate):
        OPEN_COLINDEX = 1
        HIGH_COLINDEX = 2
        LOW_COLINDEX = 3
        CLOSE_COLINDEX = 4

        maxbuycount = 10
        buypricelatchs = np.array([buyprice * np.power(buypricerate, i)for i in np.arange(0, maxbuycount)])
        buypricelatchs = np.round(buypricelatchs, 2)
        salepricelatchs =  buypricelatchs * salepricerate
        salepricelatchs = np.round(salepricelatchs, 2)
        buysalepricedict = {b: s for (b,s) in zip(buypricelatchs, salepricelatchs)}

        runningqueue=[]

        reader = StfileReader(daysdir, skid, startymd)
        delindex = np.where(reader.days[:, 0]>endymd)
        days = np.delete(reader.days, delindex, axis=0)

        #生成第一笔记录
        buyrecord=np.zeros([runningcolcount,])
        buyrecord[buydate_col] = startymd
        buyrecord[buyprice_col] = buyprice
        buyrecord[buyqty_col] = buyqty
        maxbuymoney = np.round(buyqty * buyprice, 2)
        buyrecord[buymoney_col] = maxbuymoney
        buyrecord[saleprice_col] = buysalepricedict[buyprice]
        runningqueue.append(buyrecord)
        runningqueue = np.array(runningqueue)

        closedqueue=[]

        days = days[1:]
        for skday in days:
            if len(runningqueue) == 0:
                print('全部都已关闭')
                break

            llv = skday[LOW_COLINDEX]
            hhv = skday[HIGH_COLINDEX]

            #不做日线的T
            #是不是可以有卖的？
            saled = False
            for j in np.arange(len(runningqueue) - 1, -1, -1):
                runrecord = runningqueue[j]
                if runrecord[saledate_col] == 0 and hhv >= runrecord[saleprice_col]:
                    #可以卖掉了
                    saled = True
                    runningqueue = np.delete(runningqueue, [j], axis=0)

                    runrecord[saledate_col] = skday[0]
                    saleprice = runrecord[saleprice_col]
                    qty = runrecord[buyqty_col]
                    buymoney  = runrecord[buymoney_col]
                    salemoney = np.round(saleprice * qty, 2)
                    runrecord[salemoney_col] = salemoney
                    runrecord[closedprofit_col] = salemoney - buymoney

                    #利润合计
                    runrecord[sumclosedprofit_col] = runrecord[closedprofit_col]
                    if len(closedqueue) > 0:
                        runrecord[sumclosedprofit_col] +=  np.sum(closedqueue[:, closedprofit_col], axis=0)
                    #计算浮动
                    runningprofit = self.calcRunningprofit(runningqueue, skday[0], saleprice, False)
                    runrecord[runningprofit_col] = runningprofit
                    runrecord[pureprofit_col] = runrecord[sumclosedprofit_col] + runrecord[runningprofit_col]


                    if(len(closedqueue)==0):
                        closedqueue = runrecord[None,:]
                    else:
                        closedqueue = np.vstack([closedqueue, runrecord])
            #不做T
            if saled: continue
            #是不是可以有可买的?
            minbuyprice = runningqueue[-1, buyprice_col]
            tmpbupyprices = buypricelatchs[buypricelatchs < minbuyprice]
            for j in np.arange(len(tmpbupyprices) -1, -1, -1):
                buyprice = tmpbupyprices[j]
                if llv < buyprice:
                    buyqty = int(maxbuymoney / buyprice / 100) * 100
                    buymoney = buyprice * buyqty
                    saleprice = buysalepricedict[buyprice]
                    buyrecord=np.zeros([runningcolcount,])
                    buyrecord[buydate_col] = skday[0]
                    buyrecord[buyprice_col] = buyprice
                    buyrecord[buyqty_col] = buyqty
                    buyrecord[buymoney_col] = buymoney
                    buyrecord[saleprice_col] = saleprice
                    runningqueue = np.vstack([runningqueue, buyrecord])

        #填最后一天收盘价到未完成
        p = self.calcRunningprofit(runningqueue,skday[0], skday[CLOSE_COLINDEX], True)
        print('未完成利润{}'.format(p))
        p1 = self.printRunningLog(runningqueue)
        print('========已完成=========')
        p2 = self.printClosedLog(closedqueue)

        print("净利润{:.2f}".format(p1+p2))

    #计算未完成交易现价浮动盈亏
    def calcRunningprofit(self,runningqueue,closedate, closeprice,fillvalue):
        if fillvalue:
            runningqueue[:, saledate_col] = closedate
            runningqueue[:, saleprice_col] = closeprice
        runningqueue[:, salemoney_col] = closeprice * runningqueue[:, buyqty_col]
        runningqueue[:, runningprofit_col] = runningqueue[:, salemoney_col] - runningqueue[:, buymoney_col]
        runningprofit = np.sum(runningqueue[:, runningprofit_col], axis=0)
        return runningprofit


    def printClosedLog(self, closedqueue):

        if len(closedqueue)==0:
            print('无已完成')
            return  0

        for r in closedqueue:
            print('{:.0f}\t{:.2f}\t{:.2f}\t{:.0f}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}'
                  .format(r[buydate_col], r[buyprice_col], r[buyqty_col],
                          r[saledate_col], r[saleprice_col], r[sumclosedprofit_col]
                          ,r[runningprofit_col],r[pureprofit_col]))
        sumclosedprofit = np.sum(closedqueue[:, closedprofit_col], axis=0)
        print('区完成交易{}笔，利润{:.2f}:'.format(len(closedqueue), sumclosedprofit))
        return sumclosedprofit

    def printRunningLog(self, runningqueue):

        if len(runningqueue)==0:
            print('全部完成')
            return  0

        for r in runningqueue:
            print('{:.0f}\t{:.2f}\t{:.2f}\t{:.0f}\t{:.2f}\t{:.2f}'
                  .format(r[buydate_col], r[buyprice_col], r[buyqty_col],
                          r[saledate_col], r[saleprice_col]
                          ,r[runningprofit_col]))
        sumrunningprofit = np.sum(runningqueue[:, runningprofit_col], axis=0)
        print('未完成交易{}笔，利润{:.2f}:'.format(len(runningqueue), sumrunningprofit))
        return sumrunningprofit


if __name__ == '__main__':
    buypricerate = 0.90
    salepricerate = 1.08

    daysdir = r'D:\adatas\沪深'
    runner = SktradeRunner(daysdir)
    skid = '002019'
    startymd = 20180427
    buyprice =  19.17
    buyqty = 400
    endymd = 20200831
    runner.run(skid, startymd, buyqty,buyprice,endymd,buypricerate,salepricerate)



