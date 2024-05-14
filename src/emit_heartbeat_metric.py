import datetime
import os

import graphyte

def lambda_handler(event):
    graphite_host = os.getenv("GRAPHITE_HOST", "graphite-collectd")
    graphite_metric_prefix = os.getenv("GRAPHITE_METRIC_PREFIX", "container-insights")

    current_time = datetime.datetime.now()
    minutes = current_time.minute
    val = 0 if (minutes % 4 < 2) else 1

    print("Minutes:", minutes)
    print("Val: ", val)

    graphyte.init(host=graphite_host, prefix=graphite_metric_prefix, timeout=1)
    graphyte.send(
        metric="foo.bar",
        value=val,
        timestamp=current_time.timestamp(),
    )
