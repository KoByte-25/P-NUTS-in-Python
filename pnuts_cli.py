# pnuts_cli.py
import shlex
import pickle
import os
from database import Cluster
from query_processor import QueryProcessor
from tabulate import tabulate  # for pretty table display

CLUSTER_FILE = "cluster.pkl"

# Load or create cluster
cluster = Cluster()
if os.path.exists(CLUSTER_FILE):
    with open(CLUSTER_FILE, "rb") as f:
        cluster = pickle.load(f)

qp = QueryProcessor(cluster)


class PnutsCLI:
    def __init__(self, query_processor, cluster_file=CLUSTER_FILE):
        self.qp = query_processor
        self.cluster_file = cluster_file
        self.current_db = None  # currently selected database

    def save_cluster(self):
        self.qp.save(self.cluster_file)

    def run(self):
        print("Welcome to P'NUTS CLI. Type 'help' for commands, 'exit' to quit.")
        while True:
            try:
                command = input("pnuts> ").strip()
                if not command:
                    continue
                if command.lower() in ["exit", "quit"]:
                    self.save_cluster()
                    print("Exiting. Cluster saved.")
                    break
                self.handle_command(command)
            except Exception as e:
                print(f"Error: {e}")

    def handle_command(self, command):
        tokens = shlex.split(command)
        if not tokens:
            return
        cmd = tokens[0].lower()

        # Help command
        if cmd == "help":
            print(
                "Commands:\n"
                "  show_dbs                       - List all databases\n"
                "  use <database_name>            - Switch database\n"
                "  insert <table> col=val ...     - Insert record\n"
                "  update <table> <pk> col=val...- Update record by primary key\n"
                "  delete <table> <pk>            - Delete record by primary key\n"
                "  select <table> [col=val ...]   - Select records (optional filters)\n"
                "  exit / quit                     - Exit CLI"
            )
            return

        # Show all databases
        if cmd == "show_dbs":
            print("Databases:", list(self.qp.cluster.databases.keys()))
            return

        # Switch database
        if cmd == "use":
            if len(tokens) < 2:
                print("Usage: use <database_name>")
                return
            db_name = tokens[1]
            if db_name not in self.qp.cluster.databases:
                print(f"Database '{db_name}' does not exist.")
            else:
                self.current_db = db_name
                print(f"Switched to database '{db_name}'.")
            return

        # Ensure database is selected
        if not self.current_db:
            print("No database selected. Use 'use <db_name>' to select a database.")
            return

        # Insert record
        if cmd == "insert":
            if len(tokens) < 3:
                print("Usage: insert <table> col=val ...")
                return
            table_name = tokens[1]
            record = {}
            for token in tokens[2:]:
                if "=" not in token:
                    print(f"Invalid column=value pair: {token}")
                    return
                k, v = token.split("=", 1)
                # Try converting to int/float, else leave as string
                try:
                    if "." in v:
                        v = float(v)
                    else:
                        v = int(v)
                except:
                    v = v
                record[k] = v
            self.qp.insert(self.current_db, table_name, record)
            print("Inserted successfully.")
            return

        # Update record
        if cmd == "update":
            if len(tokens) < 4:
                print("Usage: update <table> <pk> col=val ...")
                return
            table_name = tokens[1]
            pk_value = tokens[2]
            updated_fields = {}
            for token in tokens[3:]:
                if "=" not in token:
                    print(f"Invalid column=value pair: {token}")
                    return
                k, v = token.split("=", 1)
                try:
                    if "." in v:
                        v = float(v)
                    else:
                        v = int(v)
                except:
                    v = v
                updated_fields[k] = v
            self.qp.update(self.current_db, table_name, pk_value, updated_fields)
            print("Updated successfully.")
            return

        # Delete record
        if cmd == "delete":
            if len(tokens) != 3:
                print("Usage: delete <table> <pk>")
                return
            table_name = tokens[1]
            pk_value = tokens[2]
            self.qp.delete(self.current_db, table_name, pk_value)
            print("Deleted successfully.")
            return

        # Select records
        if cmd == "select":
            if len(tokens) < 2:
                print("Usage: select <table> [col=val ...]")
                return
            table_name = tokens[1]
            filters = {}
            for token in tokens[2:]:
                if "=" not in token:
                    print(f"Invalid filter: {token}")
                    return
                k, v = token.split("=", 1)
                try:
                    if "." in v:
                        v = float(v)
                    else:
                        v = int(v)
                except:
                    v = v
                filters[k] = v
            results = self.qp.select(self.current_db, table_name, filters)
            if not results:
                print("No records found.")
            else:
                # Pretty print table
                headers = list(results[0].keys())
                rows = [list(r.values()) for r in results]
                print(tabulate(rows, headers=headers, tablefmt="grid"))
            return

        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    cli = PnutsCLI(qp)
    cli.run()