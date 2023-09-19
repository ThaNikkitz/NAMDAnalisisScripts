import prody
import argparse
from datetime import datetime
import numpy

parser = argparse.ArgumentParser(description = 'Calculate the collective dipole of the given selection.')
parser.add_argument('-i', '--in_file', type = str, required = True, help = 'Path, either absolute or relative, to the input file')
parser.add_argument('-a', '--average', action = 'store_true', required = False, default = False, help = 'Calculate the average for the trajectory if included (with "-a" option), frame-by-frame-wise if not included. Default: False')
parser.add_argument('-b', '--bins', action = 'store_true', required = False, default = False, help = 'Return dipole of selection "sel" binned across a cylinder. Default: False')

arg = parser.parse_args()
inFile = open(arg.in_file, 'r')

dcdName = []
outName = 'outFile.out'

avg = arg.average


# Reading inputs from the input parameters file. This is for the analysis calculation,
# NOT for the simulation itself.

print('\nReading the input and asigning variables')

for line in inFile:
    l = line.strip().split()
    if len(l) > 0:
        if 'dcd' in l[0]: # Any amount of .dcd files
            dcdName.append(l[1])
        elif l[0] == 'pdb':
            pdbName = l[1]
        elif l[0] == 'psf':
            psfName = l[1]
        elif l[0] == 'ref': # Alignment selection
            if len(l[1:]) > 1:
                refName = ' '.join(l[1:])
            else:
                refName = l[1]
        elif 'sel' in l[0]: # Should be a broader selection, not including the position bounds (without "and z <= XX") E.g., "name OH2"
            if len(l[1:]) > 1:
                selName = ' '.join(l[1:])
            else:
                selName = l[1]
        elif l[0] == 'out':
            outName = l[1]
        if arg.bins == True:
            if l[0].lower() == 'zmin':
                zMin = float(l[1])
            elif l[0].lower() == 'zmax':
                zMax = float(l[1])
            elif l[0].lower() == 'nbins':
                nBins = int(l[1])
            elif l[0].lower() == 'rad':
                rad = float(l[1])
            elif l[0].lower() == 'thr':
                thr = l[1:] # Can be a space-separated list. Each element is a number of minimum frames that define a "time-wise bin"
                            # E.g. If 5, 100, 500 is given, data about residence time in intervals < 5 | 5 - 100 | 100 - 500 | 500 > will be returned.
                            # The first interval is not considered. If set to 0, all actual intervals are considered.
        else:
            print("--bins (-b) flag was either not set or was set to False. Data won't be binned.")

    else:
        pass

inFile.close()

pdb = prody.parsePDB(pdbName)
dcd = prody.Trajectory(dcdName[0])
if len(dcdName) > 1:
    for d in dcdName[1:]:
        dcd.addFile(d)

dcd.link(pdb)
dcd.setCoords(pdb)
dcd.setAtoms(pdb.select(refName)) # refName = Selection used when aligning frames (frame.superpose())
atomsSelection = pdb.select(selName)

moleculesInBins = numpy.zeros((len(atomsSelection), nBins))
lCyl = abs(zMax) + abs(zMin)
binSize = lCyl/nBins
binArray = numpy.arange(zMin, zMax + binSize, binSize)
binsInTime = numpy.zeros_like((len(dcd)/thr), len(binArray))

f0 = dcd.next()
prody.wrapAtoms(pdb, unitcell = f0.getUnitcell()[:3], center = prody.calcCenter(pdb.select(refName)))
f0.superpose()
# Initializers for positions, indices and whether it's in bin or not at frame 0
oldPos = pdb.select(f'{selName} and (x^2 + y^2) < {rad**2} and z > {zMin} and z < {zMax}').getCoords()[:,-1]
oldInd = pdb.select(f'{selName} and (x^2 + y^2) < {rad**2} and z > {zMin} and z < {zMax}').getIndices()
oldInBin = numpy.argwhere((oldPos[:,numpy.newaxis] >= binArray[numpy.newaxis,:-1]) & (oldPos[:,numpy.newaxis] < binArray[numpy.newaxis,1:]))
for f, frame in enumerate(dcd):
        prody.wrapAtoms(pdb, unitcell = frame.getUnitcell()[:3], center = prody.calcCenter(pdb.select(refName)))
        frame.superpose()
        sel = pdb.select(f'{selName} and (x^2 + y^2) < {rad**2} and z > {zMin} and z < {zMax}')
        pos = sel.getCoords()[:,-1] # Grab selection position, z-coordinate
        ind = sel.getIndices() # Grab selection (atom) indices
        # Defines which INDEX of the pos/ind array goes into which bin.
        inBin = numpy.argwhere((pos[:,numpy.newaxis] >= binArray[numpy.newaxis,:-1]) & (pos[:,numpy.newaxis] < binArray[numpy.newaxis,1:])) 
        horizontalStack = numpy.vstack((ind, inBin[:,1])).T # Combine atom index information with bin's index information
        oldHorizontalStack = numpy.vstack((oldInd, oldInBin[:,1])).T # Same as above, for previous frame (old) data
        mask = numpy.flatnonzero((oldHorizontalStack == horizontalStack[:,None]).all(-1).any(-1))
        moleculesInBins[mask] += 1