from app.services.intent import detect_intent, extract_city, extract_hour, parse_message
from app.models import Intent


def test_detect_current_intent():
    assert detect_intent("Quel temps fait-il à Tanger Med ?") == Intent.CURRENT


def test_detect_forecast_intent():
    assert detect_intent("Prévisions pour Sfax") == Intent.FORECAST


def test_extract_city_known_place():
    assert (
        extract_city(
            "Observation Fnideq à 12h",
            known_places=["Fnideq", "Tanger Med", "Rabat Ville"],
        )
        == "Fnideq"
    )


def test_extract_hour():
    assert extract_hour("Observation Fnideq à 12h") == 12
    assert extract_hour("Rabat Ville à 18h00") == 18


def test_parse_message_defaults_city():
    parsed = parse_message("Bonjour", default_city="Rabat Ville")
    assert parsed.city == "Rabat Ville"
    assert parsed.hour is None
