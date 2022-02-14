from fileinput import filename
import pandas as pd
import scipy.io as sio
from scipy import signal
import matplotlib.pyplot as plt
import numpy as np
import os
import matplotlib
import sys
import glob
class aristaSingleCellData:

    def __init__(self,fijiExportPos,MatLabSensorPos,sex,strain,hemisphere):
        self.fijiExpPos = fijiExportPos
        self.matSenPos  = MatLabSensorPos
        self.sex        = sex  
        self.strain     = strain
        self.hemisphere = hemisphere    


        # preallocation
        self.ca_df       = None
        self.data        = None
        self.stimulus_df = None
        self.sen_df      = None
        self.cellType    = None
        self.fig         = None
        #self.time       = None
    
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

        if highCutOff > len(self.sen_df):
            highCutOff =  len(self.sen_df)
        
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
    
   
    def timeVectorConversion(self):
        """[generate ellapsed time for each experiment by convertig matlab time to python time. Hence, each experiment has a duration of 600.2s]
        """
        # convert matlab time to python time
        self.data['epoch time']= pd.to_datetime(self.data['epoch time']-719529, unit='D')
        # generate ellapsed time
        self.data['time_s'] = self.data['epoch time'].diff().dt.total_seconds() 
        self.data['time_s'].iloc[0] = 0.0
        self.data['time_s'] = self.data['time_s'].cumsum()

    def filterSensorTemperature(self,filterDegree = 5,cutOff = 0.075):
        """[applicate low pass filter on Sensor Temperature data to get digital noise out of the signal. digital Butterworth filter used.]

        Args:
            filterDegree (5). Defaults to 5.
            cutOff (0.075): [cut off frequencies which are above 7.5% of original signal]. Defaults to 0.075.
        """
        # calculate sample frequency by calculating the mean periode from the time vector
        # F = 1/P
        sampleFrequency = 1/self.data['time_s'].diff().mean()
        w = cutOff / (sampleFrequency / 2) # Normalize the frequency to design digital filter, not analog one
        b, a = signal.butter(filterDegree, w, 'low')
        self.data['sensor TF'] = signal.filtfilt(b, a, self.data['sensor T']) 

    def plot_sensorT_and_df(self):
        pass

        """[plotting df/f and sensor time over ellapsed time of experiment with yyplot. colorblind friendly colors for graphs and grid added.]
        """
        
        x  = self.data['time_s']
        y1 = self.data['sensor TF']
        y2 = self.data['df/f']
        #combine two plots in one
        fig, ax1 = plt.subplots()

        #sensor TF data, colored 
        line1 = ax1.plot(x,y1,'#ff7f00')
        ax1.set_ylabel('Temperature in °C', color='#ff7f00')
        ax1.tick_params(axis='y', color='#ff7f00', labelcolor='#ff7f00')
        ax1.set_title('\u0394f/f and Sensor Temperature')  #title of graph

        #df/f data, colored
        ax2 = ax1.twinx() #add second y axis
        line2 = ax2.plot(x,y2,'#377eb8')
        ax2.set_ylabel('\u0394f/f', color='#377eb8')
        ax2.tick_params(axis='y', color='#377eb8', labelcolor='#377eb8')
        
        #set legend
        lines = line1 + line2
        ax2.legend(lines, ['sensor TF','\u0394f/f']) 
        plt.grid(color = '#4daf4a', linestyle = '--', linewidth = 0.5)#set grid
        ax1.set_xlabel('time, s')
        return fig
        
    #def getproperties_and_save_Pos(self,targetDir):

        """[create dictionary with properties and call them. define tiemStr and combine new filename with every property.]

        Returns:
            [type]: [return target directry of new file and new filename.]
        """
        FijiPos = os.path.join(dirname, 'testData/WT_CC_F_L_2021-12-20--12-30-26.csv')
        file = os.path.basename(FijiPos) #get only filename from directory

        properties = file.split('_') #crate list with filename attributes
        prob_dict = {'WT':'wildtype', 'CC':'cold cell', 'HC':'hot cell', 'F':'female', 'M':'male', 'L':'left', 'R':'right'} #create dictionary with property keys
        self.strain = prob_dict[properties[0]]
        self.cellType = prob_dict[properties[1]]
        self.sex = prob_dict[properties[2]]
        self.hemisphere = prob_dict[properties[3]]

        timeStr = self.data.iloc[0,0].strftime('%Y-%m-%d--%H-%M-%S') #create date/timestamp
        fileName = f'{self.strain}_{self.cellType}_{self.sex}_{self.hemisphere}_{timeStr}' #define new filename

        return os.path.join(targetDir,fileName)

    def getsex(self):
          if 'M' in self.fijiExpPos.upper():
              self.sex = 'male'
          elif 'F' in self.fijiExpPos.upper():
              self.sex = 'female' 
          else:
              self.sex = 'not defined'            

    def getstrain(self):
           if 'WT' in self.fijiExpPos.upper():
               self.strain = 'wildtype'
           elif '605x603' in self.fijiExpPos.upper():
               self.strain = '605x603'
           elif '603x605' in self.fijiExpPos.upper():
               self.strain = '603x605'
           else:
               self.strain = 'not defined'  

    def gethemisphere(self):
            if 'L' in self.fijiExpPos.upper():
                self.hemisphere = 'left'
            elif 'R' in self.fijiExpPos.upper():
                self.hemisphere = 'right'
            else:
                self.hemisphere = 'not defined'  


    def getCellType(self):
        if 'CC' in self.fijiExpPos.upper():
            self.cellType = 'CC'    
        elif 'HC' in self.fijiExpPos.upper():
            self.cellType = 'HC'
        else:
            self.cellType = 'WC'


    def makeSavePosition(self,targetDir):
        self.getstrain()
        self.getsex()
        self.gethemisphere()
        self.getCellType()
        timeStr = self.data.iloc[0,0].strftime('%Y-%m-%d--%H-%M-%S')       
        fileName = f'{self.strain}_{self.cellType}_{self.sex}_{self.hemisphere}_{timeStr}'
        return os.path.join(targetDir,fileName)
    
    def writeData(self,targetDir):
        if targetDir != None:
            savePos = self.makeSavePosition(targetDir) #change to self.getproperties_and_save_Pos(targetDir) if other solution better
            self.data.to_csv(savePos+'.csv')
            if self.fig != None:
                self.fig.savefig(savePos+'.png')

        
    def main(self,targetDir = None, cutOff=100):
        """[summary]

        Args:
            cutOff (int, optional): [description]. Defaults to 100.
        """
        self.readData()
        self.makeStimulusDF(cutOff)
        self.mergeDataSets()
        # convert matlab time to python time
        self.timeVectorConversion()
        # filter sensor temperature
        self.filterSensorTemperature()
        #show plot
        self.fig = self.plot_sensorT_and_df()
        self.writeData(targetDir)

# relative data paths
dirname = os.path.realpath('.')
fijiExportPos = os.path.join(dirname, 'testData/CC01.csv')
matSenPos     = os.path.join(dirname, 'testData/temperature_data_2021_12_20-12_40.mat')

#testing
ascd = aristaSingleCellData(fijiExportPos,matSenPos,'F','WT','L')
ascd.main(os.path.join(dirname, 'testData/'))
ascd.data





#test
import glob
FijiPos = os.path.join(dirname, 'testData/WT_CC_F_L_2021-12-20--12-30-26.csv')
file = os.path.basename(FijiPos)

properties = file.split('_')
prob_dict = {'WT':'wildtype', 'CC':'cold cell', 'HC':'hot cell', 'F':'female', 'M':'male', 'L':'left', 'R':'right'}
strain = prob_dict[properties[0]]
celltype = prob_dict[properties[1]]
sex = prob_dict[properties[2]]
hemisphere = prob_dict[properties[3]]
date = properties[4]