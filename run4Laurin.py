import numpy as np
import faulthandler
import tempFileIO  as tIO
import tciPlot 
import dill,os
import matplotlib.pyplot as plt
from importlib import reload  
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
tIOobject.savePandas()
tPLT = tciPlot.tciPlot(df)
tPLT.lineP_simpleSurvey()
print('here')
plt.show()