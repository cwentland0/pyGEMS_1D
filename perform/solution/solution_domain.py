import os

import numpy as np
from scipy.sparse.linalg import spsolve
from scipy.linalg import solve

from perform.constants import REAL_TYPE
from perform.input_funcs import get_initial_conditions, catch_list, \
	catch_input, read_input_file
from perform.solution.solution_phys import SolutionPhys
from perform.solution.solution_interior import SolutionInterior
from perform.solution.solution_boundary.solution_inlet import SolutionInlet
from perform.solution.solution_boundary.solution_outlet import SolutionOutlet
from perform.space_schemes import calc_rhs
from perform.jacobians import calc_d_res_d_sol_prim
from perform.time_integrator import get_time_integrator
# gas models
# TODO: make an __init__.py with getGasModel()
from perform.gas_model.calorically_perfect_gas import CaloricallyPerfectGas


class SolutionDomain:
	"""
	Container class for interior and boundary physical solutions
	"""

	def __init__(self, solver):

		param_dict = solver.param_dict

		# time integrator
		self.time_integrator = get_time_integrator(solver.time_scheme, param_dict)

		# gas model
		gas_file = str(param_dict["gas_file"])
		gas_dict = read_input_file(gas_file)
		gas_type = catch_input(gas_dict, "gas_type", "cpg")
		if gas_type == "cpg":
			self.gas_model = CaloricallyPerfectGas(gas_dict)
		else:
			raise ValueError("Ivalid choice of gas_type: " + gas_type)
		gas = self.gas_model

		# solution
		sol_prim_init = get_initial_conditions(self, solver)
		self.sol_int = SolutionInterior(gas, sol_prim_init,
										solver, self.time_integrator)
		self.sol_inlet = SolutionInlet(gas, solver)
		self.sol_outlet = SolutionOutlet(gas, solver)

		# average solution for Roe scheme
		if solver.space_scheme == "roe":
			ones_prof = np.ones((self.gas_model.num_eqs, self.sol_int.num_cells + 1),
								dtype=REAL_TYPE)
			self.sol_ave = SolutionPhys(gas, self.sol_int.num_cells + 1,
										sol_prim_in=ones_prof)

		# for flux calculations
		ones_prof = np.ones((self.gas_model.num_eqs, self.sol_int.num_cells + 1),
							dtype=REAL_TYPE)
		self.sol_left = SolutionPhys(gas, self.sol_int.num_cells + 1,
										sol_prim_in=ones_prof)
		self.sol_right = SolutionPhys(gas, self.sol_int.num_cells + 1,
										sol_prim_in=ones_prof)

		# to avoid repeated concatenation of ghost cell states
		self.sol_prim_full = \
			np.zeros((self.gas_model.num_eqs,
					self.sol_inlet.num_cells + self.sol_int.num_cells + self.sol_outlet.num_cells),
					dtype=REAL_TYPE)
		self.sol_cons_full = np.zeros(self.sol_prim_full.shape, dtype=REAL_TYPE)

		# probe storage (as this can include boundaries as well)
		self.probe_locs = catch_list(param_dict, "probe_locs", [None])
		self.probe_vars = catch_list(param_dict, "probe_vars", [None])
		if (self.probe_locs[0] is not None) and (self.probe_vars[0] is not None):
			self.num_probes = len(self.probe_locs)
			self.num_probe_vars = len(self.probe_vars)
			self.probe_vals = np.zeros((self.num_probes, self.num_probe_vars,
										solver.num_steps), dtype=REAL_TYPE)

			# get probe locations
			self.probe_idxs = [None] * self.num_probes
			self.probe_secs = [None] * self.num_probes
			for idx, probe_loc in enumerate(self.probe_locs):
				if probe_loc > solver.mesh.x_right:
					self.probe_secs[idx] = "outlet"
				elif (probe_loc < solver.mesh.x_left):
					self.probe_secs[idx] = "inlet"
				else:
					self.probe_secs[idx] = "interior"
					self.probe_idxs[idx] = np.abs(solver.mesh.x_cell - probe_loc).argmin()

			assert (not ((("outlet" in self.probe_secs) or ("inlet" in self.probe_secs))
						and (("source" in self.probe_vars) or ("rhs" in self.probe_vars)))), \
						"Cannot probe source or rhs in inlet/outlet"

		else:
			self.num_probes = 0

		# copy this for use with plotting functions
		solver.num_probes = self.num_probes
		solver.probe_vars = self.probe_vars

		# TODO: include initial conditions in probe_vals, time_vals
		self.time_vals = \
			np.linspace(solver.dt * (solver.time_iter),
				solver.dt * (solver.time_iter - 1 + solver.num_steps),
				solver.num_steps, dtype=REAL_TYPE)

		# for compatability with hyper-reduction
		# are overwritten if actually using hyper-reduction
		self.num_samp_cells = solver.mesh.num_cells
		self.num_flux_faces = solver.mesh.num_cells + 1
		self.num_grad_cells = solver.mesh.num_cells
		self.direct_samp_idxs = np.arange(0, solver.mesh.num_cells)
		self.flux_samp_left_idxs = np.arange(0, solver.mesh.num_cells + 1)
		self.flux_samp_right_idxs = np.arange(1, solver.mesh.num_cells + 2)
		self.grad_idxs = np.arange(1, solver.mesh.num_cells + 1)
		self.grad_neigh_idxs = np.arange(0, solver.mesh.num_cells + 2)
		self.grad_neigh_extract = np.arange(1, solver.mesh.num_cells + 1)
		self.flux_left_extract = np.arange(1, solver.mesh.num_cells + 1)
		self.flux_right_extract = np.arange(0, solver.mesh.num_cells)
		self.grad_left_extract = np.arange(0, solver.mesh.num_cells)
		self.grad_right_extract = np.arange(0, solver.mesh.num_cells)
		self.flux_rhs_idxs = np.arange(0, solver.mesh.num_cells)

	def fill_sol_full(self):
		"""
		Fill sol_prim_full and sol_cons_full from interior and ghost cells
		"""

		sol_int = self.sol_int
		sol_inlet = self.sol_inlet
		sol_outlet = self.sol_outlet

		idx_in = sol_inlet.num_cells
		idx_int = idx_in + sol_int.num_cells

		# sol_prim_full
		self.sol_prim_full[:, :idx_in] = sol_inlet.sol_prim.copy()
		self.sol_prim_full[:, idx_in:idx_int] = sol_int.sol_prim.copy()
		self.sol_prim_full[:, idx_int:] = sol_outlet.sol_prim.copy()

		# sol_cons_full
		self.sol_cons_full[:, :idx_in] = sol_inlet.sol_cons.copy()
		self.sol_cons_full[:, idx_in:idx_int] = sol_int.sol_cons.copy()
		self.sol_cons_full[:, idx_int:] = sol_outlet.sol_cons.copy()

	def advance_iter(self, solver):
		"""
		Advance physical solution forward one time iteration
		"""

		if not solver.run_steady:
			print("Iteration " + str(solver.iter))

		for self.time_integrator.subiter in range(self.time_integrator.subiter_max):

			self.advance_subiter(solver)

			# iterative solver convergence
			if self.time_integrator.time_type == "implicit":
				self.sol_int.calc_res_norms(solver, self.time_integrator.subiter)
				if self.sol_int.res_norm_l2 < self.time_integrator.res_tol:
					break

		# "steady" convergence
		if solver.run_steady:
			self.sol_int.calc_d_sol_norms(solver, self.time_integrator.time_type)

		self.sol_int.update_sol_hist()

	def advance_subiter(self, solver):
		"""
		Advance physical solution forward one subiteration of time integrator
		"""

		calc_rhs(self, solver)

		sol_int = self.sol_int
		gas_model = self.gas_model
		mesh = solver.mesh

		if self.time_integrator.time_type == "implicit":

			res = self.time_integrator.calc_residual(sol_int.sol_hist_cons,
													sol_int.rhs, solver)
			res_jacob = calc_d_res_d_sol_prim(self, solver)

			d_sol = spsolve(res_jacob, res.ravel('C'))

			# if solving in dual time, solving for primitive state
			if self.time_integrator.dual_time:
				sol_int.sol_prim += d_sol.reshape((gas_model.num_eqs, mesh.num_cells),
													order='C')
			else:
				sol_int.sol_cons += d_sol.reshape((gas_model.num_eqs, mesh.num_cells),
													order='C')

			sol_int.update_state(from_cons=(not self.time_integrator.dual_time))
			sol_int.sol_hist_cons[0] = sol_int.sol_cons.copy()
			sol_int.sol_hist_prim[0] = sol_int.sol_prim.copy()

			# use sol_int.res to store linear solve residual
			res = res_jacob @ d_sol - res.ravel('C')
			sol_int.res = \
				np.reshape(res, (gas_model.num_eqs, mesh.num_cells), order='C')

		else:

			d_sol = self.time_integrator.solve_sol_change(sol_int.rhs)
			sol_int.sol_cons = sol_int.sol_hist_cons[0] + d_sol
			sol_int.update_state(from_cons=True)

	def calc_boundary_cells(self, solver):
		"""
		Helper function to update boundary ghost cells
		"""

		self.sol_inlet.calc_boundary_state(solver,
											sol_prim=self.sol_int.sol_prim,
											sol_cons=self.sol_int.sol_cons)
		self.sol_outlet.calc_boundary_state(solver,
											sol_prim=self.sol_int.sol_prim,
											sol_cons=self.sol_int.sol_cons)

	def write_iter_outputs(self, solver):
		"""
		Helper function to save restart files and update probe/snapshot data
		"""

		# write restart files
		if solver.save_restarts and (solver.iter % solver.restart_interval) == 0:
			self.sol_int.write_restart_file(solver)

		# update probe data
		if self.num_probes > 0:
			self.update_probes(solver)

		# update snapshot data (not written if running steady)
		if not solver.run_steady:
			if (solver.iter % solver.out_interval) == 0:
				self.sol_int.update_snapshots(solver)

	def write_steady_outputs(self, solver):
		"""
		Helper function for write "steady" outputs and check "convergence" criterion
		"""

		# update convergence and field data file on disk
		if (solver.iter % solver.out_interval) == 0:
			self.sol_int.write_steady_data(solver)

		# check for "convergence"
		break_flag = False
		if self.sol_int.d_sol_norm_l2 < solver.steady_tol:
			print("Steady solution criterion met, terminating run")
			break_flag = True

		return break_flag

	def write_final_outputs(self, solver):
		"""
		Helper function to write final field and probe data to disk
		"""

		if solver.solve_failed:
			solver.sim_type += "_FAILED"

		if not solver.run_steady:
			self.sol_int.write_snapshots(solver, solver.solve_failed)

		if self.num_probes > 0:
			self.write_probes(solver)

	def update_probes(self, solver):
		"""
		Update probe storage
		"""

		# TODO: throw error for source probe in ghost cells

		for probe_iter, probe_idx in enumerate(self.probe_idxs):

			probe_sec = self.probe_secs[probe_iter]
			if probe_sec == "inlet":
				sol_prim_probe = self.sol_inlet.sol_prim[:, 0]
				sol_cons_probe = self.sol_inlet.sol_cons[:, 0]
			elif probe_sec == "outlet":
				sol_prim_probe = self.sol_outlet.sol_prim[:, 0]
				sol_cons_probe = self.sol_outlet.sol_cons[:, 0]
			else:
				sol_prim_probe = self.sol_int.sol_prim[:, probe_idx]
				sol_cons_probe = self.sol_int.sol_cons[:, probe_idx]
				sol_source_probe = self.sol_int.source[:, probe_idx]

			try:
				probe = []
				for var_str in self.probe_vars:
					if var_str == "pressure":
						probe.append(sol_prim_probe[0])
					elif var_str == "velocity":
						probe.append(sol_prim_probe[1])
					elif var_str == "temperature":
						probe.append(sol_prim_probe[2])
					elif var_str == "source":
						probe.append(sol_source_probe[0])
					elif var_str == "density":
						probe.append(sol_cons_probe[0])
					elif var_str == "momentum":
						probe.append(sol_cons_probe[1])
					elif var_str == "energy":
						probe.append(sol_cons_probe[2])
					elif var_str == "species":
						probe.append(sol_prim_probe[3])
					elif var_str[:7] == "species":
						spec_idx = int(var_str[7:])
						probe.append(sol_prim_probe[3 + spec_idx - 1])
					elif var_str[:15] == "density-species":
						spec_idx = int(var_str[15:])
						probe.append(sol_cons_probe[3 + spec_idx - 1])
			except:
				raise ValueError("Invalid probe variable " + str(var_str))

			self.probe_vals[probe_iter, :, solver.iter - 1] = probe

	def write_probes(self, solver):
		"""
		Save probe data to disk
		"""

		probe_file_base_name = "probe"
		for vis_var in self.probe_vars:
			probe_file_base_name += "_" + vis_var

		for probe_num in range(self.num_probes):

			# account for failed simulations
			time_out = self.time_vals[:solver.iter]
			probe_out = self.probe_vals[probe_num, :, :solver.iter]

			probe_file_name = (probe_file_base_name + "_" + str(probe_num + 1)
								+ "_" + solver.sim_type + ".npy")
			probe_file = os.path.join(solver.probe_output_dir, probe_file_name)

			probe_save = np.concatenate((time_out[None, :], probe_out), axis=0)
			np.save(probe_file, probe_save)
