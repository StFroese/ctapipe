"""
Test individual tool functionality
"""
import subprocess
import sys

import matplotlib as mpl
import numpy as np

# pylint: disable=C0103,C0116,C0415
import pytest
import tables

from ctapipe.core import run_tool
from ctapipe.core.tool import ToolConfigurationError
from ctapipe.utils import get_dataset_path

GAMMA_TEST_LARGE = get_dataset_path("gamma_test_large.simtel.gz")
LST_MUONS = get_dataset_path("lst_muons.simtel.zst")
PROD5B_PATH = get_dataset_path(
    "gamma_20deg_0deg_run2___cta-prod5-paranal_desert-2147m-Paranal-dark_cone10-100evts.simtel.zst"
)


def test_muon_reconstruction_simtel(tmp_path):
    from ctapipe.tools.muon_reconstruction import MuonAnalysis

    muon_simtel_output_file = tmp_path / "muon_reco_on_simtel.h5"
    assert (
        run_tool(
            MuonAnalysis(),
            argv=[
                f"--input={LST_MUONS}",
                f"--output={muon_simtel_output_file}",
                "--SimTelEventSource.focal_length_choice=EQUIVALENT",
                "--overwrite",
            ],
            cwd=tmp_path,
        )
        == 0
    )

    with tables.open_file(muon_simtel_output_file) as t:
        table = t.root.dl1.event.telescope.parameters.muons[:]
        assert len(table) > 20
        assert np.count_nonzero(np.isnan(table["muonring_radius"])) == 0


def test_muon_reconstruction_dl1(tmp_path, dl1_muon_file):
    from ctapipe.tools.muon_reconstruction import MuonAnalysis

    muon_dl1_output_file = tmp_path / "muon_reco_on_dl1a.h5"
    assert (
        run_tool(
            MuonAnalysis(),
            argv=[
                f"--input={dl1_muon_file}",
                f"--output={muon_dl1_output_file}",
                "--HDF5EventSource.focal_length_choice=EQUIVALENT",
                "--overwrite",
            ],
            cwd=tmp_path,
        )
        == 0
    )

    with tables.open_file(muon_dl1_output_file) as t:
        table = t.root.dl1.event.telescope.parameters.muons[:]
        assert len(table) > 20
        assert np.count_nonzero(np.isnan(table["muonring_radius"])) == 0

    assert run_tool(MuonAnalysis(), ["--help-all"]) == 0


def test_display_dl1(tmp_path, dl1_image_file, dl1_parameters_file):
    from ctapipe.tools.display_dl1 import DisplayDL1Calib

    mpl.use("Agg")

    # test simtel
    run_tool(
        DisplayDL1Calib(),
        argv=[
            "--max-events=1",
            "--telescope=11",
            "--SimTelEventSource.focal_length_choice=EQUIVALENT",
        ],
        cwd=tmp_path,
        raises=True,
    )
    # test DL1A
    run_tool(
        DisplayDL1Calib(),
        argv=[f"--input={dl1_image_file}", "--max-events=1", "--telescope=11"],
        raises=True,
    )

    # test DL1B, should error since nothing to plot
    with pytest.raises(ToolConfigurationError):
        run_tool(
            DisplayDL1Calib(),
            argv=[f"--input={dl1_parameters_file}", "--max-events=1", "--telescope=11"],
            raises=True,
        )

    run_tool(DisplayDL1Calib(), ["--help-all"], raises=True)


def test_info():
    from ctapipe.tools.info import info

    info(show_all=True)


def test_fileinfo(tmp_path, dl1_image_file):
    """check we can run ctapipe-fileinfo and get results"""
    import yaml
    from astropy.table import Table

    index_file = tmp_path / "index.fits"
    command = f"ctapipe-fileinfo {dl1_image_file} --output-table {index_file}"
    output = subprocess.run(command.split(" "), capture_output=True, encoding="utf-8")
    assert output.returncode == 0, output.stderr
    header = yaml.safe_load(output.stdout)
    assert "ID" in header[str(dl1_image_file)]["CTA"]["ACTIVITY"]

    tab = Table.read(index_file)
    assert len(tab["CTA PRODUCT CREATION TIME"]) > 0

    command = f"ctapipe-fileinfo {dl1_image_file} --flat"
    output = subprocess.run(command.split(" "), capture_output=True, encoding="utf-8")
    assert output.returncode == 0, output.stderr
    header = yaml.safe_load(output.stdout)
    assert "CTA ACTIVITY ID" in header[str(dl1_image_file)]


def test_dump_triggers(tmp_path):
    from ctapipe.tools.dump_triggers import DumpTriggersTool

    sys.argv = ["dump_triggers"]
    outfile = tmp_path / "triggers.fits"
    tool = DumpTriggersTool(infile=PROD5B_PATH, outfile=str(outfile))

    assert run_tool(tool, cwd=tmp_path) == 0

    assert outfile.exists()
    assert run_tool(tool, ["--help-all"]) == 0


def test_dump_instrument(tmp_path):
    from ctapipe.tools.dump_instrument import DumpInstrumentTool

    sys.argv = ["dump_instrument"]

    ret = run_tool(
        DumpInstrumentTool(),
        [f"--input={PROD5B_PATH}"],
        cwd=tmp_path,
        raises=True,
    )
    assert ret == 0
    assert (tmp_path / "FlashCam.camgeom.fits.gz").exists()

    ret = run_tool(
        DumpInstrumentTool(),
        [f"--input={PROD5B_PATH}", "--format=ecsv"],
        cwd=tmp_path,
        raises=True,
    )
    assert ret == 0
    assert (tmp_path / "MonteCarloArray.optics.ecsv").exists()

    ret = run_tool(
        DumpInstrumentTool(),
        [f"--input={PROD5B_PATH}", "--format=hdf5"],
        cwd=tmp_path,
        raises=True,
    )
    assert ret == 0
    assert (tmp_path / "subarray.h5").exists()

    ret = run_tool(DumpInstrumentTool(), ["--help-all"], cwd=tmp_path, raises=True)
    assert ret == 0

    # test the tool uses options correctly
    out = tmp_path / "foo"
    out.mkdir()
    ret = run_tool(
        DumpInstrumentTool(),
        [
            f"--input={GAMMA_TEST_LARGE}",
            "-o",
            str(out),
            "--SimTelEventSource.focal_length_choice=EQUIVALENT",
        ],
        cwd=tmp_path,
        raises=True,
    )
    assert ret == 0
    assert (out / "FlashCam.camgeom.fits.gz").exists()
