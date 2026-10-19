import h5py
import numpy as np

from dbars.io.supplementary import read_zana_bars


def test_read_zana_bars(tmp_path):
    p = tmp_path / "morphs_kinematic_bars.hdf5"
    with h5py.File(p, "w") as f:
        g = f.create_group("Snapshot_99")
        g["SubhaloID"] = np.array([0, 1, 2])
        g["Barred"] = np.array([False, False, True])
        g["BarSize"] = np.array([[5.9, -1, 1.56], [3.8, -1, 1.39]])
        g["BarStrength"] = np.array([[0.27, -1, 0.24], [0.17, -1, 0.15]])
        g["QualityFlags"] = np.array([[0.3, 0.5, 0.4], [0.8, -1, 0.75], [1.0, -1, 1.0]])
        g["StellarMass"] = np.array([5e12, 4e11, 2e11])
    df = read_zana_bars(p, 99)
    assert df["sid"].tolist() == [0, 1, 2] and df["zana_barred"].tolist() == [False, False, True]
    assert df.loc[2, "zana_r_phi"] == 1.56 and df.loc[2, "zana_r_peak"] == 1.39
    assert np.isnan(df.loc[1, "zana_r_phi"]) and np.isnan(df.loc[1, "zana_a2max"])
