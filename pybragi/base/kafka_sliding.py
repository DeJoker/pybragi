import random
import time
from sortedcontainers import SortedDict
from kafka import KafkaConsumer, TopicPartition, OffsetAndMetadata
import threading

class SlidingWindow:
    def __init__(self):
        self.offsets = {}
        self.locks = {}

    def add_message(self, tp: TopicPartition, offset):
        if tp not in self.offsets:
            self.offsets[tp] = SortedDict()
            self.locks[tp] = threading.Lock()

        with self.locks[tp]:
            self.offsets[tp][offset] = False  # False means not yet processed

    def mark_processed(self, tp: TopicPartition, offset):
        if tp in self.offsets:
            with self.locks[tp]:
                if offset in self.offsets[tp]:
                    self.offsets[tp][offset] = True  # Mark as processed

    def _get_committable_offset(self, tp: TopicPartition):
        if tp in self.offsets:
            with self.locks[tp]:
                sorted_offsets: SortedDict = self.offsets[tp]
                offset_id = 0
                for offset, processed in sorted_offsets.items():
                    if not processed:
                        break
                    offset_id = offset
                if offset_id:
                    for offset in list(sorted_offsets.keys()):
                        if offset <= offset_id:
                            sorted_offsets.pop(offset)
                        else:
                            break # 因为是sorted如果迭代中遇到无需提交的 那么后面都不需要
                    return offset_id
                else:
                    return None
        return None
    
    def committable_offset(self):
        to_commit = {}
        for tp in self.offsets:
            cur_offset = self._get_committable_offset(tp)
            if cur_offset:
                to_commit[tp] = OffsetAndMetadata(cur_offset+1, '')
        # assert len(to_commit) == 0
        return to_commit
    
    def size(self):
        size = 0
        for tp in self.offsets:
            sorted_offsets: SortedDict = self.offsets[tp]
            size += len(sorted_offsets)
        return size
                

if __name__ == '__main__':
    sw = SlidingWindow()
    for i in range(12000, 12999):
        tp = TopicPartition("xx", i%6)
        sw.add_message(tp, i)
    
    print(f"size={sw.size()}")
    msgs = [ i for i in range(12000, 12999)]
    random.shuffle(msgs) # 打乱本列表
    for k,msg in enumerate(msgs):
        sw.mark_processed(TopicPartition("xx", msg%6), msg)
        to_commit = sw.committable_offset()
        if to_commit:
            print(f"loop={k} commit={to_commit}")
            print(f"size={sw.size()}")
    print(f"size={sw.size()}")
    time.sleep(0.1)
    time.sleep(0.1)


