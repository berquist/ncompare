"""Compare the structure of two NetCDF files."""
import random
import traceback
from pathlib import Path
from typing import Union

import colorama
import netCDF4
import numpy as np
import xarray as xr
from colorama import Fore, Style

from ncompare.printing import lists_diff, print_normal, side_by_side
from ncompare.sequence_operations import common_elements
from ncompare.utils import make_valid_path


def compare(nc_a: str,
            nc_b: str,
            comparison_var_group: str = None,
            comparison_var_name: str = None,
            no_color: bool = False,
            show_chunks: bool = False
            ) -> None:
    """Compare the variables contained within two different NetCDF datasets.

    Parameters
    ----------
    nc_a : str
        filepath to NetCDF4
    nc_b : str
        filepath to NetCDF4
    comparison_var_group : str, optional
        The name of a group which contains a desired comparison variable
    comparison_var_name : str, optional
        The name of a variable for which we want to compare values
    no_color : bool, default False
    show_chunks : bool, default False

    Returns
    -------
    int
        Exit code: 0 for a no-issue exit, anything greater than 0 for a problematic exit.
    """
    nc_a = make_valid_path(nc_a)
    nc_b = make_valid_path(nc_b)

    print(f"File A: {nc_a}")
    print(f"File B: {nc_b}")

    if no_color:
        for k, v in Fore.__dict__.items():
            Fore.__dict__[k] = ""
        for k, v in Style.__dict__.items():
            Style.__dict__[k] = ""
    else:
        colorama.init(autoreset=True)

    run_through_comparisons(nc_a, nc_b, comparison_var_group, comparison_var_name, show_chunks)

    print_normal("\nDone.")

def run_through_comparisons(nc_a: Union[str, Path],
                            nc_b: Union[str, Path],
                            comparison_var_group,
                            comparison_var_name,
                            show_chunks) -> None:
    """Execute a series of comparisons between two NetCDF files.

    Parameters
    ----------
    nc_a
    nc_b
    comparison_var_group
    comparison_var_name
    show_chunks
    """
    # Show the dimensions of each file and evaluate differences.
    print(Fore.LIGHTBLUE_EX + "\nRoot-level Dimensions:")
    list_a = _get_dims(nc_a, print_list=False)
    list_b = _get_dims(nc_b, print_list=False)
    left, right, both = lists_diff(list_a, list_b)

    # Show the groups in each NetCDF file and evaluate differences.
    print(Fore.LIGHTBLUE_EX + "\nGroups:")
    list_a = _get_groups(nc_a, print_list=False)
    list_b = _get_groups(nc_b, print_list=False)
    left, right, both = lists_diff(list_a, list_b)

    if comparison_var_group:

        # Show the variables within the selected group.
        print(Fore.LIGHTBLUE_EX + "\nVariables within specified group <%s>:" % comparison_var_group)
        vlist_a = _print_vars(nc_a, comparison_var_group)
        vlist_b = _print_vars(nc_b, comparison_var_group)
        left, right, both = lists_diff(vlist_a, vlist_b)

        if comparison_var_name:
            try:
                # Print the first part of the values array for the selected variable.
                print(Fore.LIGHTBLUE_EX + "\nSample values within specified variable <%s>:" % comparison_var_name)
                _print_sample_values(nc_a, comparison_var_group, comparison_var_name)
                _print_sample_values(nc_b, comparison_var_group, comparison_var_name)
                # compare_sample_values(nc_a, nc_b, groupname=comparison_var_group, varname=comparison_var_name)

                print(Fore.LIGHTBLUE_EX + "\nChecking multiple random values within specified variable <%s>:"
                      % comparison_var_name)
                compare_multiple_random_values(nc_a, nc_b, groupname=comparison_var_group, varname=comparison_var_name)

            except KeyError:
                print(Style.BRIGHT + Fore.RED + "\nError when comparing values for variable <%s> in group <%s>." %
                      (comparison_var_name, comparison_var_group))
                print(traceback.format_exc())
                print("\n")
        else:
            print(Fore.LIGHTBLACK_EX + "\nNo variable selected for comparison. Skipping..")
    else:
        print(Fore.LIGHTBLACK_EX + "\nNo variable group selected for comparison. Skipping..")

    print(Fore.LIGHTBLUE_EX + "\nAll variables:")
    compare_two_nc_files(nc_a, nc_b, show_chunks=show_chunks)

def compare_multiple_random_values(nc_a: Path, nc_b: Path, groupname: str, varname: str, num_comparisons: int = 100):
    """Iterate through N random samples, and evaluate whether the differences exceed a threshold."""
    # Open a variable from each NetCDF
    nc_var_a = xr.open_dataset(nc_a, backend_kwargs={"group": groupname})[varname]
    nc_var_b = xr.open_dataset(nc_b, backend_kwargs={"group": groupname})[varname]

    num_mismatches = 0
    for i in range(num_comparisons):
        match_result = _match_random_value(nc_var_a, nc_var_b)
        if match_result is True:
            print_normal(".", end="")
        elif match_result is None:
            print_normal("n", end="")
        else:
            print_normal("x", end="")
            num_mismatches += 1

    if num_mismatches > 0:
        print(Fore.RED + f" {num_mismatches} mismatches, out of {num_comparisons} samples.")
    else:
        print(Fore.CYAN + " No mismatches.")
    print_normal("Done.")

