#!/usr/bin/env python
import nwdevices

dbFileName = '/root/sw/git/cms/input.db'
targetDirectory = '/root/config/auto_config_backup'

if __name__ == '__main__':
	networkDevices = nwdevices.NetworkDevices(dbFileName, targetDirectory)
	networkDevices.CollectConfiguration()