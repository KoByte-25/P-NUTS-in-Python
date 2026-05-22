import tkinter as tk
from database import Cluster, Node

# -----------------------------
# Setup Cluster
# -----------------------------
cluster = Cluster()
replica1 = Node("Replica1")
cluster.add_replica(replica1)

user_schema = {
    "user_id": str,
    "name": str,
    "age": int
}

cluster.create_table("User", "user_id", user_schema)

# -----------------------------
# GUI Setup
# -----------------------------
root = tk.Tk()
root.title("Mini P'NUTS Database")
root.geometry("500x400")
# Labels and Entry Fields
tk.Label(root, text="User ID").pack()
entry_id = tk.Entry(root)
entry_id.pack()

tk.Label(root, text="Name").pack()
entry_name = tk.Entry(root)
entry_name.pack()

tk.Label(root, text="Age").pack()
entry_age = tk.Entry(root)
entry_age.pack()

def insert_user():
    user_id = entry_id.get()
    name = entry_name.get()
    age = int(entry_age.get())

    cluster.insert("User", {
        "user_id": user_id,
        "name": name,
        "age": age
    })

    output_label.config(text="Inserted successfully!")

def update_user():
    user_id = entry_id.get()
    age = int(entry_age.get())

    # Update on master
    cluster.master.get_table("User").update(user_id, {"age": age})

    # Log update
    updated_record = cluster.master.get_table("User").get(user_id)
    cluster.replication_log.append(("User", updated_record))
    cluster.replicate()

    output_label.config(text="Updated successfully!")

def view_master():
    user_id = entry_id.get()
    record = cluster.master.get_table("User").get(user_id)
    output_label.config(text=f"Master: {record}")

def view_replica():
    user_id = entry_id.get()
    record = replica1.get_table("User").get(user_id)
    output_label.config(text=f"Replica: {record}")

tk.Button(root, text="Insert", command=insert_user).pack(pady=5)
tk.Button(root, text="Update Age", command=update_user).pack(pady=5)
tk.Button(root, text="View Master", command=view_master).pack(pady=5)
tk.Button(root, text="View Replica", command=view_replica).pack(pady=5)

output_label = tk.Label(root, text="")
output_label.pack(pady=10)

root.mainloop()
