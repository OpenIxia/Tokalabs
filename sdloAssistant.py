"""
sdloAssistant.py

A class that sends Tokalabs REST APIs using Python requests

There are two ways to use this class:

1> This option was the original method by creating an instance for a sandbox.
    This means you have to create a new instance for each sandbox that you like to control.
    
    sandbox_1 = sdloAssistant.Controller(sdloControllerIp, username, password, sandbox=sandboxName)
    sandbox_1.reserve()
    
2> This option allows you create just one instance and use setSandbox() to switch
    sandboxes by sandbox names.
    
    sandbox = sdloAssistant.Controller(sdloControllerIp, username, password)
    sandbox.setSandbox(sandboxName)
    sandbox.reserve()
    
To run a suite in a sandbox instance, pass in the suite name to the runSuite() function.
    
Requirements
   - Python 3.7
   - requests module
"""

from __future__ import absolute_import, print_function, division

import os, re, requests, urllib3, time, datetime, platform, inspect, yaml, json
import timeit
from pprint import pprint

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Controller:
    """

    """
    logFile = None

    def __init__(self, controllerIp, user, password, sandbox=None, logLevel='debug'):
        """
        Parameters
           controllerIp <str>: The Tokalabs controller IP address.
           user <str>: The Tokalabs controller login name.
           password <str>: The password
           sandbox <None|str>: This parameter is kept for backward compatibility.
                               Optional: Use this if you want to manage a sandbox by
                               passing in the sandbox name to use.

           logLevel <str>: info|debug.  The debug option includes rest api commands.

        Usage example:
           sandboxObj = sdloAssistant.Controller(sdloControllerIp, username, password)
           sandboxObj.setSandbox(sandboxName)
           sandboxObj.reserve()
           username = sandboxObj.getDeviceUsername(deviceName='IxNetworkAPIServer')
        """
        self.controllerIp = controllerIp
        self.user = user
        self.password = password
        self.sandbox = sandbox
        # blueprintChild will be updated with a blueprint sandbox child name if it's a blueprint reservation
        self.blueprintChild = None
        self.logLevel = logLevel
        self.httpHeader = 'https://{}'.format(self.controllerIp)
        self.headers = {'Content-Type': 'application/json'}

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Initiate a log file
        currentDir = os.path.dirname(os.path.abspath(__file__))
        Controller.logFile = '{}/{}'.format(currentDir, 'sdloAssistant.log')

        today = str(datetime.datetime.now()).split(' ')[0]
        with open(Controller.logFile, 'w+') as sdloLogFile:
            sdloLogFile.write('Log date: {}\n\n'.format(today))

        self.connect()

        if self.sandbox:
            self.setSandbox(self.sandbox)
            
    def connect(self):
        """
        Make initial connection to Tokalabs with username/password.
        This will automatically get the webtoken and token for the requests headers
        """
        response = self.sendRest('post', '/tokalabs/api/login',
                                 {'username': self.user, 'password': self.password})

        # Ex: NPT0PXsm6KNl4RQe
        self.webtoken = response.json()['additionalDetails']['token']['token'].split('/')[1]

        # Ex: admin/NPT0PXsm6KNl4RQe
        self.token = response.json()['additionalDetails']['token']['token']

        self.headers = {'Content-Type': 'application/json', 'Authorization': self.token}

    def setSandbox(self, sandbox):
        """
        Verify if the sandbox is already reserved. If it is, get the device details.

        Parameter
           sandbox <str>: The sandbox to use
        """
        self.sandbox = sandbox
        # This gets filled in getDeviceMgmtInterfaceDetails()
        self.deviceDict = {} 
        if self.isSandboxReserved() == True:
            self.getDeviceMgmtInterfaceDetails()
        
    def sendRest(self, verb, restApi, params={}):
        """
        Send the REST API and verify the status code

        Parameters
           verb <str>:  get|post|put|delete: Toka uses GET for just about every execution.  Toka uses POST for logging.
           restApi <str>:  The REST API to enter.
           params <json>: Data payload.
           headerContentType: <str>: json|xml
                                     Defaults to application/json.
                                     New API for reserving/releasing blueprints uses application/xml

        Return
            The response from the controller
        """
        self.logInternal('{}()\n\t{}: {} \n\tJSON DATA: {}'.format(
            inspect.stack()[1][3],
            verb.upper(),
            self.httpHeader+restApi,
            params))

        if verb == 'get':
            response = requests.get(self.httpHeader+restApi, json=params, headers=self.headers, verify=False)

        if verb == 'post':
            response = requests.post(self.httpHeader+restApi, json=params, headers=self.headers, verify=False)

        if verb == 'put':
            response = requests.put(self.httpHeader+restApi, json=params, headers=self.headers, verify=False)

        if verb == 'delete':
            response = requests.delete(self.httpHeader+restApi, json=params, headers=self.headers, verify=False)

        if str(response.status_code).startswith('2') == False:
            raise SdloAssistantException('response status_code = {}\n{}'.format(response.status_code,
                                                                                response.json()))

        return response

    def logMsg(self, msgType, msg):
        """
        This is a private function for sdloAssistant use only.
        Formatting the stdout log messages with a timestamp

        Parameter
           msgType <str>: info|debug|error
           msg <str>: The message for stdout.
        """
        timestamp = str(datetime.datetime.now()).split(' ')[1]

        if self.logLevel == 'debug' and msgType == 'internal':
            debugFormat = '\n{}: [sdloAssistant]: {}'.format(timestamp, msg)
            print(debugFormat)

            with open(Controller.logFile, 'a') as sdlLogFile:
                sdlLogFile.write(debugFormat+'\n')

        if msgType in ['info', 'error', 'debug']:
            infoFormat = '\n{}: [{}]: {}'.format(timestamp, msgType, msg)
            print(infoFormat)

            with open(Controller.logFile, 'a') as sdlLogFile:
                sdlLogFile.write(infoFormat+'\n')

    def logInfo(self, msg):
        self.logMsg('info', msg)

    def logDebug(self, msg):
        self.logMsg('debug', msg)

    def logError(self, msg):
        self.logMsg('error', msg)

    def logInternal(self, msg):
        self.logMsg('internal', msg)

    def isSandboxReserved(self):
        """
        Verify if the sandbox is available

        Return
           True: Sandbox is currently reserved
           False: Sandbox is available
        """
        url = '/tokalabs/api/topologies?name=^{}$'.format(self.sandbox)
        response = self.sendRest('get', url)

        for sandbox in response.json()['additionalDetails']['topologiesList']:
            if sandbox['name'] == self.sandbox:
                self.logInternal('reservation details: {}'.format(sandbox['reservationDetails']))
                reservationStatus = sandbox['reservationDetails']['reservationStatus']

                self.logInternal('SandboxName [{}] status: {}'.format(self.sandbox, reservationStatus))

                if reservationStatus == 'reserved':
                    self.logInternal('Sandbox is currently reserved: {}'.format(self.sandbox))
                    return True

                if reservationStatus == 'available':
                   self.logInternal('Sandbox is available: {}'.format(self.sandbox))
                   return False

    def reserve(self, forceTakeOwnership=False):
        """
        Reserve a sandbox or a blueprint.
        If forceTakeOwnership is False, wait until the sandbox is available.
        If forceTakeOwnership is True, take over the sandbox if it is reserved.

        Note:
            If reserving a blueprint, a child sandbox is created. The name of the child sandbox is
            saved in self.blueprintChild so the release() function knows which sandbox to release.
            You need to be running a contiguous script for this to work.
            Otherwise, you need to keep track of the child sandbox name.

        Parameter
           forceTakeOwnership <bool>: True = take over the sandbox that is currently owned.
        """
        if self.isSandboxExists(self.sandbox) == False:
            raise SdloAssistantException('The Sandbox [{}] does not exists'.format(self.sandbox))

        waitInterval = 3
        while True:
            result = self.isSandboxReserved()

            if result == True and forceTakeOwnership in [True, 'True']:
                self.logInternal('forceTakeOwnership is set to True. Taking over the sandbox.')
                self.release()
                break

            if result == True and boolforceTakeOwnership in [False, 'False']:
                self.logInternal('Sandbox [{}] is currently reserved. Waiting for owner to release it.'.format(self.sandbox))
                time.sleep(waitInterval)
                continue

            if result == False:
                break

        url = '/tokalabs/api/topology/{}/reserve/user={}/token={}'.format(self.sandbox, self.user,
                                                                          self.webtoken.strip())

        self.logInfo('Reserving sandbox: {}'.format(self.sandbox))

        # Time how long it took to reserve all the devices in the sandbox.
        startTime = timeit.default_timer()

        response = self.sendRest('get', url)
        if response.json()['status'] != 'Sandbox Reserved Successfully':
            raise SdloAssistantException('Reserving sandbox failed: {}'.format(response.json()['status']))

        self.logInfo('Successfully reserved sandbox: {}'.format(response.json()['TopologyName']))
        stopTime = timeit.default_timer()
        totalTime = stopTime - startTime
        self.logInfo('Time taken to make the reservation: {} seconds -> {} minutes'.format(totalTime, int(totalTime/60)))

        reservedSandboxName = response.json()['TopologyName']
        if reservedSandboxName != self.sandbox:
            self.blueprintChild = reservedSandboxName
            self.logInfo('The blueprint child sandbox name is: {}'.format(self.blueprintChild))
        else:
            self.logInfo('The reserved sandbox name is: {}'.format(self.sandbox))

        # Get all the sandbox devices and details and store in a dict so functions like
        # getDeviceIp, getDevicePorts, getDeviceUsername,... won't need to keep calling a for loop.
        self.getDeviceMgmtInterfaceDetails()

    def release(self):
        """
        Release a regular sandbox or a blueprint child sandbox.

        Note:
           If you are not running a contiguous script that includes both reserve() and
           release() in the same script, you will need to pass in the sandbox name to be released.
           Especially if the sandbox is a child of a blueprint. The blueprint child
           sandbox name is obfuscated.
        """
        if self.blueprintChild:
            # The self.blueprintChild is defined in reserve()
            sandbox = self.blueprintChild
        else:
            # Sandbox types: child, blueprint, regular
            sandboxType = self.getSandboxType()

            if sandboxType == 'blueprint':
                self.logError('"{}" is a blueprint type.  You need to provide the blueprint child sandbox name or a regular sandbox name'.format(
                    self.sandbox))
                return
            else:
                sandbox = self.sandbox

        self.logInfo('Releasing sandbox: {}'.format(sandbox))
        url = '/tokalabs/api/topology/{}/release/user={}/token={}'.format(sandbox, self.user, self.webtoken.strip())
        startTime = timeit.default_timer()
        response = self.sendRest('get', url)

        stopTime = timeit.default_timer()
        totalTime = stopTime - startTime
        self.logInfo('Time taken to release the sandbox: {} seconds -> {} minutes'.format(totalTime, int(totalTime/60)))

        self.logInfo('Release sandboxName [{}] status: {}'.format(sandbox, response.json()['status']))
        if response.json()['status'] != 'Sandbox Released Successfully':
            raise SdloAssistantException('Release sandbox failed: {}. {}'.format(response.json()['status'], response.json()['message']))

    def runSuite(self, suiteName):
        """
        Run a suite

        Parameter
           suiteName <str>: The suite name to run
        """
        self.logInfo('runSuite: sandbox:{}  suiteName:{}'.format(self.sandbox, suiteName))
        url = '/tokalabs/api/topology/{}/run/suite/suite={}/user={}/token={}'.format(self.sandbox, suiteName,
                                                                                     self.user, self.webToken)

        response = self.sendRest('get', url)
        self.logInfo('runSuite response status: {}'.format(response.json()))

        if response.json()['status'] != 'Suite Started':
            raise SdloAssistantException('{}: suiteName:{}'.format(response.json()['status'], suiteName))
        else:
            self.logInfo('Run suite successfully started: {}'.format(suiteName))

    def waitForAllDevicesToBeReserved(self):
        """
        For debugging purpose.  After entering the command to reserve a sandbox, this
        keeps checking each device until it is indeed reserved.
        """
        allDevices = self.getSandboxDevices()

        # This block of code waits and verifies that all the devices are indeed reserved.
        for device in allDevices:
            result = self. getDeviceDetails(device['name'])
            if result['devicesList'][0]['deviceType'] == 'Ixia':
                continue

            while True:
                result = self. getDeviceDetails(device['name'])
                status = result['devicesList'][0]['reservationDetails']['reservationStatus']
                self.logInfo('device reservation status:{}  status:{}'.format(device['name'], status ))
                if status != 'reserved':
                    time.sleep(1)
                else:
                    break

    def waitForCompletion(self, suiteName):
        """
        Wait for the test suite to complete

        Parameter
           suiteName <str>: The suite name to wait for
        """
        url = '/tokalabs/api/topology/{}/status/suite/suite={}/user={}/token={}'.format(
            self.sandbox, suiteName, self.user, self.webToken)

        while True:
            response = self.sendRest('get', url)
            currentStatus = response.json()['TestSuiteStatus']
            self.logInternal('Suite current running status: {}'.format(currentStatus))

            if currentStatus != 'Stopped':
                time.sleep(3)

            if currentStatus in ['Aborted', 'Stopped']:
                break

    def getSandboxChildren(self):
        """
        Get all the child sandboxes of a blueprint
        """
        return self.getSandboxDetails()['childTopologies']

    def getSandboxDetails(self):
        """
        Get the sandbox details
        """
        url = '/tokalabs/api/topologies?name={}'.format(self.sandbox)
        response = self.sendRest('get', url)

        for device in response.json()['additionalDetails']['topologiesList']:
            if device['name'] == self.sandbox:
                return device

    def getAllSandboxDetails(self):
        """
        Get all of the sandbox details
        """
        url = '/tokalabs/api/topologies'
        response = self.sendRest('get', url)
        return response.json()['additionalDetails']['topologiesList']

    def getSandboxType(self):
        return self.getSandboxDetails()['type']

    def getSandboxDevices(self):
        """
        Get the sandbox's list of devices.  Sandbox must be in the reserved state.

        If a sandbox name wasn't provided, topologiesList is empty:
           {'status': 'Success', 'message': 'Sandbox GET API success.', 'additionalDetails': 
           {'metadata': {'totalRecords': 0, 'sortOn': 'name', 'sortOrder': 'asc', 'pageNum': 1, 'pageSize': 200}, 
            'topologiesList': []}}

        Returns:
           Example:
            [{'abstractId': 'DUT1', 'name': 'AutoVM-VMOneProfil-oIxhHy'},
             {'abstractId': 'DUT2', 'name': 'IxNetworkWebAPI'}},
            ]
        """
        #url = '/tokalabs/api/topologies?name=%s' % (self.sandbox)
        url = '/tokalabs/api/topologies?name=^{}$&fieldsToFetch=devices'.format(self.sandbox)
        response = self.sendRest('get', url)

        if len(response.json()['additionalDetails']['topologiesList']) == 1:
            # Blueprint
            return response.json()['additionalDetails']['topologiesList'][0]['devices']
        else:
            # Regular
            return response.json()['additionalDetails']['topologiesList'][1]['devices']

    def getInstantiatedVmName(self, vmProfileName):
        """
        vmProfileName: The VM profile name in the sandbox

        Instantiated VM names are in format:
            {'name': 'AutoVM-cumulusProf-XqJWdN', 'abstractId': 'DUT1'}

        Chop up the vmProfileName and get the 11 characters to look up
        the sandbox devices.

        Return
           The instantiated VM name | None
        """
        elevenCharacters = vmProfileName[:11]
        for device in self.getSandboxDevices():
            if bool(re.search('AutoVM-{}*-*'.format(elevenCharacters), device['name'])):
                return device['name']

    def getResults(self):
        """
        with the current release (1.0.3), getting results can only get the latest suite run result.
        Cannot get a specific script or suite from past test runs.

        {'testStatus': 'Completed',
         'total': '5',
         'casesPassed': '4',
         'casesFailed': '1',
         'stepsPassed': '3',
         'stepsFailed': '0'}

        Returns: Passed|Failed
        """
        url = '/testrunner/{}/TestControl.php?task=2'.format(self.sandbox)
        response = self.sendRest('get', url)
        if response.json()['casesFailed'] != '0' or response.json()['stepsFailed'] != '0':
            self.logError('Test result: Failed')
            return 'Failed'
        else:
            self.logInfo('Test result: Passed')
            return 'Passed'

    def showResults(self):
        """
        For Show all the results of the latest run.

        {'testStatus': 'Completed',
         'total': '5',
         'casesPassed': '4',
         'casesFailed': '1',
         'stepsPassed': '3',
         'stepsFailed': '0'}

        Returns: All results
        """
        url = '/testrunner/{}/TestControl.php?task=2'.format(self.sandbox)
        response = self.sendRest('get', url)
        print()
        pprint(response.json())
        print()

        return response.json()

    def getDeviceDetails(self, deviceHostname):
        """
        Get the device details
        """
        url = '/tokalabs/api/devices?hostname=^{}$'.format(deviceHostname)
        response = self.sendRest('get', url)
        return response.json()['additionalDetails']

    def getVlinkConnections(self, vlinkName):
        """
        Get all the vlink connections

        Returns
           A list of vLink connections
        """
        vlinkConnectionList = self.getDeviceDetails(vlinkName)['devicesList'][0]['physicalPortConnections']
        return vlinkConnectionList

    def isSandboxExists(self, sandboxName):
        """
        Verify if the sandbox exists.

        Return
           If exists, return True
           Else, return False
        """
        url = '/tokalabs/api/topologies'
        response = self.sendRest('get', url)
        topologyList = response.json()['additionalDetails']['topologiesList']
        if sandboxName in [topology['name'] for topology in topologyList]:
            return True
        else:
            return False

    def isDeviceExists(self, deviceName):
        """
        Verify if the device exists.

        Parameter
            deviceName: The device name

        Return
           If exists, return True
           Else, return False
        """
        if deviceName in [device['name'] for device in self.getSandboxDevices()]:
            return True
        else:
            return False

    def getDevicePorts(self, srcDeviceName, targetDeviceName, isSrcDeviceIxia=False):
        """
        Get all the port connections between two devices.

        If a device is a traffic generator such as Ixia, then pass in the Ixia device
        name for the parameter srcDeviceName and set isSrcDeviceIxia=True.


        Parameters:
           srcDeviceName:  The Ixia chassis device name in the sandbox.
           targetDeviceName:  The target device name in the sandbox.
           isSrcDeviceIxia: <bool>: True = is an Ixia chassis.
                            If it's an Ixia chassis, the returned port list format is:
                            [[<chassisIp>, 1, 1], [<chassisIp>, 1, 2]]

        Return
           Returns a list of srcPorts and targetPorts
           For example:
              (['1/3', '1/4'], ['3/1', '3/2'])
              The index 0 list are the srcPorts
              The index 1 list are the targetPorts

              If the srcPorts are Ixia ports, then the list looks like this:
              [[<chassisIp>, 1, 1], [<chassisIp>, 1, 2]]
        """
        for deviceName in [srcDeviceName, targetDeviceName]:
            if deviceName not in self.deviceDict.keys():
                raise SdloAssistantException(f'Did you reserve the sandbox? No such device name in the sandbox" {deviceName}')

            if 'ports' not in self.deviceDict[deviceName]:
                self.logError(f'No ports found in device name: {deviceName}')
                return None

        chassisIp = self.getDeviceIp(srcDeviceName, mgmtInterfaceIndex=0)
        srcPorts = []
        targetPorts = []

        for portDetails in self.deviceDict[srcDeviceName]['ports']:
            if 'directConnectionDetails' in portDetails and portDetails['directConnectionDetails']['targetHost'] == targetDeviceName:
                srcPort = portDetails['directConnectionDetails']['sourcePortId']
                targetPort = portDetails['directConnectionDetails']['targetPortId']

                if isSrcDeviceIxia:
                    # Extracting formats: 1.1.1 or 1/1/1 or 1.1 or 1/1
                    match = re.match('([0-9]+[^ 0-9]+)?([0-9]+)[^ 0-9]+([0-9]+)', srcPort)
                    if match:
                        slot = int(match.group(2))
                        port = int(match.group(3))
                        srcPorts.append([chassisIp, slot, port])
                        targetPorts.append(targetPort)
                else:
                    srcPorts.append(srcPort)
                    targetPorts.append(targetPort)
                        
        self.logInternal('getDevicePorts: srcPorts:{} targPorts:{}'.format(srcPorts, targetPorts))
        return srcPorts,targetPorts

    def getDeviceUsername(self, deviceName, mgmtInterfaceIndex=0):
        """
        Get device username from the mgmt interface

        Parameter
           deviceName {str}: The device name
           mgmtInterfaceIndex {int}: 0=primaryInterface  1=secondaryInterface

        Return
           The username
        """
        if deviceName not in self.deviceDict.keys():
            raise SdloAssistantException(f'Did you reserve the sandbox? No such device name in the sandbox" {deviceName}')

        try:
            return self.deviceDict[deviceName]['mgmtInterfaces'][mgmtInterfaceIndex]['username']
        except:
            return None

    def getDeviceIp(self, deviceName=None, mgmtInterfaceIndex=0):
        """
        Search the sandbox for the deviceName.
        If the sandbox is a child of a blueprint, then the sandbox name
        must be the child sandbox name and pass in the original device name.

        Parameter
          deviceName <str>: The device name from the sandbox or child sandbox
          mgmtInterfaceInidex <int>: A Device supports multiple mgmt interfaces. Which interface to retrieve IP from?
                                     0=primary interface.  1=secondary interface

        Return
            None|IP address
        """
        try:
            if deviceName not in self.deviceDict.keys():
                raise SdloAssistantException(f'Did you reserve the sandbox? No such device name in the sandbox" {deviceName}')
        except Exception as errMsg:
            return (None, 'Must reserve a sandbox first')

        try:
            return self.deviceDict[deviceName]['mgmtInterfaces'][mgmtInterfaceIndex]['networkAddress']
        except:
            return None

    def getDeviceMgmtInterfaceDetails(self):
        """
        Get all sandbox devices and all its details.
        Mainly a helper function for internal usage, but could also be used elsewhere.
        This function gets called after a reservation or if connected to a reserved sandbox.

        Return
            A dictionary of all the devices and its details
        """
        for device in self.getSandboxDevices():
            deviceName = device['name']
            self.deviceDict[deviceName] = dict()
            mgmtInterfaces = []
            deviceDetails = self.getDeviceDetails(deviceName)

            for dev in deviceDetails['devicesList']:
                for key,value in dev.items():
                    if isinstance(value, dict) == False:
                        self.deviceDict[deviceName].update({key:value})

                for eachMgmtInterface in dev['deviceManagement']['managementInterfaces']:
                    mgmtInterfaces.append(eachMgmtInterface)

                if 'physicalPortConnections' in dev:
                    self.deviceDict[device['name']].update({'ports': dev['physicalPortConnections']['interfaces']})

            self.deviceDict[device['name']].update({'mgmtInterfaces': mgmtInterfaces})

        return self.deviceDict

    def addDevice(self, data):
        """
        Add new device to inventory

        data <dict>: A dictionary of the device details.
                     Refer to the Tokalabs API user guide for all the data details.

        # Example
           data = {"deviceType":"Server", "hostname":"testAPI", "vendor":"Dell",
                   "deviceManagement":{"allowUsersToManageDevices":True,
                                       "managementInterfaces":[{"type":"https","networkAddress":"10.4.17.73",
                                                                "managementType":"primary","authType":"password",
                                                                "supportsSFTP":False,"username":""}]
                   }}

        Returns
            {'status': 'Success', 'message': 'Device added successfully!',
             'additionalDetails': {'deviceType': 'Server', 'deviceName': 'testAPI'}}
        """
        url = '/tokalabs/api/devices/network'
        response = self.sendRest('post', url, data)
        return response.json()

    def createSandbox(self, data):
        """
        Create a new sandbbox or blueprint.
        The type field value is either regular|blueprint.
        The devices have to be VMwareProfiles or else you get an error.

        data <dict>: A dictionary of sandbox details.
                     Refer to the Tokalabs API user guide for all the data details.

        Example:
           sandboxData = {'type': 'regular', 'name': 'hgeeSandbox',
                          'devices':[{'name': 'IxNetworkAPIServer', 'abstractId': 'DUT1'}],
                          'indirectConnections': [],
                          'additionalDetails': None
                         }

           blueprintData = {'type': 'blueprint', 'name': 'hgeeTestBlueprint',
                            'devices':[{'name': 'Cumulus Profile', 'abstractId': 'DUT1'}],
                            'indirectConnections': [],
                            'additionalDetails': None
                           }
        """
        url = '/tokalabs/api/topologies'
        response = self.sendRest('post', url, data)
        return response.json()
    
    def createSandboxKeywords(self, keywordsData):
        """
        Usage example:
        
           keywordData = {'keywordsList': [
              {'name': 'ixNetApiServerDeviceName', 'value': 'IxNetworkAPIServer',
               'dataType': 'String', 'executionProfile': 'Default'},
              {'name': 'forceTakeSandboxOwnership', 'value': 'True',
               'dataType': 'String', 'executionProfile': 'Default'},
           ]}

           obj.setSandbox(<sandbox_name>)
           obj.createSandboxKeywords(keywordData)
        """
        url = '/tokalabs/api/keywords/sandbox/{}'.format(self.sandbox)
        response = self.sendRest('post', url, keywordsData)
        return response.json()
        
    def getSandboxKeywords(self, executionProfile='Default'):
        """
        Get sandbox keywords

        Parameters
            executionProfile <str>: The execution profile to retrieve keywords from
                                    Default==Default execution profile

        Return
            A dictionary of keyword/value
        """
        if executionProfile == 'Default':
            url = f'/tokalabs/api/keywords/sandbox/{self.sandbox}'
        else:
            url = f'/tokalabs/api/keywords/sandbox/{self.sandbox}?executionProfile={executionProfile}'

        response = self.sendRest('get', url)

        if response.json()['additionalDetails'] == []:
            self.logError(response.json()['message'])
            return

        keywordsListRaw = response.json()['additionalDetails']['keywordsList']
        keywordsList = {}

        for keyword in keywordsListRaw:
            self.logDebug(f'Keywords: {keyword}')
            keywordsList[keyword['name']] = keyword['value']

        self.logInfo(f'Sandbox keywords: {keywordsList}')
        return keywordsList

    def addVCenter(self, vcenterName, ipAddress, username, password):
        """
        Create a vCenter profile

        Parameters
           vcenterName <str>: The name of the vCenter profile to create in Tokalabs
           ipAddress <str>: The vCenter IP address
           username <str>: The vCenter login username
           password <str>: The vCenter login password
        """
        data = {'hostname': vcenterName,
                'assetID': '',
                'deviceManagement': {
                    'allowUsersToManageDevices': True,
                    'managementInterfaces': [
                        {'managementType': 'primary',
                         'enabled': True,
                         'type': 'https',
                         'networkAddress': ipAddress,
                         'authType': 'password',
                         'username': username,
                         'password': password
                        }
                    ]
                }}

        url = '/tokalabs/api/devices/vmware/vcenter/'
        self.sendRest('post', url, data)
        
    def addVMAsDeviceFromVCenter(self, vmName, vCenterProfile, protocolType='ssh', networkPort='',
                         username='admin', password='admin', data=None):
        """
        Add a VM from vCenter as a device in inventory.

        Either provide your own data or use the API parameters to create a basic VM device.
        """
        if data is None:
            data = {"hostname": vmName,
                    "vcenter": vCenterProfile,
                    "network": "",
                    #"vmprofile": "hubert-vm-profile",
                    "deviceManagement": {
                        "allowUsersToManageDevices": True,
                        "fetchIPAddressUsingVMwareTools": True,
                        "managementInterfaces": [
                            {"managementType": "primary",
                             "enabled": True,
                             "type": protocolType,
                             "networkAddress": '1.1.1.1',
                             "networkPort": networkPort,
                             "authType": "password",
                             "username": username,
                             "password": password,
                             "password_2": "",
                             "privateKey": "",
                             "passphrase": "",
                             "supportsSFTP": True
                            }
                        ]
                    }}
        
        url = '/tokalabs/api/devices/vmware/vm/'
        self.sendRest('post', url, data)

    def connectDevicePorts(self, srcDeviceName, targetDeviceName, srcPortId, targetPortId):
        """
        Connect device ports between two devices.
        Could be a L1 swtich to a device or a device to a device.
        
        Parameters
           srcDeviceName: From which device
           targetDeviceName: Connect to which device
           srcPortId: '1.1.1'
           targetPortId: '3/4/5'
           
        Usage
           sandboxObj.connectDevicePorts('VMone1', 'VMone2', '1/2', '2/2')
        """
        url = '/tokalabs/api/connections'
        data = {'sourceHost': srcDeviceName, 'sourcePortId': srcPortId,
                'targetHost': targetDeviceName, 'targetPortid': targetPortId}
        self.sendRest('post', url, data)
        
    def configCalendarReservation(self, sandbox=None, start=None, end=None,
                                  user=None, executionProfile="Default", notes=None):
        """
        Configure a sandbox calendar reservation for a user.
        The user cannot be an admin.

        sandbox <str>: Required: The name of the sandbox to schedule a reservation.
        user <str>:    Required: A non-admin user to reserve the sandbox for.

        start and end <str>: Required
           In a Linux shell, enter the date and time in this format:
              date "+%s" -d "03/29/2021 18:30:28"
              1617067828 <-- This is your date and time for the start/end parameters.

        params = {
            "sandbox": "TrafficTest",
            "executionProfile": "Default",
            "user": "jsmith",
            "start": 1589992938,
            "end": 1589996538,
            "notes": "Reservation Notes",
            "oppId": "Sample opportunity id"
        }
        """
        if self.sandbox == None and sandbox == None:
            raise SdloAssistantException('You must provide a sandbox name')

        if self.sandbox:
            sandbox = self.sandbox
            
        url = '/tokalabs/api/sandbox/reservations'
        params = {
            "sandbox": sandbox,
            "executionProfile": exceutionProfile,
            "start": start,
            "end": end,
            "user": user,
            "notes": notes
        }
        
        self.sendRest('post', url, params)
        
    def createVMwareProfile(self, vmProfileName, vCenterProfile, protocolType='ssh',
                            username='admin', password='admin', webOptions=None, data=None):
        """
        Create a VMware Profile. This creates a clone of a VM or a template from vCenter.
        Either pass in your own data or create a basic VM profile using all the parameters
        for this API.

        To include web options, pass in a list:
           webOption = [{"name": "woption1", "command": ["line1", "line2"]}] 
        """
        if webOptions is None:
            webOptions = []
            
        if data is None:
            data = {"hostname": vmProfileName,
                    "vcenter": vCenterProfile,
                    #"sourceType": "template", 
                    "source": "devOpsServer-1.0.0 Template",   
                    #"locationId": '',
                    "reservable": False, 
                    "deviceManagement": { 
                        "allowUsersToManageDevices": True, 
                        "fetchIPAddressUsingVMwareTools": True, 
                        "managementInterfaces": [  
                            { 
                                "managementType": "primary", 
                                "enabled": True, 
                                "type": "ssh", 
                                "networkPort": 1234, 
                                "authType": "password", 
                                "username": username, 
                                "password": password, 
                                "password_2": "", 
                                "privateKey": "", 
                                "passphrase": "", 
                                "supportsSFTP": True
                            }
                        ] 
                    }, 
                    "snmpConfiguration": { 
                        "enabled": False, 
                        "communityString": "public" 
                    },   
                    "webOptions": webOptions 
            } 
            
        url = '/tokalabs/api/devices/vmware/vmprofile/'
        self.sendRest('post', url, data)


class SdloAssistantException(Exception):
    def __init__(self, msg=None):
        if platform.python_version().startswith('3'):
            super().__init__(msg)

        if platform.python_version().startswith('2'):
            super(SdloAssistantException, self). __init__(msg)

        showErrorMsg = '\nsdloAssistant Exception error: {}\n\n'.format(msg)
        print(showErrorMsg)

        with open(Controller.logFile, 'a') as sdlLogFile:
            sdlLogFile.write(showErrorMsg)

    