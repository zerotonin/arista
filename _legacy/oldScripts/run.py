# -*- coding: utf-8 -*-
"""
Created on Tue Jan 10 11:29:53 2017

@author: rkossen
"""

import numpy as np
import tempFileIO  as tIO
import dill
import matplotlib.pyplot as plt

reload(tIO)
%matplotlib wx
genotype     = 'NompC-HeterozControl'
gender       = 'f01b'
celltype     = 'HC'
cellnumber   = '1'
stimulus     = 'descAmp'
saveDirTemp  = '/home/rkossen/CalciumImagingData/CompiledData/'
sourceDir    = '/home/rkossen/CalciumImagingData/Arista-Temperature/NompC3-HeterozControl/'#'/media/gwdg-backup/BackUp/RobertK_Backup/Calcium_Imaging/Arista-Temperature/NompC3-NSybLexA-LexOpGCamp6/'

fPos = '/media/gwdg-backup/BackUp/RobertK_Backup/Calcium_Imaging/Arista-Temperature/ascamp/temperature/temperature_data_2016_05_27_fl1_fr1_ascamp.mat'
fPos2 ='/media/gwdg-backup/BackUp/RobertK_Backup/Calcium_Imaging/Arista-Temperature/ascamp/response/ascampCC1_160527_fl1_fr1.txt'
#sensorFpos   = sourceDir + 'temperature_data_2017_01_08-17_15.mat'
#responseFpos = sourceDir + '2017-08-01-NompC3_NSybLexA-LexOpGCamp6_m02_1_CC1.txt'


tIOobject  = tIO.tempFileIO(genotype,gender,stimulus,celltype,cellnumber,saveDir=saveDirTemp)
#data = tIOobject.readInData(responseFpos,sensorFpos) 
data = tIOobject.verboseMode(sourceDir)
tIOobject.calcResponse()
tIOobject.savePy()



