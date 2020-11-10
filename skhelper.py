import numpy as np
import tensorflow as tf

'''读取K线'''
K_FEATURE_MONTH_COUNT = 9

'''评价K线'''
K_FUTURE_MONTH_COUNT = 3 #rose fell plain

DAYSDIR = r'D:\PycharmProjects\a3c\days'

#下个状态三个，平，上涨、下跌
FUTURE_LABEL = {'flat':0,
          'up60c':  1, 'up40c':  2, 'up20c': 3,
          'up60h':  4, 'up40h':  5, 'up20h': 6,
          'dn60l':  7, 'dn40l':  8, 'dn20l': 9,
          'dn60c': 10, 'dn40c': 11, 'dn20c': 12
                }
FUTURE_ID = {FUTURE_LABEL[lb]:lb for lb in FUTURE_LABEL}
N_FUTURE = len(FUTURE_ID)

'''每次有上涨机会都会加分。涨幅大加的多60% 1.2 %40 1.1， %20加0.1,下跌不扣分。'''
future_label_score = {'flat': 0,
          'up60c':1.2, 'up60h':1.2, 'up40c':1.1,
          'up40h':1.1, 'up20c':0.3, 'up20h':0.3,
          'dn60c': -0.1, 'dn60l': -0.1, 'dn40c': -0.1,
          'dn40l': -0.1, 'dn20c': -0.1, 'dn20l': -0.1}

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
            monthdatas = self.reader.removeDateAfter(monthdatas, removeafterdate)
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
        records=[]
        with open('{}\{}.txt'.format(DAYSDIR, skid),mode='r') as f:
            lines = f.readlines()
            for l in lines:
                if l.count('/') > 0:
                    words = l.split('\t')
                    yyyymm=int(words[0].strip().replace('/','')[0:6])
                    if yyyymm <= 200000 :
                        continue
                    openv=float(words[1].strip())
                    highv=float(words[2].strip())
                    lowv=float(words[3].strip())
                    closev=float(words[4].strip())
                    #print(yyyymm,openv,highv,lowv,closev)
                    records.append([yyyymm,openv,highv,lowv,closev])
            self.days=np.array(records)

    def toMonth(self):
        if len(self.monthdatas) > 0:
            return self.monthdatas

        yymm = 0
        monthdata = []
        for i in range(self.days.shape[0]):
            daydata = self.days[i]
            if (yymm != daydata[0]):
                yymm = daydata[0]
                monthdata=[yymm,daydata[1],daydata[2],daydata[3],daydata[4]]
                self.monthdatas.append(monthdata)
            else:
                monthdata[2] = max(monthdata[2],daydata[2])
                monthdata[3] = min(monthdata[3],daydata[3])
                monthdata[4] = daydata[4]
        self.monthdatas = np.array(self.monthdatas)
        return self.monthdatas

    def removeDateAfter(self, monthdatas, removedate):
        return np.delete(monthdatas, np.where(monthdatas[:, 0] >= removedate), axis=0)

    '''水平扩展，垂直错开一个月'''
    def HExpand(self, monthdatas):
        '''掐头'''
        hexpandcount = K_FEATURE_MONTH_COUNT + K_FUTURE_MONTH_COUNT
        maxrow = len(monthdatas) - K_FEATURE_MONTH_COUNT + 1
        hs = monthdatas[0: maxrow]
        for i in range(hexpandcount):
            c1 = monthdatas.copy()[i:, 1:]
            if len(c1) > maxrow:
                c1 = c1[:maxrow - len(c1)]
            elif len(c1) < maxrow:
                dlt = maxrow - len(c1)
                for _ in range(dlt):
                    c1 = np.vstack((c1,c1[-1,]))
            hs = np.hstack([hs, c1])

        return hs

    '''每一行求对数'''
    def LogNormalData(self, monthdatas):
        #岫除负
        mins = np.min(monthdatas,axis=1)
        delindexes = np.where(mins <= 0)

        #不会处理负数
        monthdatas = np.delete(monthdatas,delindexes,axis=0)
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
        nextcloseh = np.max(monthdata[:, 1 + K_FEATURE_MONTH_COUNT * 4:][:, 3::4],axis=1)
        nextclosel = np.min(monthdata[:, 1 + K_FEATURE_MONTH_COUNT * 4:][:, 3::4],axis=1)
        future = np.zeros([len(close),])

        future[(nextcloseh - close >= np.log(1.6)) & (future == 0)] = FUTURE_LABEL['up60c']
        future[(hhv - close >= np.log(1.6)) & (future == 0)] = FUTURE_LABEL['up60h']
        future[(nextcloseh - close >= np.log(1.4)) & (future == 0)] = FUTURE_LABEL['up40c']
        future[(hhv - close >= np.log(1.4)) & (future == 0)] = FUTURE_LABEL['up40h']
        future[(nextcloseh - close >= np.log(1.2)) & (future == 0)] = FUTURE_LABEL['up20c']
        future[(hhv - close >= np.log(1.2)) & (future == 0)] = FUTURE_LABEL['up20h']

        future[(nextclosel - close <= np.log(0.4)) & (future == 0)] = FUTURE_LABEL['dn60c']
        future[(llv - close <= np.log(0.4)) & (future == 0)] = FUTURE_LABEL['dn60l']
        future[(nextclosel - close <= np.log(0.6)) & (future == 0)] = FUTURE_LABEL['dn40c']
        future[(llv - close <= np.log(0.6)) & (future == 0)] = FUTURE_LABEL['dn40l']
        future[(nextclosel - close <= np.log(0.8)) & (future == 0)] = FUTURE_LABEL['dn20c']
        future[(llv - close <= np.log(0.8)) & (future == 0)] = FUTURE_LABEL['dn20l']

        monthdata = np.hstack([monthdata,future[:,None]])
        return monthdata

    def splitTrainTest(self,trainrate, monthdatas):
        len=monthdatas.shape[0]
        indexes = np.arange(len)
        trainsize = int(len*trainrate)
        indexes_train = np.random.choice(indexes,trainsize,replace=False)
        indexes_test = np.delete(indexes, indexes.searchsorted(indexes_train))

        return monthdatas[indexes_train], monthdatas[indexes_test]





