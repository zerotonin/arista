import numpy as np
import tempFileIO  as tIO
import dill
import matplotlib.pyplot as plt
reload(tIO)

genotype     = 'NompC3'
gender       = 'm'
celltype     = 'CC'
cellnumber   = '1'
stimulus     = 'ascAmp'
saveDirTemp  = '/home/rkossen/CalciumImagingData/CompiledData/'
sourceDir    = '/media/gwdg-backup/BackUp/RobertK_Backup/Calcium_Imaging/Arista-Temperature/NompC3-NSybLexA-LexOpGCamp6/'
#sensorFpos   = sourceDir + 'temperature_data_2017_01_08-17_15.mat'
#responseFpos = sourceDir + '2017-08-01-NompC3_NSybLexA-LexOpGCamp6_m02_1_CC1.txt'


tIOobject  = tIO.tempFileIO(genotype,gender,stimulus,celltype,cellnumber,saveDir=saveDirTemp)
#data = tIOobject.readInData(responseFpos,sensorFpos) 
data = tIOobject.verboseMode(sourceDir)
tIOobject.calcResponse()
tIOobject.savePy()



