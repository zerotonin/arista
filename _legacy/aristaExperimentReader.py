import aristaSingleCellData
import os, glob, re



class aristaExperimentReader:
    
    def __init__(self,source_directory,save_directory,log_file_pos=None):
        self.source_directory = source_directory
        self.save_directory   = save_directory 
        self.log_file_pos     = log_file_pos 
      
    def get_all_files_in_experiment_dir(self):
        all_file_list = [f for f in os.listdir(self.source_directory)]
        self.csv_file_list = [os.path.join(self.source_directory, f) for f in all_file_list if f.endswith('.csv')]
        self.mat_file_list = [os.path.join(self.source_directory, f) for f in all_file_list if f.endswith('.mat')]
        
    def get_mat_file(self):
        if len(self.mat_file_list) == 1:
            self.mat_file = self.mat_file_list[0]
        else:
            self.mat_file = None

    def read_single_cell_data(self):

        with open(self.log_file_pos,'a') as f:
            for csv_file in self.csv_file_list:
                try:
                    ascd = aristaSingleCellData.aristaSingleCellData(csv_file,self.mat_file)
                    ascd.main(self.save_directory)
                except:
                    if self.mat_file is None:
                        f.write(f'missing or too many mat files: {csv_file}\n')
                    else:
                        f.write(f'{csv_file}\n')

        f.close()
    
    def main(self):
        self.log_file_pos = os.path.join(self.save_directory,'log.txt')
        self.get_all_files_in_experiment_dir()
        self.get_mat_file()
        self.read_single_cell_data()



class multiCaExperimentReader:

    def __init__(self,parent_directory,save_directory):
        self.parent_directory = parent_directory
        self.save_directory = save_directory
        self.experiment_dir_list = list()
    
    def get_all_experiment_directories(self):
        for dirpaths, dirnames, _ in os.walk(parent_directory):
            if not dirnames: self.experiment_dir_list.append(dirpaths)
    
    def main(self):
        self.get_all_experiment_directories()

        for experiment_directory in self.experiment_dir_list:
            aer = aristaExperimentReader(experiment_directory,self.save_directory)
            aer.main()


parent_directory ='/media/gwdg-backup/BackUp/Alex/Cata/Data/het'
save_dir ='/media/gwdg-backup/BackUp/Alex/Cata/result_data/het'

mer = multiCaExperimentReader(parent_directory,save_dir)
mer.main()



