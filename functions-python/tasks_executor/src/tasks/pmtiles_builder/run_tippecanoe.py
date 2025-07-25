import logging
import subprocess


def run_tippecanoe(input_file, output_file, local_dir="./unzipped"):
    cmd = [
        "tippecanoe",
        "-o",
        f"{local_dir}/{input_file}",
        "--force",
        "--no-tile-size-limit",
        "-zg",
        f"{local_dir}/{output_file}",
    ]
    try:
        subprocess.run(cmd, check=True)
        logging.info("Tippecanoe command executed successfully.")
    except subprocess.CalledProcessError as e:
        logging.info(f"Error running tippecanoe: {e}")
