import os
import pandas as pd

class MetaRegister():

    def __init__(self,registerFpos,sourceDir = '/home/bgeurten/ownCloud/personalSwaps/Laurin-Bart/result/'):
        self.registerFpos = registerFpos
        self.sourceDir    = sourceDir
        self.csvFiles     = self.getFilesInDir(self.sourceDir,'.csv')

    def getFilesInDir(self,sourceDir,pattern):
        return [os.path.join(dp, f) for dp, dn, filenames in os.walk(sourceDir) for f in filenames if os.path.splitext(f)[1] == pattern]

    def getMetaInfo(self,fPos):
        metaDict = self.analyseFileName(fPos)
        pass

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