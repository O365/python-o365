from O365 import *

#Initilise the information array
calcols = CatColors()


#Load information directly from array
print 'Colorid:', calcols.colors[1].colorid
print 'RGB:', calcols.colors[1].rgb
print 'HEX:', calcols.colors[1].hex
print 'Name:', calcols.colors[1].name


#Load information by searching by id
print 'RGB(16):', calcols.get_rgbstring_fromid(16)
print 'HEX(16):', calcols.get_hexstring_fromid(16)
print 'Name(16):', calcols.get_name_fromid(16)
