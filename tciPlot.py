import matplotlib.pyplot as plt
class tciPlot():
    
    def __init__(self,dataFrame):

        self.df = dataFrame
    
    def delete_xcaption(self,ax):    
        ax.set_xlabel(r'')
        ax.set_xticklabels([])

    def lineP_frameTemps(self,ax = plt.gca()):
        self.df.plot(x="frames", y=["targetTempDeg", "temperatureDeg"],ax=ax)
        ax.set_ylabel(r'temperature, °C')

    def lineP_frame_deltaF(self,ax = plt.gca()):
        self.df.plot(x="frames", y="deltaFbyF",ax=ax)
        ax.set_ylabel(r'cell response, $\frac{\delta{}f}{f}$')
    
    def lineP_simpleSurvey(self):
        f, (a0, a1) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [4, 1],'hspace':0.025})
        self.lineP_frame_deltaF(a0)
        self.delete_xcaption(a0)
        a0.grid(True,axis='both',linestyle='--')
        self.lineP_frameTemps(a1)
        a1.grid(True,axis='both',linestyle='--')
    
    def plt_fitOnRaw(self,ax,time_sec,raw,expFit,polyFit,linFit):
        self.plt_dfbf(ax,time_sec,raw,'raw data')
        ax.plot(time_sec,expFit,label='exp. fit',color='k',linestyle='--',)
        ax.plot(time_sec,polyFit,label='poly fit',color='g',linestyle='-.')
        ax.plot(time_sec,polyFit,label='lin fit',color='r',linestyle=':')
        ax.legend()
    
    def plt_dfbf(self,ax,time_sec,dfbyf,labelStr):
        ax.plot(time_sec,dfbyf,label=labelStr,color='b')
        ax.set_ylabel(r'cell response, $\frac{\delta{}f}{f}$')
        ax.set_xlabel('time, s')
        ax.legend()

    def correctionSurvey(self,time_sec,raw,expFit,polyFit,linFit,expCorr,polyCorr,linCorr):
        f, (a0, a1,a2,a3) = plt.subplots(4, 1, gridspec_kw={'hspace':0.025})
        self.plt_fitOnRaw(a0,time_sec,raw,expFit,polyFit,linFit)
        self.delete_xcaption(a0)
        a0.grid(True,axis='both',linestyle='--')
        self.plt_dfbf(a1,time_sec,expCorr,'exp. corrected')
        self.delete_xcaption(a1)
        a1.grid(True,axis='both',linestyle='--')
        self.plt_dfbf(a2, time_sec, polyCorr, 'poly corrected')
        self.delete_xcaption(a2)
        a2.grid(True,axis='both',linestyle='--')
        self.plt_dfbf(a2, time_sec, linCorr, 'linear corrected')
        a3.grid(True,axis='both',linestyle='--')

        
