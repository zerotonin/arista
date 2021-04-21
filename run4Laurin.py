#  _________.__               .__             _________.__            __   
# /   _____/|__| ____    ____ |  |   ____    /   _____/|  |__   _____/  |_ 
# \_____  \ |  |/    \  / ___\|  | _/ __ \   \_____  \ |  |  \ /  _ \   __\
# /        \|  |   |  \/ /_/  >  |_\  ___/   /        \|   Y  (  <_> )  |  
#/_______  /|__|___|  /\___  /|____/\___  > /_______  /|___|  /\____/|__|  
#        \/         \//_____/           \/          \/      \/             
#

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
tAna.augmentDF()

reload(tciPlot)
tPLT = tciPlot.tciPlot(df)
tPLT.correctionSurvey(tAna.time_sec,tAna.df['deltaFbyF'],tAna.dfbf_expfit,tAna.dfbf_polyfit,tAna.dfbyf_expCorr,tAna.dfbyf_polyCorr)
plt.show()

tIOobject.savePandas()
tPLT = tciPlot.tciPlot(df)
tPLT.lineP_simpleSurvey()
print('here')
plt.show()


#   _____                       .__                  _____  .__  .__  .__                                     __   
#  /     \ _____    ______ _____|__|__  __ ____     /  _  \ |  | |  | |__| ____   ____   _____   ____   _____/  |_ 
# /  \ /  \\__  \  /  ___//  ___/  \  \/ // __ \   /  /_\  \|  | |  | |  |/ ___\ /    \ /     \_/ __ \ /    \   __\
#/    Y    \/ __ \_\___ \ \___ \|  |\   /\  ___/  /    |    \  |_|  |_|  / /_/  >   |  \  Y Y  \  ___/|   |  \  |  
#\____|__  (____  /____  >____  >__| \_/  \___  > \____|__  /____/____/__\___  /|___|  /__|_|  /\___  >___|  /__|  
#        \/     \/     \/     \/              \/          \/            /_____/      \/      \/     \/     \/      
#
#
    
    

import massiveAligner
from importlib import reload  

reload(massiveAligner)
sourceDir      = '/media/gwdg-backup/BackUp/Laurin/ms-thesis/analysis_data2/'
saveDir        = '/media/gwdg-backup/BackUp/Laurin/ms-thesis/result/'
experimentType = 'adaptation'

mA = massiveAligner.massiveAligner(sourceDir,saveDir,experimentType)
mA.run()