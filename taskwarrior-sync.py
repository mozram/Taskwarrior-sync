#!/bin/python3

'''
The sequence for syncing are:
1. Zip the file to /tmp folder
2. Encrypt the file via GPG (armored possible?)
3. Get timestamp via network service to make sure consistent epoch time
4. Push
'''

from datetime import datetime
import requests
import json
import os
import subprocess
from pathlib import Path
import argparse
import re

## Check for required variable. Since most of it sensitive, user must set it up
try:
    GIST_ACCESS_TOKEN=os.environ['TASK_SYNC_TOKEN']
except:
    print("Error: Export PLEASE_SYNC_TOKEN with your Gist access token")
    exit()

try:
    GIST_ID=os.environ['TASK_GIST_ID']
except:
    print("Error: Export PLEASE_GIST_ID with your Gist ID")
    exit()

try:
    PGP_ID = os.environ['TASK_USER_ID']
except:
    print("Error: Export TASK_USER_ID with your PGP ID")
    exit()

HOME = str(Path.home()) + "/"
TASK_FOLDER = HOME + ".task"
TASK_CONFIG = HOME + ".taskrc"
TMP = "/tmp/"
PACKED_CONFIG = "taskConfig.tar.gz"
PACKED_CONFIG_DECRYPTED = "taskConfig_dec.tar.gz"
GIST_FILENAME = "task-sync.json"
BACKLOG_TASK = TASK_FOLDER + "/backlog.data"
COMPLETED_TASK = TASK_FOLDER + "/completed.data"
PENDING_TASK = TASK_FOLDER + "/pending.data"
UNDO_TASK = TASK_FOLDER + "/undo.data"

# Temporary enumeration of status
STATUS_NO_CHANGES = 0
STATUS_LOCAL_NEWER = 1
STATUS_REMOTE_NEWER = 2

## Compress file and folder via tar -czf task.tar.gz TASK_CONFIG TASK_FOLDER
def packConfig():
    print("Packing config into tar...")
    r = subprocess.run(args=[ "tar",
                              "-czf",
                              TMP + PACKED_CONFIG,
                              TASK_CONFIG,
                              TASK_FOLDER
                              ],
                       universal_newlines = True,
                       stdout = subprocess.PIPE )
    # print(r.stdout)

def unpackConfig():
    print("Unpacking tar config...")
    r = subprocess.run(args=[ "tar",
                              "-xzf",
                              TMP + PACKED_CONFIG_DECRYPTED,
                              "-C",
                              "/"
                              ],
                       universal_newlines = True,
                       stdout = subprocess.PIPE )

## Encrypt the package
def encryptConfig():
    print("Encrypting config...")
    r = subprocess.run(args=[ "gpg",
                          "--recipient",
                          PGP_ID,
                          "--encrypt",
                          "--armor",
                          "--output",
                          "-",
                          TMP + PACKED_CONFIG ],
                  universal_newlines = True,
                  stdout = subprocess.PIPE )
    # print(r.stdout)
    return r.stdout

def decryptConfig( input ):
    print("Decrypting config...")
    # decrypt the data and overwrite local data
    echo_r = subprocess.Popen(('echo', input), stdout=subprocess.PIPE)
    decrypt_r = subprocess.Popen(('gpg', '--decrypt'), stdin=echo_r.stdout, stdout=subprocess.PIPE)
    # Write decrypted data
    write_r = subprocess.Popen(('tee', TMP + PACKED_CONFIG_DECRYPTED), stdin=decrypt_r.stdout, stdout=subprocess.PIPE)
    echo_r.wait()
    decrypt_r.wait()
    write_r.wait()
    # print(decrypt_r.stdout)s

def packJson( input, timestamp ):
    print("Packing config to JSON format...")
    # Build JSON object
    packedData = {}
    packedData['modified'] = timestamp
    packedData['data'] = input.replace("\n", "\\n")

    # Build JSON Object
    jData = json.dumps(packedData)
    # print( "Packed JSON: " + jData)

    return jData

## Get gist
def getGist():
    print("Fetching config from GIST...")
    headers = {'Authorization': f'token {GIST_ACCESS_TOKEN}'}
    r = requests.get('https://api.github.com/gists/' + GIST_ID, headers=headers) 
    # print(r.json())
    jsonData = r.json()

    return json.loads(jsonData['files'][GIST_FILENAME]['content'])

## Update gist
def updateGist( content ):
    print("Pushing config to GIST...")
    # content=open(filename, 'r').read()
    headers = {'Authorization': f'token {GIST_ACCESS_TOKEN}'}
    r = requests.patch('https://api.github.com/gists/' + GIST_ID, data=json.dumps({'files':{GIST_FILENAME:{"content":content}}}),headers=headers) 
    #print(r.json())

## Using file modified as indicator more recent file is not reliable as if 
#   we just did sync, the file modified will be more recent than the one
#   from Gist. Instead, we check all list, get the last entry each,
#   get the modified value. Any copy that has more recent modified most
#   like is the latest one
def checkVersion():
    # Check completed, backlog, pending and undo both remote and local
    # Get the last entry
    # Get the modified value from both and compare
    print("Version checked")

