# python-o365
A simple python library for interaction with Office 365. 


# NB
cat blank.pdf | lp -d "ricoh-double" -U tester -oColorModel=Gray -oDuplex=DuplexNoTumble -oJobType=LockedPrint -oLockedPrintPassword=1234

args = '/usr/bin/lp -U tester -oColorModel=Gray -oDuplex=DuplexNoTumble -oJobType=LockedPrint -oLockedPrintPassword=1234'.split()
p = subprocess.Popen(args,stdin=subprocess.PIPE)                                                           
p.stdin.write(open('README.md','rb').read())
p.communicate()
request id is ricoh-double-8 (0 file(s))
(None, None)


# To the King!
