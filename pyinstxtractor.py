'''
PyInstaller Extractor v1.6 (Supports pyinstaller 3.2, 3.1, 3.0, 2.1, 2.0)
Author : Extreme Coders
E-mail : extremecoders(at)hotmail(dot)com
Web    : https://0xec.blogspot.com
Date   : 05-Sept-2016
Url    : https://sourceforge.net/projects/pyinstallerextractor/

For any suggestions, leave a comment on
https://forum.tuts4you.com/topic/34455-pyinstaller-extractor/

This script extracts a pyinstaller generated executable file.
Pyinstaller installation is not needed. The script has it all.

For best results, it is recommended to run this script in the
same version of python as was used to create the executable.
This is just to prevent unmarshalling errors(if any) while
extracting the PYZ archive.

Usage : Just copy this script to the directory where your exe resides
        and run the script with the exe file name as a parameter

C:\path\to\exe\>python pyinstxtractor.py <filename>
$ /path/to/exe/python pyinstxtractor.py <filename>

Licensed under GNU General Public License (GPL) v3.
You are free to modify this source.
'''

import os
import struct
import marshal
import zlib
import sys
import imp
import types
from uuid import uuid4 as uniquename


class CTOCEntry:
    def __init__(self, position, cmprsdDataSize, uncmprsdDataSize, cmprsFlag, typeCmprsData, name):
        self.position = position
        self.cmprsdDataSize = cmprsdDataSize
        self.uncmprsdDataSize = uncmprsdDataSize
        self.cmprsFlag = cmprsFlag
        self.typeCmprsData = typeCmprsData
        self.name = name


