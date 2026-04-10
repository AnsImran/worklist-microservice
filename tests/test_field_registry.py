"""Tests for the FieldRegistry — patient_linked strategy and custom patient handling."""


def test_patient_linked_from_pool(field_registry):
    """Known patient in pool returns their pre-assigned MRN."""
    # Pick the first patient from the pool
    patients = field_registry._pools.get("patients.json", {}).get("patients", [])
    assert len(patients) > 0
    known_name = patients[0]["name"]
    expected_mrn = patients[0]["mrn"]
    expected_dob = patients[0]["dob"]

    mrn_field = next(f for f in field_registry.fields if f["name"] == "mrn")
    dob_field = next(f for f in field_registry.fields if f["name"] == "dob")

    context = {"patient_name": known_name}
    mrn = field_registry.generate_value(mrn_field, context)
    dob = field_registry.generate_value(dob_field, context)

    assert mrn == expected_mrn
    assert dob == expected_dob


def test_patient_linked_custom_name_generates_mrn(field_registry):
    """Unknown patient name generates a random MRN in SHHD2200000+ range."""
    mrn_field = next(f for f in field_registry.fields if f["name"] == "mrn")
    context = {"patient_name": "Nonexistent, Person Z"}

    mrn = field_registry.generate_value(mrn_field, context)
    assert mrn is not None
    assert mrn.startswith("SHHD")
    num = int(mrn[4:])
    assert 2200000 <= num <= 2999999


def test_patient_linked_custom_name_generates_dob(field_registry):
    """Unknown patient name generates a valid DOB string."""
    dob_field = next(f for f in field_registry.fields if f["name"] == "dob")
    context = {"patient_name": "Nonexistent, Person Z"}

    dob = field_registry.generate_value(dob_field, context)
    assert dob is not None
    parts = dob.split("/")
    assert len(parts) == 3
    month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
    assert 1 <= month <= 12
    assert 1 <= day <= 28
    assert 1940 <= year <= 2005


def test_patient_linked_no_name_returns_none(field_registry):
    """No patient_name in context returns None."""
    mrn_field = next(f for f in field_registry.fields if f["name"] == "mrn")
    context = {}

    mrn = field_registry.generate_value(mrn_field, context)
    assert mrn is None
