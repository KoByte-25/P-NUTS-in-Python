# Imports
from flask import Flask, render_template, request, redirect, url_for
from database import Cluster, Node
import pickle
import os

# Path to save your cluster
CLUSTER_FILE = "cluster.pkl"

def save_cluster():
    with open(CLUSTER_FILE, "wb") as f:
        pickle.dump(cluster, f)

def load_cluster():
    global cluster
    if os.path.exists(CLUSTER_FILE):
        with open(CLUSTER_FILE, "rb") as f:
            cluster = pickle.load(f)

#Create Flask app
app = Flask(__name__)

#Create Mini P'NUTS cluster
cluster = Cluster()

load_cluster()
# -----------------------------
#Routes go here
# -----------------------------

# Homepage route
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Form submission for creating a database
        db_name = request.form.get("db_name")
        replicas_count = int(request.form.get("replicas", 0))
        if db_name:
            cluster.create_database(db_name)

            # Add replicas if any
            for i in range(1, replicas_count + 1):
                replica_node = Node(f"{db_name}_Replica{i}")
                cluster.add_replica(db_name, replica_node)

            save_cluster() 
            return redirect(url_for("select_database", db_name=db_name))

    # Send database list to template
    databases = list(cluster.databases.keys())
    return render_template("index.html", databases=databases)

@app.route("/show_create_db_form")
def show_create_db_form():
    # Just render the index.html with a flag to show create database form
    return render_template("index.html",
                           databases=list(cluster.databases.keys()),
                           show_create_form=True)

@app.route("/database/<db_name>")
def select_database(db_name):
    if db_name not in cluster.databases:
        return redirect(url_for("index"))

    # Get tables of selected database
    db = cluster.databases[db_name]
    tables = list(db.tables.keys())  # currently empty if no tables

    # Pass selected database and tables to template
    return render_template("index.html",
                           databases=list(cluster.databases.keys()),
                           selected_db=db_name,
                           tables=tables,
                           cluster=cluster)

@app.route("/delete_database/<db_name>", methods=["POST"])
def delete_database(db_name):
    if db_name in cluster.databases:
        # Delete database
        del cluster.databases[db_name]
        if db_name in cluster.master_nodes:
            del cluster.master_nodes[db_name]
        if db_name in cluster.replica_nodes:
            del cluster.replica_nodes[db_name]
        if db_name in cluster.replication_logs:
            del cluster.replication_logs[db_name]
        
        # Save cluster after deletion
        save_cluster()
    return redirect(url_for("index"))

@app.route("/database/<db_name>/prepare_table", methods=["POST"])
def prepare_table_form(db_name):
    data = request.get_json()
    table_name = data["table_name"]
    num_columns = int(data["num_columns"])

    return render_template(
        "partials/table_columns_form.html",
        db_name=db_name,
        table_name=table_name,
        num_columns=num_columns
    )

@app.route("/database/<db_name>/create_table", methods=["POST"])
def create_table_route(db_name):
    table_name = request.form.get("table_name")
    num_columns = len([key for key in request.form if key.startswith("col_name_")])

    schema = {}
    primary_key = None

    # Build schema from form inputs
    for i in range(num_columns):
        col_name = request.form.get(f"col_name_{i}")
        col_type_str = request.form.get(f"col_type_{i}")

        # Convert type string to Python type
        dtype = int if col_type_str == "int" else float if col_type_str == "float" else str
        schema[col_name] = dtype

        # Determine primary key from checkbox
        if request.form.get(f"pk_{i}"):
            primary_key = col_name

    if primary_key is None:
        return "Error: No primary key selected", 400

    # Create table in master
    cluster.create_table(db_name, table_name, primary_key, schema)

    # Append tuple to replication log
    cluster.replication_logs[db_name].append(
        ("CREATE_TABLE", table_name, primary_key, schema)
    )

    # Replicate to all replicas
    cluster.replicate(db_name)

    save_cluster()# Redirect back to selected database (database home page)
    return redirect(url_for("select_database", db_name=db_name))

@app.route("/database/<db_name>/<table_name>/view")
def view_table(db_name, table_name):
    db = cluster.databases[db_name]
    table = db.get_table(table_name)

    # Prepare structure info
    structure = []
    for col_name, dtype in table.schema.items():
        structure.append({
            "name": col_name,
            "type": dtype.__name__,
            "is_pk": col_name == table.primary_key
        })

    # Prepare records
    records = list(table.records.values())

    return render_template(
        "partials/table_view.html",
        db_name=db_name,
        table_name=table_name,
        structure=structure,
        records=records,
        table=table 
    )

@app.route("/database/<db_name>/<table_name>/view/records")
def view_records(db_name, table_name):
    db = cluster.databases[db_name]
    table = db.get_table(table_name)

    structure = table.schema.keys()
    records = list(table.records.values())

    return render_template(
        "partials/table_records.html",
        db_name=db_name,
        table_name=table_name,
        structure=structure,
        records=records,
        table=table 
    )

