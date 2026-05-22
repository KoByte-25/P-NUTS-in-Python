class Table:
    def __init__(self, name, primary_key, schema):
        self.name = name
        self.primary_key = primary_key
        self.schema = schema
        self.records = {}

    def insert(self, record):
        key = record.get(self.primary_key)

        if key is None:
            raise ValueError("Primary key is missing")

        if key in self.records:
            raise ValueError("Duplicate primary key")

        # Validate schema
        for column, datatype in self.schema.items():
            if column not in record:
                raise ValueError(f"Missing column: {column}")
            if not isinstance(record[column], datatype):
                raise TypeError(f"Incorrect type for column: {column}")

            # Add version if not present
            if "_version" not in record:
                record["_version"] = 1

            self.records[key] = record

    def get(self, key):
        return self.records.get(key)
    
    def update(self, key, updated_fields):
        if key not in self.records:
            raise ValueError("Record not found")

        record = self.records[key]

        for field, value in updated_fields.items():
            if field not in self.schema:
                raise ValueError(f"Invalid column: {field}")
            if not isinstance(value, self.schema[field]):
                raise TypeError(f"Incorrect type for column: {field}")
            record[field] = value

        # Increase version
        record["_version"] += 1


class Database:
    def __init__(self):
        self.tables = {}

    def create_table(self, name, primary_key, schema):
        if name in self.tables:
            raise ValueError("Table already exists")

        table = Table(name, primary_key, schema)
        self.tables[name] = table

    def get_table(self, name):
        if name not in self.tables:
            raise ValueError("Table does not exist")

        return self.tables[name]

class Node:
    def __init__(self, name):
        self.name = name
        self.database = Database()

    def create_table(self, name, primary_key, schema):
        self.database.create_table(name, primary_key, schema)

    def get_table(self, name):
        return self.database.get_table(name)

