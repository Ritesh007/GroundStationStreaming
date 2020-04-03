# Copyright 2008-2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# This software is provided for demonstration purposes only and is not
# maintained by the author.
# This software should not be used for production use
# without further testing and enhancement

import socket
import select
import os
import io

#   -------------------------------------------------------
#   Functions to send or receive & process UDP datagrams
#   -------------------------------------------------------

def startUdpListenerSimple(listenerPort, bufferSize, outputFile):

    #   Starts a UDP server and writes received data to a file, no packet processing

    localIP             = "127.0.0.1"
    numPacketsReceived  = 0
    numPacketsProcessed = 0
    totalDataSize       = 0
    inMemoryPayload     = b''
    inMemoryPayload = io.BytesIO(b'')
    outputMessageEveryNPackets = 1000

    try:
        UDPServerSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #   Set the socket timeout to 120 seconds to trigger post-
        #   -processing after 2 mins of no data
        UDPServerSocket.settimeout(120)
        UDPServerSocket.bind((localIP, listenerPort))
        print("\nUDP server listening on %s:%s" % (localIP, listenerPort) )
    except Exception as e:

        if e.errno == 1:
            print(" (ERR) [ERROR_ROOT_REQUIRED] Socket open error: %s" % e )
        else:
            print(" (ERR) [ERROR_CANT_OPEN_SOCKET] Socket open error: %s" % e )
        return 0

    #   Open file handle
    try:
        f = open(outputFile, "wb")
    except Exception as e:
        print(" (ERR) File open error: %s" % e )
        return 0

    while(True):

        try:
            bytesAddressPair = UDPServerSocket.recvfrom(bufferSize)
            message          = bytesAddressPair[0]

            try:
                #   Extract VRT payload from the data then write data to ByteIO Stream (in-memory buffer)
                payload = extractVrtPayloadFromBin(message)
                inMemoryPayload.write(payload)

                if numPacketsReceived == 0:
                    #   Provide output for first packet only
                    print ("Received first packet. Size: %d Bytes" % (len(message)) )
                    print ("VRT Payload Size: %d Bytes" % (len(payload)) )

            except Exception as e:
                print(" (ERR) Packet processing error: %s" % e )

            numPacketsReceived += 1

        except socket.timeout:
            #   No data received within the configured timeout period
            print ("Num Packets Received: %d" % (numPacketsReceived) )

            #   Get data from the BytesIO in-memory stream
            bufferData = inMemoryPayload.getvalue()
            totalBytesReceived = len(bufferData)
            if numPacketsReceived > 1 and totalBytesReceived > 0:

                #   Assume the transmission has finished
                #   Write received data to file
                try:
                    print("Writing memory buffer (%d Bytes) to output file..." % (totalBytesReceived) )
                    num_bytes_written = f.write(bufferData)

                    #   Make sure the buffer is flushed correctly
                    f.flush()
                    os.fsync(f.fileno())
                    f.close()

                    #   Clear the memory buffer
                    inMemoryPayload = b''

                    print("%d Bytes written to output file" % (num_bytes_written) )
                    exit()

                except Exception as e:
                    print("(ERR) File write error: %s" % e )
                    return 0


        except Exception as e:
            print("(ERR) Socket receive error: %s" % e )
            return 0

#   ---------------------------------------------
#   Functions to process VITA 49 data
#   ---------------------------------------------

def convertMaskAndTrimBytesToBitString(data, mask, rightShift, length):

    #   Performs multiple operations:
    #   1. Convert bytes to a Python integer bit string
    #   2. Mask values not needed
    #       e.g. 0b11111100 masked with 0b00001111 becomes 0b00001100
    #   3. Shift values we need to the right
    #       e.g. 0b00001100 shifted by 2 becomes 0b00000011
    #   4. Right-Trim the bit string to the desired length

    # Network / Big Endian format
    _BYTE_ORDER = r'big'

    try:
        #   1. Convert to int
        bytes = int.from_bytes(data, _BYTE_ORDER)
        #   2. Mask + 3 right-shift
        output = (bytes & mask) >> rightShift

        #   4. Right-Trim to the required length
        fmt = '0' + str(length) + 'b' # e.g. 04b / 08b
        output = format(output, fmt)

        return output

    except Exception as e:
        print(" (ERR) convertMaskAndTrimBytesToBitString error: %s" % e )
        return None

