from __future__ import annotations

from app.config import Settings
from app.models import ChatResponse, Intent
from app.services.bms_store import BmsStore
from app.services.intent import (
    DAILY_METRICS,
    Metric,
    apply_session_context,
    parse_message,
)
from app.services.obs_daily_store import DailyObsStore
from app.services.obs_store import ObsStore
from app.services.reply_style import pad_label, styled_reply
from app.services.scenarios import (
    detect_region,
    is_scenario_query,
    run_alert_scenario,
    run_rain_scenario,
    scenario_metric,
)
from app.services.session import SessionStore
from app.services.special_store import SpecialStore
from app.services.suggestions import build_suggestions
from app.services.weather import WeatherService


HELP_TEXT = (
    "Je réponds à partir des bulletins DRMNO / PFA :\n\n"
    "1) Observations · 2) Quotidien · 3) Alertes BMS · 4) SPECIAL\n"
    "5) Comparaisons · 6) Scénarios régionaux · 7) Suivi de conversation\n\n"
    "Exemples :\n"
    "• « Températures extrêmes à Kenitra demain » puis « et le vent ? »\n"
    "• « Pareil pour Tanger »\n"
    "• « Où risque-t-il de pleuvoir dans le Nord demain ? »\n"
    "• Cliquez une province sur la carte de vigilance\n"
)


