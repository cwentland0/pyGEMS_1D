# linear models
from perform.rom.projection_rom.linear_proj_rom.linear_galerkin_proj import LinearGalerkinProj
from perform.rom.projection_rom.linear_proj_rom.linear_lspg_proj import LinearLSPGProj
from perform.rom.projection_rom.linear_proj_rom.linear_splsvt_proj import LinearSPLSVTProj

# TensorFlow-Keras autoencoder models
TFKERAS_IMPORT_SUCCESS = True
try:
	import os
	os.environ['TF_CPP_MIN_LOG_LEVEL'] = "2"  # don't print all the TensorFlow warnings
	from perform.rom.projection_rom.autoencoder_proj_rom.autoencoder_tfkeras.autoencoder_galerkin_proj_tfkeras import AutoencoderGalerkinProjTFKeras
	from perform.rom.projection_rom.autoencoder_proj_rom.autoencoder_tfkeras.autoencoder_lspg_proj_tfkeras import AutoencoderLSPGProjTFKeras
	from perform.rom.projection_rom.autoencoder_proj_rom.autoencoder_tfkeras.autoencoder_splsvt_proj_tfkeras import AutoencoderSPLSVTProjTFKeras

except ImportError:
	TFKERAS_IMPORT_SUCCESS = False


def get_rom_model(model_idx, rom_domain, solver, sol_domain):
	"""
	Helper function to retrieve various models
	Helps keep the clutter our of rom_domain
	"""

	# linear subspace methods
	if rom_domain.rom_method == "linear_galerkin_proj":
		model = LinearGalerkinProj(model_idx, rom_domain, solver, sol_domain)

	elif rom_domain.rom_method == "linear_lspg_proj":
		model = LinearLSPGProj(model_idx, rom_domain, solver, sol_domain)

	elif rom_domain.rom_method == "linear_splsvt_proj":
		model = LinearSPLSVTProj(model_idx, rom_domain, solver, sol_domain)

	# TensorFlow-Keras autoencoder models
	elif rom_domain.rom_method[-7:] == "tfkeras":
		if TFKERAS_IMPORT_SUCCESS:

			if rom_domain.rom_method == "autoencoder_galerkin_proj_tfkeras":
				model = AutoencoderGalerkinProjTFKeras(model_idx, rom_domain,
														solver, sol_domain)

			elif rom_domain.rom_method == "autoencoder_lspg_proj_tfkeras":
				model = AutoencoderLSPGProjTFKeras(model_idx, rom_domain,
													solver, sol_domain)

			elif rom_domain.rom_method == "autoencoder_splsvt_proj_tfkeras":
				model = AutoencoderSPLSVTProjTFKeras(model_idx, rom_domain,
													solver, sol_domain)

			else:
				raise ValueError("Invalid TF-Keras ROM method name: "
								+ rom_domain.rom_method)

		else:
			raise ValueError("TF-Keras models failed to import,"
							+ " please check that TensorFlow >= 2.0 is installed")

	# TODO: PyTorch autoencoder models

	else:
		raise ValueError("Invalid ROM method name: " + rom_domain.rom_method)

	return model
