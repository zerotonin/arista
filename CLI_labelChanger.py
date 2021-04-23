class CLI_labelChanger():
    def __init__(self,labelList,listTitleStr = 'labels'):
        self.labelList = labelList
        self.listTitleStr = listTitleStr
        self.labelChanger = dict()

    def listAllOptions(self):
        print(chr(27) + "[2J")
        print('These '+self.listTitleStr+' were entered:')
        print((20+len(self.listTitleStr))*'=')
        for i, dest in enumerate(self.labelList, 1):
            print(" %d. %s" % (i, dest))
        print('')


    

    def renameDLG(self):
        self.listAllOptions()

        correct = '?'
        while (correct != 'y') and (correct != 'n'):
            correct = input('Is this correct? [y/n]')

        if correct == 'y':
            print('All labels will be used!')
            for label in self.labelList:
                self.labelChanger[label] = label
        else:
            for label in self.labelList:

                print('============================================')
                self.enterNewLabel(label)

        print('============================================')
        print('Here are the rules for relabling:')
        print(self.labelChanger)

        return self.labelChanger
        
    
    def enterNewLabel(self,label):

        print("Old label: " + label)
        correct = '?'
        while (correct != 'y') and (correct != 'n') and (correct != 'd'):
            correct = input('Do you want to change the label [y/n] or delete it [d] ?')

        if correct == 'n':

            self.labelChanger[label] = label
        
        elif correct == 'd':
            correct = '?'
            while (correct != 'y')and (correct != 'n'):
                correct = input('Are you sure to delete this label: ' + label + ' ? [y/n]')
                if correct == 'n':
                    self.enterNewLabel(label)
                else:
                    self.labelChanger[label] = '!deleteThisLabel!'
        else:
            correct = '?'
            while (correct != 'y'):
                newLabel = input('Enter new label: ')
                print(label + " -> " + newLabel)
                correct = input('Is this correct? [y/n]')
            self.labelChanger[label] = newLabel