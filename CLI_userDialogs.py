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

class CLI_choiceDLG():
    def __init__(self,choiceList,listTitleStr = 'labels',choiceQuest= 'Pick an option '):
        self.choiceList   = choiceList
        self.choiceNum    = len(self.choiceList)
        self.listTitleStr = listTitleStr
        self.choiceQuest  = choiceQuest

    def listAllOptions(self):
        print(chr(27) + "[2J")
        print('These '+self.listTitleStr+' were entered:')
        print((20+len(self.listTitleStr))*'=')

        print(" %d. %s" % (0, 'abort dialog'))
        for i, dest in enumerate(self.choiceList, 1):
            print(" %d. %s" % (i, dest))
        print('')
    
    def pickOption(self,choice='None'):

        self.listAllOptions()
        choice = input(self.choiceQuest + '[0:' +str(self.choiceNum)+']: ')

        if self.testChoice(choice):
            print('You chose: ' + str(choice))
            return int(choice)-1
        else:
            self.pickOption(choice)



    def testChoice(self,string):

        try:
            string_int = int(string)
            if string_int >= 0 and string_int < self.choiceNum+1:
                return True
            else:
                return False
        except ValueError:
            # Handle the exception
            print('Please enter an integer')
            return False