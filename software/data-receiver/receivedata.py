# Copyright 2008-2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# This software is provided for demonstration purposes only and is not
# maintained by the author.
# This software should not be used for production use
# without further testing and enhancement

import awsgs
import time
import os
import sys

bufferSize    = 409600
listenerPort  = 50000

#   Set the output fileName
if len(sys.argv) < 2:
    timestr = time.strftime("%Y%m%d-%H%M")
    outputFile = timestr + '-' + 'noname' + '-raw.bin'
else:
    outputFile=sys.argv[1]

print("\nRemoving previous output file (%s) if exists" % outputFile)
if os.path.isfile(outputFile):
    os.remove(outputFile)

#   Capture and process binary data from a direct broadcast stream
awsgs.startUdpListenerSimple(listenerPort, bufferSize, outputFile)
