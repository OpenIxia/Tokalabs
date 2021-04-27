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
   python reserveSandbox.py -sandbox /path/sandbox.yml -reserve|-release
   
   # -forceTakeOwnership: Include this parameter to force takeover the sandbox if sandbox is already reserve.
   python reserveSandbox.py -sandbox /path/sandbox.yml -reserve -forceTakeOwnership
"""

import sys, os, traceback, yaml, argparse
import sdloAssistant

try:
    parser = argparse.ArgumentParser()
    parser.add_argument('-sandbox', help='The sandbox yml config file')
    parser.add_argument('-reserve', action='store_true', help='Reserve the sandbox')
    parser.add_argument('-release', action='store_true', help='Release the sandbox.')
    parser.add_argument('-forceTakeOwnership', action='store_true', default=False,
                        help='For sandbox reservation only. Force take ownership of sandbox if it is reserved.')
    args = parser.parse_args()
    
    if not os.path.exists(args.sandbox):
        raise Exception(f'No such config file found: {args.sandbox}')

    with open(args.sandbox) as paramsObj:
        params = yaml.safe_load(paramsObj)
        
    print(f'\nconfigFile params: {params}')

    sandboxObj = sdloAssistant.Controller(params['sdloControllerIp'], params['user'], params['password'])

    # Set the sandbox name to use
    sandboxObj.setSandbox(params['sandbox'])

    if args.reserve:
        sandboxObj.reserve(forceTakeOwnership=args.forceTakeOwnership)

    if args.release:
        sandboxObj.release()

    sys.exit(0)
    
except Exception as errMsg:
    print(f'\nreserveSandbox.py error: {errMsg}\n{traceback.format_exc()}\n')
    sys.exit(1)
    
