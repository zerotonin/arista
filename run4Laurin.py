import numpy as np
import tempFileIO  as tIO
import dill,os
import matplotlib.pyplot as plt
from importlib import reload  
reload(tIO)

genotype     = 'NompC3'
gender       = 'm'
celltype     = 'CC'
cellnumber   = '1'
stimulus     = 'ascAmp'
saveDirTemp  = '~/ownCloud/personalSwaps/Laurin-Bart/resultDir'
sourceDir    = '~/ownCloud/personalSwaps/Laurin-Bart/exampleDataSet'


tIOobject  = tIO.tempFileIO(genotype,gender,stimulus,celltype,cellnumber,saveDir=saveDirTemp)
#data = tIOobject.readInData(responseFpos,sensorFpos) 
data = tIOobject.verboseMode(sourceDir,responseExt='*.csv')
tIOobject.calcResponse()
#tIOobject.savePy()

