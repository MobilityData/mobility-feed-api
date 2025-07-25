# Yes, indexing shapes.txt can greatly speed up lookups. You can preprocess shapes.txt once to build an on-disk index
# mapping each shape_id to its file offsets. Then, for each needed shape_id, seek directly to its entries.
#
# Explanation:
#
#
# First, scan shapes.txt and record the byte offsets for each shape_id in an index (e.g. a pickle or JSON file).
# When processing, use the index to seek and read only the relevant lines for each shape_id.
# Here’s a two-step approach:
import csv
import pickle
import logging


def create_shapes_index(local_dir):
    index = {}
    shapes = f"{local_dir}/shapes.txt"
    outfile = f"{local_dir}/shapes_index.pkl"
    with open(shapes, "r", encoding="utf-8") as f:
        header = f.readline()
        columns = next(csv.reader([header]))
        count = 0
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                break
            row = dict(zip(columns, next(csv.reader([line]))))
            sid = row["shape_id"]
            index.setdefault(sid, []).append(pos)
            count += 1
            if count % 1000000 == 0:
                logging.debug(f"Indexed {count} lines so far...")

    logging.info(f"Total indexed lines: {count}")
    logging.info(f"Total unique shape_ids: {len(index)}")
    with open(outfile, "wb") as idxf:
        pickle.dump(index, idxf)
    logging.info("Indexing complete. Saved to shapes_index.pkl.")
