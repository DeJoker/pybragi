
from datetime import datetime

timestamp_ms = 1564412442015
date_time = datetime.fromtimestamp(timestamp_ms / 1000)
print(date_time)

date_time_2011 = datetime.fromisoformat("2011-01-01 00:00:00")
print(date_time_2011.timestamp()) # 1325347200

date_time_2012 = datetime.fromisoformat("2012-01-01 00:00:00.000000")
print(date_time_2012.timestamp())



def parse_snowflake(snowflake_id):
    # 标准雪花算法中，时间戳占41位，从第二位开始
    # 通常时间戳是相对于某个起始时间的毫秒数
    
    # 右移22位，提取时间戳部分（41位）
    timestamp_ms = (snowflake_id >> 22)
    
    snowflake_epoch = date_time_2011.timestamp() * 1000
    
    timestamp_ms = timestamp_ms + snowflake_epoch
    
    date_time = datetime.fromtimestamp(timestamp_ms / 1000)
    
    return {
        "snowflake_id": snowflake_id,
        "timestamp_ms": timestamp_ms,
        "datetime": date_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
        "worker_id": (snowflake_id >> 12) & 0x3FF,
        "sequence": snowflake_id & 0xFFF
    }

# 9223372036854775807
print("maxint64", 2**63 - 1)
print("maxuint64", 2**64 - 1)
print(93101040883586, parse_snowflake(93101040883586))
print(29852255327621, parse_snowflake(29852255327621))
print(14992517903964, parse_snowflake(14992517903964))
print(50034490746159, parse_snowflake(50034490746159))





