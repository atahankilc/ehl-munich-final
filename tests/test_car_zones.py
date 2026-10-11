"""3D car view zones (D-039): deterministic placement of requirements and equipment on the car."""

from bmw_req.car_zones import MODELS_GLTF, ZONES, model_url, option_zone, requirement_zone


def test_requirements_land_where_customers_experience_them():
    assert requirement_zone("Sustained, well-supported rear-seat relaxation", "Comfort & Space") == "rear_seats"
    assert requirement_zone("Fit everyday luggage more flexibly", "Comfort & Space") == "trunk"
    assert requirement_zone("Keep public fast-charging stops short", "Range & Charging") == "charging"
    assert requirement_zone("Cabin comfort soon after entering", "Comfort & Space") == "cabin"
    assert requirement_zone("Clear surrounding views despite rear-cabin obstructions", "Driver Assistance") == "front"
    assert requirement_zone("Natural voice interaction that understands local customers",
                            "Infotainment & Digital") == "cockpit"


def test_unknown_text_falls_back_to_category_then_cabin():
    assert requirement_zone("Something new", "Powertrain (as experienced)") == "powertrain"
    assert requirement_zone("Something new", None) == "cabin"


def test_option_zones():
    assert option_zone("Automatic tailgate operation", "Comfort & Space") == "trunk"
    assert option_zone("BMW 3D Head-Up Display", "Infotainment & Digital") == "cockpit"
    assert option_zone("Massage function in the rear", "Comfort & Space") == "rear_seats"


AXES = {"+x", "-x", "+y", "-y", "+z", "-z"}


def test_every_zone_and_model_is_well_formed():
    for z in ZONES.values():
        f, r, h = z["pos"]
        assert -1 <= f <= 1 and -1 <= r <= 1 and 0 <= h <= 1
    assert set(MODELS_GLTF) == {"F70", "G60", "G68", "G70"}
    for d, m in MODELS_GLTF.items():
        assert m["file"] and "/" not in m["file"] and m["license"] == "CC BY 4.0", d
        assert m["source_url"].startswith("https://") and m["author"] and m["name"], d
        up, front = m["orientation"]["up"], m["orientation"]["front"]
        # up and front must be valid, distinct, non-parallel axes
        assert up in AXES and front in AXES and up[1] != front[1], d
    assert MODELS_GLTF["G68"]["shared_with"] == "G60" and MODELS_GLTF["G68"]["file"] == MODELS_GLTF["G60"]["file"]


def test_model_url_prefers_glb_then_gltf(tmp_path):
    assert model_url("G60", tmp_path) is None
    (tmp_path / "g60").mkdir()
    (tmp_path / "g60" / "scene.gltf").write_text("{}")
    assert model_url("G60", tmp_path) == "/models/g60/scene.gltf"
    assert model_url("G68", tmp_path) == "/models/g60/scene.gltf"
    (tmp_path / "g60.glb").write_bytes(b"glTF")
    assert model_url("G60", tmp_path) == "/models/g60.glb"
    assert model_url("X99", tmp_path) is None