# Get last line of each file
def getLastLine( inputFile ):
    file = open( inputFile, 'r' )
    lines = file.readlines()
    for line in lines:
        lastLine = line
    return lastLine

# Only backlog file use proper JSON
# Return Epoch in integer type
def getModifiedBacklog( inputJSON ):
    # Build JSON Object
    jData = json.loads(inputJSON)
    # Backlog uses ISO8601 date format, but not quite. Need to append few thing before it compliance
    modified = jData['modified']
    modified = modified[:4] + "-" + modified[4:6] + "-" + modified[6:11] + ":" + modified[11:13] + ":" + modified[13:]
    utc_dt = datetime.strptime( modified, '%Y-%m-%dT%H:%M:%SZ' )
    timestamp = (utc_dt - datetime(1970, 1, 1)).total_seconds()
    return int(timestamp)

# Get modified epoch for other file
def getModified( inputString ):
    # Build JSON Object
    output = re.search("modified:\"(.*)\" status", inputString )
    # print(output[1])
    return int(output[1])

# Return most recent timestamp
def getLatestModified():
    print("Get latest modified timestamp...")
    # Get each file last line
    backlogLastLine = getLastLine( BACKLOG_TASK )
    backlogLatestModified = getModifiedBacklog( backlogLastLine )
    # print(backlogLatestModified)

    completedLastLine = getLastLine( COMPLETED_TASK )
    completedLatestModified = getModified( completedLastLine )
    # print(completedLatestModified)

    pendingLastLine = getLastLine( PENDING_TASK )
    pendingLatestModified = getModified( pendingLastLine )
    # print(pendingLatestModified)
    
    allModified = [ backlogLatestModified, completedLatestModified, pendingLatestModified]

    return max(allModified)

def compareModifiedTime():
    # Status variable
    status = STATUS_NO_CHANGES
    # Pull remote data
    remoteGistContent = getGist()
    # Get remote modified time
    print("Extracting remote content...")
    remoteModified = int(remoteGistContent['modified'])
    # Get local modified time
    localModified = getLatestModified()
    # Compare time
    print("Comparing local and remote config...")
    if remoteModified > localModified:
        print("Remote config newer than local...")
        status = STATUS_REMOTE_NEWER
    elif localModified > remoteModified:
        print("Local config newer than remote...")
        status = STATUS_LOCAL_NEWER

    return status, localModified, remoteModified, remoteGistContent


parser = argparse.ArgumentParser(description='Simple Task Warrior task sync. Uses Github as storage and PGP as encryption')
parser.add_argument('--push', action="store_true", help='Push config and task data to Gist')
parser.add_argument('--pull', action="store_true", help='Pull config and task data to Gist')
parser.add_argument('--sync', action="store_true", help='Sync the config')

args = parser.parse_args()

if args.push:
    # print('Push config')
    confirmPush = False

    compareStatus, localModified, remoteModified, remoteGistContent = compareModifiedTime()
    if compareStatus == STATUS_REMOTE_NEWER:
        # Remote config is newer. Pushing may cause data loss
        remoteTime = datetime.fromtimestamp(remoteModified)
        localTime = datetime.fromtimestamp(localModified)
        userInput = input("Remote copy is newer than local. Proceed pushing? [y/N]: ")
        if userInput == 'y':
            confirmPush = True
        else:
            print("Push canceled")
    elif compareStatus == STATUS_NO_CHANGES:
        print("No changes...")
    else:
        # If local is newer, push the config
        print("No conflict...")
        confirmPush = True

    if confirmPush:
        packConfig()
        data = encryptConfig()
        packedJson = packJson( data, localModified )
        updateGist(packedJson)


if args.pull:
    # print('Pull config')
    confirmPull = False

    compareStatus, localModified, remoteModified, remoteGistContent = compareModifiedTime()
    if compareStatus == STATUS_LOCAL_NEWER:
        # Local newer than remote, ask user to continue or not
        localTime = datetime.fromtimestamp(localModified)
        remoteTime = datetime.fromtimestamp(remoteModified)
        print("Local copy timestamp: " + str(localTime))
        print("Remote copy timestamp: " + str(remoteTime))
        userInput = input("Local copy is newer than remote. Proceed pulling? [y/N]: ")
        if userInput == 'y':
            confirmPull = True
        else:
            print("Pull canceled")
    elif compareStatus == STATUS_NO_CHANGES:
        print("No changes...")
    else:
        print("No conflict...")
        confirmPull = True
    
    if confirmPull:
        # Get remote content
        remoteConfigData = str(remoteGistContent['data']).replace("\\n","\n")
        decryptConfig(remoteConfigData)
        # Unpack
        unpackConfig()
        print("Pull completed")

if args.sync:
    print("Running automatic sync...")
    # Compare local and remote modified
    compareStatus, localModified, remoteModified, remoteGistContent = compareModifiedTime()
    # Do some comparison logic
    if compareStatus == STATUS_LOCAL_NEWER:
        # Push
        print("Pushing config...")


# maxMod = getLatestModified()
# print(maxMod)
