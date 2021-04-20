import matplotlib.pyplot as plt
class tciPlot():
    
    def __init__(self,dataFrame):

        self.df = dataFrame
    
    def lineP_frameTemps(self,ax = plt.gca()):
        self.df.plot(x="frames", y=["targetTempDeg", "temperatureDeg"],ax=ax)
        ax.set_ylabel(r'temperature, °C')

    def lineP_frame_deltaF(self,ax = plt.gca()):
        self.df.plot(x="frames", y="deltaFbyF",ax=ax)
        ax.set_ylabel(r'cell response, $\frac{\delta{}f}{f}$')
    
    def lineP_simpleSurvey(self):
        f, (a0, a1) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [4, 1],'hspace':0.025})
        self.lineP_frame_deltaF(a0)
        a0.set_xlabel(r'')
        a0.set_xticklabels([])
        a0.grid(True,axis='both',linestyle='--')
        self.lineP_frameTemps(a1)
        a1.grid(True,axis='both',linestyle='--')

    def correctionSurvey(self):
        f, (a0, a1) = plt.subplots(2, 1, gridspec_kw={'hspace':0.025})