@app.route("/database/<db_name>/<table_name>/view/structure")
def view_structure(db_name, table_name):
    db = cluster.databases[db_name]
    table = db.get_table(table_name)

    structure = []
    for col_name, dtype in table.schema.items():
        structure.append({
            "name": col_name,
            "type": dtype.__name__,
            "is_pk": col_name == table.primary_key
        })

    return render_template(
        "partials/table_structure.html",
        db_name=db_name,
        table_name=table_name,
        structure=structure,
        table=table
    )

@app.route("/database/<db_name>/<table_name>/view/structure/update_form")
def update_table_form(db_name, table_name):
    db = cluster.databases[db_name]
    table = db.get_table(table_name)

    structure = []
    for col_name, dtype in table.schema.items():
        structure.append({
            "name": col_name,
            "type": dtype.__name__,
            "is_pk": col_name == table.primary_key
        })

    return render_template(
        "partials/update_table_form.html",
        db_name=db_name,
        table_name=table_name,
        table=table,
        structure=structure
    )

@app.route("/database/<db_name>/<table_name>/view/structure/update", methods=["POST"])
def update_table_route(db_name, table_name):
    """
    Update a table's schema except for the primary key.
    Preserves PK, validates existing records, replicates changes to replicas.
    Returns updated table view partial.
    """

    db = cluster.databases[db_name]
    if not db:
        return f"Database '{db_name}' not found", 404

    table = db.get_table(table_name)

    # Get the new schema from JSON body (sent by JS)
    new_schema_input = request.get_json()
    if not new_schema_input:
        return "No schema data provided", 400

    # Build final schema, preserving primary key
    new_schema = {}
    for col_name, type_str in new_schema_input.items():
        if type_str == "int":
            dtype = int
        elif type_str == "float":
            dtype = float
        else:
            dtype = str
        new_schema[col_name] = dtype

    # Always preserve primary key column and type
    pk = table.primary_key
    new_schema[pk] = table.schema[pk]

    try:
        # Update the table in cluster
        cluster.update_table(db_name, table_name, new_schema)
        save_cluster()  # persist changes

        # Prepare updated table structure and records for right-panel
        updated_table = cluster.databases[db_name].tables[table_name]
        structure = []
        for col_name, dtype in updated_table.schema.items():
            structure.append({
                "name": col_name,
                "type": dtype.__name__,
                "is_pk": col_name == updated_table.primary_key
            })

        # Render table_view partial again
        return render_template(
            "partials/table_view.html",
            db_name=db_name,
            table_name=table_name,
            table=updated_table,
            structure=structure
        )

    except Exception as e:
        return str(e), 400

@app.route("/database/<db_name>/<table_name>/delete_table", methods=["POST"])
def delete_table_route(db_name, table_name):
    try:
        cluster.delete_table(db_name, table_name)
        save_cluster()  # ensure persistence

        # After deletion, show database home page (right panel with selected DB)
        db = cluster.databases[db_name]
        tables = list(db.tables.keys())
        return render_template(
            "index.html",
            databases=list(cluster.databases.keys()),
            selected_db=db_name,
            tables=tables,
            cluster=cluster
        )
    except Exception as e:
        return str(e), 400

@app.route("/database/<db_name>/<table_name>/schema")
def get_table_schema(db_name, table_name):
    db = cluster.databases[db_name]
    table = db.get_table(table_name)

    schema = []
    for col_name, dtype in table.schema.items():
        schema.append({
            "name": col_name,
            "type": dtype.__name__
        })

    return schema

@app.route("/database/<db_name>/<table_name>/insert", methods=["POST"])
def insert_record_route(db_name, table_name):

    db = cluster.databases[db_name]
    table = db.get_table(table_name)

    data = request.get_json()
    record = {}

    # --- Type Conversion ---
    for col_name, dtype in table.schema.items():
        if col_name not in data:
            return f"Missing column: {col_name}", 400

        value = data[col_name]

        try:
            if dtype == int:
                record[col_name] = int(value)
            elif dtype == float:
                record[col_name] = float(value)
            else:
                record[col_name] = str(value)
        except:
            return f"Invalid value for column '{col_name}'", 400

    try:
        cluster.insert(db_name, table_name, record)
        save_cluster()
    except Exception as e:
        return str(e), 400


    # Reload full table view after insert
    table = cluster.databases[db_name].tables[table_name]

    structure = []
    for col_name, dtype in table.schema.items():
        structure.append({
            "name": col_name,
            "type": dtype.__name__,
            "is_pk": col_name == table.primary_key
        })

    records = list(table.records.values())

    return render_template(
        "partials/table_view.html",
        db_name=db_name,
        table_name=table_name,
        structure=structure,
        records=records,
        table=table
    )

