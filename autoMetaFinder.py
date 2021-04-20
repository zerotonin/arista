import os
import re

class autoMetaFinder():

    def __init__(self,csvPos):
        self.csvPos   = csvPos
        self.expDir   = None
        self.cellType = None
        self.cellNum  = None
        self.expNum   = None
        self.gender   = None
        self.strain   = None
        self.export   = None

    def getStrBetween(self,searchStr,a,b):
        result = re.search(a+'(.*)'+b,searchStr)
        return result.group(1)
    
    def getCellTypeAndNum(self):
        cellTypeNumStr= os.path.basename(self.csvPos)
        self.cellType = cellTypeNumStr.split('_')[0]
        self.cellNum  = int(self.getStrBetween(cellTypeNumStr,'_','.csv'))
        self.expDir = os.path.dirname(self.csvPos)

    def getExpNumGenderStrain(self):
        expNumGenderStr = os.path.basename(self.expDir)
        self.expNum = int(expNumGenderStr.split('_')[0])
        self.gender = expNumGenderStr.split('_')[1]

        strainDir = os.path.dirname(self.expDir)
        self.strain = os.path.basename(strainDir)
    
    def prepMetaData(self):
        self.export = {'expDir'   : self.expDir,
                       'cellType' : self.cellType,
                       'cellNum'  : self.cellNum,
                       'expNum'   : self.expNum,
                       'gender'   : self.gender,
                       'strain'   : self.strain}

    def run(self):
        self.getCellTypeAndNum()
        self.getExpNumGenderStrain()
        self.prepMetaData()
        return self.export