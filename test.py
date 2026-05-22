from database import Cluster, Node

# Create cluster
cluster = Cluster()

# Add replica
replica1 = Node("Replica1")
cluster.add_replica(replica1)

# Define schema
user_schema = {
    "user_id": str,
    "name": str,
    "age": int
}

# Create table in cluster
cluster.create_table("User", "user_id", user_schema)

# Insert through cluster (goes to master)
cluster.insert("User", {
    "user_id": "u1",
    "name": "Alice",
    "age": 22
})

# Check master
master_table = cluster.master.get_table("User")
print("Master:", master_table.get("u1"))

# Check replica
replica_table = replica1.get_table("User")
print("Replica:", replica_table.get("u1"))

# Update record on master
cluster.master.get_table("User").update("u1", {"age": 25})

# Log update manually
updated_record = cluster.master.get_table("User").get("u1")
cluster.replication_log.append(("User", updated_record))

cluster.replicate()

print("After Update:")
print("Master:", cluster.master.get_table("User").get("u1"))
print("Replica:", replica1.get_table("User").get("u1"))
