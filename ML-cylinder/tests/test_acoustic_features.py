import numpy as np
import pytest
from src.acoustic_features import extract_acoustic_features, load_bands, validate_bands
from src.sensor_roles import metadata_for

def test_sensor_roles_are_both_acoustic():
    assert metadata_for("sph0645")["sensor_role"] == "acoustic_vibration"
    assert metadata_for("inmp441")["sensor_role"] == "sound"
    assert metadata_for("sph0645")["physical_quantity"] == "pcm_amplitude"

def test_acoustic_fft_features_find_tone_and_energy():
    fs=24000; t=np.arange(fs)/fs; signal=.4*np.sin(2*np.pi*200*t)
    result=extract_acoustic_features(signal,fs,role="acoustic_vibration")
    assert result["dominant_frequency"] == pytest.approx(200,abs=1)
    assert result["band_energy_fundamental_motion_band"] > result["band_energy_impact_band"]

def test_band_validation_rejects_above_nyquist():
    with pytest.raises(ValueError): validate_bands({"bad":(100,600)},1000)

def test_default_bands_support_deployed_16khz_input():
    validate_bands(load_bands(), 16000)
