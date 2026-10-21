"""Output formatting rules for OBS answers.

STRICT FILTERING RULE:
- If the user asks about a targeted parameter (vent/wind, humidité/humidity,
  température, pression, pluviométrie, …), answer ONLY with that parameter,
  plus location, date/time, and source document.
- If the user asks a general query (e.g. « Météo à Mdiq à 09h »), return the
  full observation summary.
"""

STRICT_FILTERING_RULE = (
    "Check if the user is asking about a targeted parameter "
    "(vent/wind, humidité/humidity, température, pression, pluviométrie). "
    "If a specific parameter is requested, answer ONLY with that parameter, "
    "along with the location, date/time, and source document. "
    "If the user asks a general query (e.g. 'Météo à Mdiq à 09h'), "
    "return the full summary."
)
