from msilib.schema import Error
import aristaSingleCellData
import os, glob, re


parentDir = './Data/641/WT_01_f'
saveDir = './sortedData'
allFiles = [f for f in os.listdir(parentDir)]
csvFiles = [os.path.join(parentDir, f) for f in allFiles if f.endswith('.csv')]
matFiles = [os.path.join(parentDir, f) for f in allFiles if f.endswith('.mat')]

if len(matFiles) == 1:
    matFile = matFiles[0]
else:
    raise ValueError('found more or less than one mat file')

for f in csvFiles:
    ascd = aristaSingleCellData.aristaSingleCellData(f,matFile)
    ascd.main(saveDir)