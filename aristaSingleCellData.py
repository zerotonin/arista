import pandas as pd
import scipy.io as sio
import matplotlib.pyplot as plt

fijiExportPos = '/media/bgeurten/58DF-F2AF/exp02/Arista_left/CC01.csv'
matSenPos  = '/media/bgeurten/58DF-F2AF/exp02/Arista_left/temperature_data_2021_12_20-12_40.mat'

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
        Bart Ist deer ooolste
        pass

    def reduceSensorDataToFrameCount(self):
        # group by function
        pass

    def mergeDataFrames(self):
        pass


ascd = aristaSingleCellData(fijiExportPos,matSenPos)
ascd.readData()
ascd.ca_df
ascd.sen_df['frame'] = pd.to_numeric(ascd.sen_df['frame'], downcast='integer')