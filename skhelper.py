import numpy as np
import tensorflow as tf
import time

'''读取K线'''
K_FEATURE_MONTH_COUNT = 9

'''评价K线'''
K_FUTURE_MONTH_COUNT = 1

DAYSDIR = r'D:\PycharmProjects\a3c\days'

#下个状态三个，平，上涨、下跌
FUTURE_LABEL = {'flat':0,
          'h30':1, 'h20':2, 'h10':3,
          'l30':4, 'l20':5, 'l10':6
                }
FUTURE_ID = {FUTURE_LABEL[lb]:lb for lb in FUTURE_LABEL}
N_FUTURE = len(FUTURE_ID)

'''每次有上涨机会都会加分。涨幅大加的多60% 1.2 %40 1.1， %20加0.1,下跌不扣分。'''
future_label_score = {'flat': 0,
                      'h10':1.1, 'h20':1.2, 'h30':1.3,
                      'l10':-1.1,'l20': -1.2, 'l30':-1.3}


future_reward = {FUTURE_LABEL[lb]: future_label_score[lb] for lb in future_label_score}

np.random.seed(1)
tf.set_random_seed(1)

def setDaysdir(dir):
    global  DAYSDIR
    DAYSDIR = dir

class SkBrain(object):
    def __init__(self, scope, globalagent):
        self.scope = scope
        self.n_s = K_FEATURE_MONTH_COUNT * 4
        self.future_input = tf.placeholder('int32',[None,])
        self.s_input = tf.placeholder('float32',[None,self.n_s])
        self.LR = 0.01
        self.globalagent = globalagent
        self.buildnet()
        self.sess = tf.Session()
        self.sess.run(tf.global_variables_initializer())
        self.reader = None

    def buildnet(self):
        #with tf.variable_scope('stocknet'):
        w_init = tf.random_normal_initializer(0.0, 0.03)
        b_init = tf.constant_initializer(0.01)
        with tf.variable_scope(self.scope):
            l1 = tf.layers.dense(inputs=self.s_input,units=600,activation=tf.nn.relu6,kernel_initializer=w_init,bias_initializer=b_init)
            #l2 = tf.layers.dense(l1, units=100,activation=tf.nn.relu6,kernel_initializer=w_init,bias_initializer=b_init)
            future = tf.layers.dense(inputs=l1,units=N_FUTURE,activation=None,kernel_initializer=w_init,bias_initializer=b_init)
            self.future_softmax = tf.nn.softmax(future)

            #将来走势现实值和估计值的交叉熵
        self.loss = tf.reduce_mean(tf.nn.sparse_softmax_cross_entropy_with_logits(labels=self.future_input,logits=future))
        self.print_op = tf.print('loss',self.loss)
        self.train_op  = tf.train.AdamOptimizer(self.LR).minimize(self.loss)
            #self.train_op = tf.train.RMSPropOptimizer(self.LR).minimize(self.loss)
        self.net_params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.scope)
        if self.globalagent != None:
            self.setparamop = [t.assign(s) for s,t in zip(self.globalagent.net_params,self.net_params)]

    def getParams(self):
        p = self.sess.run(self.net_params)
        return p

    def setParams(self):
        self.sess.run(self.setparamop)


    def trainSkid(self, skid, samplerate, episodecount, removeafterdate):
        self.allstockdatas = np.array([])
        self.reader = SkdayReader(skid)
        monthdatas = self.reader.toMonth()
        if len(monthdatas) == 0:
            return -1
        if removeafterdate>0 :
            monthdatas = self.reader.removeMonthDateAfter(monthdatas, removeafterdate)
        if len(monthdatas) < K_FEATURE_MONTH_COUNT + K_FUTURE_MONTH_COUNT:
          return -1
        fullmonthdata = self.reader.HExpand(monthdatas)
        monthdatas = self.reader.LogNormalData(fullmonthdata)
        monthdatas = self.reader.markFutureLabel(monthdatas)
        self.allstockdatas = monthdatas

        if len(self.allstockdatas) < 3:
            return -1
        self.skid = skid

        ##最后一行没有future所以扣除
        monthdatas = self.allstockdatas[:-1]
        traindatas, testdatas = self.reader.splitTrainTest(samplerate, monthdatas)
        for i in range(episodecount):
            s_input = traindatas[:,1:1 + K_FEATURE_MONTH_COUNT * 4]
            future_input = traindatas[:,-1].ravel()
            feed={self.s_input: s_input, self.future_input: future_input}
            self.sess.run([self.train_op], feed_dict=feed)
        #self.sess.run([self.print_op],feed_dict = feed)
        if len(testdatas)>0:
            self.selfTest(testdatas)
        return 0



    def verifySkids(self,samplerate, removeafterdate):
        monthdatas = self.allstockdatas[:-1]
        traindatas, testdatas = self.reader.splitTrainTest(samplerate, monthdatas)
        if len(testdatas)>0:
            return self.selfTest(testdatas)
        return 0

    def predict(self,yyyymm, removeafterdate):
        #取最后的K_FEATURE_MONTH_COUNT行进行预测和打分
        fullmonthdata = self.allstockdatas[-K_FEATURE_MONTH_COUNT:, :]

        #最后一行用于预测
        hs = fullmonthdata[-1,:]
        hs = hs[None, :]
        hs = hs[:, 1: K_FEATURE_MONTH_COUNT*4 + 1]

        future_prob = self.sess.run(self.future_softmax,feed_dict={self.s_input: hs})[0]
        future_v = np.argmax(future_prob)
        fullmonthdata[-1, -1] = future_v
        futurev = fullmonthdata[:, -1]

        futurescore = [future_reward[x] for x in futurev]
        futurescore = np.array(futurescore)
        if len(futurescore) < K_FEATURE_MONTH_COUNT:
            #补0
            padding = np.zeros(K_FEATURE_MONTH_COUNT - len(futurescore))
            futurescore = np.hstack([padding, futurescore])

        return futurescore



    #随机抽取，检查正确率。
    def selfTest(self,testdatas):
        s_input = testdatas[:, 1:1 + K_FEATURE_MONTH_COUNT * 4]
        feed = {self.s_input: s_input}
        future_predict_prob = self.sess.run(self.future_softmax, feed_dict=feed)

        future_predict = [np.random.choice(np.arange(0,N_FUTURE),p=p)  for p in future_predict_prob]
        future_predict = np.array(future_predict)
        correctcount = testdatas[future_predict ==  testdatas[:,-1]].shape[0]
        correctrate = correctcount / len(testdatas) * 100
        #print('{} 共取样{}个，正确{}个,正确率{:.2f}%'.format(self.skid,len(testdatas),correctcount,correctrate))
        return correctrate
        #errindex = future_predict !=  testdatas[:,-1]
        #errsample=np.hstack([testdatas[errindex,0][:,None],testdatas[errindex,-1][:,None],future_predict[errindex][:,None]])
        #print(errsample)


