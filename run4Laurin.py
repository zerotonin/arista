import numpy as np
import faulthandler
import tempFileIO  as tIO
import tciPlot, tciAnalysis,autoMetaFinder
import dill,os
import matplotlib.pyplot as plt
from importlib import reload  
from tqdm import tqdm
import pandas as pd
reload(tIO)

genotype     = 'NompC3'
gender       = 'm'
celltype     = 'CC'
cellnumber   = '1'
stimulus     = 'ascAmp'
saveDirTemp  = r'/home/bgeurten/ownCloud/personalSwaps/Laurin-Bart/resultDir'
sourceDir    = r'/home/bgeurten/ownCloud/personalSwaps/Laurin-Bart/exampleDataSet'


faulthandler.enable()
tIOobject  = tIO.tempFileIO(genotype,gender,stimulus,celltype,cellnumber,saveDir=saveDirTemp)
#data = tIOobject.readInData(responseFpos,sensorFpos) 
data = tIOobject.verboseMode(sourceDir,responseExt='*.csv')
#tIOobject.calcResponse()
#tIOobject.savePy()
df = tIOobject.prepPandas()

reload(tciAnalysis)
tAna = tciAnalysis.tciAnalysis(df)
tAna.driftCorrection()
tAna.chooseFit()

reload(tciPlot)
tPLT = tciPlot.tciPlot(df)
tPLT.correctionSurvey(tAna.time_sec,tAna.df['deltaFbyF'],tAna.dfbf_expfit,tAna.dfbf_polyfit,tAna.dfbyf_expCorr,tAna.dfbyf_polyCorr)
plt.show()

tIOobject.savePandas()
tPLT = tciPlot.tciPlot(df)
tPLT.lineP_simpleSurvey()
print('here')
plt.show()


import tempFileIO  as tIO
from pathlib import Path
import tciPlot, tciAnalysis,autoMetaFinder
from tqdm import tqdm
import matplotlib.pyplot as plt

sourceDir = '/media/gwdg-backup/BackUp/Laurin/ms-thesis/analysis_data2/'
saveDir   = '/media/gwdg-backup/BackUp/Laurin/ms-thesis/result/'
for path in tqdm(Path(sourceDir).rglob('*.csv'),desc='running...'):
    aMF = autoMetaFinder.autoMetaFinder(path)
    metaDict = aMF.run()
    tIOobject  = tIO.tempFileIO(metaDict['strain'],
                                metaDict['gender'],
                                'adaptation',
                                metaDict['cellType'],
                                metaDict['cellNum'],
                                saveDir=saveDir,
                                fps = 10)
    for matPath in Path(metaDict['expDir']).rglob('*.mat'):
        tIOobject.readInData(str(path),str(matPath))
        df = tIOobject.prepPandas()
        tAna = tciAnalysis.tciAnalysis(df)
        tAna.driftCorrection()
        tPLT = tciPlot.tciPlot(df)
        tPLT.correctionSurvey(tAna.time_sec,tAna.df['deltaFbyF'],tAna.dfbf_expfit,tAna.dfbf_polyfit,tAna.dfbyf_expCorr,tAna.dfbyf_polyCorr)
        plt.show()
