'''
Source: https://docs.microsoft.com/en-us/graph/api/resources/outlookcategory?view=graph-rest-1.0
-1  255,255,255 #FFFFFF No color
0   240,125,136 #F07D88 Red
1   255,140,0   #FF9509 Orange
2   254,203,111 #FECB6F Brown
3   255,241,0   #FFF100 Yellow
4   95,190,125  #5FBE7D Green
5   51,186,177  #33BAB1 Teal
6   163,179,103 #A3B367 Olive
7   85,171,229  #55ABE5 Blue
8   168,149,226 #A895E2 Purple
9   228,139,181 #E48BB5 Cranberry
10  185,192,203 #B9C0CB Steel
11  76,89,110   #4C596E DarkSteel
12  171,171,171 #ABABAB Gray
13  102,102,102 #666666 DarkGray
14  71,71,71    #474747 Black
15  145,10,25   #910A19 DarkRed
16  206,75,40   #CE4B28 DarkOrange
17  153,110,54  #996E36 DarkBrown
18  176,169,35  #B0A923 DarkYellow
19  2,104,2     #026802 DarkGreen
20  28,99,103   #1C6367 DarkTeal
21  92,106,34   #5C6A22 DarkOlive
22  37,64,105   #254069 DarkBlue
23  86,38,133   #562685 DarkPurple
24  128,39,93   #80275D DarkCranberry
'''

class MasterCategoryColorDefinition(object):
    '''Color types for Category '''

    def __init__(self, colorid, outlookname, rgbstring, hexstring, name):
        '''Creates a new structure class for holding category color information.'''
        self.colorid = colorid
        self.outlookname = outlookname
        self.rgb = rgbstring
        self.hex = hexstring
        self.name = name



class MasterCategoryColorPreset(object):
    '''Array for holding Category Coluors '''

    def __init__(self):
        '''Pre loads the class with the standard set of colours'''
        self.colors = []

        self.colors.append(MasterCategoryColorDefinition(-1, 'none',     '255,255,255', '#FFFFFF', 'No Color'))
        self.colors.append(MasterCategoryColorDefinition(0,  'preset0',  '240,125,136', '#F07D88', 'Red'))
        self.colors.append(MasterCategoryColorDefinition(1,  'preset1',  '255,140,0',   '#FF9509', 'Orange'))
        self.colors.append(MasterCategoryColorDefinition(2,  'preset2',  '254,203,111', '#FECB6F', 'Peach'))
        self.colors.append(MasterCategoryColorDefinition(3,  'preset3',  '255,241,0',   '#FFF100', 'Yellow'))
        self.colors.append(MasterCategoryColorDefinition(4,  'preset4',  '95,190,125',  '#5FBE7D', 'Green'))
        self.colors.append(MasterCategoryColorDefinition(5,  'preset5',  '51,186,177',  '#33BAB1', 'Teal'))
        self.colors.append(MasterCategoryColorDefinition(6,  'preset6',  '163,179,103', '#A3B367', 'Olive'))
        self.colors.append(MasterCategoryColorDefinition(7,  'preset7',  '85,171,229',  '#55ABE5', 'Blue'))
        self.colors.append(MasterCategoryColorDefinition(8,  'preset8',  '168,149,226', '#A895E2', 'Purple'))
        self.colors.append(MasterCategoryColorDefinition(9,  'preset9',  '228,139,181', '#E48BB5', 'Maroon'))
        self.colors.append(MasterCategoryColorDefinition(10, 'preset10', '185,192,203', '#B9C0CB', 'Steel'))
        self.colors.append(MasterCategoryColorDefinition(11, 'preset11', '76,89,110',   '#4C596E', 'Dark steel'))
        self.colors.append(MasterCategoryColorDefinition(12, 'preset12', '171,171,171', '#ABABAB', 'Gray'))
        self.colors.append(MasterCategoryColorDefinition(13, 'preset13', '102,102,102', '#666666', 'Dark gray'))
        self.colors.append(MasterCategoryColorDefinition(14, 'preset14', '71,71,71',    '#474747', 'Black'))
        self.colors.append(MasterCategoryColorDefinition(15, 'preset15', '145,10,25',   '#910A19', 'Dark red'))
        self.colors.append(MasterCategoryColorDefinition(16, 'preset16', '206,75,40',   '#CE4B28', 'Dark orange'))
        self.colors.append(MasterCategoryColorDefinition(17, 'preset17', '153,110,54',  '#996E36', 'Dark peach'))
        self.colors.append(MasterCategoryColorDefinition(18, 'preset18', '176,169,35',  '#B0A923', 'Dark yellow'))
        self.colors.append(MasterCategoryColorDefinition(19, 'preset19', '2,104,2',     '#026802', 'Dark green'))
        self.colors.append(MasterCategoryColorDefinition(20, 'preset20', '28,99,103',   '#1C6367', 'Dark teal'))
        self.colors.append(MasterCategoryColorDefinition(21, 'preset21', '92,106,34',   '#5C6A22', 'Dark olive'))
        self.colors.append(MasterCategoryColorDefinition(22, 'preset22', '37,64,105',   '#254069', 'Dark blue'))
        self.colors.append(MasterCategoryColorDefinition(23, 'preset23', '86,38,133',   '#562685', 'Dark purple'))
        self.colors.append(MasterCategoryColorDefinition(24, 'preset24', '128,39,93',   '#80275D', 'Dark maroon'))

    def get_hexstring_fromid(self, colorid):
        '''Finds the Hex Value by Color ID'''
        for i, c in enumerate(self.colors):
            if c.colorid == colorid:
                return c.hex

    def get_rgbstring_fromid(self, colorid):
        '''Finds the Hex Value by Color ID'''
        for i, c in enumerate(self.colors):
            if c.colorid == colorid:
                return c.rgb

    def get_name_fromid(self, colorid):
        '''Finds the Hex Value by Color ID'''
        for i, c in enumerate(self.colors):
            if c.colorid == colorid:
                return c.name

    def get_item_fromid(self, colorid):
        '''Finds the whole sub object by Color ID'''
        for i, c in enumerate(self.colors):
            if c.colorid == colorid:
                return c

    def get_item_fromname(self, name):
        '''Finds the whole sub object by Name'''
        for i, c in enumerate(self.colors):
            if c.name == name:
                return c

    def get_item_fromoutlook(self, name):
        '''Finds the whole sub object by Outlook Name'''
        for i, c in enumerate(self.colors):
            if c.outlookname == name.lower():
                return c

