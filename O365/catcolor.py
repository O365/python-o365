'''
-1  255,255,255 #FFFFFF No color
0   240,125,136 #F07D88 Red
1   255,140,0   #FF9509 Orange
2   254,203,111 #FECB6F Peach
3   255,241,0   #FFF100 Yellow
4   95,190,125  #5FBE7D Green
5   51,186,177  #33BAB1 Teal
6   163,179,103 #A3B367 Olive
7   85,171,229  #55ABE5 Blue
8   168,149,226 #A895E2 Purple
9   228,139,181 #E48BB5 Maroon
10  185,192,203 #B9C0CB Steel
11  76,89,110   #4C596E Dark steel
12  171,171,171 #ABABAB Gray
13  102,102,102 #666666 Dark gray
14  71,71,71    #474747 Black
15  145,10,25   #910A19 Dark red
16  206,75,40   #CE4B28 Dark orange
17  153,110,54  #996E36 Dark peach
18  176,169,35  #B0A923 Dark yellow
19  2,104,2     #026802 Dark green
20  28,99,103   #1C6367 Dark teal
21  92,106,34   #5C6A22 Dark olive
22  37,64,105   #254069 Dark blue
23  86,38,133   #562685 Dark purple
24  128,39,93   #80275D Dark maroon
'''

class CatColorType(object):
    '''Color types for Category '''

    def __init__(self, colorid, rgbstring, hexstring, name):
        '''Creates a new structure class for holding category color information.'''
        self.colorid = colorid
        self.rgb = rgbstring
        self.hex = hexstring
        self.name = name



class CatColors(object):
    '''Array for holding Category Colors '''

    def __init__(self):
        '''Pre loads the class with the standard set of colors'''
        self.colors = []

        self.colors.append(CatColorType(0, '240,125,136', '#F07D88', 'Red'))
        self.colors.append(CatColorType(1, '255,140,0', '#FF9509', 'Orange'))
        self.colors.append(CatColorType(2, '254,203,111', '#FECB6F', 'Peach'))
        self.colors.append(CatColorType(3, '255,241,0', '#FFF100', 'Yellow'))
        self.colors.append(CatColorType(4, '95,190,125', '#5FBE7D', 'Green'))
        self.colors.append(CatColorType(5, '51,186,177', '#33BAB1', 'Teal'))
        self.colors.append(CatColorType(6, '163,179,103', '#A3B367', 'Olive'))
        self.colors.append(CatColorType(7, '85,171,229', '#55ABE5', 'Blue'))
        self.colors.append(CatColorType(8, '168,149,226', '#A895E2', 'Purple'))
        self.colors.append(CatColorType(9, '228,139,181', '#E48BB5', 'Maroon'))
        self.colors.append(CatColorType(10, '185,192,203', '#B9C0CB', 'Steel'))
        self.colors.append(CatColorType(11, '76,89,110', '#4C596E', 'Dark steel'))
        self.colors.append(CatColorType(12, '171,171,171', '#ABABAB', 'Gray'))
        self.colors.append(CatColorType(13, '102,102,102', '#666666', 'Dark gray'))
        self.colors.append(CatColorType(14, '71,71,71', '#474747', 'Black'))
        self.colors.append(CatColorType(15, '145,10,25', '#910A19', 'Dark red'))
        self.colors.append(CatColorType(16, '206,75,40', '#CE4B28', 'Dark orange'))
        self.colors.append(CatColorType(17, '153,110,54', '#996E36', 'Dark peach'))
        self.colors.append(CatColorType(18, '176,169,35', '#B0A923', 'Dark yellow'))
        self.colors.append(CatColorType(19, '2,104,2', '#026802', 'Dark green'))
        self.colors.append(CatColorType(20, '28,99,103', '#1C6367', 'Dark teal'))
        self.colors.append(CatColorType(21, '92,106,34', '#5C6A22', 'Dark olive'))
        self.colors.append(CatColorType(22, '37,64,105', '#254069', 'Dark blue'))
        self.colors.append(CatColorType(23, '86,38,133', '#562685', 'Dark purple'))
        self.colors.append(CatColorType(24, '128,39,93', '#80275D', 'Dark maroon'))

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
