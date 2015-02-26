import subprocess
import os

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
			command.append(str(op))

		print command
		p = subprocess.Popen(command,stdout=subprocess.PIPE,stdin=subprocess.PIPE)
		#outs = p.communicate(input=item)[0]
		p.stdin.write(item)
		outs = p.communicate()
		print outs


class Option( object ):


	def __init__(self,name,options,default=None):
		self.name = name
		self.options = options
		if default:
			self.default = default
		else:
			self.default = self.options[0]


	def __str__(self):
		return '-o{0}={1} '.format(self.name,self.default)


	def setDefault(self,index):
		if index > len(options):
			return False
		if index < 0:
			return False
		self.default = self.options[index]
		return True


if __name__ == '__main__':
	ops = []
	ops.append(Option('ColorModel',['Gray']))
	ops.append(Option('Duplex',['DuplexNoTumble']))
	ops.append(Option('JobType',['LockedPrint']))
	ops.append(Option('LockedPrintPassword',['1234']))
	p = Printer('ricoh-double',{'U':'tester'},ops)
	p.sendPrint(open('README.md','rb').read())



