import logging

apps_path = './config/apps.json'
accounts_path = './config/users.json'
executor_workers_pool = 100
db_url = "mongodb://localhost:27017"
database_name = 'edu4job'
database_workers_pool = 25
logging.basicConfig(level=logging.INFO)
