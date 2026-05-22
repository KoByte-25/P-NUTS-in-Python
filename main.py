# main.py
from database import Cluster
from query_processor import QueryProcessor
import pickle, os

# Load existing cluster if exists
CLUSTER_FILE = "cluster.pkl"
cluster = Cluster()
if os.path.exists(CLUSTER_FILE):
    with open(CLUSTER_FILE, "rb") as f:
        cluster = pickle.load(f)

qp = QueryProcessor(cluster)

# Example usage
#qp.insert("PNUTS_Company", "employee", {"employee_id": 3, "employee_name": "Alice", "employee_address": "Yangon", "salary" : 50000.0})
#qp.update("PNUTS_Company", "employee", 3, {"employee_name": "Bob"})
#records = qp.select("PNUTS_Company", "employee")
#print(records)
qp.delete("PNUTS_Company", "employee", 3)
records = qp.select("PNUTS_Company", "employee")
print(records)

# Save changes
qp.save()