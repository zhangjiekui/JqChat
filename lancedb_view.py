import lancedb
import pandas as pd
import pyarrow as pa

from graphrag.config.defaults import VECTOR_STORE_DICT
base_dir = fr"/data/projects/JqChatV2/graphragtest/"
_uri = VECTOR_STORE_DICT.get("db_uri")
uri = f"{base_dir}{_uri}"
print(uri)
db = lancedb.connect(uri) 
table_names = db.table_names()

for table_name in table_names:
    print("===============")
    print(table_name)
    table = db.open_table(table_name).to_pandas()
    print(table.iloc[0:3,1:3])
    table.to_csv(f"{uri}/{table_name}.csv")