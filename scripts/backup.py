import os
import sys
import subprocess
from datetime import datetime

# --- Allow importing from the parent 'app' directory ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.logging_config import log

# --- Configuration ---
BACKUP_DIR = "backups"
MONGO_CONTAINER_NAME = "vyayamam-mongo" # The name we gave our container in the `docker run` command

def create_backup():
    """
    Creates a compressed, timestamped backup of the MongoDB database
    by executing `mongodump` inside the running Docker container.
    """
    log.info("🛡️  Starting database backup process...")

    # 1. Ensure the backup directory exists on the host machine
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        log.info(f"Backup directory '{BACKUP_DIR}/' is ready.")
    except OSError as e:
        log.error(f"❌ ERROR: Could not create backup directory '{BACKUP_DIR}'. Details: {e}")
        return

    # 2. Create a timestamped filename for the backup
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    db_name = settings.DB_NAME
    filename = f"{db_name}_backup_{timestamp}.gz"
    
    # This is the path *inside the Docker container* where the backup will be temporarily created.
    container_backup_path = f"/data/{filename}"
    # This is the final path on your *local machine*.
    host_backup_path = os.path.join(BACKUP_DIR, filename)

    # 3. Construct the `mongodump` command to be run inside the container
    dump_command = [
        "docker", "exec", MONGO_CONTAINER_NAME,
        "mongodump",
        f"--db={db_name}",
        f"--archive={container_backup_path}",
        "--gzip"
    ]
    
    # 4. Construct the `docker cp` command to copy the backup from the container to the host
    copy_command = [
        "docker", "cp",
        f"{MONGO_CONTAINER_NAME}:{container_backup_path}",
        host_backup_path
    ]

    # 5. Execute the commands
    try:
        # Run the mongodump command inside the container
        log.info(f"Executing `mongodump` inside container '{MONGO_CONTAINER_NAME}'...")
        subprocess.run(dump_command, check=True, capture_output=True, text=True)
        log.info("✅ `mongodump` completed successfully inside the container.")

        # Copy the created backup file to the host
        log.info(f"Copying backup from container to '{host_backup_path}'...")
        subprocess.run(copy_command, check=True, capture_output=True, text=True)
        log.info("✅ Backup file copied successfully.")
        
        log.info(f"🎉 SUCCESS! Database backup created at: {host_backup_path}")

    except subprocess.CalledProcessError as e:
        log.error("❌ ERROR: Backup process failed.")
        log.error(f"Command: {' '.join(e.cmd)}")
        log.error(f"Return Code: {e.returncode}")
        log.error(f"Output: {e.stdout}")
        log.error(f"Error Output: {e.stderr}")
    except FileNotFoundError:
        log.error("❌ ERROR: 'docker' command not found. Is Docker installed and running?")
    except Exception as e:
        log.error(f"❌ An unexpected error occurred: {e}")


if __name__ == "__main__":
    create_backup()
