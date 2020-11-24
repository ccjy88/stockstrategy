import numpy as np
import os
import re
import time

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



class Week20Strategy(object):
    def __init__(self, daysdir):
        self.daysdir = daysdir

    def findgroupWeek20(self, endyyyymmdd, priorsweekcount, targetsuccessymd):
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
        yyyy = int(endyyyymmdd / 10000)
        mm  = int(endyyyymmdd / 100 % 100)
        dd  = int(endyyyymmdd % 100 )
        successymd = self.totime(targetsuccessymd)


        reader = StfileReader(daysdir, skid, beginyyyymmdd)
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
        for i in range(0,len(weeks) - 1):
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

                '''反弹百分比'''
                upllvcloserate = 1.15

                '''最后一根阳线涨8%'''
                closeuprate = 1.08

                if 1 - llv / h  >= 0.2 and llvarg <= len(weeks) - 1: #下跌超20%
                    '''最低收盘价后面，大于20%的索引'''
                    successindexes = np.where(weeks[llvclosearg+1:,HIGH_C] / llvclose >= upllvcloserate )[0]

                    if len(successindexes)== 0:
                        fondweekcount = 0
                    else:
                        for j in range(len(successindexes)):
                            successindex = successindexes[j]+llvclosearg+1
                            #还必须上涨10%
                            if weeks[successindex,CLOSE_C] / weeks[successindex-1,CLOSE_C]>=closeuprate:
                                # 打印日期
                                fondweekcount = 2
                                weekindex = weeks[successindex,0]
                                targetmonday = self.weektomonday(weekindex)
                                if time.mktime(self.totime(targetmonday)) >= time.mktime(successymd):
                                    print('week20%\t{}\t{}'.format(skid, targetmonday))
                            else:
                                fondweekcount = 0
                else:
                    fondweekcount = 0
    def totime(self,yyyymmdd):
        yyyy = int(yyyymmdd / 10000)
        mm  = int(yyyymmdd / 100 % 100)
        dd  = int(yyyymmdd % 100 )
        dt = time.strptime('{:04d}-{:02d}-{:02d}'.format(yyyy,mm,dd),'%Y-%m-%d')
        return dt


    def weektomonday(self, yyyyww):
        yy = int(yyyyww / 100)
        ww = int(yyyyww % 100)

        dt = time.strptime('{}-{}-0'.format(yy, ww), '%Y-%U-%w')
        dt = time.mktime(dt)
        dt = dt + 5 * 24 * 3600 + 8 *3600 #加五天又8小时。北京东8区。
        dt = time.gmtime(dt)
        yyyymmdd = dt.tm_year * 10000 + dt.tm_mon * 100 + dt.tm_mday
        return yyyymmdd


if __name__ == '__main__':
    daysdir = r'D:\adatas\沪深'
    #daysdir = r'D:\adatas\days'
    brain = Week20Strategy(daysdir)
    priorsweekcount = 8
    # 这周数据保留，从这一周的事面开始删除
    endyyyymmdd = 20201120
    targetyyyymmdd = endyyyymmdd
    brain.findgroupWeek20(endyyyymmdd, priorsweekcount, targetyyyymmdd)

