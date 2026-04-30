import csv, os, pickle, dill,fileDialog
import numpy as np
import scipy.io as sio
from scipy.interpolate import interp1d
import datetime as dt
import pandas as pd
class tempFileIO:
    """

    """
    
    # you can define default parameters so the user does not have to define it himself, 
    # only if he wants to (here: auto_threshold=0.5)
    def __init__(self,genotype,gender,stimulus,celltype,cellnumber,saveDir='~',offset = 0.5,fps = 10):
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
        self.fps = fps


    
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
                
    def getStimulus(self):
        self.stimulus = self.stimulusList[self.stimulusType]        
                
    def verboseMode(self,workingDir,responseExt = '*.txt'):
        sensorFpos   = str(fileDialog.App('openMatFileDialog','Temperature Data',workingDir).result)
        responseFpos = str(fileDialog.App('openFijiFileDialog','Temperature Data',workingDir).result)
        data = self.readInData(responseFpos,sensorFpos) 

        return data
    




#        ______________
#       |[]            |
#       |  __________  |
#       |  |File I/O|  |
#       |  |  Input |  |
#       |  |________|  |
#       |   ________   |
#       |   [ [ ]  ]   |
#       \___[_[_]__]___|

    # function for extracting the sensor temperature from a matlab file
    def readSensorTfileMAT(self,fPos):
        temp = sio.loadmat(fPos)
        self.sensorDataRaw = temp['data']
        try:
            self.getDate()
        except:
            self.getDateFromHeadStr(str(temp['__header__']))
        return temp['data']

    def getDateFromHeadStr(self,headStr):
        self.date = str(dt.datetime.strptime(headStr[-21:-1],'%b %d %H:%M:%S %Y'))[0:10]
    def getDate(self):
        matlab_datenum=self.sensorDataRaw[0,0]
        python_datetime = dt.datetime.fromordinal(int(matlab_datenum)) + dt.timedelta(days=matlab_datenum%1) - dt.timedelta(days = 366)
        self.date = str(python_datetime.date())
   
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
        self.responseData = df.iloc[:,-1].to_list()
        return self.responseData

    def readInData(self,responseFpos,sensorFpos):
        #read in response file
        if responseFpos.endswith('txt'):
            response  = self.readResponseFile(responseFpos)
        elif responseFpos.endswith('csv'):
            response  = self.readResponseFileCSV(responseFpos)
        else:
            raise ValueError('unknown file extension for response file: ' + str(responseFpos))
        #get real frames
        newFrames = range(0,len(response))
        #read in sensor file
        dataT     = self.readSensorTfileMAT(sensorFpos)
        # Check if Matfile is broken!
        if len(dataT)< 1000: # this is a broken matlab file
            frameTemp,self.targetTemp  = self.loadTemplateTemperatureData()
        else:
            #align framenumber with temperature
            frameTemp = self.alignTemperature2Frame(dataT)
        
        #interpolate
        iData = self.interpFrameTemperature(frameTemp,newFrames)

        self.data = np.vstack((iData[:,0],iData[:,1],np.array(response))).T
        
        return self.data
    
    def loadTemplateTemperatureData(self):
        if self.stimulusType == 'adaptation':
            template=pd.read_pickle('brokenTempFile_adap.pkl')
            iData      = template[['frames','temperatureDeg']].to_numpy()
            targetTemp = template['targetTempDeg'].to_numpy()
        else:
            raise NotImplementedError('Stimulus Template ' + str(self.stimulusType) + ' not implemented yet!')
        return iData,targetTemp

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


#        ______________
#       |[]            |
#       |  __________  |
#       |  |File I/O|  |
#       |  | Output |  |
#       |  |________|  |
#       |   ________   |
#       |   [ [ ]  ]   |
#       \___[_[_]__]___|

        
    def setFpos(self):
        defName = self.date +'_'+self.genotype+'_'+self.gender+'_'+self.stimulusType+'_'+self.celltype+'_'+self.cellNumber +'.pkl'
        defName = os.path.join(self.saveDir,defName)
        return str(fileDialog.App('saveTCIdataDialog','Save Data',defName).result)

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
                        'fps':self.fps}
        return returnValue
    

    def prepPandas(self):
        dataDict  = {'frames':self.data[:,0],'temperatureDeg':self.data[:,1],'targetTempDeg':self.targetTemp ,'deltaFbyF':self.data[:,2]}
        #for key,value in dataDict.items():
        #    print(key,len(value))
        self.getStimulus()
        dataDF = pd.DataFrame.from_dict(dataDict)
        dataDF.attrs['date']         = self.date
        dataDF.attrs['gender']       = self.gender
        dataDF.attrs['celltype']     = self.celltype
        dataDF.attrs['genotype']     = self.genotype
        dataDF.attrs['offset']       = self.offset
        dataDF.attrs['stimulusType'] = self.stimulusType
        dataDF.attrs['stimulus']     = self.stimulus
        dataDF.attrs['cellNumber']   = self.cellNumber
        dataDF.attrs['fps']          = self.fps

        return dataDF

    def savePandas(self,savePos='verbose'):
        if savePos == 'verbose':
            savePos = self.setFpos()
        df = self.prepPandas()
        df.to_pickle(savePos)

            
    def saveTXT(self,directory):
        fPos = directory+'/'+self.date +'_'+self.genotype+'_'+self.gender+'_'+self.stimulusType+'_'+self.celltype+'_'+self.cellNumber+'.txt'
        headerStr = ' date: ' + self.date + '\n genotype: '+self.genotype+'\n gender: '+self.gender+'\n stimulus: '+self.stimulusType+'\n celltype: '+self.celltype
        np.savetxt(fPos,self.data,fmt='%i %2.2f %1.6f',header=headerStr)
    
