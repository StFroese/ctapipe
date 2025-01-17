import numpy as np

from ctapipe.containers import (
    EventIndexContainer,
    ParticleClassificationContainer,
    ReconstructedEnergyContainer,
)
from ctapipe.core import run_tool
from ctapipe.io import TableLoader, read_table


def test_apply_energy_regressor(
    energy_regressor_path,
    dl2_shower_geometry_file_lapalma,
    tmp_path,
):
    from ctapipe.tools.apply_models import ApplyModels

    input_path = dl2_shower_geometry_file_lapalma
    output_path = tmp_path / "energy.dl2.h5"

    ret = run_tool(
        ApplyModels(),
        argv=[
            f"--input={input_path}",
            f"--output={output_path}",
            f"--energy-regressor={energy_regressor_path}",
            "--StereoMeanCombiner.weights=konrad",
            "--chunk-size=5",  # small chunksize so we test multiple chunks for the test file
        ],
        raises=True,
    )
    assert ret == 0

    prefix = "ExtraTreesRegressor"
    table = read_table(output_path, f"/dl2/event/subarray/energy/{prefix}")
    for col in "obs_id", "event_id":
        assert table[col].description == EventIndexContainer.fields[col].description

    for name, field in ReconstructedEnergyContainer.fields.items():
        colname = f"{prefix}_{name}"
        assert colname in table.colnames
        assert table[colname].description == field.description

    loader = TableLoader(output_path, load_dl2=True)
    events = loader.read_subarray_events()

    assert f"{prefix}_energy" in events.colnames
    assert f"{prefix}_energy_uncert" in events.colnames
    assert f"{prefix}_is_valid" in events.colnames
    assert f"{prefix}_telescopes" in events.colnames
    assert np.any(events[f"{prefix}_is_valid"])
    assert np.all(np.isfinite(events[f"{prefix}_energy"][events[f"{prefix}_is_valid"]]))

    events = loader.read_telescope_events()
    assert f"{prefix}_energy" in events.colnames
    assert f"{prefix}_energy_uncert" in events.colnames
    assert f"{prefix}_is_valid" in events.colnames
    assert f"{prefix}_telescopes" in events.colnames

    assert f"{prefix}_tel_energy" in events.colnames
    assert f"{prefix}_tel_is_valid" in events.colnames

    from ctapipe.io.tests.test_table_loader import check_equal_array_event_order

    trigger = read_table(output_path, "/dl1/event/subarray/trigger")
    energy = read_table(output_path, "/dl2/event/subarray/energy/ExtraTreesRegressor")
    check_equal_array_event_order(trigger, energy)


def test_apply_both(
    energy_regressor_path,
    particle_classifier_path,
    dl2_shower_geometry_file_lapalma,
    tmp_path,
):
    from ctapipe.tools.apply_models import ApplyModels

    input_path = dl2_shower_geometry_file_lapalma
    output_path = tmp_path / "particle-and-energy.dl2.h5"

    ret = run_tool(
        ApplyModels(),
        argv=[
            f"--input={input_path}",
            f"--output={output_path}",
            f"--energy-regressor={energy_regressor_path}",
            f"--particle-classifier={particle_classifier_path}",
            "--StereoMeanCombiner.weights=konrad",
            "--chunk-size=5",  # small chunksize so we test multiple chunks for the test file
        ],
    )
    assert ret == 0

    prefix = "ExtraTreesClassifier"
    table = read_table(output_path, f"/dl2/event/subarray/classification/{prefix}")
    for col in "obs_id", "event_id":
        assert table[col].description == EventIndexContainer.fields[col].description

    for name, field in ParticleClassificationContainer.fields.items():
        colname = f"ExtraTreesClassifier_{name}"
        assert colname in table.colnames
        assert table[colname].description == field.description

    loader = TableLoader(output_path, load_dl2=True)
    events = loader.read_subarray_events()
    assert f"{prefix}_prediction" in events.colnames
    assert f"{prefix}_telescopes" in events.colnames
    assert f"{prefix}_is_valid" in events.colnames
    assert f"{prefix}_goodness_of_fit" in events.colnames

    events = loader.read_telescope_events()
    assert f"{prefix}_prediction" in events.colnames
    assert f"{prefix}_telescopes" in events.colnames
    assert f"{prefix}_is_valid" in events.colnames
    assert f"{prefix}_goodness_of_fit" in events.colnames

    assert f"{prefix}_tel_prediction" in events.colnames
    assert f"{prefix}_tel_is_valid" in events.colnames

    assert "ExtraTreesRegressor_energy" in events.colnames

    from ctapipe.io.tests.test_table_loader import check_equal_array_event_order

    trigger = read_table(output_path, "/dl1/event/subarray/trigger")
    particle_clf = read_table(
        output_path, "/dl2/event/subarray/classification/ExtraTreesClassifier"
    )
    check_equal_array_event_order(trigger, particle_clf)