def checkForStreamId(data):

    streamIdIncluded = False

    #   We only want the first 4 bits, set other bits to zero, shift 4 places to the right, then trim to 4 in length
    binString = convertMaskAndTrimBytesToBitString(data, 0b11110000, 4, 4)
    if binString!=None:
        streamIdIncluded = binString == '0011' or binString == '0001' or binString == '0100' or binString == '0101'
    return [streamIdIncluded, binString]

def checkForClassId(data):

    classIdIncluded = False

    #   We only want bit 5, set the others to zeros and shift 3 places to the right, then trim length to 1
    binString = convertMaskAndTrimBytesToBitString(data, 0b00001000, 3, 1)
    classIdIncluded = binString == '1'

    return [classIdIncluded, binString]

def checkForTrailer(data):

    trailerIncluded = False

    #   We only want bit 6, set the others to zeros and shift 4 places to the right, then trim length to 1
    binString = convertMaskAndTrimBytesToBitString(data, 0b00000100, 4, 1)
    trailerIncluded = binString == '1'

    return [trailerIncluded, binString]

def checkForTimeStamp(data):

    timeStampIncluded = False

    #   We only want bits 1+2, set the others to zeros and shift 6 places to the right, then trim length to 1
    binString = convertMaskAndTrimBytesToBitString(data, 0b11000000, 6, 2)
    timeStampIncluded = binString != '10'

    return [timeStampIncluded, binString]

def extractVrtPayloadFromBin(udpData):

    #   Strips the VITA49 header and returns the payload data
    #   Expects VITA 49.2 AWS Uncoded Frame Data Format

    #   packet type       : first 4 bits of Byte 1 (streamIdIncluded)
    #   classIdIncluded   : bit 5 of Byte 1
    #   trailerIncluded   : bit 6 of Byte 1
    #   timeStampIncluded : first 2 bits of Byte 2

    #print("============================================")
    #print("Parsing VRT Header...")
    #print('')
    #print("  Byte 1: {:08b}".format(int.from_bytes(udpData[0:1], r'big')))
    #print("  Byte 2: {:08b}".format(int.from_bytes(udpData[1:2], r'big')))
    #print('')

    #   Check Byte 01 to see if StreamId is included
    streamIdIncluded = checkForStreamId(udpData[0:1])
    #print("  streamIdIncluded  : %s" % streamIdIncluded)

    #   Check Byte 01 to see if ClassId is included
    classIdIncluded = checkForClassId(udpData[0:1])
    #print("  classIdIncluded   : %s" % classIdIncluded)

    #   Check Byte 01 to see if a Trailer is included
    trailerIncluded = checkForTrailer(udpData[0:1])
    #print("  trailerIncluded   : %s" % trailerIncluded)

    #   Check Byte 02 to see if a TimeStamp is included
    timeStampIncluded = checkForTimeStamp(udpData[1:2])
    #print("  timeStampIncluded : %s" % (timeStampIncluded) )

    #   Calculate the length of the VITA 49 header based on the above fields
    vrtHeaderLength = 4 #   Min header length
    vrtHeaderLength += 4 if streamIdIncluded[0] else 0
    vrtHeaderLength += 8 if classIdIncluded[0] else 0
    vrtHeaderLength += 12 if timeStampIncluded[0] else 0
    #print("Processed packet. VRT Header Length : %d" % (vrtHeaderLength) )
    #print('')
    #print("============================================")

    #   Return the vrt payload only (skip the vrt header)
    return udpData[vrtHeaderLength:]
