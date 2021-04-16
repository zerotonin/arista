import csv, wx, pickle, dill
import numpy as np
import scipy.io as sio
from scipy.interpolate import interp1d
import datetime as dt
import pandas as pd
class tempFileIO:
    """
Class to store and define ROIs.
    """
    
    # you can define default parameters so the user does not have to define it himself, 
    # only if he wants to (here: auto_threshold=0.5)
    def __init__(self,genotype,gender,stimulus,celltype,cellnumber,saveDir='~',offset = 0.5):
        self.degree_sign= u'\N{DEGREE SIGN}'
        self.data = 0
        self.iData = 0
        self.sensorData = 0
        self.sensorDataRaw = 0
        self.responseData = 0
        self.targetTemp = 0
        self.date = '0000-00-00'
        self.gender = gender
        self.celltype = celltype
        self.genotype = genotype
        self.offset = offset
        self.stimulusType = stimulus
        self.offset = offset
        self.saveDir = saveDir
        self.cellNumber = cellnumber
        self.stimulusList = {'ascAmp':     np.array([22.0, 22.5, 21.5, 23.0, 21.0, 24.0, 20.0, 26.0, 18.0]),
                             'ascAmpFlip': np.array([22.0, 21.5, 22.5, 21.0, 23.0, 20.0, 24.0, 18.0, 26.0]),
                             'descAmp':    np.array([22.0, 18.0, 26.0, 20.0, 24.0, 21.0, 23.0, 21.5, 22.5]),
                             'descAmpFlip':np.array([22.0, 26.0, 18.0, 24.0, 20.0, 23.0, 21.0, 22.5, 21.5]),
                             'adaptation': np.array([22.0, 24.0, 22.0, 24.0, 20.0, 24.0, 22.0, 24.0, 22.0])}
        self.getStimulus()
    # function for extracting the sensor temperature from a matlab file
    def readSensorTfileMAT(self,fPos):
        temp = sio.loadmat(fPos)
        
        self.sensorDataRaw = temp['data']
        self.getDate()
        return temp['data']
    # function for extracting the sensor temperature from a txt file
    def readSensorTfileTXT(self,tempfile):
        with open(str(tempfile)) as file:
            lines = list(csv.reader(file))
    
        strList = []    #turn the list of lists into a list of strings
        lList = []       # split each string of the list into 4 parts (time,sensorT,setT,driveT), and make a list of lists(floats)
        pairList = []    #list of frames and sensor temperatures only
        temp = []        #list of sensor temperature
    
        for l in lines:
                strList.append("".join(l))
        for s in strList:
            a = s.split()                    #split each string in 4
            b = [float(i) for i in a]        #turn strings into floats
            lList.append(b)        
        for i in range(len(lList)):
            pairList.append(lList[i][:,2])    #discard the last 2 values of each line
    
        table = np.array(pairList)   #convert list of lists into a 2d array
        self.sensorDataRaw = table
        self.getDate()
        #temp = table[:,1] #take the second column of the 2d array (sensor temperature)
    
        return table
        
    def readResponseFile(self,responsefile):   # turns the txt file into a time vector and a deltaF/Fo vector
        # make a list of the lines in the txt (list of lists)
        with open(str(responsefile)) as file:
            lines = list(csv.reader(file))
        # remove first element (header line)
        lines = lines[1:]
    
        #define empty lists
        strList = []    #turn the list of lists into a list of strings
        lList =[]       #split each string of the list into 2 parts (time,deltaF/F0), and make a list of lists(floats)
        response = []   #list of deltaF/F0 values
    
        #Loops
        for l in lines:
            strList.append("".join(l))
        for s in strList:
            a = s.split()                    #split each string in two
            b = [float(i) for i in a]        #turn strings into floats
            c = [round(i,5) for i in b]      #round floats
            lList.append(c)
        for l in lList:
            response.append(l[1])    #df is the response vector
    
        self.responseData = response
        return response

    def readResponseFileCSV(self,responsefile):
        df=pd.read_csv(responsefile, sep=',')
        self.responseData = df['Mean'].to_list()
        return df['Mean'].to_list()

    
    def alignTemperature2Frame(self,dataT):
        frames       = dataT[:,1]
        uniqueFrames = np.unique(frames)
        temperature  = np.zeros(uniqueFrames.size)
        targetTemperature  = np.zeros(uniqueFrames.size)
        counter      = 0
        for i in uniqueFrames:
            idx = dataT[:,1] == i
            temperature[counter]        = np.median(dataT[idx,2])
            targetTemperature[counter]  = np.median(dataT[idx,3])
            counter +=1
        self.sensorData = np.vstack((uniqueFrames,temperature)).T
        self.targetTemp = targetTemperature
        return self.sensorData
    
    def interpFrameTemperature(self,frameTemp,newFrames):
        set_interp = interp1d(frameTemp[:,0], frameTemp[:,1], kind='linear')
        newTemperatures = set_interp(newFrames)        
        set_interp = interp1d(frameTemp[:,0], self.targetTemp, kind='linear')
        self.targetTemp = set_interp(newFrames)
        self.iData = np.vstack((newFrames,newTemperatures)).T
        return self.iData
        
    def readInData(self,responseFpos,sensorFpos):
        #read in response file
        if responseFpos.endswith('txt'):
            response  = self.readResponseFile(responseFpos)
        elif responseFpos.endswith('csv'):
            response  = self.readResponseFileCSV(responseFpos)
        else:
            raise ValueError('unknown file extension for response file: ' + str(responseFpos))
        #read in sensor file
        dataT     = self.readSensorTfileMAT(sensorFpos)
        #align framenumber with temperature
        frameTemp = self.alignTemperature2Frame(dataT)
        #get real frames
        newFrames = range(0,len(response))
        #interpolate
        iData = self.interpFrameTemperature(frameTemp,newFrames)
        print(iData.shape,len(response))
        self.data = np.vstack((iData[:,0],iData[:,1],np.asarray(response))).T
        
        return self.data
    
    def readInDataTXT(self,responseFpos,sensorFpos):
        #read in response file
        response  = self.readResponseFile(responseFpos)
        #read in sensor file
        dataT     = self.readSensorTfileTXT(sensorFpos)
        #align framenumber with temperature
        frameTemp = self.alignTemperature2Frame(dataT)
        #get real frames
        newFrames = range(0,len(response))
        #interpolate
        iData = self.interpFrameTemperature(frameTemp,newFrames)
        
        self.data = np.vstack((iData[:,0],iData[:,1],np.asarray(response))).T
        
        return self.data
        
    def saveTXT(self,directory):
        fPos = directory+'/'+self.date +'_'+self.genotype+'_'+self.gender+'_'+self.stimulusType+'_'+self.celltype+'_'+self.cellNumber+'.txt'
        headerStr = ' date: ' + self.date + '\n genotype: '+self.genotype+'\n gender: '+self.gender+'\n stimulus: '+self.stimulusType+'\n celltype: '+self.celltype
        np.savetxt(fPos,self.data,fmt='%i %2.2f %1.6f',header=headerStr)
    
    def savePy(self):
        fPos = self.setFpos()
