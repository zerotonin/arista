import pandas as pd
import scipy.io as sio
import matplotlib.pyplot as plt
import numpy as np
import os

class aristaSingleCellData:

    def __init__(self,fijiExportPos,MatLabSensorPos):
        self.fijiExpPos = fijiExportPos
        self.matSenPos = MatLabSensorPos
        
        # preallocation
        self.ca_df       = None
        self.data        = None
        self.stimulus_df = None
        self.sen_df      = None
    
    def readFijiCaData(self):
        """[read the csv file that is generated in the Matlab recording program. Column names are set to frame and df/f (flourescence). 
        Lastly, the index of the Dataframe is set as frame.]
        """
        self.ca_df = pd.read_csv(self.fijiExpPos)
        self.ca_df.columns=['frame','df/f'] 
        self.ca_df = self.ca_df.set_index('frame')

    def readMatLabSensorData(self):
        """[Matlab data of the temperature sensor data are loaded and converted into a dataframe with the respective column names.]
        """
        test = sio.loadmat(self.matSenPos)
        self.sen_df =pd.DataFrame(test['data'],columns=['epoch time','frame','sensor T','target T','drive T'])
        

    def readData(self):
        """[the loaded data is merged ]
        """
        self.readFijiCaData()
        self.readMatLabSensorData()
    
    def getDataLenCutOffs(self,cutOff):
        """[low index and high index cutoffs are set since we are not interested in the whole data, but only the one of the detected Ca2+.]

        Args:
            cutOff (int): the number of data entries we want to keep after the detection of the last Ca2+ frame 

        Returns:
            tuple of ints: the lower and upper index of the relevant data in the sensory data frame
        """
        lowIndex   = self.sen_df[self.sen_df['frame'] == 0].last_valid_index()
        highIndex  = self.sen_df.frame.idxmax()
        lowCutOff  = lowIndex +1 # we are not interested in the 0 frame data  as this is the data before the first ca2+ image
        highCutOff = highIndex + cutOff

        if highCutOff > len(ascd.sen_df):
            highCutOff =  len(ascd.sen_df)
        
        return (lowCutOff,highCutOff)



    def cutSensorDataToRecording(self,cutOff):
        """[drop all unnecessary Data from the dataframe which is not within the Ca2+ recording. Basically, apply the before defined lower and higher cutoffs to the data.]

        Args:
            cutOff ([int]): [description]
        """
        lowCut, highCut = self.getDataLenCutOffs(cutOff)
        self.sen_df = self.sen_df.drop(self.sen_df[(self.sen_df.index < (lowCut))].index) 
        self.sen_df = self.sen_df.drop(self.sen_df[(self.sen_df.index > (highCut))].index)
        self.sen_df['frame'] = self.sen_df['frame'] -1 # as the frames in ca_df start at zero

        

    def reduceSensorDataToFrameCount(self):
        """group the dataframe by frame and calculate the mean of alle sensor-, target-, and drive temperatures. Missing values which were not recorded during the 
        recording session are filled with NaN values.

        Returns:
            [dataframe]: The dataframe grouped after frame number with mean sensor, drive and target temperature of each frame. 
        """
        grouped_df = self.sen_df.groupby('frame', as_index=True).mean()
        grouped_df = grouped_df.reindex(list(range(grouped_df.index.min(),grouped_df.index.max()+1)),fill_value=np.NaN)
        return grouped_df


    def interpolateMissingFrames(self,df):
        """[Filled missing NaN values with interpolated temperature data]

        Args:
            df ([dataframe]): dataframe with mean temperatures and missing NaN values

        Returns:
            [dataframe]: [dataframe with missing values replaced by interpolated temperature values.]
        """
        return df.interpolate()
    

    def makeStimulusDF(self,cutOff):
        
        # type cast the frame column to integer
        self.sen_df['frame'] = pd.to_numeric(self.sen_df['frame'], downcast='integer')
        # reduce the first and last stimulus entry so that pre and post stimuli are not overrepresented
        self.cutSensorDataToRecording(cutOff)
        # now we reduce the dataframe so that we have one entry per recorded Ca2+ frame
        self.stimulus_df = self.reduceSensorDataToFrameCount()   
        # some frames are missed by the DAQ software so we interpolate the temperature data    
        self.stimulus_df = self.interpolateMissingFrames(self.stimulus_df)
    
    def mergeDataSets(self):
        """[combination of all dataframe rows into one singluar dataframe]
        """
        self.data = pd.concat([self.stimulus_df,self.ca_df],axis=1)
    
    def main(self,cutOff=100):
        """[summary]

        Args:
            cutOff (int, optional): [description]. Defaults to 100.
        """
        self.readData()
        self.makeStimulusDF(cutOff)
        self.mergeDataSets()



# relative data paths
dirname = os.path.realpath('.')
fijiExportPos = os.path.join(dirname, 'testData/CC01.csv')
matSenPos     = os.path.join(dirname, 'testData/temperature_data_2021_12_20-12_40.mat')

#testing
ascd = aristaSingleCellData(fijiExportPos,matSenPos)
ascd.main()
ascd.data


#filter test

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

fs = 10  # Sampling frequency
t = ascd.data.index

signala = ascd.data['df/f'] # df/f (flourescnence curve)
plt.plot(t, signala, label='df/f')

signalb = ascd.data['sensor T']  # sensor temperatur curve
plt.plot(t, signalb, label='sensor T')

signalc = ascd.data['target T']  # target temperatur curve
plt.plot(t, signalc, label='target T')

signald = ascd.data['drive T']  # drive Temperatur curve
plt.plot(t, signald, label='drive T')

fc = 0.1  # Cut-off frequency of the filter
w = fc / (fs / 2) # Normalize the frequency to design digital filter, not analog one
b, a = signal.butter(5, w, 'low')
output = signal.filtfilt(b, a, signalb) 
plt.plot(t, output, label='filtered')
plt.legend()
plt.show()



#test 2

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

fs = 10  # Sampling frequency
t = ascd.data.index
signala = ascd.data['df/f'] # df/f (flourescnence curve)
plt.plot(t, signala, label='df/f')

signalb = ascd.data['sensor T']  # sensor temperatur curve
plt.plot(t, signalb, label='sensor T')

signalc = ascd.data['target T']  # target temperatur curve
plt.plot(t, signalc, label='target T')

signald = ascd.data['drive T']  # drive Temperatur curve
plt.plot(t, signald, label='drive T')

cutoff = 1  # Cut-off frequency of the filter
nyq_freq = fc / (fs / 2) # Normalize the frequency

def butter_lowpass(cutoff, nyq_freq, order=4):
    normal_cutoff = float(cutoff) / nyq_freq
    b, a = signal.butter(order, normal_cutoff, btype='lowpass')
    return b, a

def butter_lowpass_filter(data, cutoff, nyq_freq, order=4):
    b, a = butter_lowpass(cutoff, nyq_freq, order=order)
    y = signal.filtfilt(b, a, data)
    return y
plt.legend()
plt.show()