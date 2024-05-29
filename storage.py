import json
import os

storage_path = os.path.join(os.path.dirname(__file__), 'data')
tasks_storage_path = os.path.join(storage_path, 'tasks')


class LocalFileStorage:
    @staticmethod
    def start_task(task_id, prompt):
        data_file = os.path.join(tasks_storage_path, f"{task_id}.json")
        with open(data_file, 'w') as f:
            f.write(json.dumps({
                "status": "PENDING",
                "prompt": prompt
            }))

    @staticmethod
    def update_task_status(task_id, status, **kwargs):
        data_file = os.path.join(tasks_storage_path, f"{task_id}.json")
        data = LocalFileStorage.get_task(task_id)
        data['status'] = status
        for arg in kwargs:
            data[arg] = kwargs[arg]
        with open(data_file, 'w') as f:
            f.write(json.dumps(data))

    @staticmethod
    def get_task(task_id):
        data_file = os.path.join(tasks_storage_path, f"{task_id}.json")
        if os.path.exists(data_file):
            with open(data_file, 'r') as f:
                return json.load(f)
        else:
            return {}
