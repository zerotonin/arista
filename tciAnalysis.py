import numpy as np
from scipy.signal import medfilt, butter, filtfilt
from scipy.optimize import curve_fit, minimize
import tciPlot
import matplotlib.pyplot as plt
class tciAnalysis():
    def __init__(self, dataFrame):
        self.df = dataFrame

        # short hands
        self.fps =self.df.attrs['fps']
        # in seconds
        self.time_sec = self.df['frames']/self.fps
        

    def filter_HP(self):
        b,a = butter(2, 0.001, btype='high', fs=self.fps)
        self.dFbF_hp = filtfilt(b,a, self.df['deltaFbyF'], padtype='even')

    # exponential function for fitting
    def exp_func(self,x, a, b, c):
        return a*np.exp(-b*x) + c

    def fitLinear(self):
        coefs_GCaMP = np.polyfit(self.time_sec, self.dFbF_hp, deg=1)
        self.dfbf_linfit = np.polyval(coefs_GCaMP, self.time_sec)
    
    def fitLowPoly(self):
        coefs_GCaMP = np.polyfit(self.time_sec, self.dFbF_hp, deg=4)
        self.dfbf_polyfit = np.polyval(coefs_GCaMP, self.time_sec)

    def fitExp(self):
        GCaMP_parms, parm_cov = curve_fit(self.exp_func, self.time_sec, self.dFbF_hp, p0=[1,1e-3,1],bounds=([0,0,0],[4,0.1,4]), maxfev=1000)
        self.dfbf_expfit = self.exp_func(self.time_sec, *GCaMP_parms)

    def driftCorrection(self):

        # filter for fitting
        self.filter_HP()
        #fitting
        self.fitExp()
        self.fitLowPoly()
        self.fitLinear()
        # correction
        self.dfbyf_linCorr = self.df['deltaFbyF'] - self.dfbf_linfit 
        self.dfbyf_polyCorr = self.df['deltaFbyF'] - self.dfbf_polyfit    
        self.dfbyf_expCorr = self.df['deltaFbyF'] - self.dfbf_expfit 

    def chooseFit(self):
        tPLT = tciPlot.tciPlot(self.df)
        tPLT.correctionSurvey(self.time_sec,
                              self.df['deltaFbyF'],
                              self.dfbf_expfit,
                              self.dfbf_polyfit,
                              self.dfbf_linfit,
                              self.dfbyf_expCorr,
                              self.dfbyf_polyCorr,
                              self.dfbyf_linCorr)
        plt.show()
   
    '''
    def calcResponse(self):
        # shorthand
        stim = self.stimulus
        stimRel = np.append(0,np.diff(stim))
        lower = stim -self.offset
        upper = stim +self.offset
        response = np.zeros(len(stim))
        #calculate timing windows and take median response
        counter = 0
        for i in range(len(upper)):    
            # timing window
            idx = (self.data[:,1]< upper[i]) & (self.data[:,1]>lower[i] ) & (self.targetTemp ==stim[i])
            # median response            
            response[counter] = np.median(self.data[idx ,2])
            counter += 1
        # prepare return values    
        respDataAbs =   np.vstack((stim,response)).T   
        respDataAbs =  respDataAbs[respDataAbs[:,0].argsort(),]
        respDataRel =   np.vstack((stimRel,response)).T   
        respDataRel =  respDataRel[respDataRel[:,0].argsort(),]
        self.relResponse = respDataRel
        self.absResponse = respDataAbs
    '''