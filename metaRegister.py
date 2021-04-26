import os
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from tqdm import tqdm
from CLI_userDialogs import CLI_labelChanger
from CLI_userDialogs import CLI_choiceDLG
from CLI_userDialogs import CLI_yesNoDLG
from scipy.interpolate import interp1d
class MetaRegister():

    def __init__(self,sourceDir,registerFpos):
        self.registerFpos = registerFpos
        self.sourceDir    = sourceDir
        self.csvFiles     = self.getFilesInDir(self.sourceDir,'.csv')

        self.colNames = ['stimulus','strain','cellType','gender','date','expNum','animalNum','driftCorr','sampleNum','originalSampleNum','temperatureSource','filePosition']
        self.metaRegistry = pd.DataFrame([],columns=self.colNames)

#        ______________
#       |[]            |
#       |  __________  |
#       |  |File I/O|  |
#       |  |Routines|  |
#       |  |________|  |
#       |   ________   |
#       |   [ [ ]  ]   |
#       \___[_[_]__]___|

    def getFilesInDir(self,sourceDir,pattern):
        return [os.path.join(dp, f) for dp, dn, filenames in os.walk(sourceDir) for f in filenames if os.path.splitext(f)[1] == pattern]
    
    
    def read_csvFile(self,fPos):
        data = pd.read_csv(fPos)
        del(data['Unnamed: 0'])
        return data
    
    def saveRegistry(self):
        self.metaRegistry.to_csv(self.registerFpos, index = False)

    def loadRegistry(self,fPos):
        self.metaRegistry = pd.read_csv(fPos)

    
#  ____        _ _     _   _____            _     _              
# |  _ \      (_) |   | | |  __ \          (_)   | |             
# | |_) |_   _ _| | __| | | |__) |___  __ _ _ ___| |_ _ __ _   _ 
# |  _ <| | | | | |/ _` | |  _  // _ \/ _` | / __| __| '__| | | |
# | |_) | |_| | | | (_| | | | \ \  __/ (_| | \__ \ |_| |  | |_| |
# |____/ \__,_|_|_|\__,_| |_|  \_\___|\__, |_|___/\__|_|   \__, |
#                                      __/ |                __/ |
#                                     |___/                |___/ 



    def getMetaInfo(self,fPos):
        metaDict = self.analyseFileName(fPos)
        sampleNum,temeperatureSource = self.analyseData(fPos)
        metaDict['sampleNum']           = sampleNum
        metaDict['originalSampleNum']   = sampleNum
        metaDict['temperatureSource']   = temeperatureSource
        metaDict['filePosition']        = fPos
        return metaDict

    def analyseFileName(self,fPos):
        baseStr = os.path.basename(fPos)[0:-4]
        attribs = baseStr.split('_')
        attribs.reverse()
        if len(attribs) > 8: # there was a underscore in the strain name
            date,driftCorr,stimulus,expNum,animalNum,gender,cellType = attribs[0:7]
            strain = ''
            for strPart in attribs[7::]:
                strain = strPart + '_' + strain # have to  build it reverse as the list is reversed
            strain = strain[0:-1]
        else:
            date,driftCorr,stimulus,expNum,animalNum,gender,cellType,strain = attribs

        driftCorr = driftCorr.split('-')[1]
        expNum = int(expNum[1::])
        animalNum = int(animalNum[1::])
        return {'stimulus':stimulus,'strain':strain,'cellType':cellType,'gender':gender,'date':date,'expNum':expNum,'animalNum':animalNum,'driftCorr':driftCorr}
    
    def analyseData(self,fPos):
        data      = self.read_csvFile(fPos)
        sampleNum = len(data)
        tempAvail = self.checkTemperatureData(data)
        return sampleNum, tempAvail

    def checkTemperatureData(self,data):
        if np.isnan(data['temperatureDeg'][0]):
            return 'None'
        else:
            return 'Original'

    def makeRegistry(self):
        for csvFilePos in tqdm(self.csvFiles,desc='reading csv files'):
            metaInfo = self.getMetaInfo(csvFilePos)
            self.metaRegistry = self.metaRegistry.append(metaInfo, ignore_index=True)
            plt.show()




 #   _____       _       _____  ______    _____                     _     
 #  / ____|     | |     |  __ \|  ____|  / ____|                   | |    
 # | (___  _   _| |__   | |  | | |__    | (___   ___  __ _ _ __ ___| |__  
 #  \___ \| | | | '_ \  | |  | |  __|    \___ \ / _ \/ _` | '__/ __| '_ \ 
 #  ____) | |_| | |_) | | |__| | |       ____) |  __/ (_| | | | (__| | | |
 # |_____/ \__,_|_.__/  |_____/|_|      |_____/ \___|\__,_|_|  \___|_| |_|
 

    
    def getLogIndex(self,dataFrame,columnStr,searchValue):
        return dataFrame[columnStr] == searchValue
    
    def getDataSubSet(self,columnStr,searchValue,dataFrame = None):
        if dataFrame is None:
            dataFrame = self.metaRegistry.copy()
        logicalIndex = self.getLogIndex(dataFrame,columnStr,searchValue)
        return dataFrame[logicalIndex].copy()


