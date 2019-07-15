from O365 import *

#Initilise the information array
calcols = utils.MasterCategoryColorPreset()

#Load information directly from array
print('Colorid:', calcols.colors[1].colorid)
print('RGB:', calcols.colors[1].rgb)
print('HEX:', calcols.colors[1].hex)
print('Name:', calcols.colors[1].name)


#Load information by searching by id
print('RGB(16):', calcols.get_rgbstring_fromid(16))
print('HEX(16):', calcols.get_hexstring_fromid(16))
print('Name(16):', calcols.get_name_fromid(16))

#Load info object from Outlook Preset name
print('Preset3:', calcols.get_item_fromoutlook("Preset3").__dict__)
