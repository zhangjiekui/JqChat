import time
from jq_queue.jq_queues import JqFileSystemQueue as FileSystemQueue
lazyllm_queue = FileSystemQueue()

for i in range(10):
    # lazyllm.SQLiteQueue().enqueue(f"SQLite({i})")
    lazyllm_queue.enqueue(i)
lazyllm_queue.enqueue("DONE")

condition = True
while condition:
    try:
        values =lazyllm_queue.dequeue()
        if values:
            for value in values:
                print(f"output: {value}")
                if value == "DONE":
                    condition = False
        time.sleep(1)

    except:
        condition = False
        break
print("Done:全部完成")