def compare_two_nc_files(nc_one: Path, nc_two: Path,
                         show_chunks: bool = False
                         ) -> None:
    """Go through all groups and all variables, and show them side by side - whether they align and where they don't."""
    side_by_side(' ', 'File A', 'File B')
    with netCDF4.Dataset(nc_one) as nc_a, netCDF4.Dataset(nc_two) as nc_b:

        side_by_side('-', '-', '-', dash_line=True)
        side_by_side('num variables in root group:', len(nc_a.variables), len(nc_b.variables))
        for v_idx, v_a, v_b in common_elements(nc_a.variables, nc_b.variables):
            _print_var_properties_side_by_side(v_a, v_b, nc_a, nc_b, show_chunks=show_chunks)

        for g_idx, g_a, g_b in common_elements(nc_a.groups, nc_b.groups):
            side_by_side(f"group #{g_idx:02}", g_a.strip(), g_b.strip(), dash_line=True, highlight_diff=False)

            vars_a_sorted = ""
            vars_b_sorted = ""
            if g_a:
                vars_a_sorted = sorted(nc_a.groups[g_a].variables)
            if g_b:
                vars_b_sorted = sorted(nc_b.groups[g_b].variables)
            side_by_side('num variables in groups:', len(vars_a_sorted), len(vars_b_sorted))

            for v_idx, v_a, v_b in common_elements(vars_a_sorted, vars_b_sorted):
                _print_var_properties_side_by_side(v_a, v_b, nc_a, nc_b, g_a=g_a, g_b=g_b, show_chunks=show_chunks)

def _print_var_properties_side_by_side(v_a, v_b, nc_a, nc_b,
                                       g_a=None,
                                       g_b=None,
                                       show_chunks=False):
    # Variable name
    side_by_side("var:", v_a[:47], v_b[:47], highlight_diff=False)

    # Get the properties of each variable
    variable_a, v_a_dtype, v_a_shape, v_a_chunking = _var_properties(nc_a, v_a, g_a)
    variable_b, v_b_dtype, v_b_shape, v_b_chunking = _var_properties(nc_b, v_b, g_b)

    # Data type
    side_by_side("dtype:", v_a_dtype, v_b_dtype, highlight_diff=False)
    # Shape
    side_by_side("shape:", v_a_shape, v_b_shape, highlight_diff=False)
    # Chunking
    if show_chunks:
        side_by_side("chunksize:", v_a_chunking, v_b_chunking, highlight_diff=False)

    # Scale Factor
    if getattr(variable_a, 'scale_factor', None):
        sf_a = variable_a.scale_factor
    else:
        sf_a = ' '
    if getattr(variable_b, 'scale_factor', None):
        sf_b = variable_b.scale_factor
    else:
        sf_b = ' '
    side_by_side("sf:", str(sf_a), str(sf_b), highlight_diff=True)

def _var_properties(ds: netCDF4.Dataset, varname: str, groupname: str = None) -> tuple:
    """Get the properties of a variable.

    Parameters
    ----------
    ds
    varname
    groupname : optional
        if None, the variable is retrieved from the 'root' group of the NetCDF

    Returns
    -------
    netCDF4.Variable
    str
        dtype of variable values
    tuple
        shape of variable
    tuple
        chunking
    """
    if varname:
        if groupname:
            the_variable = ds.groups[groupname].variables[varname]
        else:
            the_variable = ds.variables[varname]
        v_dtype = str(the_variable.dtype)
        v_shape = str(the_variable.shape).strip()
        v_chunking = str(the_variable.chunking()).strip()
    else:
        the_variable = None
        v_dtype = ""
        v_shape = ""
        v_chunking = ""

    return the_variable, v_dtype, v_shape, v_chunking

def _match_random_value(nc_var_a: netCDF4.Variable,
                        nc_var_b: netCDF4.Variable,
                        thresh: float = 1e-6
                        ) -> Union[bool, None]:
    # Get a random indexer
    rand_index = []
    for d in nc_var_a.shape:
        rand_index.append(random.randint(0, d - 1))
    rand_index = tuple(rand_index)

    # Get the values from each variable
    v1 = nc_var_a.values[rand_index]
    v2 = nc_var_b.values[rand_index]

    # Evaluate the values
    if np.isnan(v1) or np.isnan(v2):
        return None
    else:
        diff = v2 - v1
        if abs(diff) > thresh:
            print()
            print(Fore.RED + f"Difference exceeded threshold (diff == {diff}")
            print_normal(f"var shape: {nc_var_a.shape}")
            print_normal(f"indices:   {rand_index}")
            print_normal(f"value a: {v1}")
            print_normal(f"value b: {v2}", end="\n\n")
            return False
        else:
            return True

def _print_sample_values(nc_filepath, groupname: str, varname: str) -> None:
    comparison_variable = xr.open_dataset(nc_filepath, backend_kwargs={"group": groupname})[varname]
    print_normal(comparison_variable.values[0, :])

def _print_vars(nc_filepath: Path, groupname: str) -> list:
    try:
        grp = xr.open_dataset(nc_filepath, backend_kwargs={"group": groupname})
    except OSError as err:
        print_normal("\nError occurred when attempting to open group within <%s>.\n" % nc_filepath)
        raise err
    grp_varlist = sorted(list(grp.variables.keys()))
    print_normal(grp_varlist)
    return grp_varlist

def _get_groups(nc_filepath: Path,
                print_list: bool = True
                ) -> list:
    with netCDF4.Dataset(nc_filepath) as ds:
        groups_list = list(ds.groups.keys())
    if print_list:
        print_normal(sorted(groups_list))
    return groups_list

def _get_dims(nc_filepath: Path,
              print_list: bool = True
              ) -> list:
    with xr.open_dataset(nc_filepath) as ds:
        dims_list = list(ds.dims.items())

    if print_list:
        print_normal(str(sorted(dims_list, key=lambda x: x[0])))
    return dims_list
