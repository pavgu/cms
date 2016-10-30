import subprocess32
import os
import datetime
import pexpect
import git
from Crypto.Cipher import AES
from shutil import copyfile
from shutil import move
from multiprocessing import Pool

def SimpleNetworkDeviceFactory(deviceName, deviceIP, deviceType, configBackupDirectoryPath):
	if deviceType == 'exos':
		return EXOSDevice(deviceName, deviceIP, configBackupDirectoryPath)
	elif deviceType == 'screenos':
		return ScreenOSDevice(deviceName, deviceIP, configBackupDirectoryPath)
	elif deviceType == 'junos':
		return JunOSDevice(deviceName, deviceIP, configBackupDirectoryPath)
	elif deviceType == 'seos':
		return SEOSDevice(deviceName, deviceIP, configBackupDirectoryPath)
	elif deviceType == 'junos-epg':
		return JUNOSEPGDevice(deviceName, deviceIP, configBackupDirectoryPath)
	elif deviceType == 'sgsn-mme':
		return SGSNMMEDevice(deviceName, deviceIP, configBackupDirectoryPath)
		
def CreateStringWithSpaces(*args):
	producedCommand = ''
	for arg in args:
			producedCommand = producedCommand + ' ' + str(arg)
	return producedCommand.lstrip()
	
def CollectDeviceConfiguration(networkDevice):
	networkDevice.CollectConfiguration()

class TftpFile:
	def __init__(self, tftpFileName):
		self.tftpServerIP = '10.10.40.1'
		self.tftpDirectory = '/tftpboot'
		assert os.path.isdir(self.tftpDirectory)
		self.tftpFileName = tftpFileName
		self.ResetTftpFile()
		
	def GetFullTftpFileName(self):
		return self.tftpDirectory + '/' + self.tftpFileName
		
	def GetTftpServerIP(self):
		return self.tftpServerIP
	
	def ResetTftpFile(self):
		fullTftpFileName = self.GetFullTftpFileName()
		fileObject = open(fullTftpFileName, 'w+')
		fileObject.close()
		os.chmod(fullTftpFileName, 0666)

class NetworkDevice(object):
	def __init__(self, deviceName, deviceIP, configBackupDirectoryPath):
		self.deviceName = deviceName
		self.deviceIP = deviceIP
		self.configBackupDirectoryPath = configBackupDirectoryPath
		
		self.SetLogFileNames()
		
	def SetLogFileNames(self):
		self.fullDestinationFileName = self.configBackupDirectoryPath + '/' + self.deviceName + '.log'

	def PreProcess(self):
		self.SetLogFileNames()
		startLine = CreateStringWithSpaces('START:', self.deviceName,'(' + self.deviceIP + ')')
		print startLine

	def Process(self):
		raise NotImplementedError('You must implement method Process to be able to collect the configuration file from the end node')
		
	def PostProcess(self):
		finishLine = CreateStringWithSpaces('__FINISH__:', self.deviceName, '(' + self.deviceIP + ')')
		print finishLine

	def CollectConfiguration(self):
		self.PreProcess()
		self.Process()
		self.PostProcess()
		
######### SWITCH DEVICES ###########

class EXOSDevice(NetworkDevice):
	def __init__(self, deviceName, deviceIP, configBackupDirectoryPath):
		super(EXOSDevice, self).__init__(deviceName, deviceIP, configBackupDirectoryPath)
		self.sshUser = 'user'
		self.tftpFile = TftpFile(deviceName)
	
	def Process(self):
		loginCommand = CreateStringWithSpaces('ssh -l', self.sshUser, self.deviceIP)
		tftpServerIP = self.tftpFile.GetTftpServerIP()
		uploadTftpFileCommand = CreateStringWithSpaces('upload configuration', tftpServerIP, self.deviceName, 'vr VR-Default')
		try:
			child = pexpect.spawn(loginCommand)
			# Now check if the configuration of the switch is not saved. If it is not saved, save it.
			# If the prompt is preceeded with * it means that the configuration has not been saved
			# and there are pending changes
			index = child.expect(['\*.+ # ', ' # '])
			if index == 0:
				child.sendline('save configuration')
				child.expect('(y/N)')
				child.sendline('y')
				child.expect(' # ')
				child.sendline(uploadTftpFileCommand)
				child.expect([' # '])
				child.sendline('exit')
				self.isCollectionSuccessfulFlag = True
			elif index == 1:
				child.sendline(uploadTftpFileCommand)
				child.expect([' # '])
				child.sendline('exit')
				self.isCollectionSuccessfulFlag = True
		except:
			errorString = CreateStringWithSpaces('\nWARNING:\n Problem connecting/communicating with', self.deviceName, '(' + self.deviceIP + ')\n')
			print errorString
			self.isCollectionSuccessfulFlag = False
		
	def PostProcess(self):
		super(EXOSDevice, self).PostProcess()
		# Copy the backup file to the end destination
		if self.isCollectionSuccessfulFlag:
			fullTftpFileName = self.tftpFile.GetFullTftpFileName()
			move(fullTftpFileName, self.fullDestinationFileName)
			os.utime(self.fullDestinationFileName, None)

