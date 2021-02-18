from perform.inputFuncs import catchList

import numpy as np
import pdb

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import matplotlib.gridspec as gridspec
mpl.rc('font', family='serif',size='8') 	# TODO: adapt axis label font size to number of subplots
mpl.rc('axes', labelsize='x-large')
mpl.rc('figure', facecolor='w')
mpl.rc('text', usetex=False)
mpl.rc('text.latex',preamble=r'\usepackage{amsmath}')

# TODO: this is kind of a mess
# 	I'm struggling to write effective hierarchy for field, probe, and residual, as probe shares similarities with field and residual plots
# TODO: add RHS, flux plotting

class visualization:

	def __init__(self, visID, visVars, visXBounds, visYBounds, numSpeciesFull):

		if (self.visType in ["field","probe"]):

			# check requested variables
			self.visVars	= visVars
			for visVar in self.visVars:
				if (visVar in ["pressure","velocity","temperature","source","density","momentum","energy"]):
					pass
				elif ((visVar[:7] == "species") or (visVar[:15] == "density-species")):
					try:
						if (visVar[:7] == "species"):
							speciesIdx = int(visVar[7:])
						elif (visVar[:15] == "density-species"):
							speciesIdx = int(visVar[15:])

						assert ((speciesIdx > 0) and (speciesIdx <= numSpeciesFull)), \
							"Species number must be a positive integer less than or equal to the number of chemical species"
					except:
						raise ValueError("visVar entry " + visVar + " must be formated as speciesX or density-speciesX, where X is an integer")
				else:
					raise ValueError("Invalid entry in visVar"+str(visID))

			self.numSubplots = len(self.visVars)

		# residual plot
		else:
			self.visVars = ["residual"]
			self.numSubplots = 1

		self.visXBounds = visXBounds
		assert(len(self.visXBounds) == self.numSubplots), "Length of visXBounds"+str(visID)+" must match number of subplots: "+str(self.numSubplots)
		self.visYBounds = visYBounds
		assert(len(self.visYBounds) == self.numSubplots), "Length of visYBounds"+str(visID)+" must match number of subplots: "+str(self.numSubplots)

		if (self.numSubplots == 1):
			self.numRows = 1 
			self.numCols = 1
		elif (self.numSubplots == 2):
			self.numRows = 2
			self.numCols = 1
		elif (self.numSubplots <= 4):
			self.numRows = 2
			self.numCols = 2
		elif (self.numSubplots <= 6):
			self.numRows = 3
			self.numCols = 2
		elif (self.numSubplots <= 9):
			# TODO: an extra, empty subplot shows up with 7 subplots
			self.numRows = 3
			self.numCols = 3
		else:
			raise ValueError("Cannot plot more than nine subplots in the same image")

		# axis labels
		# TODO: could change this to a dictionary reference
		self.axLabels = [None] * self.numSubplots
		if (self.visType == "residual"):
			self.axLabels[0] = "Residual History"
		else:
			for axIdx in range(self.numSubplots):
				varStr = self.visVars[axIdx]
				if (varStr == "pressure"):
					self.axLabels[axIdx] = "Pressure (Pa)"
				elif (varStr == "velocity"):
					self.axLabels[axIdx] = "Velocity (m/s)"
				elif (varStr == "temperature"):
					self.axLabels[axIdx] = "Temperature (K)"
				elif (varStr == "source"):
					self.axLabels[axIdx] = "Reaction Source Term"
				elif (varStr == "density"):
					self.axLabels[axIdx] = "Density (kg/m^3)"
				elif (varStr == "momentum"):
					self.axLabels[axIdx] = "Momentum (kg/s-m^2)"
				elif (varStr == "energy"):
					self.axLabels[axIdx] = "Total Energy"

				# TODO: some way to incorporate actual species name
				elif (varStr[:7] == "species"):
					self.axLabels[axIdx] = "Species "+str(varStr[7:])+" Mass Fraction" 
				elif (varStr[:15] == "density-species"):
					self.axLabels[axIdx] = "Density-weighted Species "+str(varStr[7:])+" Mass Fraction (kg/m^3)"
				else:
					raise ValueError("Invalid field visualization variable:"+str(varStr))
