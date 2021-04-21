import tciPlot, tciAnalysis,autoMetaFinder,os,glob
import tempFileIO  as tIO
from tqdm import tqdm
import matplotlib.pyplot as plt

class massiveAligner():
    
    def __init__(self,sourceDir,saveDir,experimentType):
        self.sourceDir      = sourceDir
        self.saveDir        = saveDir
        self.experimentType = experimentType
        self.metaDict       = None
        self.tIOobject      = None
        self.df             = None
        self.tAna           = None
        self.savePos        = None    
        self.testPos        = None    

    def fullAnalysis(self):
        self.tAna = tciAnalysis.tciAnalysis(self.df)
        self.tAna.driftCorrection()
        self.tAna.chooseFit()
        self.tAna.augmentDF()

    def makeSavePos(self):
        self.savePos  = self.metaDict['strain']+'_'+ self.metaDict['cellType']
        self.savePos += '_'+ self.metaDict['gender']
        self.savePos += '_a'+ str(self.metaDict['cellNum'])
        self.savePos += '_e'+ str(self.metaDict['expNum'])
        self.savePos += '_'+ self.experimentType
        self.savePos += '_driftCorr-'+ self.df.attrs['driftCorr']
        self.savePos += '_'+ self.df.attrs['date']
        self.savePos += '.csv'
        self.savePos = os.path.join(self.saveDir,self.savePos)

    def makeTestPos(self):
        self.testPos  = self.metaDict['strain']+'_'+ self.metaDict['cellType']
        self.testPos += '_'+ self.metaDict['gender']
        self.testPos += '_a'+ str(self.metaDict['cellNum'])
        self.testPos += '_e'+ str(self.metaDict['expNum'])
        self.testPos += '_'+ self.experimentType
        self.testPos += '_driftCorr-*'
        self.testPos += '_'+ self.df.attrs['date']
        self.testPos += '.csv'
        self.testPos = os.path.join(self.saveDir,self.testPos)

    def run(self):
        csvFiles = [os.path.join(dp, f) for dp, dn, filenames in os.walk(self.sourceDir) for f in filenames if os.path.splitext(f)[1] == '.csv']
        csvFiles.sort()
        for path in tqdm(csvFiles,desc='analysing Ca2+ files'):
            aMF = autoMetaFinder.autoMetaFinder(path)
            self.metaDict  = aMF.run()
            self.tIOobject = tIO.tempFileIO(self.metaDict['strain'],
                                        self.metaDict['gender'],
                                        self.experimentType ,
                                        self.metaDict['cellType'],
                                        self.metaDict['cellNum'],
                                        saveDir=self.saveDir,
                                        fps = 10)
            
            matFiles = [os.path.join(dp, f) for dp, dn, filenames in os.walk(self.metaDict['expDir']) for f in filenames if os.path.splitext(f)[1] == '.mat']
            for matPath in matFiles:
                try:
                    self.tIOobject.readInData(str(path),str(matPath))
                    self.df   = self.tIOobject.prepPandas()
                    self.makeTestPos()
                    if len(glob.glob(self.testPos)) == 0:
                        self.fullAnalysis()
                        self.makeSavePos()
                        self.df.to_csv(self.savePos)
                except:
                    raise Exception('Could not analyse file: ' + str(path))
            