class Cluster:
    def __init__(self):
        # Store multiple databases
        self.databases = {}  # db_name -> Database object
        self.master_nodes = {}  # db_name -> master Node
        self.replica_nodes = {}  # db_name -> list of replica Nodes
        self.replication_logs = {}  # db_name -> replication log list

    def create_database(self, db_name):
        if db_name in self.databases:
            raise ValueError(f"Database '{db_name}' already exists")

        # Create a Database object
        self.databases[db_name] = Database()

        # Create master Node
        master_node = Node(f"{db_name}_Master")
        master_node.database = self.databases[db_name]
        self.master_nodes[db_name] = master_node

        # Empty list for replicas
        self.replica_nodes[db_name] = []

        # Empty replication log
        self.replication_logs[db_name] = []

    def add_replica(self, db_name, replica_node):
        if db_name not in self.databases:
            raise ValueError(f"Database '{db_name}' does not exist")
        # Assign replica node its own copy of the database
        replica_node.database = self.databases[db_name]
        self.replica_nodes[db_name].append(replica_node)

    def insert(self, db_name, table_name, record):
        if db_name not in self.databases:
            raise ValueError(f"Database '{db_name}' does not exist")

        # Write to master
        master = self.master_nodes[db_name]
        table = master.get_table(table_name)
        table.insert(record)

        # Log operation
        self.replication_logs[db_name].append(("INSERT",table_name, record))

        # Replicate to all replicas
        self.replicate(db_name)

    def replicate(self, db_name):
        """
        Replicate all pending operations from master to replicas for a given database.
        """
        log = self.replication_logs[db_name]

        while log:
            entry = log.pop(0)
            op_type = entry[0]

            if op_type == "CREATE_TABLE":
                _, table_name, primary_key, schema = entry
                for replica in self.replica_nodes[db_name]:
                    # Use replica.database to access tables
                    replica.database.tables[table_name] = Table(table_name, primary_key, schema)

            elif op_type == "UPDATE_TABLE":
                _, table_name, updated_schema = entry
                for replica in self.replica_nodes[db_name]:
                    table = replica.database.get_table(table_name)
                    table.schema = updated_schema

            elif op_type == "DELETE_TABLE":
                _, table_name = entry
                for replica in self.replica_nodes[db_name]:
                    if table_name in replica.database.tables:
                        del replica.database.tables[table_name]

            elif op_type == "INSERT":
                _, table_name, record = entry
                for replica in self.replica_nodes[db_name]:
                    table = replica.database.get_table(table_name)
                    key = record[table.primary_key]
                    existing = table.get(key)
                    if existing is None:
                        table.insert(record.copy())
                    else:
                        if record["_version"] > existing["_version"]:
                            table.records[key] = record.copy()

            elif op_type == "UPDATE":
                _, table_name, updated_record = entry
                for replica in self.replica_nodes[db_name]:
                    table = replica.database.get_table(table_name)
                    key = updated_record[table.primary_key]
                    existing = table.get(key)
                    if existing:
                        table.records[key] = updated_record.copy()

            elif op_type == "DELETE":
                _, table_name, pk_value = entry
                for replica in self.replica_nodes[db_name]:
                    table = replica.database.get_table(table_name)
                    if pk_value in table.records:
                        del table.records[pk_value]

            else:
                raise ValueError(f"Unknown operation type: {op_type}")

    def get_master(self, db_name):
        return self.master_nodes[db_name]

    def get_replicas(self, db_name):
        return self.replica_nodes[db_name]

    def create_table(self, db_name, table_name, primary_key, schema):
        if db_name in self.databases:
            db = self.databases[db_name]
            if table_name in db.tables:
                raise ValueError(f"Table {table_name} already exists")

            # Create the table in master
            db.tables[table_name] = Table(table_name, primary_key, schema)

            # Log replication as a tuple (not dict!)
            self.replication_logs[db_name].append(
                ("CREATE_TABLE", table_name, primary_key, schema)
            )

            # Replicate immediately to replicas
            self.replicate(db_name)

    def update_table(self, db_name, table_name, new_schema):
        if db_name not in self.databases:
            raise ValueError("Database not found")

        db = self.databases[db_name]

        if table_name not in db.tables:
            raise ValueError("Table not found")

        table = db.tables[table_name]

        primary_key = table.primary_key

        # Ensure PK still exists
        if primary_key not in new_schema:
            raise ValueError("Primary key cannot be removed")

        # --- Validate existing records ---
        for record in table.records.values():
            for col_name, dtype in new_schema.items():
                if col_name in record:
                    if not isinstance(record[col_name], dtype):
                        raise TypeError(
                            f"Record with PK={record[primary_key]} violates new type for column '{col_name}'"
                        )

        # If validation passed, update schema
        table.schema = new_schema

        # Log replication
        self.replication_logs[db_name].append(
            ("UPDATE_TABLE", table_name, new_schema)
        )

        # Replicate to replicas
        self.replicate(db_name)

    def delete_table(self, db_name, table_name):
        if db_name not in self.databases:
            raise ValueError("Database not found")
        db = self.databases[db_name]
        if table_name not in db.tables:
            raise ValueError("Table not found")

        # Delete the table
        del db.tables[table_name]

        # Log replication
        self.replication_logs[db_name].append(("DELETE_TABLE", table_name))

        # Replicate to replicas
        self.replicate(db_name)

    def update_record(self, db_name, table_name, pk_value, updated_record):
        db = self.databases[db_name]
        table = db.get_table(table_name)
        # Convert pk_value from string to actual type
        pk_type = table.schema[table.primary_key]
        pk_value = pk_type(pk_value)
        
        if pk_value not in table.records:
            raise ValueError(f"Record with PK={pk_value} not found")

        # Validate types
        for col_name, dtype in table.schema.items():
            if col_name == table.primary_key:
                continue
            if col_name not in updated_record:
                raise ValueError(f"Missing column {col_name}")
            if not isinstance(updated_record[col_name], dtype):
                try:
                    updated_record[col_name] = dtype(updated_record[col_name])
                except:
                    raise TypeError(f"Invalid type for column {col_name}")

        # Update record
        table.records[pk_value] = updated_record.copy()

        # Log replication
        self.replication_logs[db_name].append(("UPDATE", table_name, updated_record.copy()))
        self.replicate(db_name)

    def delete_record(self, db_name, table_name, pk_value):
        db = self.databases[db_name]
        table = db.get_table(table_name)

        # Convert pk_value from string to actual type
        pk_type = table.schema[table.primary_key]
        pk_value = pk_type(pk_value)
        
        if pk_value not in table.records:
            raise ValueError(f"Record with PK={pk_value} not found")

        del table.records[pk_value]

        # Log replication
        self.replication_logs[db_name].append(("DELETE", table_name, pk_value))
        self.replicate(db_name)
