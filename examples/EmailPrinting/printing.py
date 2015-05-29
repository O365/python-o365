import subprocess

class Printer( object ):


	def __init__(self, name, flags=None, options=None):
		self.name = name

		if flags:
			self.flags = flags
		else:
			self.options = {}

		if options:
			self.options = options
		else:
			self.options = []

	def __str__(self):
		ret = 'Printer: ' + self.name + '\n'
		ret +=	'With the call of: '
                for flag in self.flags.keys():
                        ret += '-{0} {1} '.format(flag,self.flags[flag])

                for op in self.options:
			o = str(op)
			if o != '':
				ret += o + ' '
	
		return ret


	def setFlag(self,flag,value):
		if flag == 'd':
			return False
		try:
			self.flags[flag] = value
		except:
			return False
		return True


	def getFlag(self,flag):
		try:
			return self.flags[flag]
		except:
			return False

	
	def addOption(self,new_op):
		for i,op in enumerate(self.options):
			if op.name == new_op.name:
				self.options[i] = new_op
				return True

		self.options.append(op)


	def getOption(self,name):
		for op in self.options:
			if op.name == name:
				return op

		return False

	def __call__(self,item):
		self.sendPrint(item)


	def sendPrint(self,item):
		#command = ['lp','-d',self.name]
		command = ['/usr/bin/lp']
		for flag in self.flags.keys():
			command.append('-{0} {1}'.format(flag,self.flags[flag]))

		for op in self.options:
			o = str(op)
			if o != '':
				command.append(str(op))

		print command
		p = subprocess.Popen(command,stdout=subprocess.PIPE,stdin=subprocess.PIPE)
		#outs = p.communicate(input=item)[0]
		p.stdin.write(item)
		outs = p.communicate()
		print outs


class Option( object ):


	def __init__(self,name,options,default=None,human_name=None):
		self.name = name
		self.options = options
		self.human_name = human_name
		if default:
			self.default = default
		else:
			self.default = self.options[0]


	def __str__(self):
		if self.default:
			return '-o{0}={1} '.format(self.name,self.default)
		return ''

	def setDefault(self,op):
		self.default = op
		return True


def listPrinters():
	lpsc = subprocess.Popen(['lpstat','-s'],stdout=subprocess.PIPE)
	lpstats = lpsc.communicate()[0]

	lpsplit = lpstats.split('\n')[1:-1]

	printers = []
	for p in lpsplit:
		printers.append(p.split()[2:4])

	return printers


def listOptions(printer):
	lpop = subprocess.Popen(['lpoptions','-p',printer,'-l'],stdout=subprocess.PIPE)
	lpout = lpop.communicate()[0].split('\n')[:-1]
	ops = []
	
	for line in lpout:
		name, values = line.split(':')
		human_name = name[name.index('/')+1:]
		name = name[:name.index('/')]
		valuelist = values.split(' ')
		for i,v in enumerate(valuelist):
			if '*' in v:
				valuelist[i] = valuelist[i].replace('*','')
				
		ops.append(Option(name,valuelist,None,human_name))
	
	return ops


def getRicoh():
	ops = listOptions('ricoh-double')
	prin = Printer('ricoh-double',{'U':'tester','t':'testPrint.pdf'},ops)

	op = prin.getOption('ColorModel')
	op.setDefault('Gray')
	prin.addOption(op)

	op = prin.getOption('Duplex')
	op.setDefault('DuplexNoTumble')
	prin.addOption(op)

	op = prin.getOption('JobType')
	op.setDefault('LockedPrint')
	prin.addOption(op)

	op = prin.getOption('LockedPrintPassword')
	op.setDefault('1234')
	prin.addOption(op)

	return prin

if __name__ == '__main__':
	r = getRicoh()
	print r

	r(open('printing.py','r').read())

#To the King!
