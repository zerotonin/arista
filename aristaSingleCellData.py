import pandas as pd
import scipy.io as sio
import matplotlib.pyplot as plt
import os

class aristaSingleCellData:

    def __init__(self,fijiExportPos,MatLabSensorPos):
        self.fijiExpPos = fijiExportPos
        self.matSenPos = MatLabSensorPos
        
        # preallocation
        self.ca_df = None
    
    def readFijiCaData(self):
        self.ca_df = pd.read_csv(self.fijiExpPos)
        self.ca_df.columns=['frame','df/f'] 

    def readMatLabSensorData(self):
        test = sio.loadmat(self.matSenPos)
        self.sen_df =pd.DataFrame(test['data'],columns=['epoch time','frame','sensor T','target T','drive T'])
        

    def readData(self):
        self.readFijiCaData()
        self.readMatLabSensorData()

    def cutSensorDataToRecording(self,cutOff=100):
        pass

    def reduceSensorDataToFrameCount(self):
        # group by function
        pass

    def mergeDataFrames(self):
        pass


# relative data paths
dirname = os.path.realpath('.')
fijiExportPos = os.path.join(dirname, 'testData/CC01.csv')
matSenPos     = os.path.join(dirname, 'testData/temperature_data_2021_12_20-12_40.mat')

#testing
ascd = aristaSingleCellData(fijiExportPos,matSenPos)
ascd.readData()
ascd.ca_df
ascd.sen_df['frame'] = pd.to_numeric(ascd.sen_df['frame'], downcast='integer')