class SkdayReader(object):
    def __init__(self,skid):
        self.skid = skid
        self.monthdatas=[]
        self.weekdatas=[]


        records=[]
        with open('{}\{}.txt'.format(DAYSDIR, skid),mode='r') as f:
            lines = f.readlines()
            for l in lines:
                if l.count('/') > 0:
                    words = l.split('\t')
                    yyyymm=int(words[0].strip().replace('/','')[0:6])
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

    def toMonth(self):
        if len(self.monthdatas) > 0:
            return self.monthdatas

        yymm = 0
        monthdata = []
        for i in range(self.days.shape[0]):
            daydata = self.days[i]
            tmpyymm = int(daydata[0]/100)
            if (yymm != tmpyymm):
                yymm = tmpyymm
                monthdata=[yymm,daydata[1],daydata[2],daydata[3],daydata[4]]
                self.monthdatas.append(monthdata)
            else:
                monthdata[2] = max(monthdata[2],daydata[2])
                monthdata[3] = min(monthdata[3],daydata[3])
                monthdata[4] = daydata[4]
        self.monthdatas = np.array(self.monthdatas)
        return self.monthdatas

    def removeMonthDateAfter(self, monthdatas, removedate):
        return np.delete(monthdatas, np.where(monthdatas[:, 0] >= removedate), axis=0)

    def removeWeekDateAfter(self, weekdatas, removedate):
        return np.delete(weekdatas, np.where(weekdatas[:, 0] >= removedate), axis=0)

    '''水平扩展，垂直错开一个月'''
    def HExpand(self, monthdatas):
        '''掐头'''
        hexpandcount = K_FEATURE_MONTH_COUNT + K_FUTURE_MONTH_COUNT - 1
        maxrow = len(monthdatas) - K_FEATURE_MONTH_COUNT + 1
        hs = monthdatas[0: maxrow]
        for i in range(hexpandcount):
            c1 = monthdatas.copy()[i+1:, 1:]
            if len(c1) > maxrow:
                c1 = c1[:maxrow - len(c1) ]
            elif len(c1) < maxrow:
                dlt = maxrow - len(c1)
                #复制最后一个实际值
                for _ in range(dlt):
                    c1 = np.vstack((c1,c1[-1,]))
            hs = np.hstack([hs, c1])

        return hs

    '''每一行求对数'''
    def LogNormalData(self, monthdatas):
        #删除负
        mins = np.min(monthdatas,axis=1)
        delindexes = np.where(mins <= 0)

        #不会处理负数
        monthdatas = np.delete(monthdatas,delindexes,axis=0)

        #求对数,我们只对对数的大小有兴趣,就是只关心涨跌百分比，对股价绝对值没兴趣。
        monthdatas[:,1:] = np.log(monthdatas[:,1:])

        '''第一行，以第后一个feature k线收盘为基准'''
        baseline = monthdatas[:, K_FEATURE_MONTH_COUNT * 4]
        monthdatas[:,1:] = monthdatas[:,1:] - baseline[:,None]
        return monthdatas


    '''取feature k线最后一个月和评价月的k线计算涨跌'''
    '''FUTURE={'flat':0, 'rose:':1 ,'fell':2 }'''
    def markFutureLabel(self, monthdata):
        global  FUTURE_LABEL
        close = monthdata[:, 1 + K_FEATURE_MONTH_COUNT * 4 - 1]
        hhv = np.max(monthdata[:, 1 + K_FEATURE_MONTH_COUNT * 4:][:, 1::4],axis=1)
        llv = np.min(monthdata[:, 1 + K_FEATURE_MONTH_COUNT * 4:][:, 2::4],axis=1)
        #nextcloseh = np.max(monthdata[:, 1 + K_FEATURE_MONTH_COUNT * 4:][:, 3::4],axis=1)
        nextclosel = np.min(monthdata[:, 1 + K_FEATURE_MONTH_COUNT * 4:][:, 3::4],axis=1)
        future = np.zeros([len(close),])

        '''从涨到跌，只打一个标签'''
        future[(nextclosel - close <= np.log(0.7)) & (future == 0)] = FUTURE_LABEL['l30']
        future[(nextclosel - close <= np.log(0.8)) & (future == 0)] = FUTURE_LABEL['l20']
        future[(nextclosel - close <= np.log(0.9)) & (future == 0)] = FUTURE_LABEL['l10']


        future[(hhv - close >= np.log(1.3)) & (future == 0)] = FUTURE_LABEL['h30']
        future[(hhv - close >= np.log(1.2)) & (future == 0)] = FUTURE_LABEL['h20']
        future[(hhv - close >= np.log(1.1)) & (future == 0)] = FUTURE_LABEL['h10']

        future[(llv - close <= np.log(0.7)) & (future == 0)] = FUTURE_LABEL['l30']
        future[(llv - close <= np.log(0.8)) & (future == 0)] = FUTURE_LABEL['l20']
        future[(llv - close <= np.log(0.9)) & (future == 0)] = FUTURE_LABEL['l10']

        monthdata = np.hstack([monthdata,future[:,None]])
        return monthdata

    def splitTrainTest(self,trainrate, monthdatas):
        len=monthdatas.shape[0]
        indexes = np.arange(len)
        trainsize = int(len*trainrate)
        indexes_train = np.random.choice(indexes,trainsize,replace=False)
        indexes_test = np.delete(indexes, indexes.searchsorted(indexes_train))

        return monthdatas[indexes_train], monthdatas[indexes_test]

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

    '''下一周最高价涨幅'''
    def calcNextweekHHV(self,weekdatas):
        week = weekdatas[:,[0,4]]
        weeknext = weekdatas[:, -1][1:]
        weeknext = np.hstack([weeknext, weeknext[-1]])
        weeknext = weeknext[:,None]

        week = np.hstack([week, weeknext])

        uprate = week[:, -1] / week[:,-2]
        week = np.hstack([week, uprate[:,None]])
        return week


# if __name__ == '__main__':
#     r = SkdayReader('300055')
#     ws = r.toWeek()
#     r.Weekhhvpercent()


