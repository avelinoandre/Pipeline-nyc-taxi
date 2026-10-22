from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd
import psycopg
from streamlit.testing.v1 import AppTest

from src.dashboard.data import validate_results


def make_results():
    # Massa pequena para testar filtros e denominadores, sem consultar o banco.
    months = pd.date_range("2018-01-01", periods=12, freq="MS")
    zones = pd.DataFrame([
        {"zone_id": 1, "zone_name": "Alpha", "borough": "Queens", "is_mapped_zone": True,
         "trip_count": 2, "share_of_dataset_pct": 50.0},
        {"zone_id": 2, "zone_name": "Beta", "borough": "Manhattan", "is_mapped_zone": True,
         "trip_count": 1, "share_of_dataset_pct": 25.0},
        {"zone_id": -1, "zone_name": "Unknown", "borough": "Unknown", "is_mapped_zone": False,
         "trip_count": 1, "share_of_dataset_pct": 25.0},
    ])
    monthly = pd.DataFrame({"month": months, "trip_count": [3, 1] + [0] * 10,
                            "observed_days": [2, 1] + [0] * 10,
                            "calendar_days": months.days_in_month,
                            "trips_per_observed_day": [1.5, 1.0] + [None] * 10})
    zone_monthly = []
    hourly = []
    profile = []
    for row in zones.to_dict("records"):
        for month in months:
            count = row["trip_count"] if month.month == (2 if row["zone_id"] == -1 else 1) else 0
            global_count = 3 if month.month == 1 else 1 if month.month == 2 else 0
            zone_monthly.append({**row, "month": month, "trip_count": count,
                                 "share_of_month_dataset_pct": count / global_count * 100 if global_count else None,
                                 "trips_per_observed_day": count / (2 if month.month == 1 else 1) if global_count else None})
        for day in range(1, 8):
            for hour in range(24):
                count = row["trip_count"] if day == 2 and hour == 8 else 0
                hourly.append({**row, "day_of_week": day, "pickup_hour": hour,
                               "observed_weekdays": 1, "trip_count": count,
                               "trips_per_observed_weekday": float(count)})
        metrics = {**row, "trips_with_fare": row["trip_count"], "trips_with_total": row["trip_count"],
                   "nonpositive_fare_trips": 0, "nonpositive_total_trips": 0}
        for name in ["fare_usd", "total_usd", "distance_miles", "duration_minutes"]:
            metrics["avg_" + name] = 12.0
            metrics["median_" + name] = 10.0
        profile.append(metrics)
    return {"zones": zones, "monthly": monthly, "zone_monthly": pd.DataFrame(zone_monthly),
            "hourly": pd.DataFrame(hourly), "profile": pd.DataFrame(profile),
            "coverage": pd.DataFrame([
                {"pickup_year": 2017, "trip_count": 1, "observed_days": 1, "unknown_pickup_zone_trips": 0},
                {"pickup_year": 2018, "trip_count": 4, "observed_days": 3, "unknown_pickup_zone_trips": 1},
            ]), "loaded_at": datetime(2026, 10, 21, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))}


class DashboardValidationTests(unittest.TestCase):
    def test_reconciled_results_keep_unknown_and_unobserved_months(self):
        results = make_results()
        validate_results(results)
        self.assertEqual(results["zones"]["trip_count"].sum(), 4)
        self.assertEqual(results["monthly"]["observed_days"].sum(), 3)

    def test_changed_total_is_rejected(self):
        results = make_results()
        results["profile"].loc[0, "trip_count"] += 1
        with self.assertRaisesRegex(ValueError, "Contagem divergente"):
            validate_results(results)

    def test_monthly_shift_is_rejected_even_when_annual_total_matches(self):
        results = make_results()
        results["zone_monthly"].loc[0, "trip_count"] -= 1
        results["zone_monthly"].loc[1, "trip_count"] += 1
        with self.assertRaisesRegex(ValueError, "mensais divergentes"):
            validate_results(results)


class DashboardAppTests(unittest.TestCase):
    def setUp(self):
        # AppTest roda o app real; somente a leitura do banco e substituida.
        import streamlit as st
        st.cache_data.clear()
        self.mock = patch("src.dashboard.data.load_analytics", return_value=make_results())
        self.loader = self.mock.start()
        self.addCleanup(self.mock.stop)
        self.app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=20).run()
        self.app.sidebar.radio(key="section").set_value("Panorama").run()

    def test_executive_view_recomputes_selected_share_against_full_dataset(self):
        self.app.sidebar.radio(key="section").set_value("Visão executiva").run()
        self.assertFalse(self.app.exception)
        html = "\n".join(element.proto.body for element in self.app.get("html"))
        self.assertIn("75,00%", html)  # Alpha + Beta: 3 de 4 viagens, incluindo Unknown no denominador.
        self.assertIn("Alpha", html)
        self.assertIn("Beta", html)
        headings = [heading.value for heading in self.app.main.subheader]
        self.assertEqual(headings, [
            "01 / Decisão em discussão", "02 / Proposta inicial",
            "03 / Evidências que sustentam a investigação", "04 / Incertezas que afetam a decisão",
            "05 / Próximo passo e resultado esperado",
        ])
        self.app.sidebar.multiselect[0].set_value([1]).run()
        self.assertFalse(self.app.exception)
        html = "\n".join(element.proto.body for element in self.app.get("html"))
        self.assertIn("50,00%", html)
        self.assertNotIn("<h3>Beta</h3>", html)
        self.assertEqual(self.loader.call_count, 1)

    def test_navigation_and_profile_metrics_keep_annual_context(self):
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.metric[0].value, "4")
        self.assertEqual(self.app.metric[3].value, "25,00%")
        for page in ["Zonas e meses", "Dias e horários", "Perfil das viagens", "Cobertura e método"]:
            self.app.sidebar.radio(key="section").set_value(page).run()
            self.assertFalse(self.app.exception, page)
        self.app.sidebar.radio(key="section").set_value("Perfil das viagens").run()
        for metric in ["Total cobrado (USD)", "Distância (milhas)", "Duração (minutos)"]:
            self.app.radio(key="profile_metric").set_value(metric).run()
            self.assertFalse(self.app.exception)
        self.assertEqual(self.loader.call_count, 1, "Filtros nao devem repetir a consulta SQL")

    def test_borough_changes_zone_options_but_not_global_metrics(self):
        self.app.sidebar.selectbox(key="borough").set_value("Queens").run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.sidebar.multiselect[0].value, [1])
        self.assertEqual(self.app.metric[0].value, "4")
        self.assertEqual(self.app.metric[3].value, "25,00%")

    def test_empty_selection_does_not_crash_comparison_pages(self):
        self.app.sidebar.multiselect[0].set_value([]).run()
        for page in ["Zonas e meses", "Dias e horários", "Perfil das viagens"]:
            self.app.sidebar.radio(key="section").set_value(page).run()
            self.assertFalse(self.app.exception)
            self.assertTrue(any("Selecione pelo menos" in message.value for message in self.app.info))

    def test_refresh_runs_a_new_query(self):
        self.assertEqual(self.loader.call_count, 1)
        self.app.sidebar.button[0].click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.loader.call_count, 2)

    def test_connection_failure_does_not_expose_credentials(self):
        import streamlit as st
        st.cache_data.clear()
        self.loader.side_effect = psycopg.OperationalError("password=never_show_this")
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertEqual(len(self.app.error), 1)
        self.assertNotIn("never_show_this", self.app.error[0].value)
        self.assertIn("PostgreSQL", self.app.error[0].value)


if __name__ == "__main__":
    unittest.main()