class PyInstArchive:
    PYINST20_COOKIE_SIZE = 24           # For pyinstaller 2.0
    PYINST21_COOKIE_SIZE = 24 + 64      # For pyinstaller 2.1+
    MAGIC = b'MEI\x0C\x0B\x0A\x0B\x0E'  # Magic number which identifies pyinstaller

    def __init__(self, path):
        self.filePath = path


    def open(self):
        try:
            self.fPtr = open(self.filePath, 'rb')
            self.fileSize = os.stat(self.filePath).st_size
        except:
            print('[*] Error: Could not open {}'.format(self.filePath))
            return False
        return True


    def close(self):
        try:
            self.fPtr.close()
        except:
            pass


    def checkFile(self):
        print('[*] Processing {}'.format(self.filePath))
        # Check if it is a 2.0 archive
        self.fPtr.seek(self.fileSize - self.PYINST20_COOKIE_SIZE, os.SEEK_SET)
        magicFromFile = self.fPtr.read(len(self.MAGIC))

        if magicFromFile == self.MAGIC:
            self.pyinstVer = 20     # pyinstaller 2.0
            print('[*] Pyinstaller version: 2.0')
            return True

        # Check for pyinstaller 2.1+ before bailing out
        self.fPtr.seek(self.fileSize - self.PYINST21_COOKIE_SIZE, os.SEEK_SET)
        magicFromFile = self.fPtr.read(len(self.MAGIC))

        if magicFromFile == self.MAGIC:
            print('[*] Pyinstaller version: 2.1+')
            self.pyinstVer = 21     # pyinstaller 2.1+
            return True

        print('[*] Error : Unsupported pyinstaller version or not a pyinstaller archive')
        return False


    def getCArchiveInfo(self):
        try:
            if self.pyinstVer == 20:
                self.fPtr.seek(self.fileSize - self.PYINST20_COOKIE_SIZE, os.SEEK_SET)

                # Read CArchive cookie
                (magic, lengthofPackage, toc, tocLen, self.pyver) = \
                struct.unpack('!8siiii', self.fPtr.read(self.PYINST20_COOKIE_SIZE))

            elif self.pyinstVer == 21:
                self.fPtr.seek(self.fileSize - self.PYINST21_COOKIE_SIZE, os.SEEK_SET)

                # Read CArchive cookie
                (magic, lengthofPackage, toc, tocLen, self.pyver, pylibname) = \
                struct.unpack('!8siiii64s', self.fPtr.read(self.PYINST21_COOKIE_SIZE))

        except:
            print('[*] Error : The file is not a pyinstaller archive')
            return False

        print('[*] Python version: {}'.format(self.pyver))

        # Overlay is the data appended at the end of the PE
        self.overlaySize = lengthofPackage
        self.overlayPos = self.fileSize - self.overlaySize
        self.tableOfContentsPos = self.overlayPos + toc
        self.tableOfContentsSize = tocLen

        print('[*] Length of package: {} bytes'.format(self.overlaySize))
        return True


    def parseTOC(self):
        # Go to the table of contents
        self.fPtr.seek(self.tableOfContentsPos, os.SEEK_SET)

        self.tocList = []
        parsedLen = 0

        # Parse table of contents
        while parsedLen < self.tableOfContentsSize:
            (entrySize, ) = struct.unpack('!i', self.fPtr.read(4))
            nameLen = struct.calcsize('!iiiiBc')

            (entryPos, cmprsdDataSize, uncmprsdDataSize, cmprsFlag, typeCmprsData, name) = \
            struct.unpack( \
                '!iiiBc{}s'.format(entrySize - nameLen), \
                self.fPtr.read(entrySize - 4))
            
            name = name.decode('utf-8').rstrip('\0')
            if len(name) == 0:
                name = str(uniquename())
                print('[!] Warning: Found an unamed file in CArchive. Using random name {}'.format(name))
                
            self.tocList.append( \
                                CTOCEntry(                      \
                                    self.overlayPos + entryPos, \
                                    cmprsdDataSize,             \
                                    uncmprsdDataSize,           \
                                    cmprsFlag,                  \
                                    typeCmprsData,              \
                                    name                        \
                                ))

            parsedLen += entrySize
        print('[*] Found {} files in CArchive'.format(len(self.tocList)))



    def extractFiles(self):
        print('[*] Begining extraction...please standby')
        extractionDir = os.path.join(os.getcwd(), os.path.basename(self.filePath) + '_extracted')

        if not os.path.exists(extractionDir):
            os.mkdir(extractionDir)

        os.chdir(extractionDir)

        for entry in self.tocList:
            basePath = os.path.dirname(entry.name)
            if basePath != '':
                # Check if path exists, create if not
                if not os.path.exists(basePath):
                    os.makedirs(basePath)

            self.fPtr.seek(entry.position, os.SEEK_SET)
            data = self.fPtr.read(entry.cmprsdDataSize)

            if entry.cmprsFlag == 1:
                data = zlib.decompress(data)
                # Malware may tamper with the uncompressed size
                # Comment out the assertion in such a case
                assert len(data) == entry.uncmprsdDataSize # Sanity Check

            with open(entry.name, 'wb') as f:
                f.write(data)

            if entry.typeCmprsData == b'z':
                self._extractPyz(entry.name)


    def _extractPyz(self, name):
        dirName =  name + '_extracted'
        # Create a directory for the contents of the pyz
        if not os.path.exists(dirName):
            os.mkdir(dirName)

        with open(name, 'rb') as f:
            pyzMagic = f.read(4)
            assert pyzMagic == b'PYZ\0' # Sanity Check

            pycHeader = f.read(4) # Python magic value

            if imp.get_magic() != pycHeader:
                print('[!] Warning: The script is running in a different python version than the one used to build the executable')
                print('    Run this script in Python{} to prevent extraction errors(if any) during unmarshalling'.format(self.pyver))

            (tocPosition, ) = struct.unpack('!i', f.read(4))
            f.seek(tocPosition, os.SEEK_SET)

            try:
                toc = marshal.load(f)
            except:
                print('[!] Unmarshalling FAILED. Cannot extract {}. Extracting remaining files.'.format(name))
                return

            print('[*] Found {} files in PYZ archive'.format(len(toc)))
            
            # From pyinstaller 3.1+ toc is a list of tuples
            if type(toc) == list:
                toc = dict(toc)            

            for key in toc.keys():
                (ispkg, pos, length) = toc[key]
                f.seek(pos, os.SEEK_SET)
                
                fileName = key
                try:
                    # for Python > 3.3 some keys are bytes object some are str object
                    fileName = key.decode('utf-8')
                except:
                    pass

                try:
                    data = f.read(length)
                    data = zlib.decompress(data)
                except:
                    print('[!] Error: Failed to decompress {}, probably encrypted. Extracting as is.'.format(fileName))
                    open(os.path.join(dirName, fileName + '.pyc.encrypted'), 'wb').write(data)
                    continue                
                
                with open(os.path.join(dirName, fileName + '.pyc'), 'wb') as pycFile:
                    pycFile.write(pycHeader)    # Write pyc magic
                    pycFile.write(b'\0' * 4)     # Write timestamp
                    if self.pyver >= 33:
                        pycFile.write(b'\0' * 4)  # Size parameter added in Python 3.3
                    pycFile.write(data)


def main():
    if len(sys.argv) < 2:
        print('[*] Usage: pyinstxtractor.py <filename>')

    else:
        arch = PyInstArchive(sys.argv[1])
        if arch.open():
            if arch.checkFile():
                if arch.getCArchiveInfo():
                    arch.parseTOC()
                    arch.extractFiles()
                    arch.close()
                    print('[*] Successfully extracted pyinstaller archive: {}'.format(sys.argv[1]))
                    print('')
                    print('You can now use a python decompiler on the pyc files within the extracted directory')
                    return

            arch.close()


if __name__ == '__main__':
    main()