#  ______ _        _               _                _______                                  _                  
# |  ____(_)      | |             | |              |__   __|                                | |                 
# | |__   ___  __ | |__  _ __ ___ | | _____ _ __      | | ___ _ __ ___  _ __   ___ _ __ __ _| |_ _   _ _ __ ___ 
# |  __| | \ \/ / | '_ \| '__/ _ \| |/ / _ \ '_ \     | |/ _ \ '_ ` _ \| '_ \ / _ \ '__/ _` | __| | | | '__/ _ \
# | |    | |>  <  | |_) | | | (_) |   <  __/ | | |    | |  __/ | | | | | |_) |  __/ | | (_| | |_| |_| | | |  __/
# |_|    |_/_/\_\ |_.__/|_|  \___/|_|\_\___|_| |_|    |_|\___|_| |_| |_| .__/ \___|_|  \__,_|\__|\__,_|_|  \___|
#                                                                      | |                                      
#                                                                      |_|                                      
#
    def augmentTemperature(self,stimulusStr):
        stimSubDF = self.getDataSubSet('stimulus',stimulusStr) 
        interpDF  = self.getDataSubSet('temperatureSource','None',stimSubDF)
        sourceDF  = self.getDataSubSet('temperatureSource','Original',stimSubDF)
        targetTemp,stimTemp =self.collectOriginalStimData(sourceDF)
        if CLI_yesNoDLG('TEMPERATURE WARNING! You are about to change data files on disk! Do you want to continiue?'):
            self.augmentSubSet(interpDF,targetTemp,stimTemp)

    def augmentSubSet(self,interpDF,targetTemp,stimTemp):
        for index, row in tqdm(interpDF.iterrows(),desc='augmenting temperature data'):
            df = self.read_csvFile(row['filePosition'])
            df['targetTempDeg'] = targetTemp
            df['temperatureDeg']= stimTemp
            df.to_csv(row['filePosition'])
            self.metaRegistry.loc[index,'temperatureSource'] = 'Median'
        self.saveRegistry()
        print(df)
    
    def collectOriginalStimData(self,sourceDF):
        targetTemp = list()
        stimTemp   = list()

        for index, row in sourceDF.iterrows():
            df = self.read_csvFile(row['filePosition'])
            targetTemp.append(df['targetTempDeg'])
            stimTemp.append(df['temperatureDeg'])
        targetTemp = np.array(targetTemp)
        stimTemp   = np.array(stimTemp)

        return np.median(targetTemp,axis = 0),np.mean(stimTemp,axis = 0)


#  _____                                 _        _______ _                
# |  __ \                               | |      |__   __(_)               
# | |__) |___  ___  __ _ _ __ ___  _ __ | | ___     | |   _ _ __ ___   ___ 
# |  _  // _ \/ __|/ _` | '_ ` _ \| '_ \| |/ _ \    | |  | | '_ ` _ \ / _ \
# | | \ \  __/\__ \ (_| | | | | | | |_) | |  __/    | |  | | | | | | |  __/
# |_|  \_\___||___/\__,_|_| |_| |_| .__/|_|\___|    |_|  |_|_| |_| |_|\___|
#                                 | |                                      
#                                 |_|                                      



    def collectData2Interp(self,stimSubDF,frameNumList):
        trialDF = pd.DataFrame([],columns=self.colNames)
        for frameNum in frameNumList:
            tempDF = self.getDataSubSet('sampleNum',frameNum,stimSubDF)
            trialDF = trialDF.append(tempDF,ignore_index=False)
        return trialDF
        
    
    def interpolate2SameSampleLength(self,stimulusStr,fps):
        stimSubDF =  self.getDataSubSet('stimulus',stimulusStr) 
        choiceFrameNum,frameNumList = self.getCorrectSampleLengthCLI(stimSubDF)
        interpDF = self.collectData2Interp(stimSubDF,frameNumList)
        if CLI_yesNoDLG('INTERPOLATION WARNING! You are about to change data files on disk! Do you want to continiue?'):
            self.interpolateSubSet(interpDF,choiceFrameNum,fps)

    
    def interpolateSubSet(self,interpDF,choiceFrameNum,fps):
        for index, row in tqdm(interpDF.iterrows(),desc='resampling data'):
            df = self.read_csvFile(row['filePosition'])
            df_resampled = self.interpolateDF(df,row['originalSampleNum'],choiceFrameNum,fps)
            df_resampled.to_csv(row['filePosition'])
            self.metaRegistry.loc[index,'sampleNum'] = choiceFrameNum
        self.saveRegistry()

    def getCorrectSampleLengthCLI(self,stimSubDF):
        frameNumList = list(stimSubDF['sampleNum'].unique())
        CLI = CLI_choiceDLG(frameNumList,'alloc. frames','Pick correct frame number')
        choiceIndex = CLI.pickOption()
        choiceFrameNum  = frameNumList.pop(choiceIndex)
        return choiceFrameNum,frameNumList


    def interpolateDF(self,df,originalFrameNum,newFrameNum,fps):

        Xresampled    = np.linspace(0,originalFrameNum,newFrameNum)
        df_resampled = df.reindex(df.index.union(Xresampled)).interpolate('linear').loc[Xresampled]

        newFrameIndex = np.linspace(0,newFrameNum-1,newFrameNum,dtype = int)
        df_resampled['frames'] = newFrameIndex
        df_resampled['time_sec'] = newFrameIndex/fps
        return df_resampled

#   _____ _             _         _           _          _     
#  / ____| |           (_)       | |         | |        | |    
# | (___ | |_ _ __ __ _ _ _ __   | |     __ _| |__   ___| |___ 
#  \___ \| __| '__/ _` | | '_ \  | |    / _` | '_ \ / _ \ / __|
#  ____) | |_| | | (_| | | | | | | |___| (_| | |_) |  __/ \__ \
# |_____/ \__|_|  \__,_|_|_| |_| |______\__,_|_.__/ \___|_|___/
                                                              
    def changeStrainLabels(self):
        CLI = CLI_labelChanger(list(self.metaRegistry['strain'].unique()),'strain labels')
        labelChanger = CLI.renameDLG()
        self.metaRegistry['strain'] =self.metaRegistry['strain'].replace(labelChanger,regex=True)