######### FIREWALL DEVICES ###########

class ScreenOSDevice(NetworkDevice):
	def __init__(self, deviceName, deviceIP, configBackupDirectoryPath):
		super(ScreenOSDevice, self).__init__(deviceName, deviceIP, configBackupDirectoryPath)
		self.sshUser = 'user'

	def Process(self):
		loginCommand = CreateStringWithSpaces('ssh -l', self.sshUser, self.deviceIP)
		scpCopyCommand = CreateStringWithSpaces('scp', self.sshUser + '@' + self.deviceIP + ':ns_sys_config', self.fullDestinationFileName, '> /dev/null 2>&1')
		try:
			child = pexpect.spawn(loginCommand)
			index = child.expect(['->'])
			if index == 0:
				# Saving configuration of the ScreenOS device
				child.sendline('save config')
				child.expect(['->'])
				child.sendline('exit')
			# Copying configuration file to the local server
			subprocess32.call(scpCopyCommand, shell = True)
			self.isCollectionSuccessfulFlag = True
		except:
			errorString = CreateStringWithSpaces('\nWARNING:\n Problem connecting/communicating with', self.deviceName, '(' + self.deviceIP + ')\n')
			print errorString
			self.isCollectionSuccessfulFlag = False
	
	def PostProcess(self):
		super(ScreenOSDevice, self).PostProcess()
		# Copy the backup file to the end destination
		if  self.isCollectionSuccessfulFlag:
			tempFileName = self.fullDestinationFileName + '.tmp'
			filterCommand = 'sed \'/saved_cfg_timestamp\'/d ' + self.fullDestinationFileName + '> ' + tempFileName
			subprocess32.call(filterCommand, shell = True)
			move(tempFileName, self.fullDestinationFileName)
			os.utime(self.fullDestinationFileName, None)

######### ROUTER DEVICES ##########

class SEOSDevice(NetworkDevice):
	def __init__(self, deviceName, deviceIP, configBackupDirectoryPath):
		super(SEOSDevice, self).__init__(deviceName, deviceIP, configBackupDirectoryPath)
		self.sshUser = 'user@local'
		self.tftpFile = TftpFile(deviceName)
	
	def Process(self):
		loginCommand = CreateStringWithSpaces('ssh -l', self.sshUser, self.deviceIP)
		tftpServerIP = self.tftpFile.GetTftpServerIP()
		uploadTftpFileCommand = 'save configuration tftp://' + tftpServerIP + '/' + self.deviceName
		try:
			child = pexpect.spawn(loginCommand)
			# Save configuration
			index = child.expect(['#'])
			if index == 0:
				child.sendline('save configuration')
				child.expect('Target file exists, overwrite?')
				child.sendline('y')
				child.expect('#')
				child.sendline(uploadTftpFileCommand)
				child.expect(['#'])
				child.sendline('exit')
				self.isCollectionSuccessfulFlag = True
		except:
			errorString = CreateStringWithSpaces('\nWARNING:\n Problem connecting/communicating with', self.deviceName, '(' + self.deviceIP + ')\n')
			print errorString
			self.isCollectionSuccessfulFlag = False
		
	def PostProcess(self):
		super(SEOSDevice, self).PostProcess()
		# Copy the backup file to the end destination
		if self.isCollectionSuccessfulFlag:
			fullTftpFileName = self.tftpFile.GetFullTftpFileName()
			move(fullTftpFileName, self.fullDestinationFileName)
			os.utime(self.fullDestinationFileName, None)

class JunOSDevice(NetworkDevice):
	def __init__(self, deviceName, deviceIP, configBackupDirectoryPath):
		super(JunOSDevice, self).__init__(deviceName, deviceIP, configBackupDirectoryPath)
		currentTimestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
		self.tempFileName = '/tmp/' + self.deviceName + '_' + currentTimestamp + '.gz'

	def Process(self):
		scpCopyCommand = CreateStringWithSpaces('scp', self.sshUser + '@' + self.deviceIP + ':/config/juniper.conf.gz', self.tempFileName, '> /dev/null 2>&1')
		gunzipCommand = 'gzip -d ' + self.tempFileName
		try:
			subprocess32.call(scpCopyCommand, shell = True)
			subprocess32.call(gunzipCommand, shell = True)
			self.isCollectionSuccessfulFlag = True
		except:
			errorString = CreateStringWithSpaces('\nWARNING:\n Problem connecting/communicating with', self.deviceName, '(' + self.deviceIP + ')\n')
			print errorString
			self.isCollectionSuccessfulFlag = False
			
	def PostProcess(self):
		super(JunOSDevice, self).PostProcess()
		# Copy the backup file to the end destination
		if self.isCollectionSuccessfulFlag:
			self.tempFileName = self.tempFileName[:-3]
			if os.path.isfile(self.tempFileName):
				move(self.tempFileName, self.fullDestinationFileName)
				os.utime(self.fullDestinationFileName, None)
				