#        dill.dumps(self.prepData())
#        dill.dump_session(fPos)
        f = open(fPos, 'wb')
        pickle.dump(self.prepData(), f)
        f.close()
        
    def getStimulus(self):
        self.stimulus = self.stimulusList[self.stimulusType]        
    
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
        

    def getfPos(self,wildcard,workingDir):
        app = wx.App(None)
        style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        dialog = wx.FileDialog(None, 'Open',workingDir, wildcard=wildcard, style=style)
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
        else:
            path = None
        dialog.Destroy()
        return path
        
    def setFpos(self):
        defName = self.date +'_'+self.genotype+'_'+self.gender+'_'+self.stimulusType+'_'+self.celltype+'_'+self.cellNumber+'.pkl'
        app = wx.App(None)

        dlg = wx.FileDialog(None, "Save result as...", self.saveDir, defName, style = wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
        result = dlg.ShowModal()
        inFile = dlg.GetPath()
        dlg.Destroy()
        
        if result == wx.ID_OK:          #Save button was pressed
            return inFile
        elif result == wx.ID_CANCEL:    #Either the cancel button was pressed or the window was closed
            return ''
        
    def verboseMode(self,workingDir,responseExt = '*.txt'):
        sensorFpos   = self.getfPos('*.mat',workingDir)
        responseFpos = self.getfPos(responseExt,workingDir)
        data = self.readInData(responseFpos,sensorFpos) 
        return data
    
    def getDate(self):
        matlab_datenum=self.sensorDataRaw[0,0]
        python_datetime = dt.datetime.fromordinal(int(matlab_datenum)) + dt.timedelta(days=matlab_datenum%1) - dt.timedelta(days = 366)
        self.date = str(python_datetime.date())

    def prepData(self):
        returnValue = { 'data':self.data, 
                        'dataInterp':self.iData,
                        'dataSensor':self.sensorDataRaw, 
                        'dataCalcium':self.responseData, 
                        'targetTemperature':self.targetTemp, 
                        'date':self.date, 
                        'gender':self.gender, 
                        'celltype':self.celltype,
                        'genotype':self.genotype, 
                        'offset':self.offset,
                        'stimulusType':self.stimulusType,
                        'cellNumber':self.cellNumber,
                        'relResponse':self.relResponse,
                        'absResponse':self.absResponse}
        return returnValue
                        
    
        
    
        
    
    
        
        
