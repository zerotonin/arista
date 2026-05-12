import sys
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QLineEdit, QFileDialog
from PyQt5.QtGui import QIcon

class App(QWidget):

    def __init__(self,dialogType,titleStr,defPath):
        super().__init__()
        self.title = titleStr
        self.left = 10
        self.top = 10
        self.width = 640
        self.height = 480
        self.defaultPath=defPath
        self.dialogType=dialogType
        self.result = None
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        
        if self.dialogType == 'openFileNameDialog':
            self.openFileNameDialog()
        elif self.dialogType == 'openFileNamesDialog':
            self.openFileNamesDialog()
        elif self.dialogType == 'saveFileDialog':
            self.saveFileDialog()
        elif self.dialogType == 'openMatFileDialog':
            self.openMatFileDialog()
        elif self.dialogType == 'openFijiFileDialog':
            self.openFijiFileDialog()
        elif self.dialogType == 'saveTCIdataDialog':
            self.saveTCIdataDialog()
        else:
            raise ValueError('Unknown dialogType: ' + str(self.dialogType))
        
        self.show()
        self.hide()
        self.close()
    def openMatFileDialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", self.defaultPath,"MatLab Files (*.mat);;All Files (*)", options=options)

        if fileName:
            self.result = fileName
    
    def openFijiFileDialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", self.defaultPath,"Comma Seperated Values (*.csv);;ASCII (*.txt);;All Files (*)", options=options)
        if fileName:
            self.result = fileName
    
    def saveTCIdataDialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getSaveFileName(self,"QFileDialog.getSaveFileName()",self.defaultPath,"Pickle Files (*.pkl);;ASCII (*.txt);;All Files (*)", options=options)
        if fileName:
            self.result = fileName
    
    ####################
    # GENERAL EXAMPLES #
    ####################
    
    def openFileNameDialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", "","All Files (*);;Python Files (*.py)", options=options)
        if fileName:
            print(fileName)
    
    def openFileNamesDialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        files, _ = QFileDialog.getOpenFileNames(self,"QFileDialog.getOpenFileNames()", "","All Files (*);;Python Files (*.py)", options=options)
        if files:
            print(files)
    
    def saveFileDialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getSaveFileName(self,"QFileDialog.getSaveFileName()","","All Files (*);;Text Files (*.txt)", options=options)
        if fileName:
            print(fileName)

    def run(self):
        app = QApplication(sys.argv)
        ex = App()
        sys.exit(app.exec_())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
