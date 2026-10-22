import os
from pathlib import Path
import unittest


@unittest.skipUnless(os.getenv("RUN_AIRFLOW_TESTS") == "1", "Use the isolated Airflow environment")
class AirflowDagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from airflow.dag_processing.dagbag import DagBag
        cls.bag = DagBag(dag_folder=str(Path("dags").resolve()))
        cls.dag = cls.bag.dags.get("nyc_taxi_pipeline")

    def test_dag_imports_with_serial_execution_and_no_schedule(self):
        self.assertEqual(self.bag.import_errors, {})
        self.assertIsNotNone(self.dag)
        self.assertIsNone(self.dag.schedule)
        self.assertFalse(self.dag.catchup)
        self.assertEqual(self.dag.max_active_runs, 1)
        self.assertEqual(self.dag.max_active_tasks, 1)

    def test_dependency_chain_stops_downstream_tasks_after_failure(self):
        names = ["prepare_bronze", "bronze_to_silver", "silver_to_gold", "create_postgres_schema", "gold_to_postgres", "validate_pipeline"]
        self.assertEqual(set(self.dag.task_ids), set(names))
        for index, name in enumerate(names):
            task = self.dag.get_task(name)
            expected = {names[index + 1]} if index + 1 < len(names) else set()
            self.assertEqual(task.downstream_task_ids, expected)
            self.assertEqual(task.trigger_rule.value, "all_success")
            self.assertFalse(task.do_xcom_push)
            self.assertEqual(task.env["TZ"], "America/Sao_Paulo")
            self.assertEqual(task.env["SPARK_MASTER"], "local[2]")
            self.assertEqual(task.cwd, str(Path.cwd()))


if __name__ == "__main__":
    unittest.main()
