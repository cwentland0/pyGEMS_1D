from perform.constants import realType, RUniv, suthTemp
from perform.gasModel.gasModel import gasModel

import numpy as np
import cantera as ct
import pdb

class canteraMixture(gasModel):
	"""
	Container class for all Cantera thermo/transport property methods
	"""

	def __init__(self, gasDict,numCells):

		self.gasType 				= gasDict["gasType"]
		self.gas				=	ct.Solution(gasDict["ctiFile"])
		#self.gasArray			=	ct.SolutionArray(self.gas,numCells)  #used for keeping track of cell properties
		#self.gasChecker			=   ct.SolutionArray(self.gas,1)  #used for state independent lookup
		
		self.numSpeciesFull 	= self.gas.n_species				# total number of species in case
		self.SpeciesNames       = self.gas.species_names
		self.molWeights 		= self.gas.molecular_weights	# molecular weights, g/mol
		#These are either not constant or not needed for TPG
		#self.enthRef 			= -2.545e+05#gasDict["enthRef"].astype(realType) 		# reference enthalpy, J/kg
		#self.tempRef 			= 0.0#gasDict["tempRef"]						# reference temperature, K
		#self.Cp 				= gasDict["Cp"].astype(realType)			# heat capacity at constant pressure, J/(kg-K)
		self.Pr 				= gasDict["Pr"].astype(realType)			# Prandtl number
		self.Sc 				= gasDict["Sc"].astype(realType)			# Schmidt number
		#self.muRef				= gasDict["muRef"].astype(realType)			# reference dynamic viscosity for Sutherland model
		

		#Don't need these for cantera all reactions are handled internally
		#self.nu 				= gasDict["nu"].astype(realType)		# ?????
		#self.nuArr 				= gasDict["nuArr"].astype(realType)		# ?????
		#self.actEnergy			= float(gasDict["actEnergy"])			# global reaction Arrhenius activation energy, divided by RUniv, ?????
		#self.preExpFact 		= float(gasDict["preExpFact"]) 			# global reaction Arrhenius pre-exponential factor		

		# misc calculations
		#self.RGas 				= RUniv / self.molWeights 			# specific gas constant of each species, J/(K*kg)
		
		self.numSpecies 		= self.numSpeciesFull - 1			# last species is not directly solved for
		print(self.numSpecies)
		self.numEqs 			= self.numSpecies + 3				# pressure, velocity, temperature, and species transport
		self.massFracSlice  = np.arange(self.numSpecies)
		#self.molWeightNu 		= self.molWeights * self.nu 
		#self.mwInvDiffs 		= (1.0 / self.molWeights[:-1]) - (1.0 / self.molWeights[-1]) 
		#self.CpDiffs 			= self.Cp[:-1] - self.Cp[-1]
		#self.enthRefDiffs 		= self.enthRef[:-1] - self.enthRef[-1]

	def padMassFrac(self,nm1MassFrac):
		nMassFrac = np.concatenate((nm1MassFrac, (1 - np.sum(nm1MassFrac, axis = 0, keepdims = True))), axis = 0)
		return nMassFrac


	def calcMixGasConstant(self, massFrac):
		gasArray=ct.SolutionArray(self.gas,massFrac.shape[1])
		gasArray.TPY=gasArray.T,gasArray.P, self.padMassFrac(massFrac).transpose()
		return RUniv/gasArray.mean_molecular_weight


	def calcMixGamma(self, RMix, CpMix):
		"""
		Compute mixture ratio of specific heats
		"""
		gammaMix = CpMix / (CpMix - RMix)
		return gammaMix


	def calcEnthalpy(self,density,vel,temp,pressure,Y,enthRefMix,CpMix):
		gasArray=ct.SolutionArray(self.gas,Y.shape[1])
		gasArray.TPY=temp,pressure,self.padMassFrac(Y).transpose()
		return density * (gasArray.enthalpy_mass + np.power(vel,2.)/2)- pressure
		

	# compute mixture specific heat at constant pressure
	def calcMixCp(self, massFrac):
		gasArray=ct.SolutionArray(self.gas,massFrac.shape[1])
		gasArray.TPY=gasArray.T,gasArray.P, self.padMassFrac(massFrac).transpose()
		return gasArray.cp_mass

	# compute density from ideal gas law  
	def calcDensity(self, solPrim, RMix=None):
		# need to calculate mixture gas constant
		if (RMix is None):
			RMix = self.calcMixGasConstant(solPrim[3:,:])

		# calculate directly from ideal gas
		return  solPrim[0,:] / (RMix * solPrim[2,:])
		

	# compute individual enthalpies for each species
	def calcSpeciesEnthalpies(self, temperature):
		assert(False)
		return

	# calculate Denisty from Primitive state
	def calcDensityFromPrim(self,solPrim,solCons):
		assert(False)
		return 
	# calculate Momentum from Primitive state
	def calcMomentumFromPrim(self,solPrim,solCons):
		assert(False)
		return 
	# calculate Enthalpy from Primitive state
	def calcEnthalpyFromPrim(self,solPrim,solCons):
		assert(False)
		return 
	# calculate rhoY from Primitive state
	def calcDensityYFromPrim(self,solPrim,solCons):
		assert(False)
		return 


	def calcStagnationEnthalpy(self, solPrim, speciesEnth=None):
		"""
		Compute stagnation enthalpy from velocity and species enthalpies
		"""
		gasArray=ct.SolutionArray(self.gas,solPrim.shape[1])
		gasArray.TPY=solPrim[2,:].transpose(),solPrim[0,:].transpose(),self.padMassFrac(solPrim[3:,:]).transpose()
		

		stagEnth = gasArray.enthalpy_mass + 0.5 * np.square(solPrim[1,:])

		return stagEnth



	def calcDensityDerivatives(self, density, 
								wrtPress=False, pressure=None,
								wrtTemp=False, temperature=None,
								wrtSpec=False, mixMolWeight=None, massFracs=None):

		"""
		Compute derivatives of density with respect to pressure, temperature, or species mass fraction
		For species derivatives, returns numSpecies derivatives
		"""

		assert any([wrtPress, wrtTemp, wrtSpec]), "Must compute at least one density derivative..."

		derivs = tuple()
		if (wrtPress):
			assert (pressure is not None), "Must provide pressure for pressure derivative..."
			DDensDPress = density / pressure
			derivs = derivs + (DDensDPress,)

		if (wrtTemp):
			assert (temperature is not None), "Must provide temperature for temperature derivative..."
			DDensDTemp = -density / temperature
			derivs = derivs + (DDensDTemp,)

		if (wrtSpec):
			# calculate mixture molecular weight
			if (mixMolWeight is None):
				assert (massFracs is not None), "Must provide mass fractions to calculate mixture mol weight..."
				mixMolWeight = self.calcMixMolWeight(massFracs)

			DDensDSpec = np.zeros((self.numSpecies, density.shape[0]), dtype=realType)
			for specNum in range(self.numSpecies):
				DDensDSpec[specNum, :] = density * mixMolWeight * (1.0 / self.molWeights[-1] - 1.0 / self.molWeights[specNum])
			derivs = derivs + (DDensDSpec,)

		return derivs


	def calcStagEnthalpyDerivatives(self, wrtPress=False,
									wrtTemp=False, massFracs=None,
									wrtVel=False, velocity=None,
									wrtSpec=False, speciesEnth=None, temperature=None):

		"""
		Compute derivatives of stagnation enthalpy with respect to pressure, temperature, velocity, or species mass fraction
		For species derivatives, returns numSpecies derivatives
		"""

		assert any([wrtPress, wrtTemp, wrtVel, wrtSpec]), "Must compute at least one density derivative..."

		derivs = tuple()
		if (wrtPress):
			DStagEnthDPress = 0.0
			derivs = derivs + (DStagEnthDPress,)
		
		if (wrtTemp):
			assert (massFracs is not None), "Must provide mass fractions for temperature derivative..."

			massFracs = self.getMassFracArray(massFracs=massFracs)
			DStagEnthDTemp = self.calcMixCp(massFracs)
			derivs = derivs + (DStagEnthDTemp,)

		if (wrtVel):
			assert (velocity is not None), "Must provide velocity for velocity derivative..."
			DStagEnthDVel = velocity.copy()
			derivs = derivs + (DStagEnthDVel,)

		if (wrtSpec):
			if (speciesEnth is None):
				assert (temperature is not None), "Must provide temperature if not providing species enthalpies..."
				speciesEnth = self.calcSpeciesEnthalpies(temperature)
			
			DStagEnthDSpec = np.zeros((self.numSpecies, speciesEnth.shape[1]), dtype=realType)
			if (self.numSpeciesFull == 1):
				DStagEnthDSpec[0,:] = speciesEnth[0,:]
			else:
				for specNum in range(self.numSpecies):
					DStagEnthDSpec[specNum,:] = speciesEnth[specNum,:] - speciesEnth[-1,:]

			derivs = derivs + (DStagEnthDSpec,)

		return derivs


	def calcSoundSpeed(self, temperature, RMix=None, gammaMix=None, massFracs=None, CpMix=None):
		"""
		Compute sound speed
		"""

		# calculate mixture gas constant if not provided
		massFracsSet = False
		if (RMix is None):
			assert (massFracs is not None), "Must provide mass fractions to calculate mixture gas constant..."
			massFracs = self.getMassFracArray(massFracs=massFracs)
			massFracsSet = True
			RMix = self.calcMixGasConstant(massFracs)
		else:
			RMix = np.squeeze(RMix)
			
		# calculate ratio of specific heats if not provided
		if (gammaMix is None):
			if (CpMix is None):
				assert (massFracs is not None), "Must provide mass fractions to calculate mixture Cp..."
				if (not massFracsSet): 
					massFracs = self.getMassFracArray(massFracs=massFracs)
				CpMix = self.calcMixCp(massFracs)
			else:
				CpMix = np.squeeze(CpMix)

			gammaMix = self.calcMixGamma(RMix, CpMix)
		else:
			gammaMix = np.squeeze(gammaMix)

		soundSpeed = np.sqrt(gammaMix * RMix * temperature)

		return soundSpeed