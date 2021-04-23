"""
This script takes in a yml config file that states which sandbox to use
and the login credentials to the Tokalab controller.
The yml config file must have these parameters:

    sdloControllerIp: 10.10.10.1
    user: admin
    password: admin
    sandbox: gitlab-pytest

Requirements
   - python 3.6+
   - pip install requests PyYAML
   - sdloAssistant.py
   - sandbox yml config file
    
Usage:
   reserveSandbox.py -sandbox /path/sandbox.yml -reserve|-release
"""

import sys, os, traceback, yaml, argparse
import sdloAssistant

try:
    parser = argparse.ArgumentParser()
    parser.add_argument('-sandbox', type=str, help='The sandbox yml config file')
    parser.add_argument('-reserve', action='store_true', help='Reserve the sandbox')
    parser.add_argument('-release', action='store_true', help='Release the sandbox.')
    args = parser.parse_args()
    
    if not os.path.exists(args.sandbox):
        raise Exception(f'No such config file found: {args.sandbox}')

    with open(args.sandbox) as paramsObj:
        params = yaml.load(paramsObj, Loader=yaml.FullLoader)
        
    print(f'\nconfigFile params: {params}')
    
    sandboxObj = sdloAssistant.Controller(params['sdloControllerIp'], params['user'], params['password'])

    sandboxObj.setSandbox(params['sandbox'])
    sandboxKeywords = sandboxObj.getSandboxKeywords()
    
    if args.reserve:
        sandboxObj.reserve(forceTakeOwnership=sandboxKeywords['forceTakeSandboxOwnership'])
        ixiaPorts,dutPorts = sandboxObj.getDevicePorts('VMone', 'VMone2', isSrcDeviceIxia=True)
        sandboxObj.logInfo(f'\n\tIxiaPorts: {ixiaPorts}\n\tRouterPorts: {dutPorts}\n')
    
    if args.release:
        sandboxObj.release()

    sys.exit(0)
    
except Exception as errMsg:
    print(f'\nreserveSandbox.py error: {errMsg}\n{traceback.format_exc()}\n')
    sys.exit(1)
    