@app.route("/database/<db_name>/<table_name>/delete_record/<pk>", methods=["POST"])
def delete_record_route(db_name, table_name, pk):
    try:
        cluster.delete_record(db_name, table_name, pk)
        save_cluster()

        table = cluster.databases[db_name].tables[table_name]

        structure = []
        for col_name, dtype in table.schema.items():
            structure.append({
                "name": col_name,
                "type": dtype.__name__,
                "is_pk": col_name == table.primary_key
            })

        records = list(table.records.values())

        return render_template(
            "partials/table_view.html",
            db_name=db_name,
            table_name=table_name,
            structure=structure,
            records=records,
            table=table
        )

    except Exception as e:
        return str(e), 400

@app.route("/database/<db_name>/<table_name>/get_record/<pk_value>")
def get_record(db_name, table_name, pk_value):
    db = cluster.databases.get(db_name)
    if not db:
        return {"error": "Database not found"}, 404

    table = db.tables.get(table_name)
    if not table:
        return {"error": "Table not found"}, 404

    # Convert pk_value to correct type
    pk_type = table.schema[table.primary_key]  # primary key type
    try:
        pk_key = pk_type(pk_value)
    except:
        return {"error": "Invalid primary key type"}, 400

    record = table.get(pk_key)
    if not record:
        return {"error": f"Record with PK={pk_key} not found"}, 404

    record["_primary_key"] = table.primary_key
    return record

@app.route("/database/<db_name>/<table_name>/update_record/<pk_value>", methods=["POST"])
def update_record_route(db_name, table_name, pk_value):
    db = cluster.databases.get(db_name)
    if not db:
        return "Database not found", 404

    table = db.tables.get(table_name)
    if not table:
        return "Table not found", 404

    try:
        updated_record = request.get_json()  # JSON from JS
        cluster.update_record(db_name, table_name, pk_value, updated_record)
        save_cluster()  # persist changes

        # Prepare structure info
        structure = []
        for col_name, dtype in table.schema.items():
            structure.append({
                "name": col_name,
                "type": dtype.__name__,
                "is_pk": col_name == table.primary_key
            })

        # Prepare records
        records = list(table.records.values())

        return render_template(
            "partials/table_view.html",
            db_name=db_name,
            table_name=table_name,
            structure=structure,
            records=records,
            table=table 
        )

    except Exception as e:
        return str(e), 400


#master node checking
@app.route("/database/<db_name>/overview_from_master")
def database_overview_from_master(db_name):
    master_node = cluster.master_nodes.get(db_name)
    if not master_node:
        return f"Master node for database '{db_name}' not found", 404

    # Fetch tables from master node
    db = master_node.database
    tables = list(db.tables.keys())

    return render_template(
        "partials/database_overview.html",
        db_name=db_name,
        master_name = master_node.name,
        tables=tables,
        cluster=cluster
    )

@app.route("/master/<db_name>/<table_name>")
def view_master_table(db_name, table_name):
    if db_name not in cluster.master_nodes:
        return "Database not found", 404

    master_node = cluster.master_nodes[db_name]

    try:
        table = master_node.get_table(table_name)
    except:
        return "Table not found", 404

    return render_template(
        "partials/master_table_view.html",
        db_name=db_name,
        master_name=master_node.name,
        table_name=table_name,
        table=table
    )


#replica node checking
@app.route("/database/<db_name>/replicas")
def view_replicas(db_name):

    replicas = cluster.replica_nodes.get(db_name, [])

    replica_data = []

    for replica in replicas:
        db = replica.database  # replica's copy
        tables_info = []

        for table_name, table_obj in db.tables.items():
            tables_info.append({
                "name": table_name,
                "record_count": len(table_obj.records)  # <-- count records here
            })

        replica_data.append({
            "replica_name": replica.name,
            "table_count": len(db.tables),
            "tables": tables_info
        })

    return render_template(
        "partials/replica_overview.html",
        db_name=db_name,
        replicas=replica_data        
    )

@app.route("/database/<db_name>/replica/<replica_name>/table/<table_name>")
def view_replica_table(db_name, replica_name, table_name):

    replicas = cluster.replica_nodes.get(db_name, [])

    replica_node = None
    replica_index = None

    for i, r in enumerate(replicas):
        if r.name == replica_name:
            replica_node = r
            replica_index = i
            break

    if not replica_node:
        return "Replica not found", 404

    db = replica_node.database
    table = db.tables.get(table_name)

    if not table:
        return "Table not found in replica", 404

    # ------------------------------
    # FILTER RECORDS BASED ON PK
    # ------------------------------

    pk_name = table.primary_key
    replica_count = len(replicas)

    filtered_records = []

    for record in table.records.values():
        pk_value = record[pk_name]

        # Only works correctly if PK is integer
        try:
            if (int(pk_value) - 1) % replica_count == replica_index:
                filtered_records.append(record)
        except:
            pass

    return render_template(
        "partials/replica_table_view.html",
        db_name=db_name,
        replica_name=replica_name,
        table_name=table_name,
        table=table,
        records=filtered_records   # send filtered records
    )

#Run server
if __name__ == "__main__":
    app.run(debug=True)