######### JUNOS GGSN-EPG DEVICES ###########

class JUNOSEPGDevice(NetworkDevice):
	def __init__(self, deviceName, deviceIP, configBackupDirectoryPath):
		super(JUNOSEPGDevice, self).__init__(deviceName, deviceIP, configBackupDirectoryPath)
		self.sshUser = 'user'
		currentTimestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
		self.tempFileName = '/tmp/' + self.deviceName + '_' + currentTimestamp + '.gz'

	def Process(self):
		scpCopyCommand = CreateStringWithSpaces('scp', self.sshUser + '@' + self.deviceIP + ':/config/juniper.conf.gz', self.tempFileName, '> /dev/null 2>&1')
		gunzipCommand = 'gzip -d ' + self.tempFileName
		try:
			subprocess32.call(scpCopyCommand, shell = True)
			subprocess32.call(gunzipCommand, shell = True)
			self.isCollectionSuccessfulFlag = True
		except:
			errorString = CreateStringWithSpaces('\nWARNING:\n Problem connecting/communicating with', self.deviceName, '(' + self.deviceIP + ')\n')
			print errorString
			self.isCollectionSuccessfulFlag = False
	
	def PostProcess(self):
		super(JUNOSEPGDevice, self).PostProcess()
		# Copy the backup file to the end destination
		if self.isCollectionSuccessfulFlag:
			self.tempFileName = self.tempFileName[:-3]
			if os.path.isfile(self.tempFileName):
				move(self.tempFileName, self.fullDestinationFileName)
				os.utime(self.fullDestinationFileName, None)
				
######### SGSN SGSN-MME DEVICES ###########

class SGSNMMEDevice(NetworkDevice):
	def __init__(self, deviceName, deviceIP, configBackupDirectoryPath):
		super(SGSNMMEDevice, self).__init__(deviceName, deviceIP, configBackupDirectoryPath)
		self.sshUser = 'om_conf'

	def Process(self):
		loginCommand = CreateStringWithSpaces('ssh -l', self.sshUser, self.deviceIP)
		exportConfigCommand = 'gsh export_config_active'
		scpCopyCommand = CreateStringWithSpaces('scp', self.sshUser + '@' + self.deviceIP + ':/Core/home/om_conf/ConfigFile_from_export', self.fullDestinationFileName, '> /dev/null 2>&1')
		try:
			child = pexpect.spawn(loginCommand)
			index = child.expect([' # '])
			if index == 0:
				child.sendline(exportConfigCommand)
				child.expect([' # '])
				child.sendline('exit')
			subprocess32.call(scpCopyCommand, shell = True)
			self.isCollectionSuccessfulFlag = True
		except:
			errorString = CreateStringWithSpaces('\nWARNING:\n Problem connecting/communicating with', self.deviceName, '(' + self.deviceIP + ')\n')
			print errorString
			self.isCollectionSuccessfulFlag = False

class NetworkDevices:
	def __init__(self, fileName, outputDirectory):
		self.deviceList = []
		assert os.path.isfile(fileName)
		self.fileName = fileName
		assert os.path.isdir(outputDirectory)
		self.outputDirectory = outputDirectory

	def CollectConfiguration(self):
		f = open(self.fileName, 'r')
		for line in f:
			# Skip  comments (start with #) or empty lines
			if not line.startswith('#'):
				if not line.strip() == '':
					splitDeviceData = line.split(';')
					configBackupDirectoryPath = splitDeviceData[0]
					configBackupDirectoryPath = configBackupDirectoryPath.rstrip()
					configBackupDirectoryPath = self.outputDirectory + '/' + configBackupDirectoryPath
					if not os.path.isdir(configBackupDirectoryPath):
						os.makedirs(configBackupDirectoryPath)
					
					deviceName = splitDeviceData[1]
					deviceName = deviceName.rstrip()
					
					deviceIP = splitDeviceData[2]
					deviceIP = deviceIP.rstrip()
					
					deviceType = splitDeviceData[3]
					deviceType = deviceType.rstrip()
					
					networkDevice = SimpleNetworkDeviceFactory(deviceName, deviceIP, deviceType, configBackupDirectoryPath)
					self.deviceList.append(networkDevice)
		
		p = Pool(40)
		p.map(CollectDeviceConfiguration, self.deviceList)
		
		self.SubmitToGit()
		
	def SubmitToGit(self):
		currentTimestamp = datetime.datetime.now().strftime("%Y-%m-%d, time: %H:%M:%S")
		self.commonLogFileName = self.outputDirectory + '/cms.log'
		self.commonLogFile = open (self.commonLogFileName, 'w+')
		self.commonLogFile.write('Configuration collected at:' + currentTimestamp + '\n\n')
		
		self.commonLogFile.close();
		
		repo = git.Repo(self.outputDirectory)
		repo.git.add('*')
		commitMessage = 'Backup of the configuration ' + currentTimestamp
		repo.git.commit(m=commitMessage)