class ChatbotService:
    def __init__(
        self,
        settings: Settings,
        weather: WeatherService,
        obs_store: ObsStore,
        daily_store: DailyObsStore,
        bms_store: BmsStore,
        special_store: SpecialStore,
    ) -> None:
        self.settings = settings
        self.weather = weather
        self.obs = obs_store
        self.daily = daily_store
        self.bms = bms_store
        self.special = special_store
        self.sessions = SessionStore()

    def _known_places(self) -> list[str]:
        names: set[str] = set()
        if self.obs.available:
            names.update(self.obs.list_station_names())
        if self.daily.available:
            names.update(self.daily.list_station_names())
        if self.special.available:
            names.update(self.special.list_cities())
        return sorted(names)

    def _reply_daily(self, city: str, date: str | None, metric: Metric | None) -> ChatResponse:
        hit = self.daily.get_observation(city, date=date)
        if hit is not None:
            return ChatResponse(
                reply=self.daily.format_observation(hit, metric=metric),
                intent=Intent.CURRENT,
                city=hit.station,
                data={
                    **hit.to_dict(),
                    "dataset": "daily",
                    "requested_metric": metric.value if metric else None,
                },
            )
        if self.daily.match_station(city) is None:
            stations = ", ".join(self.daily.list_station_names()[:12])
            return ChatResponse(
                reply=(
                    f"Je n'ai pas trouvé la station « {city} » dans les bulletins quotidiens.\n"
                    f"Stations connues (extrait) : {stations}…"
                ),
                intent=Intent.CURRENT,
                city=city,
            )
        date_label = f" pour le {date}" if date else ""
        return ChatResponse(
            reply=f"Pas d'observation quotidienne disponible pour {city}{date_label}.",
            intent=Intent.CURRENT,
            city=city,
        )

    def _reply_hourly(self, city: str, hour: int | None, metric: Metric | None) -> ChatResponse:
        hourly_metric = None if metric in DAILY_METRICS else metric
        hit = self.obs.get_observation(city, hour=hour)
        if hit is not None:
            return ChatResponse(
                reply=self.obs.format_observation(hit, metric=hourly_metric),
                intent=Intent.CURRENT,
                city=hit.station,
                data={
                    **hit.to_dict(),
                    "dataset": "hourly",
                    "requested_metric": hourly_metric.value if hourly_metric else None,
                },
            )
        if self.obs.match_station(city) is None:
            stations = ", ".join(self.obs.list_station_names()[:12])
            return ChatResponse(
                reply=(
                    f"Je n'ai pas trouvé la station « {city} » dans les bulletins horaires.\n"
                    f"Stations connues (extrait) : {stations}…"
                ),
                intent=Intent.CURRENT,
                city=city,
            )
        hour_label = f" à {hour:02d}h00" if hour is not None else ""
        return ChatResponse(
            reply=f"Pas d'observation horaire disponible pour {city}{hour_label}.",
            intent=Intent.CURRENT,
            city=city,
        )

    def _reply_bms(self, city: str, date: str | None, place_requested: bool) -> ChatResponse:
        bulletin = self.bms.for_date(date)
        if bulletin is None:
            return ChatResponse(
                reply="Aucun bulletin BMS n'est chargé pour le moment.",
                intent=Intent.ALERTS,
                city=city,
            )
        place = city if place_requested else None
        if place:
            hits = self.bms.find_for_place(place, bulletin.get("issue_date"))
            if not hits and date is None:
                for candidate in reversed(self.bms.bulletins):
                    hits = self.bms.find_for_place(place, candidate.get("issue_date"))
                    if hits:
                        bulletin = candidate
                        break
            reply = self.bms.format_bulletin(bulletin, place=place)
        else:
            reply = self.bms.format_bulletin(bulletin, place=None)
        return ChatResponse(
            reply=reply,
            intent=Intent.ALERTS,
            city=city,
            data={
                "dataset": "bms",
                "source_file": bulletin.get("source_file"),
                "issue_date": bulletin.get("issue_date"),
            },
        )

    def _reply_special(
        self,
        city: str,
        date: str | None,
        metric: Metric | None,
        day_filter: str | None,
    ) -> ChatResponse:
        forecast = self.special.get_forecast(city, date=date)
        if forecast is None:
            cities = ", ".join(self.special.list_cities())
            return ChatResponse(
                reply=(
                    f"Pas de prévision SPECIAL pour « {city} ».\n"
                    f"Villes disponibles : {cities}"
                ),
                intent=Intent.FORECAST,
                city=city,
            )
        return ChatResponse(
            reply=self.special.format_forecast(
                forecast,
                metric=metric,
                day_filter=day_filter,
            ),
            intent=Intent.FORECAST,
            city=forecast.get("city") or city,
            data={
                "dataset": "special",
                "source_file": forecast.get("source_file"),
                "issue_date": forecast.get("issue_date"),
                "requested_metric": metric.value if metric else None,
            },
        )

    def _reply_compare(
        self,
        cities: list[str],
        date: str | None,
        hour: int | None,
        metric: Metric | None,
        day_filter: str | None,
        dataset: str,
    ) -> ChatResponse:
        city_a, city_b = cities[0], cities[1]

        prefer_special = (
            dataset == "special"
            or day_filter is not None
            or metric
            in {
                Metric.TEXTREMES,
                Metric.SKY,
                Metric.PHENOMENA,
                Metric.TEMPERATURE,
                Metric.WIND,
                Metric.RAIN,
            }
            or hour is None
        ) and not (hour is not None or (metric in DAILY_METRICS and day_filter is None))

        if prefer_special and self.special.available:
            sa = self.special.match_city(city_a) or city_a
            sb = self.special.match_city(city_b) or city_b
            reply = self.special.format_compare(
                sa,
                sb,
                date=date,
                metric=metric,
                day_filter=day_filter,
            )
            if reply:
                return ChatResponse(
                    reply=reply,
                    intent=Intent.FORECAST,
                    city=f"{sa} / {sb}",
                    data={
                        "dataset": "special_compare",
                        "cities": [sa, sb],
                        "requested_metric": metric.value if metric else None,
                    },
                )

        # OBS hourly compare
        if self.obs.available and (hour is not None or dataset == "hourly"):
            ha = self.obs.get_observation(city_a, hour=hour)
            hb = self.obs.get_observation(city_b, hour=hour)
            if ha and hb:
                hourly_metric = None if metric in DAILY_METRICS else metric
                width = max(len(ha.station), len(hb.station), 8)
                left = self.obs.format_observation(ha, metric=hourly_metric)
                right = self.obs.format_observation(hb, metric=hourly_metric)
                # Build compact compare from metric lines
                def _value_line(text: str) -> str:
                    for line in text.splitlines():
                        if " : " in line and not line.startswith("Observation") and not line.startswith("Date") and not line.startswith("Source"):
                            return line.split(" : ", 1)[-1]
                    return "non renseigné"

                body = [
                    f"{pad_label(ha.station, width)} : {_value_line(left) if hourly_metric else ha.temperature_c}",
                    f"{pad_label(hb.station, width)} : {_value_line(right) if hourly_metric else hb.temperature_c}",
                ]
                return ChatResponse(
                    reply=styled_reply(
                        title=f"Comparaison OBS — {ha.station} × {hb.station}",
                        meta=[f"Date/heure : {ha.date} à {ha.time}"],
                        body_lines=body,
                        source=f"{ha.source_file} · {hb.source_file}",
                    ),
                    intent=Intent.CURRENT,
                    city=f"{ha.station} / {hb.station}",
                    data={"dataset": "hourly_compare", "cities": [ha.station, hb.station]},
                )

        # Daily OBS compare
        if self.daily.available:
            da = self.daily.get_observation(city_a, date=date)
            db = self.daily.get_observation(city_b, date=date)
            if da and db:
                width = max(len(da.station), len(db.station), 8)
                la = self.daily.format_observation(da, metric=metric)
                lb = self.daily.format_observation(db, metric=metric)

                def _pick(text: str) -> str:
                    for line in text.splitlines():
                        if " : " in line and not line.startswith("Observation") and not line.startswith("Date") and not line.startswith("Source"):
                            return line
                    return "non renseigné"

                return ChatResponse(
                    reply=styled_reply(
                        title=f"Comparaison quotidienne — {da.station} × {db.station}",
                        meta=[f"Date : {da.date}"],
                        body_lines=[
                            f"{pad_label(da.station, width)} : {_pick(la).split(' : ', 1)[-1]}",
                            f"{pad_label(db.station, width)} : {_pick(lb).split(' : ', 1)[-1]}",
                        ],
                        source=f"{da.source_file} · {db.source_file}",
                    ),
                    intent=Intent.CURRENT,
                    city=f"{da.station} / {db.station}",
                    data={"dataset": "daily_compare", "cities": [da.station, db.station]},
                )

        return ChatResponse(
            reply=(
                f"Impossible de comparer « {city_a} » et « {city_b} » "
                "avec les bulletins disponibles."
            ),
            intent=Intent.FORECAST,
            city=f"{city_a} / {city_b}",
        )

    def _decorate(
        self,
        response: ChatResponse,
        *,
        session_id: str | None,
        metric: Metric | None,
        dataset: str | None,
        day_filter: str | None,
        date: str | None,
        hour: int | None,
        cities: list[str] | None = None,
    ) -> ChatResponse:
        data = dict(response.data or {})
        ds = data.get("dataset") or dataset
        compare_cities = data.get("cities") if isinstance(data.get("cities"), list) else cities
        primary_city = response.city.split(" / ")[0] if response.city else None
        suggestions = build_suggestions(
            city=primary_city,
            metric=metric,
            dataset=str(ds) if ds else None,
            day_filter=day_filter,
            compare_cities=compare_cities,
        )
        response.suggestions = suggestions
        data["suggestions"] = suggestions
        response.data = data

        self.sessions.update(
            session_id,
            city=primary_city,
            cities=compare_cities or ([primary_city] if primary_city else []),
            metric=metric,
            dataset=ds,
            day_filter=day_filter,
            date=date,
            hour=hour,
            last_intent=response.intent.value if response.intent else None,
        )
        return response

    async def reply(
        self,
        message: str,
        city_override: str | None = None,
        session_id: str | None = None,
    ) -> ChatResponse:
        known = self._known_places()
        ctx = self.sessions.get(session_id)
        parsed = parse_message(
            message,
            default_city=ctx.city or self.settings.default_city,
            known_places=known,
        )
        parsed = apply_session_context(parsed, ctx)

        explicit_city = city_override or (
            parsed.city if parsed.city and parsed.city != self.settings.default_city else None
        )
        place_requested = bool(parsed.cities) or bool(city_override)
        lower = message.lower()
        lower_norm = "".join(
            ch
            for ch in __import__("unicodedata").normalize("NFD", lower)
            if __import__("unicodedata").category(ch) != "Mn"
        )
        for place in known:
            needle = "".join(
                ch
                for ch in __import__("unicodedata").normalize("NFD", place.lower())
                if __import__("unicodedata").category(ch) != "Mn"
            )
            if needle and needle in lower_norm:
                place_requested = True
                explicit_city = place
                break
        if city_override:
            place_requested = True
            explicit_city = city_override

        city = explicit_city or parsed.city or ctx.city or self.settings.default_city
        intent = parsed.intent

        try:
            if intent == Intent.HELP or ("liste" in lower and ("station" in lower or "ville" in lower)):
                if "station" in lower or "ville" in lower:
                    names = ", ".join(known)
                    return self._decorate(
                        ChatResponse(
                            reply=f"Lieux disponibles :\n{names}",
                            intent=Intent.HELP,
                            city=city,
                            data={"places": known, "dataset": "help"},
                        ),
                        session_id=session_id,
                        metric=parsed.metric,
                        dataset="help",
                        day_filter=parsed.day_filter,
                        date=parsed.date,
                        hour=parsed.hour,
                    )
                return self._decorate(
                    ChatResponse(reply=HELP_TEXT, intent=Intent.HELP, city=city, data={"dataset": "help"}),
                    session_id=session_id,
                    metric=parsed.metric,
                    dataset="help",
                    day_filter=parsed.day_filter,
                    date=parsed.date,
                    hour=parsed.hour,
                )

            # Regional scenario queries
            if is_scenario_query(message):
                region = detect_region(message)
                metric = scenario_metric(message) or parsed.metric
                if "alerte" in lower or "vigilance" in lower or "bms" in lower:
                    reply = run_alert_scenario(self.bms, region, parsed.date)
                    return self._decorate(
                        ChatResponse(
                            reply=reply,
                            intent=Intent.ALERTS,
                            city=region or "nord",
                            data={"dataset": "scenario", "region": region},
                        ),
                        session_id=session_id,
                        metric=metric,
                        dataset="scenario",
                        day_filter=parsed.day_filter or "Demain",
                        date=parsed.date,
                        hour=parsed.hour,
                    )
                reply = run_rain_scenario(
                    self.special,
                    region,
                    parsed.day_filter or "Demain",
                    parsed.date,
                    metric,
                )
                return self._decorate(
                    ChatResponse(
                        reply=reply,
                        intent=Intent.FORECAST,
                        city=region or "nord",
                        data={"dataset": "scenario", "region": region},
                    ),
                    session_id=session_id,
                    metric=metric,
                    dataset="scenario",
                    day_filter=parsed.day_filter or "Demain",
                    date=parsed.date,
                    hour=parsed.hour,
                )

            # City comparison
            if parsed.compare and len(parsed.cities) >= 2:
                response = self._reply_compare(
                    parsed.cities[:2],
                    parsed.date,
                    parsed.hour,
                    parsed.metric,
                    parsed.day_filter,
                    parsed.dataset,
                )
                return self._decorate(
                    response,
                    session_id=session_id,
                    metric=parsed.metric,
                    dataset=(response.data or {}).get("dataset") or "special_compare",
                    day_filter=parsed.day_filter,
                    date=parsed.date,
                    hour=parsed.hour,
                    cities=parsed.cities[:2],
                )

            # BMS alerts
            if (intent == Intent.ALERTS or parsed.dataset == "bms") and self.bms.available:
                response = self._reply_bms(city, parsed.date, place_requested=place_requested)
                return self._decorate(
                    response,
                    session_id=session_id,
                    metric=parsed.metric,
                    dataset="bms",
                    day_filter=parsed.day_filter,
                    date=parsed.date,
                    hour=parsed.hour,
                )

            # Prefer SPECIAL city match when forecast day / textremes asked
            if (
                parsed.dataset == "special" or intent == Intent.FORECAST
            ) and self.special.available:
                special_city = (
                    self.special.match_city(city)
                    or (self.special.match_city(parsed.city) if parsed.city else None)
                    or self.special.match_city(message)
                )
                if special_city:
                    city = special_city
                response = self._reply_special(
                    city,
                    parsed.date,
                    parsed.metric,
                    parsed.day_filter,
                )
                return self._decorate(
                    response,
                    session_id=session_id,
                    metric=parsed.metric,
                    dataset="special",
                    day_filter=parsed.day_filter,
                    date=parsed.date,
                    hour=parsed.hour,
                )

            if intent in {Intent.CURRENT, Intent.UNKNOWN, Intent.CLIMATE}:
                dataset = parsed.dataset
                if dataset == "daily" and self.daily.available:
                    response = self._reply_daily(city, parsed.date, parsed.metric)
                    return self._decorate(
                        response,
                        session_id=session_id,
                        metric=parsed.metric,
                        dataset="daily",
                        day_filter=parsed.day_filter,
                        date=parsed.date,
                        hour=parsed.hour,
                    )
                if dataset == "hourly" and self.obs.available:
                    response = self._reply_hourly(city, parsed.hour, parsed.metric)
                    return self._decorate(
                        response,
                        session_id=session_id,
                        metric=parsed.metric,
                        dataset="hourly",
                        day_filter=parsed.day_filter,
                        date=parsed.date,
                        hour=parsed.hour,
                    )

                if self.obs.available and self.obs.match_station(city):
                    response = self._reply_hourly(city, parsed.hour, parsed.metric)
                    return self._decorate(
                        response,
                        session_id=session_id,
                        metric=parsed.metric,
                        dataset="hourly",
                        day_filter=parsed.day_filter,
                        date=parsed.date,
                        hour=parsed.hour,
                    )
                if self.daily.available and self.daily.match_station(city):
                    response = self._reply_daily(city, parsed.date, parsed.metric)
                    return self._decorate(
                        response,
                        session_id=session_id,
                        metric=parsed.metric,
                        dataset="daily",
                        day_filter=parsed.day_filter,
                        date=parsed.date,
                        hour=parsed.hour,
                    )
                if self.special.available and self.special.match_city(city):
                    response = self._reply_special(
                        city, parsed.date, parsed.metric, parsed.day_filter
                    )
                    return self._decorate(
                        response,
                        session_id=session_id,
                        metric=parsed.metric,
                        dataset="special",
                        day_filter=parsed.day_filter,
                        date=parsed.date,
                        hour=parsed.hour,
                    )
                if self.obs.available:
                    response = self._reply_hourly(city, parsed.hour, parsed.metric)
                    return self._decorate(
                        response,
                        session_id=session_id,
                        metric=parsed.metric,
                        dataset="hourly",
                        day_filter=parsed.day_filter,
                        date=parsed.date,
                        hour=parsed.hour,
                    )
                if self.daily.available:
                    response = self._reply_daily(city, parsed.date, parsed.metric)
                    return self._decorate(
                        response,
                        session_id=session_id,
                        metric=parsed.metric,
                        dataset="daily",
                        day_filter=parsed.day_filter,
                        date=parsed.date,
                        hour=parsed.hour,
                    )
                return ChatResponse(
                    reply="Aucune donnée locale n'est chargée pour le moment.",
                    intent=Intent.CURRENT,
                    city=city,
                )

            if intent == Intent.ALERTS:
                return ChatResponse(
                    reply="Les bulletins BMS ne sont pas chargés.",
                    intent=intent,
                    city=city,
                )

            if intent == Intent.FORECAST:
                return ChatResponse(
                    reply="Les prévisions SPECIAL ne sont pas chargées.",
                    intent=intent,
                    city=city,
                )

            return ChatResponse(reply=HELP_TEXT, intent=Intent.HELP, city=city)

        except ValueError as exc:
            return ChatResponse(reply=str(exc), intent=intent, city=city)
        except Exception:
            return ChatResponse(
                reply=(
                    "Désolé, je n'ai pas pu lire les bulletins pour le moment. "
                    "Réessayez dans un instant."
                ),
                intent=intent,
                city=city,
            )
