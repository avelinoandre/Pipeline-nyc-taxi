"""Validação dos dashboards da prática, sem Spark nem PostgreSQL."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


class DashboardsAulasTest(unittest.TestCase):
    def tearDown(self):
        st.cache_data.clear()

    def test_base_real_metricas_e_tres_visuais(self):
        st.cache_data.clear()
        at = AppTest.from_file(str(APP)).run(timeout=60)
        self.assertFalse(at.exception)
        self.assertEqual(len(at.tabs), 2)
        self.assertEqual(len(at.metric), 4)
        data = pd.read_csv(ROOT / "data/clean/dataset.csv")
        self.assertEqual(len(data), 200_000)
        self.assertEqual(at.metric[0].value, "200,000")
        for metric, column in zip(list(at.metric)[1:], [
            "trip_distance", "trip_duration_minutes", "total_amount"
        ]):
            self.assertEqual(metric.value, f"{data[column].mean():.2f}")
        self.assertEqual(len(at.get("image")), 6)
        charts = at.get("vega_lite_chart")
        self.assertEqual(len(charts), 1)
        spec = json.loads(charts[0].proto.spec)
        self.assertEqual(spec["vconcat"][0]["mark"]["type"], "bar")
        scatter = spec["vconcat"][1]["hconcat"]
        self.assertEqual(len(scatter), 2)
        self.assertEqual([c["mark"]["type"] for c in scatter], ["circle", "circle"])
        self.assertEqual({p["name"] for p in spec["params"]}, {"hora_selecionada"})
        for chart in scatter:
            self.assertEqual(chart["transform"][-1]["filter"]["param"], "hora_selecionada")

    def test_widgets_recalculam_e_cache_nao_rele_csv(self):
        fixture = pd.DataFrame({
            "trip_distance": [1., 2., 3., 4., 8., 10.],
            "fare_amount": [4., 8., 12., 16., 32., 40.],
            "trip_duration_minutes": [5., 10., 15., 20., 40., 50.],
            "tip_amount": [0., 1., 2., 3., 4., 5.],
            "total_amount": [5., 10., 15., 20., 40., 50.],
            "pickup_datetime": pd.to_datetime([
                "2018-01-01 08:00", "2018-01-01 09:00", "2018-01-01 09:10",
                "2018-01-01 10:00", "2018-01-01 11:00", "2018-01-01 12:00",
            ]),
        })
        st.cache_data.clear()
        with patch("pandas.read_csv", return_value=fixture) as read:
            at = AppTest.from_file(str(APP)).run(timeout=30)
            for variables, images in [([], 0), (["trip_distance"], 1),
                                      (["fare_amount", "total_amount"], 3)]:
                at.sidebar.get("button_group")[0].set_value(variables).run(timeout=30)
                self.assertFalse(at.exception)
                self.assertEqual(len(at.get("image")), images)
                self.assertEqual(len(at.get("vega_lite_chart")), 1)
                self.assertEqual(at.metric[0].value, "6")
            at.sidebar.slider[0].set_range(2., 4.).run(timeout=30)
            self.assertFalse(at.exception)
            self.assertEqual([m.value for m in at.metric], ["3", "3.00", "15.00", "15.00"])
            self.assertEqual(read.call_count, 1)
            at.sidebar.slider[0].set_range(5., 6.).run(timeout=30)
            self.assertFalse(at.exception)
            self.assertEqual([m.value for m in at.metric], ["0", "—", "—", "—"])
            self.assertEqual(len(at.get("image")), 0)
            self.assertEqual(len(at.get("vega_lite_chart")), 0)


if __name__ == "__main__":
    unittest.main()
