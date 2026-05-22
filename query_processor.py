# query_processor.py
class QueryProcessor:
    def __init__(self, cluster):
        self.cluster = cluster

    def insert(self, db_name, table_name, record):
        """Insert a new record into a table"""
        db = self.cluster.databases.get(db_name)
        if not db:
            raise ValueError(f"Database '{db_name}' not found")
        table = db.get_table(table_name)

        # Type validation
        validated_record = {}
        for col_name, dtype in table.schema.items():
            if col_name not in record:
                raise ValueError(f"Missing column: {col_name}")
            value = record[col_name]
            if not isinstance(value, dtype):
                try:
                    value = dtype(value)
                except:
                    raise TypeError(f"Invalid type for column {col_name}")
            validated_record[col_name] = value

        # Add version
        validated_record["_version"] = 1

        # Insert via cluster (handles replication)
        self.cluster.insert(db_name, table_name, validated_record)

    def update(self, db_name, table_name, pk_value, updated_fields):
        """Update a record by primary key"""
        db = self.cluster.databases.get(db_name)
        if not db:
            raise ValueError(f"Database '{db_name}' not found")
        table = db.get_table(table_name)
        pk_col = table.primary_key
        pk_type = table.schema[pk_col]

        # Convert primary key to correct type
        pk_value = pk_type(pk_value)

        # Get existing record
        existing = table.get(pk_value)
        if not existing:
            raise ValueError(f"Record with PK={pk_value} not found")

        # Merge updated fields
        new_record = existing.copy()
        for col, value in updated_fields.items():
            if col not in table.schema:
                raise ValueError(f"Invalid column: {col}")
            dtype = table.schema[col]
            if not isinstance(value, dtype):
                try:
                    value = dtype(value)
                except:
                    raise TypeError(f"Invalid type for column {col}")
            new_record[col] = value

        # Increment version
        new_record["_version"] = existing["_version"] + 1

        # Update via cluster (handles replication)
        self.cluster.update_record(db_name, table_name, pk_value, new_record)

    def delete(self, db_name, table_name, pk_value):
        """Delete a record by primary key"""
        db = self.cluster.databases.get(db_name)
        if not db:
            raise ValueError(f"Database '{db_name}' not found")
        table = db.get_table(table_name)
        pk_type = table.schema[table.primary_key]
        pk_value = pk_type(pk_value)
        self.cluster.delete_record(db_name, table_name, pk_value)

    def select(self, db_name, table_name, filters=None):
        """Return list of records matching filters"""
        db = self.cluster.databases.get(db_name)
        if not db:
            raise ValueError(f"Database '{db_name}' not found")
        table = db.get_table(table_name)

        results = []
        for record in table.records.values():
            if filters:
                match = True
                for col, val in filters.items():
                    if col not in record or record[col] != val:
                        match = False
                        break
                if match:
                    clean_record = record.copy()
                    clean_record.pop("_version", None)  # Remove version field
                    results.append(clean_record)
            else:
                clean_record = record.copy()
                clean_record.pop("_version", None)  # Remove version field
                results.append(clean_record)
        return results

    def save(self, filename="cluster.pkl"):
        """Persist the cluster to disk"""
        import pickle
        with open(filename, "wb") as f:
            pickle.dump(self.cluster, f)