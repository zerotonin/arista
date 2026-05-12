# -*- coding: utf-8 -*-
"""
Created on Fri Jan 13 16:14:43 2017

@author: rkossen
"""

import pickle, os
import numpy as np
import matplotlib.pyplot as plt
%matplotlib wx
saveDirTemp  = '/home/rkossen/CalciumImagingData/CompiledData/'
subfolder = 'NSybLexALexOpGCamp6'

#load everything
fList = os.listdir('~')saveDirTemp+subfolder)
dataSet = list()
for fileName in fList:
     dataSet.append( pickle.load( open( saveDirTemp+subfolder+'/'+fileName, "rb" ) ))
     
#get experiment combinations
expList = list()
for exp in dataSet:
    expList.append(exp['celltype']+exp['stimulusType'])

#get uniques
uqExp = list(set(expList))
for i in range(0):
    expType  = i;
    expType2  = 1;
    expList.index(uqExp[expType])
    indices = [i for i, exp in enumerate(expList) if exp == uqExp[expType]]
    # get indices
    expList.index(uqExp[expType2])
    indices2 = [i for i, exp in enumerate(expList) if exp == uqExp[expType2]]
    #indices.extend(indices2)
    
    # extract data
    data    = np.zeros((6500,len(indices)))
    relResp = np.zeros((9,len(indices)))
    absResp = np.zeros((9,len(indices)))
    counter = 0
    for i in indices:
        exp = dataSet[i]
        data[:,counter]    = exp['data'][:,-1]
        absResp[:,counter] = exp['absResponse'][:,-1]
        relResp[:,counter] = exp['relResponse'][:,-1]
        counter+=1
#    if expType == 0:
#        data = np.delete(data, 4, 1)
#    else:
#        data = np.delete(data, 1, 1)
            
            
        
    
    # calculate central values
    relRespStim = exp['relResponse'][:,0]
    absRespStim = exp['absResponse'][:,0]
    dataStim = exp['data'][:,0:2]
    dataStim[:,0] = dataStim[:,0]/10.
    
    relRespMed = np.median(relResp,axis=1)
    absRespMed = np.median(absResp,axis=1)
    dataMed = np.mean(data,axis=1)
    #plot
    
    plt.figure()
    plt.subplot(211)
    plt.plot(dataStim[:,0],dataMed)
    plt.ylim(-.3, .6)
    plt.ylabel('delta f by f')
    plt.subplot(212)
    plt.plot(dataStim[:,0],dataStim[:,1])
    plt.xlabel('time [s]')
    plt.ylabel('stimulus temperature [deg C]')
    plt.title(uqExp[expType])
    plt.show()

plt.clf()
plt.plot(relRespStim,relRespMed,'o')
#plt.ylim(-.4, .4)
plt.xlabel('temperature change [deg C]')
plt.ylabel('peak response [delta f by f]')
